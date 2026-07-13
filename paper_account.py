"""
Paper Account — xayoliy hisob
=============================
Forward-test natijalarini R o'rniga DOLLARDA o'lchash uchun.
Treyder bilan kelishilgan (2026-07-08): boshlang'ich $5000, har savdoga 1% risk.

Har VARIANT uchun ALOHIDA balans yuritiladi (raw / m5_cisd / m5_managed) —
shunda uchta strategiyaning equity egri chizig'ini yonma-yon solishtirish mumkin.

Pozitsiya hajmi hisoblanmaydi (lot/kontrakt) — bunga hojat yo'q:
    P&L = risk_usd * net_R
Bu instrumentdan mustaqil va aniq. risk_usd savdo OCHILGANDA qulflanadi
(o'sha paytdagi balansning 1%), keyin balans yangilanadi.
"""

import json
import logging
import os

from config import DATA_SOURCE, DB_PATH, PAPER_RISK_PCT, PAPER_START_BALANCE

logger = logging.getLogger(__name__)

# MANBA IZOLYATSIYASI (Vazifa 5): har narx manbasi (mt5/yahoo/oanda) o'z
# balans faylini yuritadi - MT5 va Yahoo P&L'i hech qachon aralashmaydi
# (narx/sessiya farqlari sweep aniqlashga ta'sir qiladi, taqqoslab bo'lmaydi).
_ACCOUNT_PATH = os.path.join(os.path.dirname(DB_PATH),
                             f"paper_account_{DATA_SOURCE}.json")

# "raw" olib tashlandi (2026-07-09): xom purge barcha o'lchovda minusda edi.
# m5_ote (2026-07-09) OTE 62-79% retracement; m5_sb Silver Bullet FVG,
# m1_ote M1 micro-kirish (2026-07-11).
VARIANTS = ("m5_cisd", "m5_managed", "m5_ote", "m5_sb", "m1_ote")


def _load() -> dict:
    try:
        with open(_ACCOUNT_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    for v in VARIANTS:
        data.setdefault(v, PAPER_START_BALANCE)
    return data


def _save(data: dict):
    os.makedirs(os.path.dirname(_ACCOUNT_PATH), exist_ok=True)
    with open(_ACCOUNT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def balance(variant: str) -> float:
    return _load().get(variant, PAPER_START_BALANCE)


def risk_usd(variant: str) -> float:
    """Savdo ochilayotgan paytdagi risk summasi = balansning PAPER_RISK_PCT %."""
    return round(balance(variant) * PAPER_RISK_PCT / 100.0, 2)


def apply_pnl(variant: str, net_r: float, risk_amount: float) -> tuple[float, float]:
    """
    Savdo yakunlanganda balansni yangilaydi.
    Qaytaradi: (pnl_usd, yangi_balans)
    """
    pnl = round(risk_amount * net_r, 2)
    data = _load()
    data[variant] = round(data.get(variant, PAPER_START_BALANCE) + pnl, 2)
    _save(data)
    return pnl, data[variant]


def summary() -> str:
    """Telegram uchun qisqa hisobot."""
    data = _load()
    labels = {"m5_cisd": "M5 CISD (boshqaruvsiz)", "m5_managed": "M5 + boshqaruv",
              "m5_ote": "M5 OTE (62-79% kirish)", "m5_sb": "M5 Silver Bullet",
              "m1_ote": "M1 OTE (micro)"}
    lines = [f"💰 <b>Xayoliy hisob</b> — manba: {DATA_SOURCE.upper()} "
             f"(boshlang'ich ${PAPER_START_BALANCE:,.0f}, risk {PAPER_RISK_PCT}%)"]
    for v in VARIANTS:
        bal = data.get(v, PAPER_START_BALANCE)
        pct = (bal - PAPER_START_BALANCE) / PAPER_START_BALANCE * 100
        lines.append(f"• {labels[v]}: ${bal:,.2f} ({pct:+.2f}%)")
    return "\n".join(lines)
