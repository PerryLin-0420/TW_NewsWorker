"""
獨立的市場資料快照腳本——刻意與新聞 pipeline 脫鉤，不寄信、不影響 main.py。

以「實際交易日」而非「查詢當下的日期」為準：每筆資料的日期直接取自該
標的自己回傳的收盤時間（依交易所當地時區），並換算成 UTC 一併存起來，
讓不同時區的市場資料能對齊到同一條時間軸上比較。這避免兩個實際出現過
的問題：(1) 午夜查詢時亞股當日尚未收盤，來源回傳 NaN 卻被誤標成當天
資料；(2) 部分來源資料延遲數天，舊資料被誤標成當天的新資料。

DB 用 SQLite（data/market.db），(symbol, trading_date) 為主鍵——同一
交易日重複寫入會取代舊值，不會重複累加；也代表回補歷史與例行補抓可以
共用同一套寫入邏輯，不會因為重疊而重複計數。

用法：
    python -m src.market_data             # 例行快照：補抓最近 5 天
    python -m src.market_data --backfill  # 一次性回補 2 年歷史
"""
import logging
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "market.db"

logger = logging.getLogger("market_data")

# 地區 -> [(ticker, 顯示名稱), ...]，與 config.json 的 region_order 對齊。
# 只保留 market_correlation.py 與 tw_forecast.py 實際使用的標的；其餘
# （ETF、原油、黃金、天然氣、美元、10Y殖利率、恒生）經檢定對台股方向
# 沒有顯著的增量預測力，已不再儲存（見 README）。
TICKERS = {
    "台灣": [("^TWII", "加權指數")],
    "美國": [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq")],
    "亞洲": [("^N225", "Nikkei 225"), ("^KS11", "KOSPI")],
    "歐洲": [("^GDAXI", "DAX"), ("^FTSE", "FTSE 100"), ("^STOXX50E", "Euro Stoxx 50")],
    "大宗商品": [("HG=F", "銅")],
    "全球": [("^VIX", "VIX")],
    "半導體": [("^SOX", "費城半導體指數")],
}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            symbol TEXT NOT NULL,
            region TEXT NOT NULL,
            name TEXT NOT NULL,
            trading_date TEXT NOT NULL,
            close_utc TEXT NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            fetched_at_utc TEXT NOT NULL,
            PRIMARY KEY (symbol, trading_date)
        )
    """)
    return conn


def _fetch_and_store(conn: sqlite3.Connection, symbol: str, region: str,
                     name: str, period: str) -> int:
    """抓一段期間的歷史資料，逐筆以資料自己的實際交易日存入（不是查詢當下的日期）。"""
    import yfinance as yf

    hist = yf.Ticker(symbol).history(period=period, interval="1d")
    if hist.empty:
        logger.warning("無資料: %s (%s)", symbol, name)
        return 0

    fetched_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for ts, row in hist.iterrows():
        close = float(row["Close"])
        if math.isnan(close):
            continue  # 該交易日尚未結算或無成交，跳過而非誤存
        volume = float(row["Volume"])
        trading_date = ts.strftime("%Y-%m-%d")        # 交易所當地日期
        close_utc = ts.tz_convert("UTC").isoformat()  # 換算 UTC，供跨區對齊時間軸
        rows.append((symbol, region, name, trading_date, close_utc,
                    close, 0.0 if math.isnan(volume) else volume, fetched_at))

    if rows:
        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO prices "
                "(symbol, region, name, trading_date, close_utc, close, volume, fetched_at_utc) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
    return len(rows)


def capture(period: str = "5d") -> int:
    """例行快照：補抓最近幾天。每個標的的資料日期取自資料本身，不是查詢
    當下的日期，同一交易日重跑會取代舊值，也會自動補上前次執行漏掉的
    交易日（例如來源延遲導致上次抓到空值）。回傳寫入的資料列數。"""
    conn = _connect()
    total_rows = 0
    try:
        for region, tickers in TICKERS.items():
            for symbol, name in tickers:
                try:
                    total_rows += _fetch_and_store(conn, symbol, region, name, period)
                except Exception as exc:
                    logger.warning("抓取失敗: %s (%s) - %s", symbol, name, exc)
    finally:
        conn.close()
    n_tickers = sum(len(v) for v in TICKERS.values())
    logger.info("市場資料已更新：%d 個標的、共寫入 %d 筆交易日資料", n_tickers, total_rows)
    return total_rows


def backfill(period: str = "2y") -> int:
    """一次性回補長期歷史，供延遲相關分析的背景資料。"""
    logger.info("開始回補 %s 歷史資料...", period)
    return capture(period=period)


def load_day(trading_date: str) -> list[dict]:
    """查詢某一交易日所有標的的快照。"""
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT symbol, region, name, close, volume FROM prices WHERE trading_date = ?",
            (trading_date,),
        )
        return [{"symbol": s, "region": r, "name": n, "close": c, "volume": v}
                for s, r, n, c, v in cur.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s - %(message)s")
    if "--backfill" in sys.argv:
        backfill()
    else:
        capture()
