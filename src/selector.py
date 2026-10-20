"""
Article selection: the economic-relevance gate decides which articles go on to
content fetching and the summarizer's review.

  1. Score every title (plus feed summary) with the relevance classifier; a
     curated finance keyword hit lowers the bar (config.json keywords are a
     signal, not a gate).
  2. Keep every article above the bar — no per-region quota. Verbatim repeats
     of a title within a region (syndicated copies) are kept once; grouping of
     similar stories and de-duplication happen in the summarizer's review.
"""
import logging
import re

from src import relevance

logger = logging.getLogger("selector")


def _keyword_bonus(title: str, lang: str, keywords: dict) -> bool:
    """Soft relevance signal — a curated keyword hit lowers the gate, never forces selection."""
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


def select(raw_articles: list[dict], keywords_cfg: dict, sel_cfg: dict) -> dict:
    """
    Returns {"selected": sorted indices to fetch content for,
             "dropped": records of articles below the relevance gate,
             "econ": {index: relevance score/tier for the summarizer}}.
    """
    n = len(raw_articles)
    if n == 0:
        return {"selected": [], "dropped": [], "econ": {}}

    # Finance-relevance gate. A curated keyword hit lowers the bar; the classifier decides the rest.
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
    drop_below = rel_cfg.get("drop_below", 0.40)
    kw_drop_below = rel_cfg.get("keyword_drop_below", 0.30)  # generic keywords (AI, war) can mislead
    dropped: set[int] = set()
    if probs is not None:
        dropped = {i for i, p in enumerate(probs)
                   if p < (kw_drop_below if kw_hit[i] else drop_below)}

    selected: list[int] = []
    seen: set[tuple[str, str]] = set()
    for i, a in enumerate(raw_articles):
        if i in dropped:
            continue
        key = (a.get("region", "其他"), a["title"].strip().lower())
        if key in seen:  # 同一標題（多為通稿被多家轉載）同地區只留一則
            continue
        seen.add(key)
        selected.append(i)

    dropped_records = [
        {"title": raw_articles[i]["title"], "source": raw_articles[i]["source"],
         "region": raw_articles[i]["region"], "finance_prob": round(probs[i], 3)}
        for i in sorted(dropped, key=lambda i: probs[i])
    ]
    logger.info("selector: %d 原始 -> 相關性過濾 %d 篇 -> %d 篇入選",
                n, len(dropped), len(selected))
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
    return {"selected": selected, "dropped": dropped_records, "econ": econ}
