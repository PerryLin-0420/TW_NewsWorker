"""
跨日事件追蹤——把同一個真實事件在不同天的聚類結果串成一條「事件線」，
讓權重的時間序列能呈現「發酵到退燒」的完整過程，而不是每天各自獨立的
斷點快照。

這是 selector.py 同一天內聚類邏輯的跨日版本：兩天的事件只有在共享的詞
是「該事件線本身已出現過至少兩次」的詞，才會合併——單一天偶然出現的詞
不能當橋接，理由跟 selector._match_signature 完全一樣（避免用一次性
詞彙把不相關的事件串在一起）。一條事件線超過 dormant_after_days 天沒
再出現，視為退場；之後即使同主題重新爆發，也開一條新的事件線，而不是
喚醒舊的——避免跨越太長時間、風險等同於「隔了很久還硬要比對」的誤判。

存成單一登記檔 data/event_threads.json（不是逐日快照——事件線本來就是
橫跨多天的東西，這是專案裡少數合理需要跨日累積狀態的資料）。
"""
import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger("event_threads")

ROOT = Path(__file__).parent.parent
THREADS_PATH = ROOT / "data" / "event_threads.json"


def load_threads() -> dict:
    if THREADS_PATH.exists():
        try:
            return json.loads(THREADS_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("event_threads.json 讀取失敗，將重新建立: %s", exc)
    return {"next_id": 1, "threads": {}}


def save_threads(registry: dict) -> None:
    THREADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    THREADS_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _is_dormant(last_seen: str, run_date: str, dormant_after_days: int) -> bool:
    gap = (date.fromisoformat(run_date) - date.fromisoformat(last_seen)).days
    return gap > dormant_after_days


def _distinct_source_count(thread: dict) -> int:
    sources = set()
    for day in thread["daily"].values():
        sources.update(day.get("sources", []))
    return len(sources)


def _effective_dormant_days(thread: dict, single_source_days: int, multi_source_days: int) -> int:
    """
    A thread renewed by the SAME single source every time it appears is the
    signature of templated/periodic content (a weekly column, a monthly
    filing digest) — confirmed empirically: a "本周大事回顧" weekly-roundup
    thread and a recurring architecture column both turned out to be one
    source repeating verbatim, while a genuinely developing story (Japan
    gold-smuggling/market coverage) was picked up by three independent
    outlets over its life. Real multi-outlet news can go quiet for a few
    days between developments without being "over" — give it a longer
    grace period. A thread only ever renewed by one source stays on a
    tight leash so a recurring column can't masquerade as one continuous
    event for months. The moment a second distinct source appears, the
    thread graduates to the generous window from then on — it doesn't
    need to prove itself before every future check.
    """
    return multi_source_days if _distinct_source_count(thread) >= 2 else single_source_days


def _thread_signature(thread: dict, exclude_date: str) -> set[str]:
    """
    比對用的簽名，永遠從 thread["daily"] 現算，不做增量累積——這樣同一天
    重跑 link() 天然安全（不會因為重算兩次而讓「重複天數」灌水）。

    只有一天紀錄的事件線：用那一天的全部詞（還沒有第二天可以互相印證）。
    兩天以上：只保留在「至少兩天」出現過的詞，避免單一天的巧合詞彙
    把兩個不相關的事件線接在一起。
    """
    days = {d: v for d, v in thread["daily"].items() if d != exclude_date}
    if not days:
        return set()
    if len(days) == 1:
        return set(next(iter(days.values()))["terms"])
    counts: dict[str, int] = {}
    for v in days.values():
        for t in v["terms"]:
            counts[t] = counts.get(t, 0) + 1
    return {t for t, c in counts.items() if c >= 2}


def link(events: list[dict], run_date: str, min_shared: int = 2,
         jaccard_threshold: float = 0.34, dormant_after_days_single: int = 4,
         dormant_after_days_multi: int = 10) -> list[dict]:
    """
    將 selector.select() 產生的當日事件記錄（需含 "terms"/"score"/
    "regions"/"sources"/"articles" 欄位）比對到既有事件線，找不到就開新的。

    容忍期依「這條線目前有沒有出現過 2 家以上不同來源」動態決定——見
    _effective_dormant_days 的說明：單一來源反覆出現通常是模板內容
    （週報專欄、定期公告），多來源才是真正被交叉報導的新聞事件。

    回傳附加 thread_id / thread_first_seen / thread_day_count 的事件記錄
    （不修改傳入的 events），同時把更新後的登記檔存回磁碟。

    同一天重跑安全：處理前會先移除該 run_date 在所有事件線上的舊紀錄，
    比對簽名也排除當天，不會因為重跑而重複計數或污染簽名。
    """
    registry = load_threads()
    threads = registry["threads"]

    active_ids = [
        tid for tid, t in threads.items()
        if not _is_dormant(t["last_seen"], run_date,
                           _effective_dormant_days(t, dormant_after_days_single,
                                                   dormant_after_days_multi))
    ]

    for t in threads.values():
        t["daily"].pop(run_date, None)

    contributions: dict[str, dict] = {}
    result = []

    for ev in events:
        sig = set(ev.get("terms", []))
        best_tid, best_overlap = None, 0
        if sig:
            for tid in active_ids:
                signature = _thread_signature(threads[tid], exclude_date=run_date)
                if not signature:
                    continue
                shared = sig & signature
                if not shared:
                    continue
                union_size = len(sig | signature)
                jac = len(shared) / union_size if union_size else 0
                if (len(shared) >= min_shared or jac >= jaccard_threshold) and len(shared) > best_overlap:
                    best_tid, best_overlap = tid, len(shared)

        if best_tid is None:
            best_tid = str(registry["next_id"])
            registry["next_id"] += 1
            threads[best_tid] = {
                "thread_id": best_tid,
                "first_seen": run_date,
                "last_seen": run_date,
                "daily": {},
                "sample_title": ev["articles"][0]["title"] if ev.get("articles") else "",
            }
            active_ids.append(best_tid)

        c = contributions.setdefault(best_tid, {
            "score": 0.0, "regions": set(), "sources": set(), "terms": set(),
        })
        c["score"] += ev["score"]
        c["regions"] |= set(ev.get("regions", []))
        c["sources"] |= set(ev.get("sources", []))
        c["terms"] |= sig
        result.append({**ev, "thread_id": best_tid})

    for tid, c in contributions.items():
        t = threads[tid]
        t["daily"][run_date] = {
            "score": round(c["score"], 3),
            "regions": sorted(c["regions"]),
            "sources": sorted(c["sources"]),
            "terms": sorted(c["terms"]),
        }
        all_days = sorted(t["daily"])
        t["first_seen"] = all_days[0]
        t["last_seen"] = all_days[-1]

    save_threads(registry)

    for r in result:
        t = threads[r["thread_id"]]
        r["thread_first_seen"] = t["first_seen"]
        r["thread_day_count"] = len(t["daily"])

    logger.info("event_threads: %d 個事件比對到 %d 條線（含新開）",
                len(events), len(contributions))
    return result


def get_thread(thread_id: str) -> dict | None:
    """查詢單一事件線的完整每日分數歷史，供日後週報回溯發酵曲線用。"""
    registry = load_threads()
    return registry["threads"].get(thread_id)
