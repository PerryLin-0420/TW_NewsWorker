"""
Corpus-driven article selection — replaces the old static keyword hard-gate.

Pipeline:
  1. Extract normalized terms per title (zh via jieba, ja via fugashi + a
     domain merge-list, everything else via latin word tokens).
  2. Compare today's term frequency against a rolling window of recent daily
     snapshots to find "burst" terms — topics unusually prevalent today.
  3. Cluster articles across ALL regions that share burst terms into events
     (the same story covered by CNBC, FT, and Yahoo財經 becomes one event).
  4. Score each event by burst strength and source diversity, with an
     additive bonus when it matches a curated finance keyword (config.json
     keywords are reused as a *signal*, not a gate).
  5. Per display region, pick the top-N distinct events and cap how many
     same-event articles surface as separate footnotes.
  6. Persist today's own term frequencies as a dated snapshot (data/term_daily/
     YYYY-MM-DD.json) — never blended into one ever-growing pool. Each day's
     weight belongs to that day; a rolling window of recent snapshots is
     recomputed fresh on every run for the burst comparison. This is what
     lets a future weekly report build week-over-week weight changes and
     lag-correlate them against market data — the daily series has to exist
     on disk before that comparison is possible.
"""
import json
import logging
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import jieba

from src import relevance

logger = logging.getLogger("selector")

ROOT = Path(__file__).parent.parent
DAILY_DIR = ROOT / "data" / "term_daily"

jieba.setLogLevel(60)  # silence jieba's own INFO logging

_EN_STOP = frozenset("""
a an and are as at be been but by for from has have had he his her in into is it its
of on or she that the their there these they this to was were will with what when where which who why
how all any can could do does did not no nor being about after again against below down during
each few more most other over own same so too just now get got make made take takes taking go goes going
come comes back out off up here when whom whose amid ahead across around along among new news report
reports year years day days week month first last two three top us u also may might must shall should
would you your we our i me my than while because before between both if once only while
says said tells told according
""".split())

_ja_tagger = None


def _get_ja_tagger():
    global _ja_tagger
    if _ja_tagger is None:
        import fugashi
        _ja_tagger = fugashi.Tagger()
    return _ja_tagger


def _tokenize_ja(text: str, merge_terms: list[str]) -> list[str]:
    """fugashi/unidic-lite over-splits domain compounds (半導体 -> 半/導体);
    glue back known terms across adjacent token boundaries."""
    tokens = [w.surface for w in _get_ja_tagger()(text)]
    out, i = [], 0
    while i < len(tokens):
        matched = None
        for span in (3, 2):
            if i + span <= len(tokens):
                cand = "".join(tokens[i:i + span])
                if cand in merge_terms:
                    matched, matched_span = cand, span
                    break
        if matched:
            out.append(matched)
            i += matched_span
        else:
            out.append(tokens[i])
            i += 1
    return out


def configure_dictionaries(zh_terms: list[str], extra_names: list[str]) -> None:
    """Reuse curated vocabulary as a jieba segmentation dictionary."""
    for term in zh_terms:
        jieba.add_word(term)
    for name in extra_names:
        jieba.add_word(name)


def extract_terms(title: str, lang: str, ja_terms: list[str]) -> set[str]:
    """Language-dispatched term extraction. Latin tokens are pulled from
    every title regardless of lang (tickers/proper nouns inside zh/ja text)."""
    terms = set()
    for w in re.findall(r"[A-Za-z][A-Za-z&.\-]{2,}", title):
        w = w.strip(".-").lower()
        if len(w) >= 3 and w not in _EN_STOP:
            terms.add(w)

    has_kana = re.search(r"[぀-ヿ]", title)
    has_han = re.search(r"[一-鿿]", title)
    if lang == "ja" or has_kana:
        for w in _tokenize_ja(title, ja_terms):
            w = w.strip()
            if len(w) >= 2 and re.search(r"[぀-ヿ一-鿿]", w):
                terms.add(w)
    elif lang == "zh" or has_han:
        for w in jieba.cut(title):
            w = w.strip()
            if len(w) >= 2 and re.fullmatch(r"[一-鿿]+", w):
                terms.add(w)
    return terms


