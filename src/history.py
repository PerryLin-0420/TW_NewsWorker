"""
Historical annotation — runs every article ever crawled (data/*/news_raw.json)
through the trained relevance model and the Taiwan sentiment axis, for later analysis.

  python -m src.history backfill   # fetch page descriptions for articles with no summary (resumable)
  python -m src.history annotate   # score everything -> data/relevance/history_annotations.jsonl
                                   # (also recalibrates the Taiwan axis -> tw_axis.json)
"""
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from src import crawler, relevance, selector

logger = logging.getLogger("history")

ROOT = relevance.ROOT
BACKFILL_PATH = relevance.REL_DIR / "history_summaries.json"
OUT_PATH = relevance.REL_DIR / "history_annotations.jsonl"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsWorker/1.0)"}


def collect() -> list[dict]:
    """Unique articles across all runs (by url, else title), earliest run first."""
    seen: dict[str, dict] = {}
    for f in sorted((ROOT / "data").glob("20*/news_raw.json")):
        run = f.parent.name
        for a in json.loads(f.read_text(encoding="utf-8")):
            key = a.get("url") or a["title"]
            if key not in seen:
                seen[key] = {**a, "first_run": run}
    return list(seen.values())


def _page_description(url: str) -> str:
    resp = requests.get(url, timeout=10, headers=_HEADERS)
    if resp.status_code != 200:
        return ""
    soup = BeautifulSoup(resp.text, "lxml")
    for attrs in ({"property": "og:description"}, {"name": "description"}, {"name": "twitter:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content", "").strip():
            return re.sub(r"\s+", " ", tag["content"]).strip()[:600]
    return ""


def backfill(workers: int = 4, delay: float = 0.3) -> None:
    """Fetch page descriptions for articles that have no summary yet.
    Results (including misses, stored as "") are saved every 200 so a rerun resumes."""
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    skip = cfg["crawler"].get("skip_fetch_domains", [])
    done = json.loads(BACKFILL_PATH.read_text(encoding="utf-8")) if BACKFILL_PATH.exists() else {}
    known = relevance.summary_lookup()
    todo = [a for a in collect()
            if not known.get(a["title"]) and a["title"] not in done
            and a.get("url") and not any(d in a["url"] for d in skip)]
    logger.info("backfill: %d articles to fetch (%d already attempted)", len(todo), len(done))

    def fetch(a: dict) -> tuple[str, str]:
        time.sleep(delay)
        try:
            return a["title"], _page_description(a["url"])
        except Exception:
            return a["title"], ""

    with ThreadPoolExecutor(workers) as ex:
        for n, (title, desc) in enumerate(ex.map(fetch, todo), 1):
            done[title] = desc
            if n % 200 == 0 or n == len(todo):
                BACKFILL_PATH.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
                logger.info("backfill: %d/%d, found %d", n, len(todo), sum(bool(v) for v in done.values()))


def annotate(batch: int = 512) -> None:
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    rel_cfg = cfg["selector"].get("relevance", {})
    keywords = cfg["keywords"]
    drop_below = rel_cfg.get("drop_below", 0.40)
    kw_drop_below = rel_cfg.get("keyword_drop_below", 0.30)
    high_min = rel_cfg.get("high_min", 0.5)
    band = rel_cfg.get("tw_neutral_band", 0.5)

    summaries = relevance.summary_lookup()
    articles = collect()
    logger.info("annotate: %d articles, %d with summary", len(articles),
                sum(bool(summaries.get(a["title"])) for a in articles))
    rows = []
    for b in range(0, len(articles), batch):
        chunk = articles[b:b + batch]
        items = [(a["title"], summaries.get(a["title"], "")) for a in chunk]
        scored = relevance.score_articles(items)
        if scored is None:
            raise RuntimeError("no trained relevance classifier")
        for a, (title, summ), p, axis in zip(chunk, items, scored["econ"], scored["tw_axis"]):
            kw = selector._keyword_bonus(title, a.get("lang", "en"), keywords)
            tier = relevance.econ_tier(p, f"{title} {summ}", kw_drop_below if kw else drop_below, high_min)
            is_tw = a.get("region") == "台灣" or crawler._is_taiwan_related(title, summ)
            rows.append({
                "title": title, "url": a.get("url", ""), "source": a.get("source", ""),
                "region": a.get("region", ""), "lang": a.get("lang", ""),
                "published": a.get("published", ""), "first_run": a["first_run"],
                "text_basis": "title+summary" if summ else "title",
                "keyword_hit": kw, "econ_score": round(p, 4), "econ_tier": tier,
                "taiwan_related": is_tw, "tw_axis_raw": round(axis, 6),
            })
        logger.info("annotate: %d/%d", min(b + batch, len(articles)), len(articles))

    # Calibrate on economic Taiwan articles, then label Taiwan-related ones.
    relevance.save_tw_calibration([r["tw_axis_raw"] for r in rows
                                   if r["taiwan_related"] and r["econ_tier"] != "低"])
    stamp = datetime.now(timezone.utc).isoformat()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for r in rows:
            label = conf = z = None
            if r["taiwan_related"]:
                label, conf, z = relevance.tw_sentiment(r["tw_axis_raw"], band)
            f.write(json.dumps({**r, "tw_sentiment": label, "tw_sentiment_conf": conf,
                                "tw_sentiment_z": z, "model": relevance._MODEL_NAME,
                                "annotated_at": stamp}, ensure_ascii=False) + "\n")
    logger.info("saved %s (calibration %s)", OUT_PATH, relevance.TW_AXIS_PATH.name)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    {"backfill": backfill, "annotate": annotate}[sys.argv[1]]()
