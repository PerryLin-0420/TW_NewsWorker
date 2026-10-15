"""
今日台股開盤預測——利用時差：台北 08:00 時，台指期夜盤（05:00 收）與美股（約 04:00~05:00 收）
已經收盤，但台股尚未開盤。以「夜盤 + 費半 + 台積電 ADR」的前一晚漲跌，預測當天：
開盤跳空方向、當日漲跌、開盤後漲跌，並附預估跳空幅度。

模型為標準化後的邏輯迴歸／線性迴歸，每次以資料庫中全部歷史重新擬合。信心指數 = 模型對
預測方向給出的機率；各信心等級的「歷史命中率」由逐年滾動的樣本外回測即時計算，不寫死。
任一指標缺漏（尚未發布、換月日、Yahoo 收盤延遲）時，改用其餘可用的指標。

另外對加權指數與 0050 產生未來 5 個交易日的預測：第 1 天依同一組隔夜指標給出預估收盤、方向與信心；
第 2~5 天不給數值與方向（回測證實價量、均線、法人、新聞情緒都無法預測第 2 天以後的方向），只給
以第 1 天預估價位為中心的 80% 可能範圍，寬度由 5~250 日六條波動均線經衰減函數正規化加權
（越後面越重視長天期），D1 另有隨波動調整的 80% 範圍；係數每次以歷史資料聯合學習，目標為「範圍窄且貼近實際收盤」。並檢查長期趨勢：
處於「過熱降溫後的整理期」時（歷史上之後 1~2 週偏弱），若今日預測偏多即標示牴觸。

只在台股交易日（週一到週五、非證交所休市日）產生預測。
"""
import io
import logging
import re
import sqlite3
from functools import lru_cache
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

from src.market_data import DB_PATH

logger = logging.getLogger("tw_forecast")

TPE = timezone(timedelta(hours=8))
FULL = ["夜盤", "費半", "台積電ADR"]
TARGETS = {"gap": "開盤", "ret": "當日", "intra": "開盤後"}
# (lower bound of confidence, label); confidence = probability of the predicted direction
TIERS = [(0.9, "極高"), (0.75, "高"), (0.6, "中"), (0.0, "低")]
_US = {"費半": "^SOX", "台積電ADR": "TSM"}


def _q(conn, sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, conn, parse_dates=["trading_date"]).set_index("trading_date").sort_index()


@lru_cache(maxsize=4)
def _holidays(year: int) -> frozenset[date]:
    """Non-trading days from the TWSE holiday schedule (ranges and make-up days expanded)."""
    j = requests.get("https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule",
                     params={"response": "json", "queryYear": str(year - 1911)},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=20).json()
    out: set[date] = set()
    for d, name, note in j.get("data", []):
        if "開始交易" in name or "最後交易" in name:
            continue  # these are trading days
        out.add(date.fromisoformat(d))
        for m1, d1, m2, d2 in re.findall(r"(\d+)月(\d+)日至(\d+)月(\d+)日", note):
            cur, end = date(year, int(m1), int(d1)), date(year, int(m2), int(d2))
            while cur <= end:
                out.add(cur)
                cur += timedelta(days=1)
        for m, d_ in re.findall(r"(\d+)月(\d+)日（星期.）補假", note):
            out.add(date(year, int(m), int(d_)))
    return frozenset(out)


def is_trading_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    try:
        return day not in _holidays(day.year)
    except Exception as exc:  # schedule unavailable: fall back to weekday rule
        logger.warning("無法取得證交所休市日曆（%s），僅以週間判斷", exc)
        return True


def refresh_data() -> None:
    """Pull the latest night session, US closes and TAIEX OHLC before forecasting."""
    from src import market_data, taifex, twse_market
    today = datetime.now(TPE).date()
    taifex.update(today - timedelta(days=10), today)
    taifex.update_vix(2)                                       # accumulate VIXTWN (only ~4 months are published)
    conn = market_data._connect()
    try:
        for name, sym in _US.items():
            market_data._fetch_and_store(conn, sym, "半導體", name, "5d")
        conn.commit()
    finally:
        conn.close()
    twse_market.update_ohlc(twse_market._months_back(1))
    twse_market.update_yahoo_ohlc("0050.TW", "1mo")
    twse_market.update_stock("0050", twse_market._months_back(2))   # fills days Yahoo is missing


