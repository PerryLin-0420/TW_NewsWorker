"""
台灣期交所台指期（TX）每日行情，含一般（日盤）與盤後（夜盤）時段，只保留近月合約
（同一交易日、同一時段中成交量最大的月合約，排除週選）。

夜盤歸屬：期交所把 T-1 日 15:00 ～ T 日 05:00 的夜盤記在交易日 T，漲跌以 T-1 結算價計算，
所以「交易日 T 的盤後」就是台股 T 日開盤前可取得的最新資訊。

存入 data/market.db 的 taifex_tx 表，(trading_date, session) 為主鍵（重複寫入取代，不累加）。

用法：
    python -m src.taifex             # 例行更新：本月與上月
    python -m src.taifex --backfill  # 回補到 2017-05（夜盤開始）
"""
import io
import logging
import sqlite3
import sys
import time
from datetime import date, timedelta

import pandas as pd
import requests

from src.market_data import DB_PATH

logger = logging.getLogger("taifex")

_URL = "https://www.taifex.com.tw/cht/3/futDataDown"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_DELAY = 3.0
_SESSION = {"一般": "day", "盤後": "night"}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS taifex_tx (
            trading_date TEXT NOT NULL, session TEXT NOT NULL, contract TEXT,
            open REAL, high REAL, low REAL, close REAL, settle REAL, volume REAL, oi REAL,
            PRIMARY KEY (trading_date, session)
        )""")
    return conn


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def fetch_range(start: date, end: date) -> list[tuple]:
    resp = requests.post(_URL, data={"down_type": "1", "commodity_id": "TX",
                                     "queryStartDate": start.strftime("%Y/%m/%d"),
                                     "queryEndDate": end.strftime("%Y/%m/%d")},
                         headers=_HEADERS, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.content.decode("big5", errors="replace")), dtype=str,
                     index_col=False)  # rows carry a trailing comma the header lacks
    if df.empty or "交易時段" not in df.columns:
        return []
    df.columns = [c.strip() for c in df.columns]
    df["到期月份(週別)"] = df["到期月份(週別)"].str.strip()
    df = df[df["到期月份(週別)"].str.fullmatch(r"\d{6}")]          # monthly contracts only
    df["vol"] = df["成交量"].map(_num).fillna(0)
    rows = []
    for (d, sess), g in df.groupby(["交易日期", "交易時段"]):
        if sess.strip() not in _SESSION:
            continue
        top = g.loc[g.vol.idxmax()]
        if top.vol <= 0:
            continue
        rows.append((d.replace("/", "-"), _SESSION[sess.strip()], top["到期月份(週別)"],
                     _num(top["開盤價"]), _num(top["最高價"]), _num(top["最低價"]), _num(top["收盤價"]),
                     _num(top["結算價"]), top.vol, _num(top["未沖銷契約數"])))
    return rows


def update(start: date, end: date) -> int:
    conn = _connect()
    n, cur, first = 0, start, True
    while cur <= end:
        nxt = min((cur.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1), end)
        if not first:
            time.sleep(_DELAY)
        first = False
        try:
            rows = fetch_range(cur, nxt)
            conn.executemany("INSERT OR REPLACE INTO taifex_tx VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
            conn.commit()
            n += len(rows)
            logger.info("TAIFEX TX %s ~ %s: %d 筆", cur, nxt, len(rows))
        except Exception as exc:
            logger.warning("TAIFEX TX %s ~ %s 失敗: %s", cur, nxt, exc)
        cur = nxt + timedelta(days=1)
    conn.close()
    return n


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    today = date.today()
    if "--backfill" in sys.argv:
        update(date(2017, 5, 1), today)
    else:
        update((today.replace(day=1) - timedelta(days=1)).replace(day=1), today)
