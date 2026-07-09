"""
QT — Quarterly Theory (Daye / Traderdad)
========================================
Manba: docs/QT_Education.pdf, Triad "Quarterly Theory". Qo'shildi 2026-07-09.

G'oya: vaqt fraktal ravishda CHORAKLARGA bo'linadi va har chorakда AMD(X)
fazasi takrorlanadi:
  Accumulation → Manipulation → Distribution → Continuation/Reversal

KUNLIK CHORAKLAR (NY vaqti, "haqiqiy kun" 18:00 da ochiladi):
  Q1  18:00–00:00  Osiyo        — Accumulation (yig'ish, tor diapazon)
  Q2  00:00–06:00  London       — Manipulation (Judas, likvidlik supurish)
  Q3  06:00–12:00  NY AM        — Distribution (asosiy harakat, trend)
  Q4  12:00–18:00  NY PM        — Continuation/Reversal

SAVDO MANTIG'I: reversal/sweep setuplar MANIPULATION (Q2) da tug'iladi,
harakat DISTRIBUTION (Q3) da yoyiladi. Shuning uchun signallarни shu ikki
fazaga filtrlaymiz — Accumulation (Osiyo, tor) va kech Continuation (NY PM,
ko'pincha chalkash) ni chetlab o'tamiz.

Har 6 soatlik chorak yana 4 ta 90-daqiqalik kichik chorakka bo'linadi (shu
ichida ham AMD takrorlanadi) — buni tahlil/log uchun qaytaramiz.
"""

from __future__ import annotations

_DAY_OPEN_HOUR = 18  # NY "haqiqiy kun" ochilishi

_PHASES = [
    (1, "Asia", "Accumulation"),
    (2, "London", "Manipulation"),
    (3, "NY_AM", "Distribution"),
    (4, "NY_PM", "Continuation"),
]

# Sweep/reversal setuplar uchun ma'qul fazalar
FAVORED_PHASES = ("Manipulation", "Distribution")


def _to_naive_ny(dt):
    """tz-aware NY yoki naive datetime → naive NY datetime."""
    if getattr(dt, "tzinfo", None) is not None:
        return dt.replace(tzinfo=None)
    return dt


def daily_quarter(dt_ny) -> tuple[int, str, str]:
    """
    Kunlik chorak: (raqam 1-4, sessiya nomi, faza).
    dt_ny — NY vaqti (tz-aware yoki naive).
    """
    dt = _to_naive_ny(dt_ny)
    h = (dt.hour - _DAY_OPEN_HOUR) % 24
    idx = h // 6  # 0..3
    return _PHASES[idx]


def session_90m_quarter(dt_ny) -> int:
    """6 soatlik chorak ichidagi 90-daqiqalik kichik chorak (1-4)."""
    dt = _to_naive_ny(dt_ny)
    h = (dt.hour - _DAY_OPEN_HOUR) % 24
    minutes_into_q = (h % 6) * 60 + dt.minute
    return minutes_into_q // 90 + 1  # 1..4


def qt_phase(dt_ny) -> dict:
    """To'liq QT konteksti: {quarter, session, phase, sub_quarter, favored}."""
    q, session, phase = daily_quarter(dt_ny)
    return {
        "quarter": q,
        "session": session,
        "phase": phase,
        "sub_quarter": session_90m_quarter(dt_ny),
        "favored": phase in FAVORED_PHASES,
    }


def qt_favored(dt_ny) -> bool:
    """Signal QT bo'yicha ma'qul fazadami (Manipulation yoki Distribution)?"""
    return daily_quarter(dt_ny)[2] in FAVORED_PHASES
