"""
IPDA — Interbank Price Delivery Algorithm data ranges (ICT)
==========================================================
Manba: ICT Mentorship Core Content Month 05/07 (IPDA Data Ranges).
Qo'shildi 2026-07-11.

G'oya: IPDA (institutsional narx yetkazish algoritmi) narxni oxirgi
**20 / 40 / 60 savdo kuni** oralig'iga qarab yetkazadi. Shu oynalardagi
eng baland high va eng past low = ahamiyatli likvidlik (draw on liquidity):
  - 20 kun — qisqa muddat (asosiy)
  - 40 kun — o'rta
  - 60 kun — uzoq (undan eskisi ahamiyatsiz)

Bu darajalar PDH/PDL kabi sweep signali beradi va likvidlik maqsadi bo'ladi.
"""

from __future__ import annotations

import pandas as pd

from levels import Level

IPDA_LOOKBACKS = (20, 40, 60)


def ipda_levels(df_d1: pd.DataFrame,
                lookbacks: tuple = IPDA_LOOKBACKS) -> list[Level]:
    """
    D1 shamlar asosida IPDA 20/40/60 kunlik eng baland high / eng past low
    darajalarini qaytaradi (juftlangan: qarshi cheti = likvidlik maqsadi).

    Joriy (oxirgi, hali yopilmagan) sham hisobga OLINMAYDI - faqat yopilgan
    kunlar (df_d1[:-1]).
    """
    if len(df_d1) < 2:
        return []
    closed = df_d1.iloc[:-1]           # oxirgisi - joriy kun, tashlab yuboramiz
    date_str = df_d1.iloc[-1]["time_ny"].strftime("%Y-%m-%d")
    levels: list[Level] = []
    seen: set[tuple[str, float]] = set()
    for lb in lookbacks:
        seg = closed.tail(lb)
        if len(seg) < 2:
            continue
        hi = float(seg["high"].max())
        lo = float(seg["low"].min())
        # bir xil narx (masalan 20 va 40 bir xil ekstremum) - takrorlamaymiz
        if ("high", hi) not in seen:
            levels.append(Level(f"IPDA{lb}_High", hi, "high", date_str, None, lo))
            seen.add(("high", hi))
        if ("low", lo) not in seen:
            levels.append(Level(f"IPDA{lb}_Low", lo, "low", date_str, None, hi))
            seen.add(("low", lo))
    return levels
