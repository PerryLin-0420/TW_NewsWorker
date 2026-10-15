import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from src import market_correlation, relevance
from src.claude_cli import ClaudeAuthError, auth_hint, auth_status, call_claude

ROOT = Path(__file__).parent.parent

logger = logging.getLogger("summarizer")

_REGION_PROMPT = """\
你是財經分析師。以下是【{region}】今日財經新聞（附編號），請：
1. 用繁體中文以「列點」撰寫整體趨勢摘要，共 4~6 點，每點分兩部分，以 ||| 分隔：
   - 重點：一句話結論（30 字內），讓讀者只讀這句就掌握重點
   - 細節：2~3 條簡短要點（每條 25 字內，講數據、影響或投資人需留意之處），條與條之間以 ;; 分隔
   引用相關報導時於文中插入 [註N]（N 為對應編號）
2. 為每篇文章產生 10 字以內的繁體中文短標籤
3. 資格審查（見下方說明）
{market_context}
資格審查（第二層把關）：逐篇依「標題＋摘要」綜合判斷是否符合摘要條件——須「對台灣經濟有影響」：
- 台灣本地：台灣總體經濟、產業、企業營運、台股、新台幣、利率與政策
- 會傳導到台灣的全球事件：原油與能源、貴金屬與原物料、美國與主要央行政策、關稅與貿易、半導體與科技供應鏈、航運與物流、主要匯率、主要市場大幅波動
與台灣沒有可說明傳導路徑的他國本地新聞（他國地方政策、與台灣無關的外國個別企業消息）、單純的概念討論、輿論話題、人事與產品新聞、體育、犯罪、社會、娛樂、生活消費，視為不符合。
不得為了湊數而替無關新聞勉強推演對台灣的影響；摘要內容若只是泛用的網站介紹，則以標題為準。
撰寫摘要時，每個重點須點出與台灣經濟的關聯（受影響的產業、市場或價格）。
不符合者列入 [REJECT]，且不得用於摘要、也不得引用其 [註N]。

經濟相關度（第一層模型提供，標在每篇標題前）：
- 【高】屬經濟議題且有具體數據（金額、比率、漲跌幅等）——優先作為重點，可直接引用數據
- 【中】屬經濟議題但缺乏數據——可作補充背景，語氣保守，不得自行推估數字或誇大影響
分數為 0~1 的模型信心值，僅供參考；最終仍以你的資格審查為準。
對台灣評價（同一標記內，｜之後，僅標於台灣相關文章）：台灣利多／台灣利空／台灣中性，附 0~1 信心值（越高方向越明確）。
評價由模型推估，僅供參考，須與標題、摘要內容一致才採用；描述影響時請說明是對台灣哪個產業或市場。

輸出格式（嚴格遵守，除此之外不輸出任何其他文字）：
[SUMMARY]
- 重點一句話 [註1] ||| 要點一 [註2] ;; 要點二 ;; 要點三
- 重點一句話 ||| 要點一 ;; 要點二

[LABELS]
1. 短標籤
2. 短標籤
...

[REJECT]
編號. 不符合原因（5~10 字）；若全部符合則只寫「無」

新聞標題：
{titles}
"""

_TAIWAN_CROSS_PROMPT = """\
你是財經分析師。以下分別是【台灣本地媒體】與【國際媒體中台灣相關報導】的標題列表（統一編號）。

請：
1. 用繁體中文以「列點」撰寫台灣市場摘要，共 5~7 點，每點分兩部分，以 ||| 分隔：
   - 重點：一句話結論（30 字內）
   - 細節：2~3 條簡短要點（每條 25 字內，講數據、影響或風險機會），條與條之間以 ;; 分隔
   引用相關報導時插入 [註N]。內容須涵蓋：
   - 台灣市場與產業今日主要動向
   - 國際視角對台灣的關注點（科技、地緣、供應鏈等）
   - 若本地與國際報導有明顯角度差異或資訊落差，請明確點出
   - 投資人需留意的風險或機會
2. 為每篇文章（本地與國際合計）產生 10 字以內的繁體中文短標籤
3. 資格審查（見下方說明）
{market_context}
資格審查（第二層把關）：逐篇依「標題＋摘要」綜合判斷是否符合摘要條件——須「對台灣經濟有影響」：
- 台灣本地：台灣總體經濟、產業、企業營運、台股、新台幣、利率與政策
- 會傳導到台灣的全球事件：原油與能源、貴金屬與原物料、美國與主要央行政策、關稅與貿易、半導體與科技供應鏈、航運與物流、主要匯率、主要市場大幅波動
與台灣沒有可說明傳導路徑的他國本地新聞（他國地方政策、與台灣無關的外國個別企業消息）、單純的概念討論、輿論話題、人事與產品新聞、體育、犯罪、社會、娛樂、生活消費，視為不符合。
不得為了湊數而替無關新聞勉強推演對台灣的影響；摘要內容若只是泛用的網站介紹，則以標題為準。
撰寫摘要時，每個重點須點出與台灣經濟的關聯（受影響的產業、市場或價格）。
不符合者列入 [REJECT]，且不得用於摘要、也不得引用其 [註N]。

經濟相關度（第一層模型提供，標在每篇標題前）：
- 【高】屬經濟議題且有具體數據（金額、比率、漲跌幅等）——優先作為重點，可直接引用數據
- 【中】屬經濟議題但缺乏數據——可作補充背景，語氣保守，不得自行推估數字或誇大影響
分數為 0~1 的模型信心值，僅供參考；最終仍以你的資格審查為準。
對台灣評價（同一標記內，｜之後，僅標於台灣相關文章）：台灣利多／台灣利空／台灣中性，附 0~1 信心值（越高方向越明確）。
評價由模型推估，僅供參考，須與標題、摘要內容一致才採用；描述影響時請說明是對台灣哪個產業或市場。

輸出格式（嚴格遵守，除此之外不輸出任何其他文字）：
[SUMMARY]
- 重點一句話 [註1] ||| 要點一 [註2] ;; 要點二 ;; 要點三
- 重點一句話 ||| 要點一 ;; 要點二

[LABELS]
1. 短標籤
2. 短標籤
...

[REJECT]
編號. 不符合原因（5~10 字）；若全部符合則只寫「無」

【台灣本地媒體報導】
{local_titles}

【國際媒體中台灣相關報導】
{intl_titles}
"""




