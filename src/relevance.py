"""
Economic-relevance gate and sentiment tagger — runs before clustering so
non-economic stories (sports, crime, local news) cannot enter the summary just
because they are trending, and tells the summarizer how economic and how
bullish/bearish each selected story is.

A multilingual embedding model (CPU) turns "title. feed summary" into a vector
(title alone when no summary exists). On top of it:
  - relevance: P(significant economic impact), a logistic regression trained on
    hand labels + feedback
  - Taiwan sentiment: zero-shot projection onto a 利多台灣 − 利空台灣 axis built
    from fixed prototype phrases (no labels); the projection is standardised with
    the mean/std of historical Taiwan articles (tw_axis.json) and mapped to
    利多/中性/利空 with a neutral band

Relevance labels live in data/relevance/labels_*.json, either {"source_run",
"non_finance_idx"} (indexes into that run's news_raw.json; every other title
counts as finance) or {"finance_titles": [...], "non_finance_titles": [...]}.
Later files (name order) override earlier ones for the same title.
Retrain after adding labels:  python -m src.relevance
Recalibrate the Taiwan axis:   python -m src.history annotate
"""
import json
import logging
import re
import sys
from pathlib import Path

import numpy as np

logger = logging.getLogger("relevance")

ROOT = Path(__file__).parent.parent
REL_DIR = ROOT / "data" / "relevance"
CLF_PATH = REL_DIR / "classifier.json"
TW_AXIS_PATH = REL_DIR / "tw_axis.json"
FEEDBACK_PATH = REL_DIR / "feedback.jsonl"
_MODEL_NAME = "intfloat/multilingual-e5-base"
# Fixed prototypes defining the Taiwan polarity axis; changing them requires recalibration.
TW_POSITIVE = ["台灣出口訂單強勁、台股大漲、企業獲利創新高、利多台灣",
               "Taiwan exports surge, TAIEX rallies, record profits for Taiwanese firms"]
TW_NEGATIVE = ["台灣出口衰退、台股重挫、企業虧損、關稅與地緣風險升高、利空台灣",
               "Taiwan exports slump, TAIEX plunges, tariffs and geopolitical risks hit Taiwan"]
_SUMMARY_CHARS = 300
_model = None
_clf: dict | None = None
_tw_axis: np.ndarray | None = None
_tw_cal: dict | None = None


def article_text(title: str, summary: str = "") -> str:
    """Model input: title plus the start of the feed summary when there is one."""
    summary = re.sub(r"\s+", " ", summary or "").strip()[:_SUMMARY_CHARS]
    return f"{title}. {summary}" if summary else title


def _embed(texts: list[str]) -> np.ndarray:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME, device="cpu")
    return _model.encode([f"query: {t}" for t in texts], normalize_embeddings=True,
                         batch_size=32, show_progress_bar=False)


def _load_clf(path: Path) -> dict | None:
    """A classifier is only usable with the embedding model it was trained on."""
    if not path.exists():
        return None
    clf = json.loads(path.read_text(encoding="utf-8"))
    if clf.get("model") != _MODEL_NAME:
        logger.warning("%s 是以 %s 訓練，與目前模型 %s 不符，請重訓", path.name, clf.get("model"), _MODEL_NAME)
        return None
    return clf


def record_feedback(run_name: str, items: list[dict]) -> None:
    """Append layer-2 (summarizer) verdicts: label 1 = qualified, 0 = rejected."""
    REL_DIR.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_PATH, "a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps({"run": run_name, **it}, ensure_ascii=False) + "\n")


def _load_feedback() -> dict[str, int]:
    """Latest verdict per title; hand labels still win when the same title appears there."""
    out: dict[str, int] = {}
    if FEEDBACK_PATH.exists():
        for line in FEEDBACK_PATH.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                out[d["title"]] = int(d["label"])
            except (ValueError, KeyError):
                continue
    return out


def summary_lookup() -> dict[str, str]:
    """Best known summary per title: saved feed summaries, back-filled page
    descriptions, then the lead of fetched article content."""
    out: dict[str, str] = {}

    def put(title: str, text: str) -> None:
        if title and text and not out.get(title):
            out[title] = text

    for name in ("summaries.json", "history_summaries.json"):
        p = REL_DIR / name
        if p.exists():
            for t, v in json.loads(p.read_text(encoding="utf-8")).items():
                put(t, v.get("summary", "") if isinstance(v, dict) else v)
    for f in sorted((ROOT / "data").glob("20*/news_raw.json")):
        for a in json.loads(f.read_text(encoding="utf-8")):
            put(a["title"], a.get("summary", ""))
    for f in sorted((ROOT / "data").glob("20*/news_filtered.json")):
        for a in json.loads(f.read_text(encoding="utf-8")):
            put(a["title"], a.get("content", ""))
    return out


def tw_axis_vector() -> np.ndarray:
    """利多台灣 − 利空台灣 direction in embedding space (zero-shot, no labels)."""
    global _tw_axis
    if _tw_axis is None:
        _tw_axis = _embed(TW_POSITIVE).mean(0) - _embed(TW_NEGATIVE).mean(0)
    return _tw_axis