def _daily_snapshot_path(date_str: str) -> Path:
    return DAILY_DIR / f"{date_str}.json"


def save_daily_snapshot(date_str: str, total_docs: int, df: Counter) -> None:
    """每日獨立快照，覆寫而非累加——同一天重跑會取代舊值，不會重複計入。"""
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    _daily_snapshot_path(date_str).write_text(
        json.dumps({"date": date_str, "total_docs": total_docs, "df": dict(df)},
                  ensure_ascii=False),
        encoding="utf-8",
    )


def load_daily_snapshot(date_str: str) -> tuple[int, Counter]:
    path = _daily_snapshot_path(date_str)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("total_docs", 0), Counter(data.get("df", {}))
        except Exception as exc:
            logger.warning("%s 讀取失敗: %s", path.name, exc)
    return 0, Counter()


def load_rolling_baseline(before_date: str, window_days: int,
                          min_docs_floor: int = 1000) -> tuple[int, Counter]:
    """
    彙總 before_date 之前最近 window_days 天的每日快照，作為「近期常態」比較基準。
    每次執行都重算（不是累加的單一檔案），符合「每天重新權重」的設計：
    比較基準永遠是相對於近期一段窗口，而非整段歷史的無限平均。

    若近期窗口太稀疏（例如排程中斷造成的斷檔），burst 會退化成「今天出現次數
    夠多就算異常」，通用詞反而比真正的事件詞更容易誤判為異常。這種情況下暫時
    回頭納入所有更早的歷史快照當備援，直到近期窗口自然累積足夠資料為止——一旦
    window_days 內的資料量夠了，備援就不會被觸發，不影響「近期窗口」的設計本意。
    """
    from datetime import date, timedelta

    anchor = date.fromisoformat(before_date)
    total_n = 0
    total_df: Counter = Counter()
    window_dates: set[str] = set()
    for delta in range(1, window_days + 1):
        d = (anchor - timedelta(days=delta)).isoformat()
        window_dates.add(d)
        n, df = load_daily_snapshot(d)
        total_n += n
        total_df.update(df)

    if total_n < min_docs_floor and DAILY_DIR.is_dir():
        older_dates = sorted(
            p.stem for p in DAILY_DIR.glob("*.json")
            if p.stem < before_date and p.stem not in window_dates
        )
        for d in older_dates:
            n, df = load_daily_snapshot(d)
            total_n += n
            total_df.update(df)

    return total_n, total_df


_MIN_BASELINE_DOCS = 100  # avoids a degenerate "100% historical prevalence" prior on cold start


def _burst_score(today_count: int, today_n: int, hist_count: int, hist_n: int) -> float:
    """log-ratio of today's term prevalence vs the historical baseline.

    With an empty/tiny baseline, hist_n+0.5 in the denominator would make
    p_hist collapse toward 1.0 for every term — i.e. "this term already
    covered 100% of history" — which suppresses burst scores for everything
    on a cold start. Flooring the denominator keeps p_hist low until enough
    real history accumulates.
    """
    p_today = today_count / today_n
    p_hist = (hist_count + 0.5) / (max(hist_n, _MIN_BASELINE_DOCS) + 0.5)
    return math.log(p_today / p_hist)


def _is_trustworthy_term(term: str) -> bool:
    """Guards clustering/scoring against jieba's segmentation fallback — when
    it can't confidently split an unfamiliar zh phrase, it emits meaningless
    2-3 char fragments (e.g. "雙萬金", "互見"). Requiring dictionary
    membership (jieba's own dict, or a curated finance term already added
    via add_word — configure_dictionaries() must run first) filters those
    out while keeping recognized words and proper nouns like 台積電/半導體.
    Latin and kana terms are left alone — no evidence of the same failure
    mode there."""
    if re.fullmatch(r"[一-鿿]+", term):
        return jieba.dt.FREQ.get(term, 0) > 0
    return True