def _line(n: int, a: dict, prefix: str = "") -> str:
    """Numbered title line, followed by a short summary snippet when available."""
    snippet = re.sub(r"\s+", " ", a.get("content", "") or "").strip()[:150]
    tier = ""
    if a.get("econ_tier"):
        sent = ""
        if a.get("tw_sentiment"):
            sent = f"台灣{a['tw_sentiment']} {a['tw_sentiment_conf']:.2f}"
        tier = f"【{a['econ_tier']} {a['econ_score']:.2f}" + (f"｜{sent}" if sent else "") + "】"
    return f"{n}. {tier}{prefix}{a['title']}" + (f"\n   摘要：{snippet}" if snippet else "")


def _build_taiwan_prompt(local_articles: list[dict], intl_articles: list[dict],
                         market_context: str) -> str:
    local_block = "\n".join(_line(i + 1, a) for i, a in enumerate(local_articles))
    offset = len(local_articles)
    if intl_articles:
        intl_block = "\n".join(
            _line(offset + i + 1, a, f"[{a['source']}] ") for i, a in enumerate(intl_articles)
        )
    else:
        intl_block = "（本次無國際媒體台灣相關報導）"
    return _TAIWAN_CROSS_PROMPT.format(local_titles=local_block, intl_titles=intl_block,
                                       market_context=market_context)


def _parse_output(text: str, articles: list[dict]) -> tuple[str, list[str], dict[int, str]]:
    """從 Claude 輸出解析 [SUMMARY]、[LABELS]、[REJECT]；rejected 為 {0-based 索引: 原因}。"""
    m_sum = re.search(r'\[SUMMARY\](.*?)(?=\[LABELS\]|\[REJECT\]|$)', text, re.DOTALL)
    m_lab = re.search(r'\[LABELS\](.*?)(?=\[REJECT\]|$)', text, re.DOTALL)
    m_rej = re.search(r'\[REJECT\](.*?)$', text, re.DOTALL)

    rejected: dict[int, str] = {}
    if m_rej:
        for line in m_rej.group(1).strip().splitlines():
            m = re.match(r'^(\d+)[.、]\s*(.*)', line.strip())
            if m and 1 <= int(m.group(1)) <= len(articles):
                rejected[int(m.group(1)) - 1] = m.group(2).strip()

    summary = m_sum.group(1).strip() if m_sum else text.strip()

    labels: list[str] = []
    if m_lab:
        for line in m_lab.group(1).strip().splitlines():
            m = re.match(r'^\d+[.、]\s*(.+)', line.strip())
            if m:
                labels.append(m.group(1).strip()[:12])

    # 不足時以標題前段補齊
    for i in range(len(labels), len(articles)):
        labels.append(articles[i].get("title", "")[:10])

    return summary, labels, rejected


