"""
Economic-relevance gate and sentiment tagger — runs before clustering so
non-economic stories (sports, crime, local news) cannot enter the summary just
because they are trending, and tells the summarizer how economic and how
bullish/bearish each selected story is.

Two multilingual embedding models (CPU) each turn "title. feed summary" into a
vector (title alone when no summary exists). Vectors are cached in a SQLite
database keyed by model + input text, so retraining only embeds new texts. On top:
  - relevance: P(qualified) = mean of two logistic regressions, one per embedding
    model, both trained on hand labels + feedback
  - Taiwan sentiment (e5 vectors only): zero-shot projection onto a 利多台灣 − 利空台灣 axis built
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
import hashlib
import json
import logging
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import numpy as np

logger = logging.getLogger("relevance")

ROOT = Path(__file__).parent.parent
REL_DIR = ROOT / "data" / "relevance"
CLF_PATH = REL_DIR / "classifier.json"
TW_AXIS_PATH = REL_DIR / "tw_axis.json"
FEEDBACK_PATH = REL_DIR / "feedback.jsonl"
EMB_DB = REL_DIR / "embeddings.sqlite"
_MODEL_NAME = "intfloat/multilingual-e5-base"  # also the Taiwan-axis model
# Relevance ensemble: model -> (input prefix, max tokens). harrier expects a task instruction.
_MODELS = {
    _MODEL_NAME: ("query: ", 512),
    "microsoft/harrier-oss-v1-0.6b": (
        "Instruct: Classify whether this news article has a significant economic impact on Taiwan\nQuery: ", 256),
}
# Fixed prototypes defining the Taiwan polarity axis; changing them requires recalibration.
TW_POSITIVE = ["台灣出口訂單強勁、台股大漲、企業獲利創新高、利多台灣",
               "Taiwan exports surge, TAIEX rallies, record profits for Taiwanese firms"]
TW_NEGATIVE = ["台灣出口衰退、台股重挫、企業虧損、關稅與地緣風險升高、利空台灣",
               "Taiwan exports slump, TAIEX plunges, tariffs and geopolitical risks hit Taiwan"]
_SUMMARY_CHARS = 300
_encoders: dict = {}
_clf: dict | None = None
_tw_axis: np.ndarray | None = None
_tw_cal: dict | None = None


def article_text(title: str, summary: str = "") -> str:
    """Model input: title plus the start of the feed summary when there is one."""
    summary = re.sub(r"\s+", " ", summary or "").strip()[:_SUMMARY_CHARS]
    return f"{title}. {summary}" if summary else title


def _encoder(model: str):
    if model not in _encoders:
        import torch
        from sentence_transformers import SentenceTransformer
        # float32: these checkpoints default to bf16, which is ~5x slower on CPU
        enc = SentenceTransformer(model, device="cpu", model_kwargs={"dtype": torch.float32})
        enc.max_seq_length = _MODELS[model][1]
        _encoders[model] = enc
    return _encoders[model]


def _embed(texts: list[str], model: str = _MODEL_NAME) -> np.ndarray:
    """Normalised embeddings, read from / written to the SQLite cache."""
    prefix = _MODELS[model][0]
    keys = [hashlib.sha1((prefix + t).encode("utf-8")).hexdigest() for t in texts]
    REL_DIR.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(EMB_DB)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS emb (model TEXT, key TEXT, vec BLOB, PRIMARY KEY (model, key))")
        found: dict[str, np.ndarray] = {}
        uniq = list(dict.fromkeys(keys))
        for i in range(0, len(uniq), 500):
            chunk = uniq[i:i + 500]
            q = f"SELECT key, vec FROM emb WHERE model = ? AND key IN ({','.join('?' * len(chunk))})"
            for k, v in db.execute(q, [model, *chunk]):
                found[k] = np.frombuffer(v, dtype=np.float32)
        missing = [(k, t) for k, t in dict(zip(keys, texts)).items() if k not in found]
        if missing:
            vecs = _encoder(model).encode([prefix + t for _, t in missing], normalize_embeddings=True,
                                          batch_size=16, show_progress_bar=False).astype(np.float32)
            db.executemany("INSERT OR REPLACE INTO emb VALUES (?, ?, ?)",
                           [(model, k, v.tobytes()) for (k, _), v in zip(missing, vecs)])
            db.commit()
            found.update({k: v for (k, _), v in zip(missing, vecs)})
    return np.array([found[k] for k in keys])


def _load_clf(path: Path) -> dict | None:
    """A classifier is only usable with the embedding models it was trained on."""
    if not path.exists():
        return None
    clf = json.loads(path.read_text(encoding="utf-8"))
    trained = [m["model"] for m in clf.get("models", [])]
    if trained != list(_MODELS):
        logger.warning("%s 是以 %s 訓練，與目前模型 %s 不符，請重訓", path.name, trained, list(_MODELS))
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
    Returns {"econ": [P(qualified), mean over the ensemble], "tw_axis": [raw projection on
    the Taiwan axis]}; None when no relevance classifier is available."""
    global _clf
    if _clf is None:
        _clf = _load_clf(CLF_PATH)
        if _clf is None:
            return None
    if not items:
        return {"econ": [], "tw_axis": []}
    texts = [article_text(t, s) for t, s in items]
    probs, tw = [], None
    for m in _clf["models"]:
        X = _embed(texts, m["model"])
        probs.append(1 / (1 + np.exp(-(X @ np.array(m["coef"]) + m["intercept"]))))
        if m["model"] == _MODEL_NAME:
            tw = X @ tw_axis_vector()
    return {"econ": np.mean(probs, axis=0).tolist(), "tw_axis": tw.tolist()}


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
    texts = [article_text(t, summaries.get(t, "")) for t in titles]
    mk = lambda: LogisticRegression(C=C, max_iter=3000, class_weight="balanced")
    models, oof = [], []
    for name in _MODELS:
        X = _embed(texts, name)
        p_m = cross_val_predict(mk(), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0),
                                method="predict_proba")[:, 1]
        print(f"[relevance] {name}: cv_auc={roc_auc_score(y, p_m):.3f}")
        oof.append(p_m)
        clf = mk().fit(X, y)
        models.append({"model": name, "coef": clf.coef_[0].tolist(), "intercept": float(clf.intercept_[0])})
    p = np.mean(oof, axis=0)
    print(f"[relevance] samples={len(y)} non_finance={(y == 0).sum()} ensemble cv_auc={roc_auc_score(y, p):.3f}")
    for thr in (0.3, 0.4, 0.5, 0.6):
        print(f"  thr={thr}: finance kept {(p[y == 1] >= thr).mean():.1%}, "
              f"non-finance dropped {(p[y == 0] < thr).mean():.1%}")
    CLF_PATH.write_text(json.dumps({"models": models, "n": int(len(y))}), encoding="utf-8")
    print("saved", CLF_PATH)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    train()
