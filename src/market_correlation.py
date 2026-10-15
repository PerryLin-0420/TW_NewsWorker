"""
獨立監控模組——追蹤先前驗證過的跨市場領先/落後關係，用滾動視窗持續更新，
偵測「近期關聯強度」相對「歷史正常範圍」是否出現顯著偏移。

跟一次性驗證的差異：驗證階段（見對話中的 leadlag/backtest 分析）做的是
「全樣本、事前指定/排列檢定」的嚴謹統計檢定，目的是回答「這個關聯到底存
不存在」——那組關聯（見下方 PAIRS）已經通過方向不對稱性、偏相關、前後
半期穩定性三項檢驗，才收錄進這裡。這個模組假設關聯成立，改用滾動窗口
持續追蹤「現在」有沒有偏離「歷史」——這是監控用的描述性指標，不是新的
顯著性檢定：滾動視窗彼此高度重疊、自相關，不能拿滾動 rho 的序列本身再
去跑一次假設檢定。

時間對齊：DB 的 close_utc 欄位實際存的是「交易所當地午夜換算 UTC」，跟
trading_date 資訊量相同，無法用來判斷兩個標的誰先收盤。這裡改用各交易
所實際收盤時間（CLOSE_UTC，UTC 小時）自建時間軸，並在模組載入時斷言
每組 pair 的 lag 方向跟真實收盤順序一致——避免未來新增 pair 時把時序
方向弄反（新聞故事線那次分析吃過這個虧：close_utc 看似是時間戳，其實
只是日期換算，完全撐不起先後判斷）。

訊號定義：對每組 pair，用過去 rolling_window_days 交易日算滾動 Spearman
rho；歷史基準 = 排除「最近 recent_days 個交易日」後、其餘全部滾動 rho
值的均值/標準差；最近 recent_days 天中任一天的滾動 rho 若落在該基準
±z_threshold 個標準差之外，記為偏離（flagged）。

用法：
    python -m src.market_correlation
"""
import json
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "market.db"
OUT_PATH = ROOT / "data" / "market_correlation.json"

logger = logging.getLogger("market_correlation")

# 各交易所實際收盤時間（UTC 小時，日光節約會有 ±1h 誤差，但不影響亞洲
# <歐洲<美國的先後順序，這是這裡唯一依賴的性質）。
CLOSE_UTC = {
    "^TWII": 5.5, "^N225": 6.0, "^KS11": 6.5,
    "^STOXX50E": 16.0, "^GDAXI": 16.0, "^FTSE": 16.5,
    "^GSPC": 20.5, "^IXIC": 20.5, "^SOX": 20.5,
    "^VIX": 21.25, "HG=F": 18.5,
}

_LABELS = {
    "^TWII": "台股", "^N225": "日經", "^KS11": "韓股",
    "^GDAXI": "德DAX", "^FTSE": "英FTSE", "^STOXX50E": "歐STOXX",
    "^GSPC": "標普", "^IXIC": "那斯達克", "^SOX": "費半",
    "^VIX": "VIX", "HG=F": "銅",
}

# 已通過驗證的領先-落後關係：(A, B, lag, 類別)
# lag=0 表示 A[d] -> B[d]（A 當日先收盤）；lag=1 表示 A[d] -> B[d+1]（隔夜）。
# 只收錄通過三項檢驗的關係——方向不對稱性（反向 rho 顯著更弱）、偏相關
# （控制共同因子後訊號不塌陷）、前後半期穩定（兩段同號且 |rho|>0.15）。
# 恆生（HSI）在前後半期檢驗不穩定、原油/黃金/10Y殖利率對亞股隔夜傳遞
# 太弱，均排除在外。
PAIRS = [
    ("^SOX", "^TWII", 1, "overnight_us_asia"),
    ("^SOX", "^N225", 1, "overnight_us_asia"),
    ("^SOX", "^KS11", 1, "overnight_us_asia"),
    ("^GSPC", "^TWII", 1, "overnight_us_asia"),
    ("^GSPC", "^N225", 1, "overnight_us_asia"),
    ("^GSPC", "^KS11", 1, "overnight_us_asia"),
    ("^IXIC", "^TWII", 1, "overnight_us_asia"),
    ("^IXIC", "^N225", 1, "overnight_us_asia"),
    ("^IXIC", "^KS11", 1, "overnight_us_asia"),
    ("^GDAXI", "^GSPC", 0, "sameday_europe_us"),
    ("^FTSE", "^GSPC", 0, "sameday_europe_us"),
    ("^STOXX50E", "^GSPC", 0, "sameday_europe_us"),
    ("^N225", "^GDAXI", 0, "sameday_asia_europe"),
    ("^N225", "^STOXX50E", 0, "sameday_asia_europe"),
    ("^TWII", "^GDAXI", 0, "sameday_asia_europe"),
    ("^TWII", "^STOXX50E", 0, "sameday_asia_europe"),
    ("^VIX", "^TWII", 1, "macro_overnight"),
    ("^VIX", "^N225", 1, "macro_overnight"),
    ("^VIX", "^KS11", 1, "macro_overnight"),
    ("HG=F", "^TWII", 1, "macro_overnight"),
    ("HG=F", "^N225", 1, "macro_overnight"),
    ("HG=F", "^KS11", 1, "macro_overnight"),
]