def _dataset(conn) -> pd.DataFrame:
    tw = _q(conn, "select * from twse_ohlc")
    tw["gap"] = np.log(tw.open / tw.close.shift(1))
    tw["ret"] = np.log(tw.close / tw.close.shift(1))
    tw["intra"] = np.log(tw.close / tw.open)
    tdays = tw.index
    X = pd.DataFrame(index=tdays)
    for name, sym in _US.items():
        r = np.log(_q(conn, f"select trading_date, close from prices where symbol='{sym}'").close.dropna()).diff().dropna()
        pos = tdays.searchsorted(r.index, side="right")          # US session d -> next TW trading day
        ok = pos < len(tdays)
        X[name] = pd.Series(r.values[ok], index=tdays[pos[ok]]).groupby(level=0).sum().reindex(tdays)
    X["夜盤"] = _night_returns(conn).reindex(tdays)
    return X.join(tw[["gap", "ret", "intra"]])


def _night_returns(conn) -> pd.Series:
    """Night-session return vs the previous day session close, same contract only (skips roll days)."""
    tx = pd.read_sql("select * from taifex_tx", conn, parse_dates=["trading_date"])
    day = tx[tx.session == "day"].set_index("trading_date").sort_index()
    night = tx[tx.session == "night"].set_index("trading_date").sort_index()
    # day session T-1, keyed by the next trading date T (the next day-session date)
    prev = day[["contract", "close"]].iloc[:-1].copy()
    prev.index = day.index[1:]
    j = night.join(prev.rename(columns={"contract": "c_prev", "close": "close_prev"}), how="inner")
    j = j[j.contract == j.c_prev]
    return np.log(j.close / j.close_prev)


def _today_features(conn, day: date) -> dict:
    """Overnight moves known before today's open."""
    tw = _q(conn, "select trading_date, close from twse_ohlc")
    last_tw = tw.index[tw.index < pd.Timestamp(day)].max()
    feats = {}
    for name, sym in _US.items():
        s = _q(conn, f"select trading_date, close from prices where symbol='{sym}'").close.dropna()
        r = np.log(s).diff()
        window = r[(r.index >= last_tw) & (r.index < pd.Timestamp(day))]  # US sessions after the last TW close
        feats[name] = float(window.sum()) if len(window) else None
    # night session dated today vs the last day-session close of the same contract
    tx = pd.read_sql("select * from taifex_tx", conn, parse_dates=["trading_date"])
    night = tx[(tx.session == "night") & (tx.trading_date == pd.Timestamp(day))]
    prev_day = tx[(tx.session == "day") & (tx.trading_date < pd.Timestamp(day))].sort_values("trading_date").tail(1)
    if len(night) and len(prev_day) and night.contract.iloc[0] == prev_day.contract.iloc[0]:
        feats["夜盤"] = float(np.log(night.close.iloc[0] / prev_day.close.iloc[0]))
    else:
        feats["夜盤"] = None
    feats["last_tw"] = last_tw.date()
    return feats


def _tier(conf: float) -> str:
    return next(lab for lo, lab in TIERS if conf >= lo)


def _fit_and_score(D: pd.DataFrame, cols: list[str], target: str):
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    data = D.dropna(subset=cols + [target])
    clf = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    # walk-forward (yearly) out-of-sample hit rate per confidence tier
    hits: dict[str, list[bool]] = {}
    for y in range(data.index.min().year + 1, data.index.max().year + 1):
        tr, te = data[data.index.year < y], data[data.index.year == y]
        if len(tr) < 200 or te.empty:
            continue
        p = clf().fit(tr[cols], tr[target] > 0).predict_proba(te[cols])[:, 1]
        for pi, yi in zip(p, te[target] > 0):
            hits.setdefault(_tier(max(pi, 1 - pi)), []).append((pi >= .5) == yi)
    tier_hit = {k: (float(np.mean(v)), len(v)) for k, v in hits.items()}
    model = clf().fit(data[cols], data[target] > 0)
    size = LinearRegression().fit(data[cols], data[target])
    return model, size, tier_hit