def _significant_terms(terms: set[str], burst: dict[str, float], min_burst: float) -> set[str]:
    """The subset of a title's terms actually used for clustering and
    scoring: bursty (well above the noise floor, not just nominally >0 —
    common reporting-boilerplate words tip barely positive on any given day
    by chance, which is enough to falsely co-cluster unrelated stories) AND
    trustworthy. (The full term set still feeds the daily snapshot —
    filtering only affects clustering/scoring decisions.)"""
    return {t for t in terms if burst.get(t, -999) >= min_burst and _is_trustworthy_term(t)}


def _match_signature(term_counts: Counter, member_count: int) -> set[str]:
    """
    Terms usable to match a NEW candidate against this event. A singleton
    event offers its sole member's full term set (nothing to corroborate
    against yet). Once a 2nd member has joined, matching narrows to terms
    that RECUR across at least 2 already-merged members — a term only one
    member happened to mention doesn't stay eligible as a bridge to a 3rd,
    unrelated article. This is what stops a single article that name-drops
    two unrelated topics' keywords from chaining those topics together.
    """
    if member_count <= 1:
        return set(term_counts)
    return {t for t, c in term_counts.items() if c >= 2}


def _cluster(article_sigs: list[set[str]], min_shared: int,
             jaccard_threshold: float, max_event_size: int) -> list[list[int]]:
    """
    Incremental centroid clustering, not union-find — union-find's
    transitivity chains unrelated articles together (A-B share a term, B-C
    share a different term, so A and C merge despite having nothing in
    common; this is how a single event ended up absorbing 17 unrelated
    articles across 5 regions in practice). Matching each new article
    against an event's signature of RECURRING terms (see _match_signature),
    rather than against any one prior member's full term set, keeps a
    one-off mention from becoming a bridge to something unrelated. The hard
    size cap is the backstop for whatever chaining still slips through.
    """
    events: list[dict] = []  # each: {"members": [...], "term_counts": Counter()}
    for i, sig in enumerate(article_sigs):
        if not sig:
            events.append({"members": [i], "term_counts": Counter()})
            continue

        best_eid, best_overlap = None, 0
        for eid, ev in enumerate(events):
            if not ev["term_counts"] or len(ev["members"]) >= max_event_size:
                continue
            signature = _match_signature(ev["term_counts"], len(ev["members"]))
            shared = sig & signature
            if not shared:
                continue
            union_size = len(sig | signature)
            jac = len(shared) / union_size if union_size else 0
            if (len(shared) >= min_shared or jac >= jaccard_threshold) and len(shared) > best_overlap:
                best_eid, best_overlap = eid, len(shared)

        if best_eid is not None:
            for t in sig:
                events[best_eid]["term_counts"][t] += 1
            events[best_eid]["members"].append(i)
        else:
            events.append({"members": [i], "term_counts": Counter(sig)})

    return [ev["members"] for ev in events]


def _keyword_bonus(title: str, lang: str, keywords: dict) -> bool:
    """Soft relevance signal — curated keywords nudge score, never gate."""
    tl = title.lower()
    words = set(keywords.get(lang, [])) | set(keywords.get("en", []))
    for kw in words:
        k = kw.lower()
        if re.fullmatch(r"[a-z0-9&\s]+", k):
            if re.search(rf"\b{re.escape(k)}\b", tl):
                return True
        elif k in tl:  # zh/ja: substring is an appropriate soft signal
            return True
    return False


