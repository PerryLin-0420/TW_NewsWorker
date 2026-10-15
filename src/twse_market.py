"""
台灣證交所官方市場資料，存入 data/market.db（日期為主鍵，重複寫入會取代，不累加）：
  twse_ohlc    加權指數開高低收（MI_5MINS_HIST）
  twse_stock   個股每日行情（STOCK_DAY，官方原始價格，未還原）：用來補 Yahoo 缺漏的最近交易日
另外 0050 的開高低收從 Yahoo 取得（yahoo_ohlc，價格已還原分割與配息）。

用法：
    python -m src.twse_market                     # 例行更新：近兩個月加權指數開高低收 + 0050
    python -m src.twse_market --backfill-ohlc     # 回補 10 年加權指數開高低收 + 0050 開高低收
"""
import logging
import sqlite3
import sys
import time
from datetime import date

import requests

from src.market_data import DB_PATH

logger = logging.getLogger("twse_market")

_BASE = "https://www.twse.com.tw/rwd/zh"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_DELAY = 3.0  # TWSE blocks clients that query too fast


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS twse_ohlc (
            trading_date TEXT PRIMARY KEY,
            open REAL, high REAL, low REAL, close REAL
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS twse_stock (
            symbol TEXT NOT NULL, trading_date TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (symbol, trading_date)
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS yahoo_ohlc (
            symbol TEXT NOT NULL, trading_date TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (symbol, trading_date)
        )""")
    return conn


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _roc_date(d: str) -> str:
    y, mo, da = d.split("/")  # ROC calendar, e.g. 115/10/02
    return f"{int(y) + 1911}-{mo}-{da}"


def _get(path: str, params: dict) -> dict:
    resp = requests.get(f"{_BASE}/{path}", params={**params, "response": "json"},
                        headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_ohlc_month(year: int, month: int) -> list[tuple]:
    j = _get("TAIEX/MI_5MINS_HIST", {"date": f"{year}{month:02d}01"})
    if j.get("stat") != "OK":
        return []
    return [(_roc_date(d), _num(o), _num(h), _num(l), _num(c)) for d, o, h, l, c in j["data"]]


def _run_months(months: list[tuple[int, int]], fetch, table: str, width: int) -> int:
    conn = _connect()
    n = 0
    for i, (y, m) in enumerate(months):
        if i:
            time.sleep(_DELAY)
        try:
            rows = fetch(y, m)
        except Exception as exc:
            logger.warning("TWSE %s %d-%02d 失敗: %s", table, y, m, exc)
            continue
        conn.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({','.join('?' * width)})", rows)
        conn.commit()
        n += len(rows)
        logger.info("TWSE %s %d-%02d: %d 筆", table, y, m, len(rows))
    conn.close()
    return n


def update_ohlc(months: list[tuple[int, int]]) -> int:
    return _run_months(months, fetch_ohlc_month, "twse_ohlc", 5)


def update_stock(stock_no: str, months: list[tuple[int, int]]) -> int:
    """Official daily prices for one stock/ETF (raw, not adjusted for splits or dividends)."""
    conn = _connect()
    n = 0
    for i, (y, m) in enumerate(months):
        if i:
            time.sleep(_DELAY)
        try:
            j = _get("afterTrading/STOCK_DAY", {"date": f"{y}{m:02d}01", "stockNo": stock_no})
        except Exception as exc:
            logger.warning("TWSE STOCK_DAY %s %d-%02d 失敗: %s", stock_no, y, m, exc)
            continue
        if j.get("stat") != "OK":
            continue
        rows = [(stock_no, _roc_date(r[0]), _num(r[3]), _num(r[4]), _num(r[5]), _num(r[6]), _num(r[1]))
                for r in j["data"] if r[6] not in ("--", "")]
        conn.executemany("INSERT OR REPLACE INTO twse_stock VALUES (?,?,?,?,?,?,?)", rows)
        conn.commit()
        n += len(rows)
    conn.close()
    return n


def update_yahoo_ohlc(symbol: str, period: str) -> int:
    import yfinance as yf
    hist = yf.Ticker(symbol).history(period=period, interval="1d")
    rows = [(symbol, ts.strftime("%Y-%m-%d"), float(r.Open), float(r.High), float(r.Low), float(r.Close),
             float(r.Volume)) for ts, r in hist.iterrows() if r.Close == r.Close]
    conn = _connect()
    conn.executemany("INSERT OR REPLACE INTO yahoo_ohlc VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    logger.info("Yahoo %s: %d 筆", symbol, len(rows))
    return len(rows)


def _months_back(k: int) -> list[tuple[int, int]]:
    t = date.today()
    out = []
    for i in range(k):
        y, m = divmod(t.year * 12 + t.month - 1 - i, 12)
        out.append((y, m + 1))
    return out[::-1]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    if "--backfill-ohlc" in sys.argv:
        update_ohlc(_months_back(121))
        update_yahoo_ohlc("0050.TW", "10y")
    else:
        update_ohlc(_months_back(2))
        update_yahoo_ohlc("0050.TW", "1mo")