_RISK_CUTS = (.33, .75, .95)
_RISK_TIERS = ("低", "中", "高", "極高")


def risk_forecast(conn, today_close: float) -> dict | None:
    """Short-term swing risk for today: the expected intraday range ln(high/low) from the 1/5/22-day average
    ranges (linear model on log range). Tier = percentile of the prediction among historical predictions
    (low <33%, mid 33-75%, high 75-95%, extreme >95%). The realised median range and the share of days
    above 2% per tier come from a yearly walk-forward backtest, so they are out-of-sample."""
    from sklearn.linear_model import LinearRegression
    tw = _q(conn, "select * from twse_ohlc")
    hl = np.log(tw.high / tw.low)
    X = pd.DataFrame({"hl1": hl.shift(1), "hl5": hl.rolling(5).mean().shift(1), "hl22": hl.rolling(22).mean().shift(1)})
    X["y"] = hl
    feats = ["hl1", "hl5", "hl22"]
    hist = X.dropna()
    if len(hist) < 500:
        return None
    rows = []
    for yr in range(hist.index.min().year + 2, hist.index.max().year + 1):
        tr, te = hist[hist.index.year < yr], hist[hist.index.year == yr]
        m = LinearRegression().fit(tr[feats], np.log(tr.y))
        cut = np.quantile(np.exp(m.predict(tr[feats])), _RISK_CUTS)
        pt = np.exp(m.predict(te[feats]))
        rows.append(pd.DataFrame({"tier": np.searchsorted(cut, pt), "y": te.y}, index=te.index))
    T = pd.concat(rows)
    by_tier = {}
    for k, name in enumerate(_RISK_TIERS):
        g = T[T.tier == k]
        if len(g):
            by_tier[name] = {"median": float(g.y.median()), "over2": float((g.y > .02).mean()), "n": int(len(g))}
    m = LinearRegression().fit(hist[feats], np.log(hist.y))
    resid_var = float((np.log(hist.y) - m.predict(hist[feats])).var())
    cut = np.quantile(np.exp(m.predict(hist[feats])), _RISK_CUTS)
    last = X.iloc[[-1]].copy()                       # latest row has yesterday's range features (today's y is NaN)
    last["hl1"] = hl.iloc[-1]
    last["hl5"] = hl.iloc[-5:].mean()
    last["hl22"] = hl.iloc[-22:].mean()
    pred = float(np.exp(m.predict(last[feats])[0]))
    tier = int(np.searchsorted(cut, pred))
    pct = float((np.exp(m.predict(hist[feats])) < pred).mean())
    return {"range": pred, "points": pred * today_close, "tier": _RISK_TIERS[tier], "percentile": pct,
            "tier_stats": by_tier.get(_RISK_TIERS[tier]), "resid_var": resid_var}