def select(raw_articles: list[dict], keywords_cfg: dict, sel_cfg: dict, run_date: str) -> dict:
    """
    Returns {"selected": sorted indices to fetch content for,
              "events": serializable event records with score/terms/members}.
    The "events" record is kept even for events nobody selected from, so a
    future weekly report can compare how each event's weight moved over
    time against what actually happened in the market — that comparison is
    only possible if today's scores are on disk, not just today's picks.

    run_date: "YYYY-MM-DD" the caller's run belongs to. Burst is computed
    against a rolling window of recent daily snapshots (freshly summed every
    call, never an ever-growing accumulator), and today's own term
    frequencies are persisted as their own dated snapshot at the end.
    """
    zh_terms = keywords_cfg.get("zh", [])
    ja_terms = keywords_cfg.get("ja", [])
    configure_dictionaries(zh_terms, [])

    n = len(raw_articles)
    if n == 0:
        return {"selected": [], "events": [], "dropped": []}

    article_terms = [
        extract_terms(a["title"], a.get("lang", "en"), ja_terms) for a in raw_articles
    ]

    window_days = sel_cfg.get("baseline_window_days", 30)
    min_docs_floor = sel_cfg.get("min_baseline_docs_floor", 1000)
    hist_n, hist_df = load_rolling_baseline(run_date, window_days, min_docs_floor)
    today_df = Counter()
    for ts in article_terms:
        for t in ts:
            today_df[t] += 1

    burst = {t: _burst_score(c, n, hist_df.get(t, 0), hist_n) for t, c in today_df.items()}
    min_burst = sel_cfg.get("min_burst_score", 1.0)
    article_sigs = [_significant_terms(ts, burst, min_burst) for ts in article_terms]

    # Finance-relevance gate: off-topic articles are removed from clustering and
    # selection (they still fed today's snapshot/burst above). A curated keyword
    # hit lowers the bar; the classifier decides the rest.
    rel_cfg = sel_cfg.get("relevance", {})
    probs = None
    tw_axis = None
    if rel_cfg.get("enabled", True):
        try:
            scored = relevance.score_articles(
                [(a["title"], a.get("_summary", "")) for a in raw_articles])
            if scored is not None:
                probs, tw_axis = scored["econ"], scored["tw_axis"]
        except Exception as exc:  # never let the gate break the pipeline
            logger.warning("相關性模型失敗，略過過濾: %s", exc)
    kw_hit = [_keyword_bonus(a["title"], a.get("lang", "en"), keywords_cfg) for a in raw_articles]
    dropped: set[int] = set()
    if probs is not None:
        drop_below = rel_cfg.get("drop_below", 0.40)
        kw_drop_below = rel_cfg.get("keyword_drop_below", 0.30)  # generic keywords (AI, war) can mislead
        dropped = {i for i, p in enumerate(probs)
                   if p < (kw_drop_below if kw_hit[i] else drop_below)}
        for i in dropped:
            article_sigs[i] = set()

    groups = _cluster(
        article_sigs,
        sel_cfg.get("cluster_min_shared_terms", 2),
        sel_cfg.get("cluster_jaccard_threshold", 0.34),
        sel_cfg.get("max_event_size", 8),
    )

    events = []
    for members in groups:
        sig = set()
        for i in members:
            sig |= article_sigs[i]
        sources = {raw_articles[i]["source"] for i in members}
        base_score = sum(burst.get(t, 0) for t in sig)
        score = base_score * (1 + 0.8 * (len(sources) - 1))
        if any(kw_hit[i] for i in members):
            score += sel_cfg.get("keyword_bonus", 2.0)
        elif probs is not None and max(probs[i] for i in members) < rel_cfg.get("penalty_below", 0.6):
            # borderline relevance (e.g. local news with a possible economic angle)
            score *= rel_cfg.get("penalty_factor", 0.5)
        # 一個事件只佔用它的「主要地區」（成員數最多的地區）名額，
        # 避免跨地區事件在每個觸及的地區都各佔一個 top-N 名額。
        region_counts = Counter(raw_articles[i]["region"] for i in members)
        primary_region = min(
            region_counts.most_common(),
            key=lambda kv: (-kv[1], kv[0]),
        )[0]
        events.append({"members": members, "score": score, "primary_region": primary_region})

    article_event = {}
    for eid, ev in enumerate(events):
        for i in ev["members"]:
            article_event[i] = eid

    top_n = sel_cfg.get("top_n_per_region", 6)
    max_per_event = sel_cfg.get("max_articles_per_event", 2)

    by_region: dict[str, list[int]] = defaultdict(list)
    for i, a in enumerate(raw_articles):
        by_region[a.get("region", "其他")].append(i)

    selected: set[int] = set()
    for region, idxs in by_region.items():
        region_events: dict[int, list[int]] = defaultdict(list)
        for i in idxs:
            if i in dropped:
                continue
            eid = article_event[i]
            if events[eid]["primary_region"] != region:
                continue  # 這個事件的名額歸屬別的地區，不在此地區重複佔位
            region_events[eid].append(i)

        ranked_eids = sorted(region_events, key=lambda eid: -events[eid]["score"])
        for eid in ranked_eids[:top_n]:
            members = sorted(region_events[eid], key=lambda i: -len(article_terms[i]))
            seen_src, seen_titles = set(), set()
            for i in members:
                src = raw_articles[i]["source"]
                title_key = raw_articles[i]["title"].strip().lower()
                if src in seen_src or title_key in seen_titles:
                    # 同一標題（多為通稿被多家轉載）不重複列為兩則引用
                    continue
                seen_src.add(src)
                seen_titles.add(title_key)
                selected.add(i)
                if len(seen_src) >= max_per_event:
                    break

    save_daily_snapshot(run_date, n, today_df)

    event_records = []
    for eid, ev in enumerate(events):
        members = ev["members"]
        event_records.append({
            "event_id": eid,
            "score": round(ev["score"], 3),
            "primary_region": ev["primary_region"],
            "regions": sorted({raw_articles[i]["region"] for i in members}),
            "sources": sorted({raw_articles[i]["source"] for i in members}),
            "selected": any(i in selected for i in members),
            "terms": sorted(
                {t for i in members for t in article_sigs[i]},
                key=lambda t: -burst.get(t, 0),
            )[:10],
            "articles": [
                {"title": raw_articles[i]["title"], "source": raw_articles[i]["source"],
                 "region": raw_articles[i]["region"], "url": raw_articles[i]["url"]}
                for i in members
            ],
        })
    event_records.sort(key=lambda e: -e["score"])

    dropped_records = [
        {"title": raw_articles[i]["title"], "source": raw_articles[i]["source"],
         "region": raw_articles[i]["region"], "finance_prob": round(probs[i], 3)}
        for i in sorted(dropped, key=lambda i: probs[i])
    ]
    logger.info(
        "selector: %d 原始 -> 相關性過濾 %d 篇 -> %d 事件 -> %d 篇入選，跨 %d 地區",
        n, len(dropped), len(events), len(selected), len(by_region),
    )
    # Economic-relevance index handed to the summarizer: score plus 高/中 tier
    # (高 = economic with concrete figures in title/feed summary, 中 = economic without).
    econ: dict[int, dict] = {}
    if probs is not None:
        high_min = rel_cfg.get("high_min", 0.5)
        for i in selected:
            floor = kw_drop_below if kw_hit[i] else drop_below
            text = f"{raw_articles[i]['title']} {raw_articles[i].get('_summary', '')}"
            econ[i] = {"score": round(probs[i], 3),
                       "tier": relevance.econ_tier(probs[i], text, floor, high_min)}
            if tw_axis:
                econ[i]["tw_axis"] = tw_axis[i]  # mapped to 台灣利多/利空 later, for Taiwan-related articles only
    return {"selected": sorted(selected), "events": event_records, "dropped": dropped_records,
            "econ": econ}