_CATEGORY_LABEL = {
    "overnight_us_asia": "美股隔夜 -> 亞股",
    "sameday_europe_us": "歐股同日 -> 美股",
    "sameday_asia_europe": "亞股同日 -> 歐股",
    "macro_overnight": "宏觀因子隔夜 -> 亞股",
}

# 新聞地區（對齊 config.json region_order）-> 相關標的。用來把訊號分派
# 給 summarizer.py 對應地區的摘要 prompt，一個 pair 兩端各自的地區都會
# 收到（例如「那斯達克->台股」在【美國】跟【台灣】摘要裡都算相關）。
REGION_SYMBOLS = {
    "台灣": {"^TWII"},
    "美國": {"^GSPC", "^IXIC", "^SOX"},
    "亞洲": {"^N225", "^KS11"},
    "歐洲": {"^GDAXI", "^FTSE", "^STOXX50E"},
    "大宗商品": {"HG=F"},
    "全球": {"^VIX"},
}


def _validate_pair_direction() -> None:
    """時空防呆：每組 pair 的 lag 方向必須跟 A、B 的真實收盤順序一致，
    否則就是把『B 已經知道的資訊』誤標成『B 還不知道、A 領先』。"""
    for a, b, lag, _ in PAIRS:
        gap_hours = lag * 24 + CLOSE_UTC[b] - CLOSE_UTC[a]
        if gap_hours <= 0:
            raise AssertionError(
                f"時序方向錯誤: {a} -> {b} (lag={lag}) 換算後 B 比 A 早收盤 "
                f"({gap_hours:+.1f}h)，A 不可能領先 B"
            )


_validate_pair_direction()


def _load_config() -> dict:
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    return cfg["market_correlation"]


def _returns_frame(symbols: set[str]) -> pd.DataFrame:
    """每個標的的報酬率各自在『自己的交易日曆』上算 log-diff，算完才合併。

    不能先 pivot 成聯集日曆再整欄 shift(1)：不同交易所假日不同，聯集會在
    某個標的的欄位裡插入別的標的才有的日期（該標的當天是 NaN），shift(1)
    是照『列位置』位移，遇到這種插入就會把前一列讀成 NaN，把該標的原本
    存在的報酬率誤標成缺值——不是算錯數字，但會系統性流失樣本、且集中
    在假日附近，等同於另一種形式的時空錯位。
    """
    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" * len(symbols))
    raw = pd.read_sql_query(
        f"SELECT symbol, trading_date, close FROM prices WHERE symbol IN ({placeholders})",
        conn, params=list(symbols),
    )
    conn.close()
    raw["trading_date"] = pd.to_datetime(raw["trading_date"])

    out = {}
    for sym, g in raw.groupby("symbol"):
        s = g.sort_values("trading_date").set_index("trading_date")["close"].astype(float)
        out[sym] = np.log(s / s.shift(1))
    return pd.DataFrame(out)


def _rolling_spearman(x: pd.Series, y: pd.Series, window: int, min_periods: int) -> pd.Series:
    """逐日重算視窗內的 rank（真正的滾動 Spearman，不是用全域排名近似）。"""
    joined = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    xv, yv = joined["x"].to_numpy(), joined["y"].to_numpy()
    out = np.full(len(joined), np.nan)
    for i in range(len(joined)):
        lo = max(0, i - window + 1)
        if i - lo + 1 < min_periods:
            continue
        rho, _ = stats.spearmanr(xv[lo:i + 1], yv[lo:i + 1])
        out[i] = rho
    return pd.Series(out, index=joined.index)


def analyze_pair(returns: pd.DataFrame, a: str, b: str, lag: int, category: str,
                  window: int, recent_days: int, z_threshold: float,
                  min_baseline_obs: int) -> dict | None:
    if a not in returns.columns or b not in returns.columns:
        return None
    x = returns[a]
    y = returns[b].shift(-lag)
    roll = _rolling_spearman(x, y, window, min_periods=int(window * 0.75)).dropna()

    if len(roll) < recent_days + min_baseline_obs:
        logger.warning("%s -> %s: 歷史不足（%d 筆滾動觀測），略過", a, b, len(roll))
        return None

    hist = roll.iloc[:-recent_days]
    recent = roll.iloc[-recent_days:]
    mu, sigma = float(hist.mean()), float(hist.std(ddof=1))
    if not sigma or np.isnan(sigma):
        return None

    z = (recent - mu) / sigma
    latest_rho, latest_z = float(roll.iloc[-1]), float(z.iloc[-1])
    flagged_days = int((z.abs() > z_threshold).sum())

    # 相對歷史基準，方向朝『同號變強』還是『變弱/翻轉』（對負相關基準一樣適用）
    strengthening = (latest_rho - mu) * np.sign(mu) > 0

    return {
        "a": a, "b": b, "lag": lag, "category": category,
        "label": f"{_LABELS.get(a, a)} -> {_LABELS.get(b, b)}"
                 f"（{'隔夜' if lag else '同日'}）",
        "n_rolling_obs": int(len(roll)),
        "n_baseline_obs": int(len(hist)),
        "hist_mean": round(mu, 3),
        "hist_std": round(sigma, 3),
        "latest_date": roll.index[-1].date().isoformat(),
        "latest_rho": round(latest_rho, 3),
        "latest_z": round(latest_z, 2),
        "recent_days_n": int(len(recent)),
        "recent_flagged_days": flagged_days,
        "recent_flagged_pct": round(flagged_days / len(recent) * 100, 1),
        "flagged": bool(abs(latest_z) > z_threshold),
        "direction": "轉強" if strengthening else "轉弱/翻轉",
        "recent_series": [
            {"date": d.date().isoformat(), "rho": round(float(v), 3),
             "z": round(float((v - mu) / sigma), 2)}
            for d, v in recent.items()
        ],
    }


