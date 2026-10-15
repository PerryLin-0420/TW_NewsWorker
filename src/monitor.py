"""
Monitor — 規則式健康檢查與告警（不使用 LLM）
- 依 pipeline 回報的 outcome 分類失敗，決定是否寄告警
- 跨執行追蹤每個來源的連續失敗次數，達門檻才提醒
- 永不自動改寫 config.json；來源異動一律人工決定
"""
import json
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
LOG_DIR = ROOT / "logs"
DATA_DIR = ROOT / "data"
_HEALTH_FILE = DATA_DIR / "source_health.json"

load_dotenv(ROOT / ".env")

logger = logging.getLogger("monitor")

# reason -> (subject suffix, what the operator should do)
_REASON_GUIDE = {
    "auth": (
        "Claude CLI 認證失效",
        "摘要層無法呼叫 claude CLI。請在互動式終端機重新建立長期 token：\n"
        "  1. 用完整路徑執行 claude.exe 的 setup-token（claude 不在 PATH）\n"
        "     路徑在 %USERPROFILE%\\AppData\\Roaming\\Claude\\claude-code\\<版本>\\claude.exe\n"
        "  2. 驗證: claude.exe auth status  應回報 loggedIn: true\n"
        "  3. 補跑: python main.py --now\n"
        "注意 setup-token 建立的是長期 token；auth login 建立的 OAuth session 會週期性過期。\n"
        "本次新聞未被標記為已處理，下次執行會重新抓取，不會遺失。",
    ),
    "summarize": (
        "摘要層全部失敗",
        "所有地區摘要都失敗，但不是認證問題。請查看下方 log 的錯誤訊息。\n"
        "本次未寄出報表，也未更新 last_run.txt，下次執行會重新抓取。",
    ),
    "email": (
        "Email 寄送失敗",
        "摘要已產生但 Gmail 寄送失敗。請確認 .env 的 GMAIL_APP_PASSWORD 是否仍有效。",
    ),
    "crash": (
        "Pipeline 未預期錯誤",
        "Pipeline 拋出未處理的例外，詳見下方 traceback。",
    ),
    "sources": (
        "來源持續失敗",
        "以下來源已連續失敗多次，可能已永久失效（改版或關閉）。\n"
        "請手動檢查並在 config.json 調整或移除。系統不會自動改動設定。",
    ),
}


def _load_config() -> dict:
    with open(ROOT / "config.json", encoding="utf-8") as f:
        return json.load(f)


def _read_recent_log(log_file: Path, n_lines: int) -> str:
    if not log_file or not log_file.exists():
        return ""
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n_lines:])


