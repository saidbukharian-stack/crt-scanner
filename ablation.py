"""
Ablation logging — har signalning (qabul + rad) va filtr natijalarining jurnali
==============================================================================
Maqsad: qaysi filtr foydali, qaysi biri yaxshi signallarni "o'ldirayotganini"
o'lchash. HAR topilgan signal (qabul qilingan ham, rad etilgan ham) shu yerga
yoziladi; har filtr alohida (pass/fail) baholanadi.

Rad etilgan signal Telegram/paper_account'ga BORMAYDI — faqat shu jurnalga
va yengil "shadow" kuzatuvga (m5_cisd bo'yicha xayoliy natija).

signals_log.csv o'zi dedup manbai: bir signal_id bir marta yoziladi.
"""

import csv
import hashlib
import logging
import os

from config import DB_PATH

logger = logging.getLogger(__name__)

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
SIGNALS_LOG_CSV = os.path.join(RESULTS_DIR, "signals_log.csv")

COLUMNS = [
    "signal_id", "timestamp_utc", "symbol", "direction", "level_type",
    "sweep_wick_pct", "cisd_confirmed",
    "filter_pd", "filter_qt", "filter_qt_phase", "filter_mo_bias", "filter_hrl",
    "final_verdict", "rejected_by", "source",
    "shadow_outcome_r",
    # Vazifa 4 uchun oldindan joy (hozircha bo'sh)
    "llm_score", "llm_confidence", "llm_counter_argument",
]

_seen: set | None = None  # yozilgan signal_id'lar (dedup uchun, CSV'dan yuklanadi)


def make_signal_id(symbol: str, condition: str, level_name: str,
                   direction: str, sweep_time: str) -> str:
    """Deterministik qisqa ID (mavjud dedup kaliti bilan bir xil semantika)."""
    day = str(sweep_time)[:10]
    raw = f"{symbol}|{condition}|{level_name}|{direction}|{day}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def level_type(level_name: str) -> str:
    """Daraja nomidan turini ajratadi (PDH -> PD, CRT_9AM_.. -> CRT, ...)."""
    for pref in ("PDH", "PDL"):
        if level_name.startswith(pref):
            return "PD"
    for pref in ("Asia", "London", "CRT", "NWOG", "NDOG", "IPDA"):
        if level_name.startswith(pref):
            return pref if pref not in ("CRT",) else "CRT"
    return level_name.split("_")[0]


def _load_seen() -> set:
    global _seen
    if _seen is not None:
        return _seen
    _seen = set()
    if os.path.exists(SIGNALS_LOG_CSV):
        try:
            with open(SIGNALS_LOG_CSV, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    sid = row.get("signal_id")
                    if sid:
                        _seen.add(sid)
        except (OSError, csv.Error):
            pass
    return _seen


def already_logged(signal_id: str) -> bool:
    return signal_id in _load_seen()


def log_signal(row: dict):
    """Bitta signal qatorini qo'shadi (agar shu signal_id hali yozilmagan bo'lsa)."""
    sid = row.get("signal_id", "")
    seen = _load_seen()
    if sid in seen:
        return
    os.makedirs(RESULTS_DIR, exist_ok=True)
    exists = os.path.exists(SIGNALS_LOG_CSV)
    full = {c: row.get(c, "") for c in COLUMNS}
    with open(SIGNALS_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if not exists:
            w.writeheader()
        w.writerow(full)
    seen.add(sid)


def _rewrite(rows: list[dict]):
    with open(SIGNALS_LOG_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def update_fields(signal_id: str, updates: dict):
    """signal_id bo'yicha qatorni topib, berilgan ustunlarni to'ldiradi (CSV qayta yoziladi)."""
    if not os.path.exists(SIGNALS_LOG_CSV):
        return False
    try:
        with open(SIGNALS_LOG_CSV, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except (OSError, csv.Error):
        return False
    changed = False
    for r in rows:
        if r.get("signal_id") == signal_id:
            for k, v in updates.items():
                if k in COLUMNS:
                    r[k] = v
            changed = True
            break
    if changed:
        _rewrite(rows)
    return changed


def update_shadow(signal_id: str, r_value):
    """Rad etilgan signalning shadow (m5_cisd) natijasini yozadi."""
    return update_fields(signal_id, {"shadow_outcome_r": round(float(r_value), 3)})
