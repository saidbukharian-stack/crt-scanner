"""
Silver Bullet — ICT vaqt-oynali FVG kirish modeli
=================================================
Manba: ICT 2023 Mentorship "Silver Bullet Time Based Trading Model".
Qo'shildi 2026-07-11.

Silver Bullet = QAT'IY 1 soatlik oynada FVG'ga kirish:
  - 03:00–04:00 NY (London SB)
  - 10:00–11:00 NY (NY AM SB) — eng mashhuri
  - 14:00–15:00 NY (NY PM SB)

Mexanika: likvidlik olinadi (bizda = sweep/purge) → narx displacement bilan
FVG qoldiradi → o'sha FVG'ga qaytishда kirish → maqsad likvidlik.

Bizning tizimda m5_ote bilan bir xil ikki-bosqichli hayot sikli, faqat:
  - kirish zonasi = FVG (62-79% retracement emas)
  - vaqt oynasi = Silver Bullet soatlari (08:30-11:00 emas)
"""

from __future__ import annotations

from datetime import time as dtime

import pandas as pd

# Silver Bullet oynalari (NY soatlari, [boshlanish, tugash))
SB_WINDOWS = ((dtime(3, 0), dtime(4, 0)),
              (dtime(10, 0), dtime(11, 0)),
              (dtime(14, 0), dtime(15, 0)))


def in_sb_window(candle_time) -> bool:
    """Sham vaqti (tz-aware NY) Silver Bullet oynalaridan biriga tushadimi?"""
    t = candle_time.tz_localize(None).time() if hasattr(candle_time, "tz_localize") \
        else candle_time.time()
    return any(s <= t < e for s, e in SB_WINDOWS)


def sb_fvg_zone(df_m5: pd.DataFrame, purge_time, direction: str,
                cisd: dict) -> dict | None:
    """
    Purge'dan keyin savdo yo'nalishidagi BIRINCHI displacement FVG'ni topib,
    kirish zonasini qaytaradi (ote_zone bilan bir xil format).

    bullish: bullish FVG (high[i-2] < low[i]); kirish = FVG yuqori cheti
             (pullback'да birinchi tegiladi), stop = swing_low (cisd stop).
    bearish: bearish FVG (low[i-2] > high[i]); kirish = FVG past cheti,
             stop = swing_high.
    Qaytaradi: {"entry","stop","zone_lo","zone_hi"} yoki None.
    """
    after = df_m5[df_m5["time_ny"] > purge_time].reset_index(drop=True)
    if len(after) < 3:
        return None
    h = after["high"].values
    lo = after["low"].values
    swing = float(cisd["stop"])

    if direction == "bullish_sweep":
        for i in range(2, len(after)):
            if h[i - 2] < lo[i]:                 # bullish FVG
                gap_lo, gap_hi = float(h[i - 2]), float(lo[i])
                return {"entry": gap_hi, "stop": swing,
                        "zone_lo": gap_lo, "zone_hi": gap_hi}
    elif direction == "bearish_sweep":
        for i in range(2, len(after)):
            if lo[i - 2] > h[i]:                 # bearish FVG
                gap_lo, gap_hi = float(h[i]), float(lo[i - 2])
                return {"entry": gap_lo, "stop": swing,
                        "zone_lo": gap_lo, "zone_hi": gap_hi}
    return None