def _load_health() -> dict:
    if _HEALTH_FILE.exists():
        try:
            return json.loads(_HEALTH_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("來源健康檔讀取失敗，將重新建立: %s", exc)
    return {}


def _save_health(health: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _HEALTH_FILE.write_text(
        json.dumps(health, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _update_source_health(source_results: dict, threshold: int) -> list[dict]:
    """
    更新每個來源的連續失敗計數，回傳達到告警門檻的來源清單。
    只在剛好跨過門檻時回報一次，避免每次執行都重複告警。
    """
    if not source_results:
        return []

    health = _load_health()
    now = datetime.now(timezone.utc).isoformat()
    breached: list[dict] = []

    for name, result in source_results.items():
        entry = health.get(name, {"consecutive_failures": 0, "last_ok": None,
                                  "last_error": None, "alerted_at": None})
        if result.get("ok"):
            entry.update(consecutive_failures=0, last_ok=now,
                         last_error=None, alerted_at=None)
        else:
            entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
            entry["last_error"] = result.get("error")
            if entry["consecutive_failures"] >= threshold and not entry.get("alerted_at"):
                entry["alerted_at"] = now
                breached.append({
                    "name": name,
                    "failures": entry["consecutive_failures"],
                    "last_ok": entry.get("last_ok"),
                    "error": entry.get("last_error"),
                })
        health[name] = entry

    _save_health(health)
    return breached


def _format_source_health() -> str:
    health = _load_health()
    failing = {n: e for n, e in health.items() if e.get("consecutive_failures", 0) > 0}
    if not failing:
        return "所有來源正常。"
    lines = []
    for name, entry in sorted(failing.items(),
                              key=lambda kv: -kv[1].get("consecutive_failures", 0)):
        last_ok = entry.get("last_ok") or "（無紀錄）"
        lines.append(
            f"  - {name}: 連續失敗 {entry['consecutive_failures']} 次"
            f" | 最後成功 {last_ok}"
            f" | {entry.get('last_error') or ''}"
        )
    return "\n".join(lines)


def _send_alert(subject: str, body: str) -> None:
    gmail_addr = os.getenv("GMAIL_ADDRESS", "")
    app_pwd = os.getenv("GMAIL_APP_PASSWORD", "")
    recipient = os.getenv("RECIPIENT_EMAIL", "")

    if not all([gmail_addr, app_pwd, recipient]):
        logger.error("缺少 .env，無法寄出告警 Email")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_addr
    msg["To"] = recipient

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_addr, app_pwd)
            smtp.sendmail(gmail_addr, recipient, msg.as_bytes())
        logger.info("告警 Email 已送出 → %s", recipient)
    except Exception as exc:
        logger.error("告警 Email 寄送失敗: %s", exc)


def _build_body(outcome: dict, breached: list[dict], recent_log: str) -> str:
    reason = outcome.get("reason", "unknown")
    _, guidance = _REASON_GUIDE.get(reason, ("未分類狀況", "請查看下方 log。"))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts = [
        f"時間: {timestamp}",
        f"階段: {outcome.get('stage', '?')}",
        f"分類: {reason}",
        "",
        "=== 處理建議 ===",
        guidance,
    ]

    if outcome.get("detail"):
        parts += ["", "=== 錯誤內容 ===", str(outcome["detail"])[:3000]]

    if breached:
        parts += ["", "=== 已達門檻的來源 ==="]
        parts += [
            f"  - {b['name']}: 連續失敗 {b['failures']} 次"
            f" | 最後成功 {b['last_ok'] or '（無紀錄）'}"
            f" | {b['error'] or ''}"
            for b in breached
        ]

    parts += ["", "=== 來源健康總覽 ===", _format_source_health()]

    if recent_log:
        parts += ["", "=== 最近 Log ===", recent_log]

    return "\n".join(parts)


def run(outcome: dict, log_file: Path = None) -> None:
    """
    outcome 由 main.pipeline() 組出，欄位：
      success (bool), stage (str), reason (str), detail (str), crawl_stats (dict|None)
    """
    cfg = _load_config()
    m_cfg = cfg.get("monitor", {})
    threshold = m_cfg.get("source_failure_alert_threshold", 6)
    n_lines = m_cfg.get("log_lines_in_alert", 60)

    crawl_stats = outcome.get("crawl_stats") or {}
    breached = _update_source_health(crawl_stats.get("sources", {}), threshold)

    success = outcome.get("success", False)
    reason = outcome.get("reason", "unknown")

    if success and not breached:
        logger.info("Monitor: pipeline 正常（%s），無需介入", reason)
        return

    if success and breached:
        # Pipeline 整體成功，但有來源長期壞掉 → 提醒，不算失敗
        names = ", ".join(b["name"] for b in breached)
        logger.warning("Monitor: 來源持續失敗達門檻（%s），寄出提醒", names)
        subject_suffix = _REASON_GUIDE["sources"][0]
        body_outcome = {**outcome, "reason": "sources"}
        _send_alert(
            subject=f"[News Worker 提醒] {subject_suffix}: {names}",
            body=_build_body(body_outcome, breached, _read_recent_log(log_file, n_lines)),
        )
        return

    subject_suffix = _REASON_GUIDE.get(reason, ("執行異常", "請查看下方 log。"))[0]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    logger.warning("Monitor: pipeline 失敗（%s），寄出告警", reason)
    _send_alert(
        subject=f"[News Worker 告警] {subject_suffix} {timestamp}",
        body=_build_body(outcome, breached, _read_recent_log(log_file, n_lines)),
    )
