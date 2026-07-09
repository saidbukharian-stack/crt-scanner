"""
OTE — Optimal Trade Entry (ICT)
===============================
Manba: ICT YouTube tutoriallari (docs/transcripts/ict_batch/), ayniqsa
"OTE Pattern Recognition Series Vol.01" (E9F_aT9f038). Qo'shildi 2026-07-09.

ICT'ning o'z ta'rifi (mexanik qoidalar):
  1. Kontekst: narx PDH/PDL dan o'tadi (yoki qisqa struktura sinadi = MSS).
  2. Impuls oyog'iga (strukturани buzgan harakat) Fibonacci tortiladi.
  3. KIRISH ZONASI = 62%–79% retracement (eng shirin nuqta 70.5%).
     62% limit sifatida ishlatiladi (spread'ga kengroq).
  4. Stop = impuls boshlangan swing chetidan tashqarida.
  5. Maqsad = fib kengaytmalari (-0.5 / -1 / -2 standart deviatsiya) + likvidlik.
  6. VAQT filtri = 08:30–11:00 NY (news + volatillik "spool" bo'ladi).

Bizning tizimda: purge (sweep) -> M5 CISD (= MSS tasdig'i) shakllangач,
darrov kirmaymiz - impuls oyog'iga fib tortib, narx 62-79% ga QAYTIB
kelishini (retracement) kutamiz. Bu CISD close'da kirishdan aniqroq narx,
kattaroq R (stop bir xil - swing cheti).

Maqsadlar CRT/likvidlik bilan bir xil qoladi (treyder qarori: maqsad=likvidlik)
- OTE faqat KIRISHni yaxshilaydi. Shunda m5_cisd vs m5_ote = toza A/B:
"OTE retracement kirishi natijani yaxshiladimi?"
"""

from __future__ import annotations

from datetime import time as dtime

import pandas as pd

# OTE retracement zonasi (impuls oyog'idan)
OTE_ENTRY_FIB = 0.62   # kirish (limit) - 62%
OTE_DEEP_FIB = 0.79    # zonaning chuqur cheti - 79%

# OTE vaqt oynasi (NY) - ICT: 08:30-11:00 (news session, killzone emas)
OTE_WINDOW = (dtime(8, 30), dtime(11, 0))


def ote_zone(df_m5: pd.DataFrame, purge_time, direction: str, cisd: dict,
             entry_fib: float = OTE_ENTRY_FIB,
             deep_fib: float = OTE_DEEP_FIB) -> dict | None:
    """
    CISD shakllangач impuls oyog'iga fib tortib OTE zonasini qaytaradi.

    cisd - detect_cisd natijasi: {"entry","entry_time","stop"}.
      stop = impuls boshlangan swing cheti (bullish'da swing_low, bearish'da swing_high).

    Qaytaradi:
      {"entry": 62% narx, "stop": swing cheti, "zone_lo", "zone_hi", "disp"}
      yoki None (oyoq topilmasa / nol uzunlik).
    """
    after = df_m5[df_m5["time_ny"] > purge_time].reset_index(drop=True)
    if after.empty:
        return None
    et = str(cisd["entry_time"])
    mask = after["time_ny"].astype(str) == et
    if not mask.any():
        return None
    ei = int(mask.idxmax())
    seg = after.iloc[: ei + 1]
    if len(seg) < 2:
        return None

    if direction == "bullish_sweep":
        swing = float(cisd["stop"])               # swing_low = oyoq boshi
        disp = float(seg["high"].max())           # displacement uchi (yuqori)
        leg = disp - swing
        if leg <= 0:
            return None
        entry = disp - entry_fib * leg            # 62% (yuqoriroq narx)
        zone_hi = entry
        zone_lo = disp - deep_fib * leg           # 79% (pastroq narx)
    elif direction == "bearish_sweep":
        swing = float(cisd["stop"])               # swing_high = oyoq boshi
        disp = float(seg["low"].min())            # displacement uchi (past)
        leg = swing - disp
        if leg <= 0:
            return None
        entry = disp + entry_fib * leg            # 62% (pastroq narx)
        zone_lo = entry
        zone_hi = disp + deep_fib * leg           # 79% (yuqoriroq narx)
    else:
        return None

    return {"entry": entry, "stop": swing, "zone_lo": zone_lo,
            "zone_hi": zone_hi, "disp": disp}


def in_ote_window(candle_time) -> bool:
    """Sham vaqti (tz-aware NY) OTE oynasiga (08:30-11:00 NY) tushadimi."""
    t = candle_time.tz_localize(None).time() if hasattr(candle_time, "tz_localize") \
        else candle_time.time()
    return OTE_WINDOW[0] <= t < OTE_WINDOW[1]


# ---------------------------------------------------------------------------
# Institutsional yaxlit darajalar (00/20/50/80) - aniqlik filtri
# ICT: yirik fondlar orderlarini yaxlit darajalarga qo'yadi. Sweep shu
# darajalar yaqinida bo'lsa - "sifatliroq" signal.
# ---------------------------------------------------------------------------
_ROUND_SUBLEVELS = (0.0, 20.0, 50.0, 80.0, 100.0)  # "pip" ichidagi nuqtalar


def _figure_size(price: float) -> float:
    """Narx kattaligidan "katta figura" (00-level qadami) ni taxminlaydi."""
    ap = abs(price)
    if ap < 20:      # FX majors (1.18, 0.65) - figura 0.01
        return 0.01
    if ap < 500:     # JPY (150), ba'zi CFD - figura 1.0
        return 1.0
    return 10.0      # oltin/indekslar (2000, 15000) - figura 10


def near_institutional_level(price: float, tol_frac: float = 0.10) -> bool:
    """
    Narx yaxlit institutsional darajaga (00/20/50/80) yaqinmi?
    tol_frac - figura ulushida bag'rikenglik (0.10 = figuraning 10%, ICT ±10 pip).
    Taxminiy - instrumentga qarab moslashtirilishi mumkin.
    """
    fig = _figure_size(price)
    pos = (price % fig) / fig * 100.0   # 0..100 "pip" figura ichida
    tol = tol_frac * 100.0
    return any(abs(pos - lvl) <= tol for lvl in _ROUND_SUBLEVELS)