def run() -> list[dict]:
    cfg = _load_config()
    window = cfg["rolling_window_days"]
    recent_days = cfg["recent_days"]
    z_threshold = cfg["z_threshold"]
    min_baseline_obs = cfg["min_baseline_obs"]

    symbols = {s for a, b, _, _ in PAIRS for s in (a, b)}
    returns = _returns_frame(symbols)

    results = []
    for a, b, lag, category in PAIRS:
        r = analyze_pair(returns, a, b, lag, category, window, recent_days,
                         z_threshold, min_baseline_obs)
        if r:
            results.append(r)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "config": cfg,
        "pairs": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    flagged = [r for r in results if r["flagged"]]
    logger.info("market_correlation: %d/%d 組關係本次更新，%d 組偏離歷史基準 ±%.1fσ",
                len(results), len(PAIRS), len(flagged), z_threshold)
    return results


def load_latest_signals(max_age_hours: float = 48) -> list[dict]:
    """給 summarizer.py 用：只回傳最新一次執行中「偏離歷史基準」的關係。

    超過 max_age_hours 視為過期而不採用——今天的新聞摘要不該引用一份
    可能是好幾天前的市場快照，那本身就是一種時空錯位。檔案不存在、損毀
    或過期都安靜地回傳空清單，絕不讓市場模組的問題擋住新聞摘要主線。
    """
    if not OUT_PATH.exists():
        return []
    try:
        data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        generated_at = pd.Timestamp(data["generated_at"])
    except Exception as exc:
        logger.warning("market_correlation.json 讀取失敗，略過訊號: %s", exc)
        return []

    age_hours = (pd.Timestamp.now("UTC") - generated_at).total_seconds() / 3600
    if age_hours > max_age_hours:
        logger.warning("market_correlation.json 已過期 (%.0f 小時前)，略過訊號", age_hours)
        return []

    return [p for p in data["pairs"] if p["flagged"]]


def signals_for_region(signals: list[dict], region: str) -> list[dict]:
    """篩出跟該新聞地區相關的訊號（pair 兩端任一標的屬於該地區即算相關）。"""
    syms = REGION_SYMBOLS.get(region, set())
    return [s for s in signals if s["a"] in syms or s["b"] in syms]


def format_signal_block(signals: list[dict]) -> str:
    """把訊號組成一段可直接嵌入摘要 prompt 的文字；無訊號則回傳空字串。"""
    if not signals:
        return ""
    lines = [
        "【市場數據背景參考】（量化監控訊號，非新聞內容；"
        "與本日新聞無明顯關聯時不必勉強提及）"
    ]
    for s in signals:
        lines.append(
            f"- {s['label']}：近 {s['n_rolling_obs']} 個交易日的滾動關聯強度為 "
            f"{s['latest_rho']:.2f}，明顯{s['direction']}於歷史均值 "
            f"{s['hist_mean']:.2f}（z={s['latest_z']:+.1f}）"
        )
    return "\n".join(lines) + "\n"


def _print_report(results: list[dict], z_threshold: float) -> None:
    if not results:
        print("無可用結果")
        return
    print(f"{'類別':<18}{'關係':<28}{'最新日期':<12}{'rho':>7}{'歷史均值':>9}"
          f"{'z':>7}{'近期偏離天數':>14}{'訊號':>6}")
    for r in sorted(results, key=lambda x: -abs(x["latest_z"])):
        flag = f"** {r['direction']}" if r["flagged"] else ""
        print(f"{_CATEGORY_LABEL.get(r['category'], r['category']):<18}"
              f"{r['label']:<28}{r['latest_date']:<12}{r['latest_rho']:>7.3f}"
              f"{r['hist_mean']:>9.3f}{r['latest_z']:>7.2f}"
              f"{r['recent_flagged_pct']:>13.1f}%{flag:>8}")

    flagged = [r for r in results if r["flagged"]]
    print(f"\n共 {len(results)} 組關係，{len(flagged)} 組最新讀數偏離歷史基準 "
          f"±{z_threshold:.1f}σ")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s - %(message)s")
    res = run()
    _print_report(res, _load_config()["z_threshold"])
