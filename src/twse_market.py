"""
台灣證交所官方市場資料，存入 data/market.db（日期為主鍵，重複寫入會取代，不累加）：
  twse_market  每日市場成交資訊（FMTQIK）：全市場總成交股數、成交金額、成交筆數、加權指數收盤
  twse_ohlc    加權指數開高低收（MI_5MINS_HIST）
  twse_inst    三大法人買賣金額（BFI82U）：自營商（自行買賣／避險）、投信、外資，買進／賣出／差額
  twse_stock   個股每日行情（STOCK_DAY，官方原始價格，未還原）：用來補 Yahoo 缺漏的最近交易日
另外 0050 的開高低收從 Yahoo 取得（yahoo_ohlc，價格已還原分割與配息）。

Yahoo 的 ^TWII volume 實際上是「成交筆數」，不是成交量，所以量能分析以官方成交金額為準。

用法：
    python -m src.twse_market                     # 例行更新：近兩個月的月資料 + 近 10 個交易日的三大法人
    python -m src.twse_market --backfill          # 回補 10 年成交資訊
    python -m src.twse_market --backfill-ohlc     # 回補 10 年加權指數開高低收 + 0050 開高低收
    python -m src.twse_market --backfill-inst     # 回補三大法人（逐日，從最新往回，可中斷續跑）
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

# BFI82U row label -> column prefix
_INST_ROWS = {
    "自營商(自行買賣)": "dealer_self",
    "自營商(避險)": "dealer_hedge",
    "投信": "trust",
    "外資及陸資(不含外資自營商)": "foreign",
    "外資自營商": "foreign_dealer",
    "合計": "total",
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS twse_market (
            trading_date TEXT PRIMARY KEY,
            shares REAL, value REAL, trades REAL,
            taiex REAL, change REAL
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS twse_ohlc (
            trading_date TEXT PRIMARY KEY,
            open REAL, high REAL, low REAL, close REAL
        )""")
    inst_cols = ", ".join(f"{p}_{k} REAL" for p in _INST_ROWS.values() for k in ("buy", "sell", "net"))
    conn.execute(f"CREATE TABLE IF NOT EXISTS twse_inst (trading_date TEXT PRIMARY KEY, {inst_cols})")
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


def fetch_month(year: int, month: int) -> list[tuple]:
    j = _get("afterTrading/FMTQIK", {"date": f"{year}{month:02d}01"})
    if j.get("stat") != "OK":
        return []
    return [(_roc_date(d), _num(s), _num(v), _num(t), _num(i), _num(c)) for d, s, v, t, i, c in j["data"]]


def fetch_ohlc_month(year: int, month: int) -> list[tuple]:
    j = _get("TAIEX/MI_5MINS_HIST", {"date": f"{year}{month:02d}01"})
    if j.get("stat") != "OK":
        return []
    return [(_roc_date(d), _num(o), _num(h), _num(l), _num(c)) for d, o, h, l, c in j["data"]]


def fetch_inst_day(day: str) -> tuple | None:
    """day: YYYY-MM-DD. Returns one twse_inst row (amounts in NTD) or None."""
    j = _get("fund/BFI82U", {"dayDate": day.replace("-", ""), "type": "day"})
    if j.get("stat") != "OK":
        return None
    vals = {}
    for name, buy, sell, net in j["data"]:
        prefix = _INST_ROWS.get(name)
        if prefix:
            vals[prefix] = (_num(buy), _num(sell), _num(net))
    row = [day]
    for prefix in _INST_ROWS.values():
        row.extend(vals.get(prefix, (None, None, None)))
    return tuple(row)


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


def update(months: list[tuple[int, int]]) -> int:
    return _run_months(months, fetch_month, "twse_market", 6)


def update_ohlc(months: list[tuple[int, int]]) -> int:
    return _run_months(months, fetch_ohlc_month, "twse_ohlc", 5)


def update_inst(days: list[str], skip_existing: bool = True) -> int:
    """Fetch BFI82U for each trading day (newest first), skipping days already stored."""
    conn = _connect()
    if skip_existing:
        have = {r[0] for r in conn.execute("SELECT trading_date FROM twse_inst")}
        days = [d for d in days if d not in have]
    logger.info("三大法人：%d 個交易日待抓", len(days))
    width = 1 + 3 * len(_INST_ROWS)
    n = 0
    for i, day in enumerate(days):
        if i:
            time.sleep(_DELAY)
        try:
            row = fetch_inst_day(day)
        except Exception as exc:
            logger.warning("三大法人 %s 失敗: %s", day, exc)
            continue
        if row:
            conn.execute(f"INSERT OR REPLACE INTO twse_inst VALUES ({','.join('?' * width)})", row)
            conn.commit()
            n += 1
        if (i + 1) % 50 == 0:
            logger.info("三大法人：%d/%d（最新處理到 %s）", i + 1, len(days), day)
    conn.close()
    return n


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


def _trading_days(newest_first: bool = True) -> list[str]:
    """Trading days known from twse_market (run the FMTQIK update first)."""
    conn = _connect()
    days = [r[0] for r in conn.execute("SELECT trading_date FROM twse_market ORDER BY trading_date")]
    conn.close()
    return days[::-1] if newest_first else days


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    if "--backfill" in sys.argv:
        update(_months_back(121))
    elif "--backfill-ohlc" in sys.argv:
        update_ohlc(_months_back(121))
        update_yahoo_ohlc("0050.TW", "10y")
    elif "--backfill-inst" in sys.argv:
        update_inst(_trading_days())
    else:
        update(_months_back(2))
        update_ohlc(_months_back(2))
        update_yahoo_ohlc("0050.TW", "1mo")
        update_inst(_trading_days()[:10])
