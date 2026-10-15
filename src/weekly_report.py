"""
純數據型週報——刻意不依賴事件評分/相關性方法論（那條路線的訊號還在驗證中，
見 backtest 系列腳本），單純陳列 market_data.py 已回補的各地區標的：本週
漲跌、對比上週漲跌、對比去年同期漲跌。三者都只是格式化數字表格，不經過
LLM，零額外成本、零摘要幻覺風險。

「本週」定義為週一收盤～週五收盤（用該標的自己在那個區間內最早/最晚的
實際交易日，非日曆週一/週五本身，避免假日造成的空值）。排程建議週六
09:00 執行，那時上一個週五已收盤完畢。

用法：
    python -m src.weekly_report
"""
import json
import logging
from datetime import date, timedelta
from pathlib import Path

from src import emailer, market_data

logger = logging.getLogger("weekly_report")

_REGION_EMOJI = {
    "台灣": "🇹🇼", "美國": "🇺🇸", "亞洲": "🌏", "歐洲": "🇪🇺",
    "大宗商品": "🛢️", "全球": "🌐", "半導體": "🔬",
}

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, "Noto Sans TC", Arial, sans-serif; background:#f4f4f4; margin:0; padding:20px; }}
  .container {{ max-width:760px; margin:auto; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 2px 10px rgba(0,0,0,.1); }}
  .header {{ background:#0d1b2a; color:#fff; padding:22px 32px; }}
  .header h1 {{ margin:0; font-size:19px; letter-spacing:.5px; }}
  .header p {{ margin:6px 0 0; font-size:12px; color:#8aa; }}
  .body {{ padding:20px 32px; }}
  .region-title {{ font-size:15px; font-weight:700; color:#0d1b2a; border-bottom:2px solid #e8e8e8; padding-bottom:6px; margin:22px 0 8px; }}
  .ticker-card {{ padding:10px 0; border-bottom:1px solid #f0f0f0; }}
  .ticker-name {{ font-size:14px; font-weight:600; color:#0d1b2a; margin-bottom:6px; }}
  .stats {{ display:flex; gap:8px; }}
  .stat {{ flex:1; min-width:0; }}
  .stat-label {{ display:block; font-size:11px; color:#888; margin-bottom:2px; white-space:nowrap; }}
  .stat-value {{ display:block; font-size:15px; font-weight:600; color:#2c2c2c; }}
  .up {{ color:#c0392b; }}
  .down {{ color:#1e8449; }}
  .na {{ color:#bbb; }}
  .footer {{ background:#f0f0f0; padding:12px 32px; font-size:11px; color:#999; text-align:center; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>財經數據週報</h1>
    <p>本週 {monday} ~ {friday}</p>
  </div>
  <div class="body">
    {regions_html}
  </div>
  <div class="footer">
    由 News Worker 自動生成 &nbsp;·&nbsp; 純市場數據彙整，未經 LLM 摘要 &nbsp;·&nbsp; 僅供參考，不構成投資建議
  </div>
</div>
</body>
</html>
"""


def _week_bounds(as_of: date) -> tuple[date, date]:
    """回傳 as_of 當週（若 as_of 非週六，先往回找最近的週六）剛結束那週的 (週一, 週五)。"""
    days_since_saturday = (as_of.weekday() - 5) % 7  # Mon=0 ... Sat=5, Sun=6
    saturday = as_of - timedelta(days=days_since_saturday)
    friday = saturday - timedelta(days=1)
    monday = friday - timedelta(days=4)
    return monday, friday


def _week_change(symbol: str, monday: date, friday: date) -> dict | None:
    """區間內取實際交易日的最早/最晚收盤價算漲跌幅；資料不足 2 筆視為無資料。"""
    rows = market_data.load_range(symbol, monday.isoformat(), friday.isoformat())
    if len(rows) < 2 or not rows[0]["close"]:
        return None
    start, end = rows[0], rows[-1]
    return {
        "start_date": start["date"], "end_date": end["date"],
        "pct": (end["close"] / start["close"] - 1) * 100,
    }


def _fmt_pct(change: dict | None) -> str:
    if change is None:
        return '<span class="stat-value na">—</span>'
    pct = change["pct"]
    cls = "up" if pct > 0 else "down" if pct < 0 else ""
    sign = "+" if pct > 0 else ""
    return f'<span class="stat-value {cls}">{sign}{pct:.2f}%</span>'


def _stat(label: str, change: dict | None) -> str:
    return f'<div class="stat"><span class="stat-label">{label}</span>{_fmt_pct(change)}</div>'


def _build_html(as_of: date) -> str:
    monday, friday = _week_bounds(as_of)
    regions_html = ""

    for region, tickers in market_data.TICKERS.items():
        emoji = _REGION_EMOJI.get(region, "📌")
        cards_html = ""
        for symbol, name in tickers:
            this_week = _week_change(symbol, monday, friday)
            last_week = _week_change(symbol, monday - timedelta(days=7), friday - timedelta(days=7))
            last_year = _week_change(symbol, monday - timedelta(days=364), friday - timedelta(days=364))
            cards_html += (
                '<div class="ticker-card">'
                f'<div class="ticker-name">{name}</div>'
                '<div class="stats">'
                f'{_stat("本週漲跌", this_week)}'
                f'{_stat("上週漲跌", last_week)}'
                f'{_stat("去年同期", last_year)}'
                '</div></div>\n'
            )
        regions_html += (
            f'<div class="region-title">{emoji} {region}</div>\n{cards_html}'
        )

    return _HTML_TEMPLATE.format(
        monday=monday.isoformat(), friday=friday.isoformat(),
        regions_html=regions_html,
    )


def _enabled() -> bool:
    cfg = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))
    return cfg.get("weekly_report", {}).get("enabled", True)


def run(as_of: date | None = None) -> bool:
    if not _enabled():
        # Paused until the economic-data section of the reports is redesigned.
        logger.info("週報已暫停（config.json weekly_report.enabled=false），不寄送")
        return True
    as_of = as_of or date.today()
    monday, friday = _week_bounds(as_of)
    subject = f"財經數據週報 {monday.strftime('%m/%d')}~{friday.strftime('%m/%d')}"
    html_body = _build_html(as_of)
    return emailer.send_html(subject, html_body)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s - %(message)s")
    run()
