import calendar
import concurrent.futures as cf
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
import trafilatura

from src import relevance, selector

ROOT = Path(__file__).parent.parent

logger = logging.getLogger("crawler")

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsWorker/1.0)"}
_RSS_ATTEMPTS = 3


def _load_config() -> dict:
    with open(ROOT / "config.json", encoding="utf-8") as f:
        return json.load(f)


_TAIWAN_INTL_KEYWORDS = [
    "taiwan", "tsmc", "foxconn", "mediatek", "taiwan strait",
    "cross-strait", "taipei", "auo", "asus", "htc", "delta electronics",
    "taiwan semiconductor", "hon hai", "pegatron", "wistron", "quanta",
]


def _is_taiwan_related(title: str, content: str) -> bool:
    combined = (title + " " + content).lower()
    return any(kw in combined for kw in _TAIWAN_INTL_KEYWORDS)


def _parse_entry_dt(entry: dict) -> "datetime | None":
    """從 entry dict 解析發布時間，回傳 UTC datetime 或 None。"""
    tp = entry.get("published_parsed")  # feedparser time.struct_time
    if tp:
        try:
            return datetime.fromtimestamp(calendar.timegm(tp), tz=timezone.utc)
        except Exception:
            pass
    ts = entry.get("published_ts")  # JSON API Unix timestamp
    if ts:
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            pass
    return None


def _fetch_content(url: str, timeout: int) -> str:
    try:
        resp = requests.get(url, timeout=timeout, headers=_HEADERS)
        resp.raise_for_status()
        text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
        return (text or "").strip()
    except Exception as exc:
        logger.warning("内文抓取失敗 %s: %s", url, exc)
        return ""


def _fetch_json_api(src: dict, max_per_src: int, timeout: int) -> list[dict]:
    """鉅亨網等 JSON API 來源的抓取器。"""
    url = src["url"]
    json_path = src.get("json_path", "")
    title_field = src.get("title_field", "title")
    url_field = src.get("url_field", "url")
    time_field = src.get("time_field", "publishAt")

    resp = requests.get(url, timeout=timeout, headers=_HEADERS)
    resp.raise_for_status()
    data = resp.json()

    # 依 json_path 取陣列（支援 a.b.c 格式）
    node = data
    for key in json_path.split("."):
        node = node[key]

    articles = []
    for item in node[:max_per_src]:
        title = item.get(title_field, "").strip()
        url_template = src.get("url_template", "")
        raw_id = item.get(url_field, "")
        if url_template and raw_id:
            link = url_template.replace(f"{{{url_field}}}", str(raw_id))
        else:
            link = str(raw_id).strip()
            if link and not link.startswith("http"):
                link = "https://news.cnyes.com" + link

        published = ""
        ts = item.get(time_field)
        if ts:
            try:
                published = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                published = str(ts)

        if title and link:
            articles.append({
                "title": title,
                "url": link,
                "published": published,
                "published_ts": ts,
            })
    return articles


def _fetch_source(src: dict, max_per_src: int, timeout: int,
                   min_published: "datetime | None") -> dict:
    """抓單一來源的標題列表（不含內文）。供平行執行使用，回傳結果不含任何共享狀態。"""
    name = src["name"]
    lang = src["lang"]
    region = src.get("region", "其他")
    src_type = src.get("type", "rss")

    try:
        if src_type == "json_api":
            raw_entries = _fetch_json_api(src, max_per_src, timeout)
            rss_summaries = {}   # JSON API 無摘要欄位
        else:
            # Some feeds intermittently answer 202/empty or a garbled body; retry before failing.
            feed, err = None, "unknown"
            for attempt in range(_RSS_ATTEMPTS):
                if attempt:
                    time.sleep(2 * attempt)
                resp = requests.get(src["url"], timeout=timeout, headers=_HEADERS)
                clean_xml = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", resp.text)
                feed = feedparser.parse(clean_xml)
                if feed.entries:
                    break
                err = getattr(feed, "bozo_exception", None) or f"HTTP {resp.status_code}, {len(resp.text)} bytes"
            if not feed.entries:
                raise ValueError(f"RSS 解析錯誤: {err}（已重試 {_RSS_ATTEMPTS} 次）")
            raw_entries = [
                {
                    "title": e.get("title", "").strip(),
                    "url": e.get("link", "").strip(),
                    "published": e.get("published", "") or e.get("updated", ""),
                    "published_parsed": e.get("published_parsed"),
                }
                for e in feed.entries[:max_per_src]
            ]
            rss_summaries = {
                e.get("link", ""): e.get("summary", "")
                for e in feed.entries[:max_per_src]
            }

        articles = []
        for entry in raw_entries:
            title = entry["title"]
            link = entry["url"]
            published = entry.get("published", "")

            if not title or not link:
                continue
            if min_published:
                pub_dt = _parse_entry_dt(entry)
                if pub_dt and pub_dt < min_published:
                    continue

            articles.append({
                "source": name,
                "region": region,
                "lang": lang,
                "title": title,
                "url": link,
                "published": published,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "_summary": rss_summaries.get(link, ""),
            })

        return {"name": name, "ok": True, "error": None, "articles": articles}

    except Exception as exc:
        return {"name": name, "ok": False, "error": str(exc), "articles": []}