def forecast(day: date | None = None, refresh: bool = True) -> dict | None:
    """Forecast for today's TAIEX session, or None on non-trading days."""
    day = day or datetime.now(TPE).date()
    if not is_trading_day(day):
        logger.info("今日（%s）非台股交易日，不產生開盤預測", day)
        return None
    if refresh:
        try:
            refresh_data()
        except Exception as exc:
            logger.warning("預測資料更新失敗，使用資料庫現有資料: %s", exc)
    conn = sqlite3.connect(DB_PATH)
    try:
        D = _dataset(conn)
        feats = _today_features(conn, day)
    finally:
        conn.close()
    # Use whichever overnight inputs are available (a US close can lag on Yahoo for hours;
    # the night session alone already reflects the US close and is the strongest input).
    cols = [c for c in FULL if feats[c] is not None]
    missing = [c for c in FULL if feats[c] is None]
    if not cols:
        logger.warning("夜盤與前一晚美股資料皆缺漏，不產生開盤預測")
        return None
    if missing:
        logger.warning("開盤預測缺少 %s，改用 %s", "、".join(missing), "+".join(cols))
    x = pd.DataFrame([{c: feats[c] for c in cols}])
    out = {"date": day, "inputs": {k: feats[k] for k in FULL}, "model": cols, "items": {}}
    for target, label in TARGETS.items():
        model, size, tier_hit = _fit_and_score(D, cols, target)
        p_up = float(model.predict_proba(x[cols])[0, 1])
        conf = max(p_up, 1 - p_up)
        tier = _tier(conf)
        if target == "intra" and tier == "極高":
            tier = "高"  # too few historical cases above 90% to trust that tier
        out["items"][target] = {
            "label": label, "p_up": p_up, "up": p_up >= .5, "confidence": conf, "tier": tier,
            "tier_hit": tier_hit.get(tier, (None, 0)), "size": float(size.predict(x[cols])[0]),
        }
    logger.info("開盤預測：模型 %s｜%s", "+".join(cols),
                "，".join(f"{v['label']}{'漲' if v['up'] else '跌'} {v['confidence']:.0%}({v['tier']})"
                         for v in out["items"].values()))
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            last_close = float(_q(conn, "select trading_date, close from twse_ohlc").close.iloc[-1])
            out["risk"] = risk_forecast(conn, last_close)
        finally:
            conn.close()
    except Exception as exc:                         # the risk line is optional; never block the forecast
        logger.warning("震盪風險計算失敗: %s", exc)
        out["risk"] = None
    out["paths"], out["charts"] = {}, {}
    if not _five_day_enabled():
        return out
    conn = sqlite3.connect(DB_PATH)
    try:
        closes = {"加權指數": _q(conn, "select trading_date, close from twse_ohlc").close, "0050": _close_0050(conn)}
    finally:
        conn.close()
    dates = _next_trading_days(day, 5)
    for name, close in closes.items():
        close = close[close.index < pd.Timestamp(day)]
        if close.index.max().date() != feats["last_tw"]:
            logger.warning("%s 最新收盤（%s）不是上一個交易日（%s），略過 5 日預測",
                           name, close.index.max().date(), feats["last_tw"])
            continue
        path = five_day(close, D, feats, cols)
        path["dates"] = dates
        path["trend"] = trend_status(close)
        path["conflict"] = path["trend"]["state"] == "降溫整理" and path["d1_p_up"] >= .6
        out["paths"][name] = path
        out["charts"][_CID[name]] = render_chart(name, path)
    return out


_CID = {"加權指數": "fc_taiex", "0050": "fc_0050"}


def _five_day_enabled() -> bool:
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))
    return cfg.get("forecast", {}).get("five_day_in_email", False)


def _close_0050(conn) -> pd.Series:
    """Yahoo's split/dividend-adjusted history, with recent days Yahoo is missing filled
    from the official TWSE close (raw; identical to adjusted after the last ex-dividend)."""
    y = _q(conn, "select trading_date, close, volume from yahoo_ohlc where symbol='0050.TW'")
    y = y.close[y.volume > 0]
    t = _q(conn, "select trading_date, close from twse_stock where symbol='0050'").close
    recent = t[t.index > y.index.max() - pd.Timedelta(days=45)]
    return pd.concat([y, recent[~recent.index.isin(y.index)]]).sort_index()


def _next_trading_days(day: date, n: int) -> list[date]:
    out, d = [], day
    while len(out) < n:
        if is_trading_day(d):
            out.append(d)
        d += timedelta(days=1)
    return out


# 80% ranges, learned jointly by minimising the interval score (band width + 10 x distance by which the
# close falls outside), i.e. "as narrow as possible while still hugging the realised closes".
#  - D1: the overnight model's error, scaled with the volatility regime: c1 * s1 * (vol20 / vol250) ** kappa
#  - D2..D5: each step's variance is a normalised mix of six volatility windows (5..250 days); the weights
#    follow a decay kernel whose centre moves to longer windows as the step grows. Weights are positive and
#    sum to 1, so the range only widens with the horizon and its bounds never cross.
_WINDOWS = np.array([5, 10, 20, 60, 120, 250])
_Z80 = 1.2815515655446004  # norm.ppf(0.9)