def score_articles(items: list[tuple[str, str]]) -> dict | None:
    """Score (title, summary) pairs in one embedding pass.
    Returns {"econ": [P(economic)], "tw_axis": [raw projection on the Taiwan axis]};
    None when no relevance classifier is available."""
    global _clf
    if _clf is None:
        _clf = _load_clf(CLF_PATH)
        if _clf is None:
            return None
    if not items:
        return {"econ": [], "tw_axis": []}
    X = _embed([article_text(t, s) for t, s in items])
    z = X @ np.array(_clf["coef"]) + _clf["intercept"]
    return {"econ": (1 / (1 + np.exp(-z))).tolist(), "tw_axis": (X @ tw_axis_vector()).tolist()}


def tw_sentiment(raw: float, band: float) -> tuple[str, float, float]:
    """Map a raw Taiwan-axis projection to (利多/中性/利空, confidence 0~1, z-score).
    z is standardised against historical Taiwan articles; |z| < band is 中性.
    Confidence = min(1, |z| / 2): 0 at the centre, 1 at two standard deviations."""
    global _tw_cal
    if _tw_cal is None:
        _tw_cal = json.loads(TW_AXIS_PATH.read_text(encoding="utf-8"))
    z = (raw - _tw_cal["center"]) / _tw_cal["scale"]
    label = "利多" if z >= band else "利空" if z <= -band else "中性"
    return label, round(min(1.0, abs(z) / 2), 3), round(z, 3)


def save_tw_calibration(raw: list[float]) -> None:
    """Store mean/std of Taiwan-axis projections over historical Taiwan articles."""
    global _tw_cal
    v = np.array(raw)
    _tw_cal = {"center": float(v.mean()), "scale": float(v.std()), "n": int(len(v)),
               "model": _MODEL_NAME, "positive": TW_POSITIVE, "negative": TW_NEGATIVE}
    TW_AXIS_PATH.write_text(json.dumps(_tw_cal, ensure_ascii=False, indent=1), encoding="utf-8")


# A figure tied to a unit or currency: "3.2%", "$20bn", "1.17兆", "4.4 percent", "€5".
_DATA_RE = re.compile(
    r"\d[\d,.]*\s*(?:%|％|percent|per cent|bps?\b|basis points|billion|million|trillion|bn\b|mn\b|"
    r"[億萬兆]|個百分點|點|美元|美金|元|日圓|日元|歐元|英鎊|韓元|盧布)"
    r"|[$€£¥]\s?\d",
    re.IGNORECASE,
)


def has_data(text: str) -> bool:
    """True when the text carries concrete economic figures (amounts, rates, percentages)."""
    return bool(_DATA_RE.search(text or ""))


def econ_tier(prob: float, text: str, floor: float, high_min: float) -> str:
    """Economic-relevance tier: 高 = economic and backed by figures, 中 = economic
    without figures, 低 = below the gate. `text` is title plus feed summary."""
    if prob < floor:
        return "低"
    return "高" if prob >= high_min and has_data(text) else "中"


def load_labels() -> dict[str, int]:
    """Hand labels as {title: 0/1}. Files are applied in name order, so a later file
    (e.g. labels_fulltext.json) overrides an earlier label for the same title."""
    out: dict[str, int] = {}
    for lf in sorted(REL_DIR.glob("labels_*.json")):
        lab = json.loads(lf.read_text(encoding="utf-8"))
        if "non_finance_idx" in lab:
            neg = set(lab["non_finance_idx"])
            raw = json.loads((ROOT / "data" / lab["source_run"] / "news_raw.json")
                             .read_text(encoding="utf-8"))
            for i, a in enumerate(raw):
                out[a["title"]] = 0 if i in neg else 1
        for t in lab.get("finance_titles", []):
            out[t] = 1
        for t in lab.get("non_finance_titles", []):
            out[t] = 0
    return out


def train(C: float = 8.0, summaries: dict[str, str] | None = None) -> None:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    summaries = summary_lookup() if summaries is None else summaries
    labelled = load_labels()
    n_hand = len(labelled)
    for t, lab in _load_feedback().items():
        if t not in labelled:  # hand labels take precedence over model-generated feedback
            labelled[t] = lab
    titles = list(labelled)
    y = np.array([labelled[t] for t in titles])
    n_sum = sum(bool(summaries.get(t)) for t in titles)
    print(f"[relevance] hand-labelled={n_hand} feedback_added={len(titles) - n_hand} "
          f"with_summary={n_sum}/{len(titles)}")
    X = _embed([article_text(t, summaries.get(t, "")) for t in titles])
    mk = lambda: LogisticRegression(C=C, max_iter=3000, class_weight="balanced")
    p = cross_val_predict(mk(), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0),
                          method="predict_proba")[:, 1]
    print(f"[relevance] samples={len(y)} non_finance={(y == 0).sum()} cv_auc={roc_auc_score(y, p):.3f}")
    for thr in (0.3, 0.4, 0.5, 0.6):
        print(f"  thr={thr}: finance kept {(p[y == 1] >= thr).mean():.1%}, "
              f"non-finance dropped {(p[y == 0] < thr).mean():.1%}")
    clf = mk().fit(X, y)
    CLF_PATH.write_text(json.dumps({"coef": clf.coef_[0].tolist(),
                                    "intercept": float(clf.intercept_[0]),
                                    "model": _MODEL_NAME, "n": int(len(y))}),
                        encoding="utf-8")
    print("saved", CLF_PATH)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    train()