def run(run_dir: Path, min_published: "datetime | None" = None) -> dict:
    cfg = _load_config()
    sources = cfg["rss_sources"]
    keywords = cfg["keywords"]
    c_cfg = cfg["crawler"]
    sel_cfg = cfg.get("selector", {})
    delay = c_cfg["request_delay_seconds"]
    timeout = c_cfg["request_timeout"]
    max_per_src = c_cfg["max_articles_per_source"]
    max_chars = c_cfg["max_content_chars"]
    max_workers = c_cfg.get("max_fetch_workers", 12)
    skip_fetch_domains = c_cfg.get("skip_fetch_domains", [])
    high_min = sel_cfg.get("relevance", {}).get("high_min", 0.5)
    tw_band = sel_cfg.get("relevance", {}).get("tw_neutral_band", 0.5)

    articles_dir = run_dir / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    stats = {"sources_ok": 0, "sources_fail": 0, "raw": 0, "filtered": 0, "content_ok": 0}
    source_results: dict[str, dict] = {}

    # ── 階段一：平行抓所有來源的標題列表（純解析，不抓內文） ──────────
    raw_articles: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_fetch_source, src, max_per_src, timeout, min_published)
            for src in sources
        ]
        for src, fut in zip(sources, futures):
            result = fut.result()
            name, region = src["name"], src.get("region", "其他")
            if result["ok"]:
                stats["sources_ok"] += 1
                source_results[name] = {"ok": True, "count": len(result["articles"]), "error": None}
                logger.info("爬取來源: %s [%s] -> %d 篇", name, region, len(result["articles"]))
                raw_articles.extend(result["articles"])
            else:
                stats["sources_fail"] += 1
                source_results[name] = {"ok": False, "count": 0, "error": result["error"]}
                logger.error("來源 %s 失敗: %s", name, result["error"])

    stats["raw"] = len(raw_articles)

    # ── 階段二：跨來源統計選文（burst + 聚類），決定誰值得抓內文 ──────
    run_date = run_dir.name.split("_", 1)[0]  # run_dir 形如 2026-08-06_1539
    selection = selector.select(raw_articles, keywords, sel_cfg, run_date)
    selected_idx = selection["selected"]

    # 事件分數存檔，供日後「事件權重變化 vs 財經實際走勢」的回溯比對周報使用
    (run_dir / "events.json").write_text(
        json.dumps(selection["events"], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (run_dir / "dropped.json").write_text(
        json.dumps(selection.get("dropped", []), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── 階段三：只對入選文章抓內文 ─────────────────────────────
    filtered_articles: list[dict] = []
    for i in selected_idx:
        art = raw_articles[i]
        title, link, region = art["title"], art["url"], art["region"]
        logger.info("  [選中] %s", title[:80])

        # Sites that block scrapers (paywall / bot protection) are not fetched;
        # the RSS summary is used instead of making a request that will 403.
        if any(d in link for d in skip_fetch_domains):
            content = ""
        else:
            time.sleep(delay)
            content = _fetch_content(link, timeout)
        if content:
            content = content[:max_chars]
            stats["content_ok"] += 1
        else:
            content = art.get("_summary", "")[:max_chars]

        taiwan_related = region != "台灣" and _is_taiwan_related(title, content)
        article_data = {k: v for k, v in art.items() if k != "_summary"}
        article_data["content"] = content
        article_data["taiwan_related"] = taiwan_related
        econ = selection.get("econ", {}).get(i)
        if econ:
            # Full text is better evidence of figures than the feed summary.
            if (econ["tier"] == "中" and econ["score"] >= high_min
                    and relevance.has_data(content)):
                econ = {**econ, "tier": "高"}
            article_data["econ_score"] = econ["score"]
            article_data["econ_tier"] = econ["tier"]
            # Sentiment is measured toward Taiwan, so only Taiwan-related articles get one.
            if "tw_axis" in econ and (region == "台灣" or taiwan_related):
                label, conf, z = relevance.tw_sentiment(econ["tw_axis"], tw_band)
                article_data["tw_sentiment"] = label
                article_data["tw_sentiment_conf"] = conf
                article_data["tw_sentiment_z"] = z
        if taiwan_related:
            logger.info("    [TW] 國際台灣相關: %s", title[:60])
        filtered_articles.append(article_data)

        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title[:60])
        md_path = articles_dir / f"{safe_title}.md"
        md_path.write_text(
            f"# {title}\n\n"
            f"**來源**: {art['source']} ({region})  \n"
            f"**URL**: {link}  \n"
            f"**時間**: {art['published']}  \n\n"
            f"---\n\n{content}",
            encoding="utf-8",
        )

    stats["filtered"] = len(filtered_articles)
    stats["sources"] = source_results

    # news_raw.json keeps the feed's own summary (HTML stripped, capped) as "summary";
    # it is the extra text signal for the relevance model and for later evaluation.
    raw_clean = []
    for a in raw_articles:
        item = {k: v for k, v in a.items() if k != "_summary"}
        item["summary"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", a.get("_summary", ""))).strip()[:600]
        raw_clean.append(item)
    (run_dir / "news_raw.json").write_text(
        json.dumps(raw_clean, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "news_filtered.json").write_text(
        json.dumps(filtered_articles, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info(
        "爬蟲完成 | 來源成功:%d 失敗:%d | 原始:%d 選中:%d 有內文:%d",
        stats["sources_ok"], stats["sources_fail"],
        stats["raw"], stats["filtered"], stats["content_ok"],
    )
    return {"filtered_articles": filtered_articles, "stats": stats}
