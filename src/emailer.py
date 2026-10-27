import base64
import logging
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

logger = logging.getLogger("emailer")

_REGION_EMOJI = {
    "台灣": "🇹🇼",
    "美國": "🇺🇸",
    "亞洲": "🌏",
    "歐洲": "🇪🇺",
    "大宗商品": "🛢️",
    "全球": "🌐",
}

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, "Noto Sans TC", Arial, sans-serif; background:#f4f4f4; margin:0; padding:20px; }}
  .container {{ max-width:700px; margin:auto; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 2px 10px rgba(0,0,0,.1); }}
  .header {{ background:#0d1b2a; color:#fff; padding:22px 32px; }}
  .header h1 {{ margin:0; font-size:19px; letter-spacing:.5px; }}
  .header p {{ margin:6px 0 0; font-size:12px; color:#8aa; }}
  .body {{ padding:20px 32px; }}
  .region-block {{ margin-bottom:28px; }}
  .region-title {{ font-size:16px; font-weight:700; color:#0d1b2a; border-bottom:2px solid #e8e8e8; padding-bottom:6px; margin-bottom:10px; }}
  .summary {{ font-size:14px; line-height:1.85; color:#2c2c2c; margin:0 0 10px; }}
  .fn-ref {{ color:#4a90d9; font-size:10px; vertical-align:super; text-decoration:none; font-weight:600; }}
  .fn-ref:hover {{ text-decoration:underline; }}
  .footnotes {{ border-top:1px solid #eef0f4; padding-top:8px; margin-top:4px; }}
  .fn-item {{ display:block; font-size:12px; padding:3px 0; border-bottom:1px solid #f5f5f5; color:#555; }}
  .fn-item:last-child {{ border-bottom:none; }}
  .fn-item a {{ color:#1a5fb4; text-decoration:none; font-weight:500; }}
  .fn-item a:hover {{ text-decoration:underline; }}
  .fn-source {{ color:#999; font-size:11px; margin-left:6px; }}
  .intl-badge {{ display:inline-block; font-size:10px; color:#fff; background:#4a90d9; border-radius:3px; padding:0 4px; margin-left:4px; vertical-align:middle; }}
  .footer {{ background:#f0f0f0; padding:12px 32px; font-size:11px; color:#999; text-align:center; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>財經新聞摘要</h1>
    <p>{run_time} &nbsp;·&nbsp; {region_count} 地區 &nbsp;·&nbsp; {article_count} 則報導</p>
  </div>
  <div class="body">
    {regions_html}
  </div>
  <div class="footer">
    由 News Worker 自動生成 &nbsp;·&nbsp; 摘要由 Claude AI 產生 &nbsp;·&nbsp; 僅供參考，不構成投資建議
  </div>
</div>
</body>
</html>
"""

_REGION_BLOCK = """\
<div class="region-block">
  <div class="region-title">{emoji} {region}</div>
  {summary_html}
  <div class="footnotes">
    {footnotes_html}
  </div>
</div>
"""


def _inject_fn_refs(summary: str, articles: list[dict]) -> str:
    """將摘要中的 [註N] 替換為可點擊的 HTML 超連結。"""
    def replace(m):
        n = int(m.group(1))
        if 1 <= n <= len(articles):
            url = articles[n - 1].get("url", "#")
            return f'<a href="{url}" class="fn-ref" target="_blank">[註{n}]</a>'
        return m.group(0)
    return re.sub(r'\[註(\d+)\]', replace, summary).replace("\n", "<br>")


def _build_summary_html(summary: str, articles: list[dict]) -> str:
    """列點摘要：「重點 ||| 要點;;要點」轉為重點 + 固定顯示的簡短子列點。
    Email 客戶端（尤其手機 Gmail）不支援收放，故不依賴 <details>/JS。
    無分隔符的舊格式則原樣顯示為段落。"""
    items = []
    for line in summary.splitlines():
        line = re.sub(r'^[-•*]\s*', '', line.strip())
        if not line:
            continue
        head, sep, detail = line.partition("|||")
        subs = [d.strip() for d in detail.split(";;") if d.strip()] if sep else []
        sub_html = "".join(
            f'<li style="margin:2px 0;font-size:13px;line-height:1.6;color:#555;">'
            f'{_inject_fn_refs(d, articles)}</li>' for d in subs
        )
        items.append(
            f'<li style="margin:0 0 10px;font-size:14px;line-height:1.7;color:#1c1c1c;">'
            f'<b>{_inject_fn_refs(head.strip(), articles)}</b>'
            + (f'<ul style="margin:3px 0 0;padding-left:18px;">{sub_html}</ul>' if sub_html else "")
            + "</li>"
        )
    if not items or not any("<ul" in i for i in items):
        return f'<p class="summary">{_inject_fn_refs(summary, articles)}</p>'
    return '<ul style="margin:0 0 10px;padding-left:20px;">' + "".join(items) + "</ul>"


def _build_footnotes(local_articles: list[dict], labels: list[str],
                     intl_articles: list[dict], rejected: frozenset = frozenset()) -> str:
    """建立腳註清單 HTML，本地文章在前，國際文章（標 [國際]）在後。"""
    items = []
    all_arts = [(a, False) for a in local_articles] + [(a, True) for a in intl_articles]

    for i, (art, is_intl) in enumerate(all_arts):
        if i in rejected:  # numbering is kept so [註N] in the summary stays valid
            continue
        label = labels[i] if i < len(labels) else art.get("title", "")[:10]
        url = art.get("url", "#")
        source = art.get("source", "")
        intl_badge = '<span class="intl-badge">國際</span>' if is_intl else ""
        items.append(
            f'<div class="fn-item">'
            f'<a href="{url}" target="_blank">[註{i+1}] {label}</a>'
            f'{intl_badge}'
            f'<span class="fn-source">{source}</span>'
            f'</div>'
        )
    return "\n    ".join(items)


_DIRECTION = {"gap": ("高開", "低開"), "ret": ("上漲", "下跌"), "intra": ("走高", "走低")}


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:+.2f}%"


_TIER_HINT = {"極高": "≥90%", "高": "75~90%", "中": "60~75%", "低": "<60%"}


def _build_path_html(name: str, path: dict, img_src: str) -> str:
    """Block for one index/ETF: the chart carries everything for D2..D5; one line states D1's close and range."""
    c0, p1 = path["last_close"], path["d1_pred"]
    warn = ('<p style="font-size:13px;color:#b45f06;background:#fff4e5;padding:6px 8px;border-radius:4px;margin:6px 0 0;">'
            '⚠️ 與長期趨勢牴觸：目前處於過熱後的降溫整理期，但今日預測偏多，請保守看待。</p>') if path["conflict"] else ""
    return (
        f'<div style="margin:16px 0 4px;"><b style="font-size:14px;">{name}</b>'
        f'<span style="font-size:12px;color:#888;">（{path["last_date"].strftime("%m/%d")} 收盤 {c0:,.2f}）</span></div>'
        f'<img src="{img_src}" alt="{name} 預測圖" style="width:100%;max-width:680px;border:1px solid #eee;">'
        f'<p style="font-size:13px;line-height:1.8;margin:4px 0 0;">今日（{path["dates"][0].strftime("%m/%d")}）預估收盤 '
        f'<b>{p1:,.2f}</b>（{(p1 / c0 - 1) * 100:+.2f}%，80% 範圍 {path["d1_low"]:,.2f} ~ {path["d1_high"]:,.2f}）</p>{warn}'
    )


_RISK_COLOR = {"低": "#2e7d32", "中": "#8a6d00", "高": "#d9480f", "極高": "#a50f15"}


def _build_risk_html(risk: dict | None) -> str:
    """One line: today's expected intraday swing and its risk level, with what that level looked like historically."""
    if not risk:
        return ""
    st = risk["tier_stats"]
    hist = (f"　歷史上同等級的實際震盪中位約 {st['median'] * 100:.2f}%，超過 2% 的天數占 {st['over2']:.0%}") if st else ""
    return ('<p style="font-size:14px;margin:6px 0 2px;line-height:1.7;"><b>⚡ 今日震盪風險：</b>'
            f'預估盤中高低區間約 <b>{risk["range"] * 100:.2f}%</b>（約 {risk["points"]:,.0f} 點）｜'
            f'<b style="color:{_RISK_COLOR[risk["tier"]]};">風險{risk["tier"]}</b>'
            f'（高於歷史 {risk["percentile"]:.0%} 的日子）'
            f'<span style="font-size:12px;color:#666;">{hist}</span></p>')


def _build_forecast_html(fc: dict, image_mode: str = "cid") -> str:
    """Today's TAIEX forecast block (inline styles: mobile mail clients drop <style>).
    image_mode "cid" references inline MIME images; "data" embeds them for local previews."""
    inp = fc["inputs"]
    inputs = f"夜盤 {_pct(inp['夜盤'])}｜費半 {_pct(inp['費半'])}｜台積電 ADR {_pct(inp['台積電ADR'])}"
    missing = [k for k in ("夜盤", "費半", "台積電ADR") if k not in fc["model"]]
    note = f"（{'、'.join(missing)}資料未取得，以其餘指標預測）" if missing else ""
    rows = []
    for key, it in fc["items"].items():
        up_word, down_word = _DIRECTION[key]
        hit, n = it["tier_hit"]
        hist = f"歷史命中 {hit:.0%}" if hit is not None else "歷史命中 —"
        if it["tier"] == "低":
            body = f'<span style="color:#888;">－ 方向不明確</span>｜信心低（{hist}）'
        else:
            word = up_word if it["up"] else down_word
            color = "#d62728" if it["up"] else "#2ca02c"
            arrow = "▲" if it["up"] else "▼"
            body = (f'<b style="color:{color};">{arrow} {word}</b>｜機率 {it["confidence"]:.0%}'
                    f'｜信心{it["tier"]}（{hist}）')
            if key in ("gap", "ret"):
                body += f'｜預估 {_pct(it["size"])}'
        rows.append(f'<li style="margin:4px 0;font-size:14px;line-height:1.7;"><b>{it["label"]}：</b>{body}</li>')
    return (
        '<div class="region-block">'
        f'<div class="region-title">📈 今日台股預測（{fc["date"].strftime("%m/%d")}）</div>'
        f'<p style="font-size:13px;color:#555;margin:0 0 6px;">前一晚：{inputs}{note}</p>'
        f'<ul style="margin:0 0 6px;padding-left:20px;">{"".join(rows)}</ul>'
        + _build_risk_html(fc.get("risk"))
        + "".join(_build_path_html(name, path, (f"cid:{cid}" if image_mode == "cid" else
                                                  "data:image/png;base64," + base64.b64encode(fc["charts"][cid]).decode()))
                  for name, path in fc.get("paths", {}).items()
                  for cid in [{"加權指數": "fc_taiex", "0050": "fc_0050"}[name]])
        + '<p style="font-size:11px;color:#999;margin:10px 0 0;">歷史命中為同信心等級的逐年樣本外回測結果；D2 起只標示 80% 可能範圍，不預測方向。僅供參考，不構成投資建議。</p>'
        '</div>'
    )


def _build_html(region_results: list[dict], run_time: str, forecast: dict | None = None,
                image_mode: str = "cid") -> str:
    regions_html = ""
    total_articles = 0

    for rr in region_results:
        region = rr["region"]
        summary = rr.get("summary", "（本次無摘要）")
        local_arts = rr["articles"]
        intl_arts = rr.get("intl_taiwan_articles", [])
        labels = rr.get("labels", [])
        total_articles += len(local_arts) - sum(1 for k in rr.get("rejected", []) if k < len(local_arts))
        emoji = _REGION_EMOJI.get(region, "📌")

        all_arts = local_arts + intl_arts
        summary_html = _build_summary_html(summary, all_arts)
        footnotes_html = _build_footnotes(local_arts, labels, intl_arts, frozenset(rr.get("rejected", [])))

        regions_html += _REGION_BLOCK.format(
            emoji=emoji,
            region=region,
            summary_html=summary_html,
            footnotes_html=footnotes_html,
        )

    return _HTML_TEMPLATE.format(
        run_time=run_time,
        region_count=len(region_results),
        article_count=total_articles,
        regions_html=(_build_forecast_html(forecast, image_mode) if forecast else "")
                     + (regions_html or "<p>今日無與台灣經濟相關的消息。</p>"),
    )


def build_message(subject: str, html_body: str, sender: str, recipients: list[str],
                  images: dict[str, bytes] | None = None) -> MIMEMultipart:
    """HTML mail; inline images (referenced as cid:<key>) are attached as a multipart/related part."""
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    if images:
        msg = MIMEMultipart("related")
        msg.attach(alt)
        for cid, data in images.items():
            img = MIMEImage(data, "png")
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=f"{cid}.png")
            msg.attach(img)
    else:
        msg = alt
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    return msg


def send_html(subject: str, html_body: str, images: dict[str, bytes] | None = None) -> bool:
    """通用 HTML 郵件寄送，統一處理憑證與收件人。"""
    gmail_addr = os.getenv("GMAIL_ADDRESS", "")
    app_pwd = os.getenv("GMAIL_APP_PASSWORD", "")
    recipient = os.getenv("RECIPIENT_EMAIL", "")
    recipient_2 = os.getenv("RECIPIENT_EMAIL_2", "")
    if not all([gmail_addr, app_pwd, recipient]):
        logger.error("缺少 .env 設定 (GMAIL_ADDRESS / GMAIL_APP_PASSWORD / RECIPIENT_EMAIL)")
        return False

    all_recipients = [r for r in [recipient, recipient_2] if r]

    msg = build_message(subject, html_body, gmail_addr, all_recipients, images)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_addr, app_pwd)
            smtp.sendmail(gmail_addr, all_recipients, msg.as_bytes())
        logger.info("Email 寄送成功 → %s (主旨: %s)", ", ".join(all_recipients), subject)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail 認證失敗，請確認 App Password 是否正確")
        return False
    except Exception as exc:
        logger.error("Email 寄送失敗: %s", exc)
        return False


def run(region_results: list[dict], forecast: dict | None = None) -> bool:
    """Daily digest; an empty result list sends the "no Taiwan-economy news today" notice."""
    run_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = sum(len(r["articles"]) for r in region_results)
    if region_results:
        subject = f"財經摘要 {datetime.now().strftime('%m/%d')} — {len(region_results)} 地區 {total} 則"
    else:
        subject = f"財經摘要 {datetime.now().strftime('%m/%d')} — 今日無台灣相關經濟消息"
    html_body = _build_html(region_results, run_time, forecast)
    return send_html(subject, html_body, (forecast or {}).get("charts"))
