"""
STDV — Standard Deviation Projections
=====================================
Manba: docs/STDV/ (YugiohFX slaydlari), treyder bilan kelishilgan 2026-07-08.

MANTIQ
------
Narx Smart Money Reversal (SMR / po3) yasaganda, biz MANIPULYATSIYA OYOG'ini
qidiramiz — bu strukturani o'zgartirishdan oldin likvidlikni supurib tashlagan
tebranish. O'sha oyoqni o'lchab, uni standart deviatsiyalar bilan kengaytiramiz
va keyingi harakat qayerga borishini proyeksiya qilamiz.

  0 daraja = manipulyatsiya oyog'ining BOSHI (oyoq qayerdan boshlangan)
  1 daraja = manipulyatsiya oyog'ining UCHI (purge wick — likvidlik olingan nuqta)
  oyoq     = |1 - 0|

Keyin narx teskari yo'nalishda 0 dan o'tib, manfiy darajalarga intiladi:

  -2, -2.5, -4   (slaydlarda shu uchtasi yoqilgan)

  -4 = odatda yakuniy maqsad; slayd: "narx -4 darajaga kelganida biz ko'p
       hollarda narxda REVERSAL kutamiz".
  Slayd 4: "STDV -4 bizga narx hali targetga yetib kelmaganini signal beryapti,
       bundan foydalanib -4 darajagacha savdo amaliyotini amalga oshirish mumkin".

CRT'GA BOG'LANISHI
------------------
CRT'da manipulyatsiya oyog'i = purge (sweep) harakati:
  bearish_sweep (high supurildi): oyoq YUQORIGA ketgan
      1 = purge shamining high'i
      0 = o'sha ko'tarilishni boshlagan low (purge'dan oldingi eng past nuqta)
      maqsadlar = 0 dan PASTGA:  zero - n*leg
  bullish_sweep — to'liq teskari.

Bu 1R/2R/3R kabi o'ylab topilgan raqamlardan farqli — maqsad bozorning
o'z harakatidan kelib chiqadi.
"""

from __future__ import annotations

import pandas as pd

# Slaydlarda yoqilgan darajalar (Fib Retracement sozlamalari: -2, -2.5, -4)
STDV_LEVELS = (2.0, 2.5, 4.0)

# Manipulyatsiya oyog'ini qidirish chuqurligi (purge shamigacha bo'lgan shamlar)
STDV_LOOKBACK = 12


def _level_key(n: float) -> str:
    """2.5 -> 'stdv_2_5'  |  4.0 -> 'stdv_4'"""
    s = f"{n:g}".replace(".", "_")
    return f"stdv_{s}"


def compute_stdv(df: pd.DataFrame, purge_time, direction: str,
                 lookback: int = STDV_LOOKBACK,
                 levels: tuple = STDV_LEVELS) -> dict | None:
    """
    Purge shamiga qarab manipulyatsiya oyog'ini o'lchab, STDV proyeksiyalarini
    qaytaradi.

    df          — vaqt bo'yicha o'sish tartibidagi shamlar (time_ny ustuni bilan)
    purge_time  — purge (sweep) shamining vaqti; str yoki Timestamp
    direction   — "bullish_sweep" | "bearish_sweep"

    Qaytaradi:
        {"zero": float, "one": float, "leg": float,
         "levels": {"stdv_2": px, "stdv_2_5": px, "stdv_4": px}}
        yoki None (oyoq topilmasa / nol uzunlik bo'lsa).
    """
    if df is None or df.empty or "time_ny" not in df.columns:
        return None

    times = df["time_ny"]
    match = times[times.astype(str) == str(purge_time)]
    if match.empty:
        return None
    i = df.index.get_loc(match.index[0])

    start = max(0, i - lookback + 1)
    seg = df.iloc[start:i + 1]
    if len(seg) < 2:
        return None

    highs = seg["high"].values
    lows = seg["low"].values

    if direction == "bearish_sweep":
        # Oyoq YUQORIGA: uchi = eng baland high (purge wick)
        tip_idx = int(highs.argmax())
        one = float(highs[tip_idx])
        # Boshi = o'sha uchgacha bo'lgan eng past low
        zero = float(lows[:tip_idx + 1].min())
        sign = -1  # maqsadlar 0 dan pastda
    elif direction == "bullish_sweep":
        # Oyoq PASTGA: uchi = eng past low (purge wick)
        tip_idx = int(lows.argmin())
        one = float(lows[tip_idx])
        zero = float(highs[:tip_idx + 1].max())
        sign = 1  # maqsadlar 0 dan yuqorida
    else:
        return None

    leg = abs(one - zero)
    if leg <= 0:
        return None

    return {
        "zero": zero,
        "one": one,
        "leg": leg,
        "levels": {_level_key(n): zero + sign * n * leg for n in levels},
    }


def stdv_text(stdv: dict | None, digits: int = 5) -> str:
    """Telegram xabari uchun qisqa matn."""
    if not stdv:
        return ""
    lv = stdv["levels"]
    parts = [f"{k.replace('stdv_', '-').replace('_', '.')}={v:.{digits}f}"
             for k, v in lv.items()]
    return "• STDV maqsad: " + " | ".join(parts)