def _kernel_weights(L0: float, theta: float, steps: int) -> np.ndarray:
    k = np.arange(1, steps + 1)
    w = np.exp(-theta * np.abs(np.log(_WINDOWS)[None, :] - np.log(L0 * k)[:, None]))
    return w / w.sum(1, keepdims=True)                        # (steps x windows)


def _range_sd(s1d, V2, L0, theta, c, steps: int):
    """Cumulative sd for D2..D(1+steps) relative to the D1-predicted level; V2 = (N x windows) variances."""
    return c * np.sqrt(np.atleast_1d(s1d)[:, None] ** 2 + np.cumsum(np.atleast_2d(V2) @ _kernel_weights(L0, theta, steps).T, 1))


def _iscore(Y, sd):
    lo, hi = -_Z80 * sd, _Z80 * sd
    return ((hi - lo) + 10 * (np.clip(lo - Y, 0, None) + np.clip(Y - hi, 0, None))).mean()


def _vol_windows(r: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({L: (np.sqrt((r ** 2).rolling(L).mean()) if L == 5 else r.rolling(L).std()) for L in _WINDOWS})


def _fit_ranges(lc: pd.Series, d1_hat: pd.Series, V: pd.DataFrame, s1: float, steps: int):
    """Learn (c1, kappa) for D1 and (L0, theta, c) for D2.. on the most recent ~2000 days."""
    dev = np.column_stack([lc.shift(-h).values - lc.values for h in range(1, steps + 2)]) - d1_hat.shift(-1).values[:, None]
    ok = ~np.isnan(dev).any(1) & ~V.isna().any(axis=1).values
    dev, V2 = dev[ok][-2000:], (V.values[ok][-2000:]) ** 2
    reg = np.sqrt(V2[:, 2] / V2[:, 5])                          # vol20 / vol250
    c1, kap = min(((c, k) for c in np.round(np.arange(.7, 1.31, .05), 2) for k in (0, .25, .5, .75, 1)),
                  key=lambda t: _iscore(dev[:, :1], (t[0] * s1 * reg ** t[1])[:, None]))
    s1d = c1 * s1 * reg ** kap
    L0, theta, c = min(((L, t, c) for L in (3, 5, 10, 20, 40) for t in (.5, 1, 2, 4) for c in np.round(np.arange(.75, 1.26, .05), 2)),
                       key=lambda t: _iscore(dev[:, 1:], _range_sd(s1d, V2, *t, steps)))
    return c1, kap, L0, theta, c


def five_day(close: pd.Series, D: pd.DataFrame, feats: dict, cols: list[str], horizon: int = 5) -> dict:
    """D1: predicted close, direction, confidence and 80% range. D2..D5: no value or direction (nothing
    predicts them) - only an 80% range centred on the D1 level, from the learned multi-window decay."""
    from scipy.stats import norm
    from sklearn.linear_model import LinearRegression
    lc = np.log(close)
    r = lc.diff()
    data = D[cols].reindex(close.index).assign(ret=r).dropna()
    m1 = LinearRegression().fit(data[cols], data.ret)
    d1 = float(m1.predict(pd.DataFrame([{c: feats[c] for c in cols}]))[0])
    # Out-of-sample day-1 predictions (each year predicted by a model fit on earlier years only):
    # in-sample residuals understate the real error and made the learned ranges too narrow.
    d1_hat = pd.Series(np.nan, index=close.index)
    years = sorted(set(data.index.year))
    for y in years[1:]:
        tr, te = data[data.index.year < y], data[data.index.year == y]
        if len(tr) >= 200:
            d1_hat[te.index] = LinearRegression().fit(tr[cols], tr.ret).predict(te[cols])
    oos = (data.ret - d1_hat[data.index]).dropna()
    if len(oos) < 250:                                              # too little history: fall back to in-sample
        d1_hat[data.index] = m1.predict(data[cols])
        oos = data.ret - d1_hat[data.index]
    s1 = float(oos.iloc[-2000:].std())                              # day-1 forecast error (out of sample)
    V = _vol_windows(r)
    c1, kap, L0, theta, c = _fit_ranges(lc, d1_hat, V, s1, horizon - 1)
    v_now = V.iloc[-1].values
    s1d = c1 * s1 * (v_now[2] / v_now[5]) ** kap
    c0 = float(close.iloc[-1])
    p1 = c0 * np.exp(d1)
    p_up = float(norm.cdf(d1 / s1d))
    conf = max(p_up, 1 - p_up)
    sd = _range_sd(s1d, v_now ** 2, L0, theta, c, horizon - 1)[0]
    return {"last_close": c0, "last_date": close.index[-1].date(), "history": close.iloc[-20:],
            "d1_pred": p1, "d1_ret": d1, "d1_low": p1 * np.exp(-_Z80 * s1d), "d1_high": p1 * np.exp(_Z80 * s1d),
            "d1_p_up": p_up, "d1_confidence": conf, "d1_tier": _tier(conf),
            "low": (p1 * np.exp(-_Z80 * sd)).tolist(), "high": (p1 * np.exp(_Z80 * sd)).tolist(),
            "params": {"c1": c1, "kappa": kap, "L0": L0, "theta": theta, "c": c},
            "vol_ratio": float(v_now[2] / V[20].dropna().median()),         # current 20-day vol vs its history
            "weights": _kernel_weights(L0, theta, horizon - 1)}


def trend_status(close: pd.Series) -> dict:
    """Long-term state from the deviation from MA60 (z vs its own past-year range)."""
    z = np.log(close / close.rolling(60).mean())
    z = (z / z.rolling(250).std()).dropna()
    last = float(z.iloc[-1])
    recent = z.iloc[-11:]
    cooled = any(recent.iloc[i - 1] > 2 >= recent.iloc[i] for i in range(1, len(recent)))
    state = "過熱" if last > 2 else "降溫整理" if cooled else "正常"
    return {"z": last, "state": state}


_UP = {"極高": "#99000d", "高": "#e34a33", "中": "#fc8d59"}
_DN = {"極高": "#00441b", "高": "#238b45", "中": "#74c476"}


def tier_color(p_up: float, tier: str) -> str:
    if tier == "低":
        return "#9e9e9e"
    return (_UP if p_up >= .5 else _DN)[tier]


# One distinct colour per forecast date (none red/green: red is the range shading, green/red the direction).
DAY_COLORS = ["#2ca02c", "#ff7f0e", "#9467bd", "#1f77b4", "#8c564b"]    # D1 is always green


def _spread(values: list[float], min_gap: float) -> list[float]:
    """Push label positions apart (keeping order) so right-axis labels never overlap."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    pos = [values[i] for i in order]
    for k in range(1, len(pos)):
        pos[k] = max(pos[k], pos[k - 1] + min_gap)
    for k in range(len(pos) - 2, -1, -1):                       # pull back down if pushed past the top
        pos[k] = min(pos[k], pos[k + 1] - min_gap)
    out = [0.0] * len(values)
    for rank, i in enumerate(order):
        out[i] = pos[rank]
    return out


def render_chart(name: str, path: dict) -> bytes:
    """Recent closes plus D1 (predicted close with its range) and the D2..D5 80% range as red layers
    that darken with uncertainty. Each forecast date has its own colour: a vertical guide line, a
    coloured date on the x axis, and its price levels drawn as dashed lines running to the right axis,
    where every value is printed (no text inside the plot, so nothing overlaps)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Microsoft JhengHei", "sans-serif"]
    hist = path["history"]
    c0, p1 = path["last_close"], path["d1_pred"]
    n = len(hist)
    xs = list(range(n - 1, n + len(path["dates"])))                # trading-day axis: no weekend gaps
    lo = np.r_[c0, path["d1_low"], path["low"]]
    hi = np.r_[c0, path["d1_high"], path["high"]]
    fmt = (lambda v: f"{v:,.0f}") if c0 >= 1000 else (lambda v: f"{v:,.2f}")
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    fig.subplots_adjust(left=.08, right=.83, top=.9, bottom=.2)
    ax.plot(range(n), hist.values, c="#222", lw=1.8, zorder=3)
    # D2..D5: range shading starts at D2 (D1 is informed by the night session, D2 onwards is not)
    for h in range(3, len(xs)):
        ax.fill_between(xs[h - 1:h + 1], lo[h - 1:h + 1], hi[h - 1:h + 1], color="#d62728", alpha=0.08 + 0.07 * h, lw=0, zorder=1)
    ax.vlines(xs[2], lo[2], hi[2], color="#d62728", alpha=.35, lw=2, zorder=1)
    ax.plot(xs[:2], [c0, p1], color=DAY_COLORS[0], lw=3, zorder=4)
    ax.axhline(c0, color="#999", ls=":", lw=.8, zorder=0)
    levels = []                                                      # (x index, price, colour, kind)
    levels.append((xs[1], p1, DAY_COLORS[0], "pred"))
    for h in range(1, len(xs)):
        col = DAY_COLORS[h - 1]
        levels += [(xs[h], hi[h], col, "bound"), (xs[h], lo[h], col, "bound")]
    xmax = xs[-1] + 0.7
    ax.set_xlim(-0.5, xmax)
    ymin, ymax = min(lo[1:].min(), hist.values.min()), max(hi[1:].max(), hist.values.max())
    pad = (ymax - ymin) * .06
    ax.set_ylim(ymin - pad, ymax + pad)
    for h in range(1, len(xs)):                                      # vertical guide per forecast date
        ax.axvline(xs[h], color=DAY_COLORS[h - 1], lw=1, alpha=.45, zorder=0)
    ax.errorbar([xs[1]], [p1], yerr=[[p1 - lo[1]], [hi[1] - p1]], fmt="o", color=DAY_COLORS[0], ms=6, capsize=4, lw=2, zorder=5)
    for x, y, col, kind in levels:
        if kind == "bound" and x == xs[1]:
            ax.plot([x, xmax], [y, y], color=col, ls="--", lw=.9, alpha=.8, zorder=2)
        elif kind == "bound":
            ax.scatter([x], [y], color=col, s=22, zorder=5)
            ax.plot([x, xmax], [y, y], color=col, ls="--", lw=.9, alpha=.8, zorder=2)
        else:
            ax.plot([x, xmax], [y, y], color=col, ls="--", lw=1.2, zorder=2)
    # right-axis labels, spread out so they never overlap; short leaders join each line to its label
    ys = [l[1] for l in levels]
    gap = (ax.get_ylim()[1] - ax.get_ylim()[0]) * .033
    adj = _spread(ys, gap)
    for (x, y, col, kind), ya in zip(levels, adj):
        ax.annotate(fmt(y) + ("  預估" if kind == "pred" else ""), xy=(xmax, y), xytext=(xmax + 0.75, ya),
                    textcoords="data", color=col, fontsize=8, fontweight="bold" if kind == "pred" else "normal",
                    va="center", annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=col, lw=.7, shrinkA=0, shrinkB=0, clip_on=False))
    labels = [d.strftime("%m/%d") for d in hist.index]
    ticks = list(range(0, n - 1, 5))
    ax.set_xticks(ticks + xs[:1] + xs[1:], [labels[t] for t in ticks] + [f"{path['last_date']:%m/%d}"]
                  + [f"{d:%m/%d}" for d in path["dates"]])
    for lab, col in zip(ax.get_xticklabels()[-len(path["dates"]):], DAY_COLORS):
        lab.set_color(col)
        lab.set_fontweight("bold")
    ax.tick_params(axis="x", labelsize=8.5)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    ax.tick_params(axis="y", labelsize=8)
    ax.set_title(f"{name}：近 20 日 ＋ D1 預估 ＋ D2~D5 80% 可能範圍（紅色越深越不確定）", fontsize=10)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return buf.getvalue()