def run(filtered_articles: list[dict], run_dir: Path) -> list[dict]:
    cfg_path = ROOT / "config.json"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)

    s_cfg = cfg["summarizer"]
    delay = s_cfg["delay_between_calls_seconds"]
    timeout = s_cfg["timeout_seconds"]
    region_order = cfg.get("region_order", [])

    # 抽出國際媒體中台灣相關文章
    intl_taiwan: list[dict] = [
        a for a in filtered_articles
        if a.get("taiwan_related") and a.get("region") != "台灣"
    ]
    if intl_taiwan:
        logger.info("國際媒體台灣相關文章: %d 篇 (%s)",
                    len(intl_taiwan),
                    ", ".join(a["source"] for a in intl_taiwan))

    # 依地區分組
    groups: dict[str, list[dict]] = defaultdict(list)
    for art in filtered_articles:
        groups[art.get("region", "其他")].append(art)

    ordered_regions = [r for r in region_order if r in groups]
    ordered_regions += [r for r in groups if r not in ordered_regions]

    # 量化市場監控訊號（見 market_correlation.py）——只有「偏離歷史基準」
    # 的關係才會被納入，過期或缺檔會安靜地回傳空清單，不影響摘要主線。
    market_signals = market_correlation.load_latest_signals()

    # Fail fast on a dead login: one cheap status call beats N failing invocations.
    # An indeterminate status ({}) falls through and lets the real call decide.
    auth_ok = auth_status().get("loggedIn", True)
    if not auth_ok:
        logger.error("claude CLI 未登入，跳過所有摘要呼叫")

    results: list[dict] = []
    summary_lines: list[str] = []
    run_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for i, region in enumerate(ordered_regions):
        local_articles = groups[region]
        region_signals = market_correlation.signals_for_region(market_signals, region)
        market_context = market_correlation.format_signal_block(region_signals)
        if region_signals:
            logger.info("  %s 附帶 %d 條市場監控訊號", region, len(region_signals))

        if region == "台灣":
            n_intl = len(intl_taiwan)
            logger.info("[%d/%d] 生成台灣雙視角摘要 (本地 %d 篇 + 國際 %d 篇)",
                        i+1, len(ordered_regions), len(local_articles), n_intl)
            prompt = _build_taiwan_prompt(local_articles, intl_taiwan, market_context)
            all_articles = local_articles + intl_taiwan
            intl_display = intl_taiwan
        else:
            logger.info("[%d/%d] 生成地區摘要: %s (%d 篇)",
                        i+1, len(ordered_regions), region, len(local_articles))
            titles_block = "\n".join(_line(j + 1, a) for j, a in enumerate(local_articles))
            prompt = _REGION_PROMPT.format(region=region, titles=titles_block,
                                           market_context=market_context)
            all_articles = local_articles
            intl_display = []

        try:
            if not auth_ok:
                raise ClaudeAuthError(auth_hint())
            raw = call_claude(prompt, timeout)
            summary, labels, rejected = _parse_output(raw, all_articles)
            if rejected:
                logger.info("  %s 第二層剔除 %d 篇: %s", region, len(rejected),
                            "; ".join(f"{all_articles[k]['title'][:30]}（{why}）"
                                      for k, why in rejected.items()))
            # Feedback loop: the summarizer's verdicts become training labels for layer 1.
            relevance.record_feedback(run_dir.name, [
                {"title": a["title"], "source": a.get("source", ""), "label": 0 if k in rejected else 1,
                 "reason": rejected.get(k, "")}
                for k, a in enumerate(all_articles)
            ])
            if len(rejected) >= len(all_articles):
                logger.info("  %s 全部不符合條件，略過此地區", region)
                continue

            result = {
                "region": region,
                "summary": summary,
                "articles": local_articles,
                "labels": labels,                      # 對應 all_articles 的短標籤
                "rejected": sorted(rejected),          # all_articles 中被第二層剔除的 0-based 索引
                "intl_taiwan_articles": intl_display,
                "summarized_at": datetime.now(timezone.utc).isoformat(),
                "error": None,
                "error_type": None,
            }
            results.append(result)

            # Markdown（腳註格式）
            md_summary = "\n".join(
                re.sub(r'^[-•]\s*(.*?)\s*\|\|\|\s*(.*)$',
                       lambda m: f"- **{m.group(1)}**\n" + "\n".join(
                           f"  - {d.strip()}" for d in m.group(2).split(";;") if d.strip()),
                       ln)
                for ln in summary.splitlines()
            )
            summary_lines.append(f"## {region}\n\n{md_summary}\n\n")
            for j, art in enumerate(all_articles):
                if j in rejected:
                    continue
                label = labels[j] if j < len(labels) else art['title'][:10]
                summary_lines.append(f"[註{j+1}] [{label}]({art['url']})  \n")
            summary_lines.append("\n---\n")

            logger.info("  [OK] %s 摘要完成 (%d 字, %d 腳註)", region, len(summary), len(labels))

        except Exception as exc:
            logger.error("  地區 %s 摘要失敗: %s", region, exc)
            results.append({
                "region": region,
                "summary": "",
                "articles": local_articles,
                "labels": [],
                "intl_taiwan_articles": intl_display,
                "summarized_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
                "error_type": "auth" if isinstance(exc, ClaudeAuthError) else "other",
            })

        if auth_ok and i < len(ordered_regions) - 1:
            time.sleep(delay)

    md_path = run_dir / "summary.md"
    md_path.write_text(
        f"# 財經新聞摘要 — {run_time_str}\n\n" + "".join(summary_lines),
        encoding="utf-8",
    )

    total_articles = sum(len(r["articles"]) for r in results)
    success_count = sum(1 for r in results if r["summary"])
    logger.info("摘要完成: %d/%d 地區成功，涵蓋 %d 篇文章，已存 summary.md",
                success_count, len(results), total_articles)
    return results
