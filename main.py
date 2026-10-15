"""
News Worker — 主排程器
執行: python main.py
手動單次觸發: python main.py --now
"""
import argparse
import logging
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

ROOT = Path(__file__).parent
LOGS_DIR = ROOT / "logs"
DATA_DIR = ROOT / "data"
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

_LAST_RUN_FILE = DATA_DIR / "last_run.txt"

_LOG_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _setup_base_logging() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_LOG_FMT)
    root.addHandler(console)


def _make_run_dir(ts: str) -> tuple[Path, Path]:
    """建立資料夾並加入此次專屬 log handler，回傳 (run_dir, log_path)。"""
    run_dir = DATA_DIR / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    log_path = LOGS_DIR / f"{ts}.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(_LOG_FMT)
    handler.set_name(f"run_{ts}")
    logging.getLogger().addHandler(handler)

    return run_dir, log_path


def _remove_run_handler(ts: str) -> None:
    root = logging.getLogger()
    for h in root.handlers[:]:
        if getattr(h, "name", "") == f"run_{ts}":
            h.close()
            root.removeHandler(h)


def _read_last_run_time() -> "datetime | None":
    if _LAST_RUN_FILE.exists():
        try:
            return datetime.fromisoformat(_LAST_RUN_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            return None
    return None


def _save_last_run_time(dt: datetime) -> None:
    _LAST_RUN_FILE.write_text(dt.isoformat(), encoding="utf-8")


def _calc_min_published(now_utc: datetime) -> datetime:
    """
    取 (上次執行時間, now-24h) 兩者中較晚的值作為發布時間截止點。
    每日一跑，理論間隔 24h；floor 多留 2h 緩衝以容忍延遲啟動或補跑。
    """
    floor = now_utc - timedelta(hours=26)
    last = _read_last_run_time()
    if last is None:
        return floor
    return max(last, floor)


logger = logging.getLogger("main")


def pipeline(dry_run: bool = False) -> bool:
    """dry_run: no email, no last_run update, no monitor alert; email HTML saved to the run dir."""
    from src import crawler, emailer, monitor, summarizer

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    run_dir, log_path = _make_run_dir(ts)

    run_start_utc = datetime.now(timezone.utc)
    min_published = _calc_min_published(run_start_utc)

    start = datetime.now()
    logger.info("=" * 60)
    logger.info("Pipeline 開始 %s | 資料夾: %s", start.strftime("%Y-%m-%d %H:%M:%S"), run_dir.name)
    logger.info("發布時間截止: %s (UTC)", min_published.strftime("%Y-%m-%d %H:%M"))
    logger.info("=" * 60)

    success = False
    outcome = {"success": False, "stage": "crawl", "reason": "unknown",
               "detail": "", "crawl_stats": None}

    try:
        # 1. 爬蟲
        logger.info("--- [1/3] 爬蟲層 ---")
        crawl_result = crawler.run(run_dir, min_published=min_published)
        filtered = crawl_result["filtered_articles"]
        stats = crawl_result["stats"]
        outcome["crawl_stats"] = stats
        logger.info("爬蟲完成: 過濾後 %d 篇 (來源成功 %d / 失敗 %d)",
                    stats["filtered"], stats["sources_ok"], stats["sources_fail"])

        if not filtered:
            logger.warning("無符合條件的文章，寄出「今日無相關經濟消息」")
            region_results = []
        else:
            # 2. 摘要
            logger.info("--- [2/3] 摘要層 ---")
            outcome["stage"] = "summarize"
            region_results = summarizer.run(filtered, run_dir)
            total = sum(len(r["articles"]) for r in region_results)
            logger.info("摘要完成: %d 地區有結果，共 %d 篇", len(region_results), total)

            # Close the loop: retrain layer 1 on the summarizer's accept/reject verdicts.
            try:
                from src import relevance
                relevance.train()
            except Exception as exc:
                logger.warning("相關性模型重訓失敗（不影響本次流程）: %s", exc)

        ok_regions = [r for r in region_results if r["summary"]]
        errors = [r for r in region_results if r.get("error")]
        if errors and not ok_regions:
            # 全數失敗就不寄報，否則收件人只會收到空摘要，
            # 且 last_run 一旦前進，這個時間窗的新聞就永久跳過了。
            auth_failed = any(r.get("error_type") == "auth" for r in region_results)
            detail = next((r["error"] for r in region_results if r.get("error")),
                          "摘要層全部失敗")
            logger.error("摘要層全部失敗，跳過 Email 並保留 last_run（新聞留待下次）")
            outcome.update(success=False,
                           reason="auth" if auth_failed else "summarize",
                           detail=detail)
        else:
            # 3. Email — regions where every article was rejected are already
            # dropped by the summarizer; nothing left means "no relevant news today".
            if not ok_regions:
                logger.info("今日無與台灣經濟相關的消息，寄出通知")
            region_results = ok_regions
            forecast = None
            try:  # opening forecast for trading days only; never blocks the digest
                from src import tw_forecast
                forecast = tw_forecast.forecast()
            except Exception as exc:
                logger.warning("今日開盤預測失敗（不影響本次寄送）: %s", exc)
            logger.info("--- [3/3] Email 層 ---")
            outcome["stage"] = "email"
            if dry_run:
                run_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                (run_dir / "email_preview.html").write_text(
                    emailer._build_html(region_results, run_time, forecast, image_mode="data"), encoding="utf-8")
                logger.info("dry-run：未寄信，預覽已存 %s", run_dir / "email_preview.html")
                success = True
                outcome.update(success=True, reason="ok")
            elif emailer.run(region_results, forecast):
                success = True
                outcome.update(success=True, reason="ok")
            else:
                logger.error("Email 寄送失敗")
                outcome.update(success=False, reason="email",
                               detail="Gmail 寄送失敗，詳見 log")

    except Exception as exc:
        logger.exception("Pipeline 發生未預期錯誤: %s", exc)
        outcome.update(success=False, reason="crash", detail=traceback.format_exc())

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("Pipeline 結束，耗時 %.1f 秒，狀態: %s", elapsed, "成功" if success else "失敗")
    logger.info("=" * 60)

    if success and not dry_run:
        _save_last_run_time(run_start_utc)

    # 4. Monitor
    if not dry_run:
        try:
            monitor.run(outcome, log_file=log_path)
        except Exception as exc:
            logger.error("Monitor 執行錯誤: %s", exc)

    _remove_run_handler(ts)
    return success


def main() -> None:
    _setup_base_logging()

    parser = argparse.ArgumentParser(description="News Worker")
    parser.add_argument("--now", action="store_true", help="立即執行一次後退出")
    parser.add_argument("--no-email", action="store_true", help="搭配 --now：不寄信、不更新 last_run")
    args = parser.parse_args()

    if args.now:
        logger.info("手動觸發：立即執行一次")
        success = pipeline(dry_run=args.no_email)
        sys.exit(0 if success else 1)

    import json
    with open(ROOT / "config.json", encoding="utf-8") as f:
        cfg = json.load(f)

    daily_h, daily_m = cfg["schedule"]["daily"].split(":")

    scheduler = BlockingScheduler(timezone="Asia/Taipei")
    scheduler.add_job(
        pipeline,
        CronTrigger(hour=int(daily_h), minute=int(daily_m), timezone="Asia/Taipei"),
        id="daily_run", name=f"每日報 {cfg['schedule']['daily']}",
        max_instances=1, misfire_grace_time=300,
    )

    logger.info("排程器啟動 — 每日報 %s (Asia/Taipei)", cfg["schedule"]["daily"])
    logger.info("按 Ctrl+C 停止")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("使用者中止，排程器停止")


if __name__ == "__main__":
    main()
