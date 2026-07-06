"""
Analysis — key level (FVG/OB), order flow, DOL, SMT
====================================================
Bozor suratini boyituvchi mexanik tahlil modullari. Har biri PDF/transkript
qoidalariga asoslangan va matn (LLM uchun) qaytaradi.

Barcha funksiyalar sof mexanik — bashorat yo'q, faqat joriy holatni aniqlash.
"""

import logging

import pandas as pd

from config import SMT_PAIRS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Swing nuqtalar (order flow va SMT uchun asos)
# ---------------------------------------------------------------------------
def _swings(df: pd.DataFrame, width: int = 2):
    """
    Fraktal swing high/low nuqtalarini topadi (chap/o'ng `width` sham).
    Qaytaradi: (highs, lows) - har biri (indeks, narx) ro'yxati.
    """
    highs, lows = [], []
    h = df["high"].values
    lo = df["low"].values
    n = len(df)
    for i in range(width, n - width):
        if h[i] == max(h[i - width:i + width + 1]) and h[i] > h[i - 1]:
            highs.append((i, float(h[i])))
        if lo[i] == min(lo[i - width:i + width + 1]) and lo[i] < lo[i - 1]:
            lows.append((i, float(lo[i])))
    return highs, lows


# ---------------------------------------------------------------------------
# 1. Order flow (DOL PDF: high buzib low'dan qaytish = bullish, aksincha bearish)
# ---------------------------------------------------------------------------
def order_flow(df_h4: pd.DataFrame) -> str:
    """H4 struktura bo'yicha order flow: bullish / bearish / neytral."""
    recent = df_h4.tail(30)
    highs, lows = _swings(recent)
    if len(highs) < 2 or len(lows) < 2:
        return "neytral (struktura aniq emas)"
    hh = highs[-1][1] > highs[-2][1]   # higher high
    hl = lows[-1][1] > lows[-2][1]     # higher low
    lh = highs[-1][1] < highs[-2][1]   # lower high
    ll = lows[-1][1] < lows[-2][1]     # lower low
    if hh and hl:
        return "bullish (higher high + higher low)"
    if lh and ll:
        return "bearish (lower high + lower low)"
    if hh and ll:
        return "neytral/kengaymoqda (HH lekin LL - ekspansiya)"
    return "neytral (aralash struktura)"


# ---------------------------------------------------------------------------
# 2. DOL (Draw on Liquidity) - narx qaysi likvidlikka tortiladi
#    DOL PDF: close/wick qoidalari + order flow
# ---------------------------------------------------------------------------
def draw_on_liquidity(df_d1: pd.DataFrame, of: str, pdh: float | None,
                      pdl: float | None) -> str:
    """Kunlik sham close/wick va order flow asosida ehtimoliy DOL."""
    if len(df_d1) < 2:
        return "aniqlab bo'lmadi (kunlik ma'lumot kam)"
    # oxirgi to'liq kunlik sham (yahoo'da oxirgisi joriy kun bo'lishi mumkin)
    cur = df_d1.iloc[-1]
    prev = df_d1.iloc[-2]
    o, c, hi, lo = cur["open"], cur["close"], cur["high"], cur["low"]
    body_top, body_bot = max(o, c), min(o, c)
    upper_wick = hi - body_top
    lower_wick = body_bot - lo
    body = abs(c - o) or 1e-9

    note = []
    # close prev high/low ga nisbatan
    if c > prev["high"]:
        note.append("kunlik oldingi high ustida yopildi → yuqori narx")
        target = pdh
        direction = "yuqori (buy-side)"
    elif c < prev["low"]:
        note.append("kunlik oldingi low ostida yopildi → past narx")
        target = pdl
        direction = "past (sell-side)"
    else:
        # ichkarida yopildi - order flow yo'nalishida davom
        if of.startswith("bullish"):
            note.append("ichkarida yopildi + bullish OF → avval PDL, keyin yuqori")
            target = pdl
            direction = "avval past, keyin yuqori"
        elif of.startswith("bearish"):
            note.append("ichkarida yopildi + bearish OF → avval PDH, keyin past")
            target = pdh
            direction = "avval yuqori, keyin past"
        else:
            target = None
            direction = "aniq emas"

    # katta wick = teskari yo'nalish ishorasi
    if upper_wick > 1.5 * body:
        note.append("katta yuqori wick (rad etish) → past narx ehtimoli")
    if lower_wick > 1.5 * body:
        note.append("katta pastki wick (rad etish) → yuqori narx ehtimoli")

    tgt_str = f"{target:.5f}" if target else "aniqlanmadi"
    return f"yo'nalish: {direction}; ehtimoliy DOL darajasi: {tgt_str}. " + "; ".join(note)


# ---------------------------------------------------------------------------
# 3. FVG (Fair Value Gap) + Order Block
#    FVG: 3-sham imbalance. Bullish: sham[i-2].high < sham[i].low
# ---------------------------------------------------------------------------
def find_fvgs(df: pd.DataFrame, price: float, max_count: int = 4) -> list[str]:
    """To'ldirilmagan va narxga yaqin FVG'larni topadi (matn ro'yxati)."""
    h = df["high"].values
    lo = df["low"].values
    t = df["time_ny"].values
    fvgs = []
    n = len(df)
    for i in range(2, n):
        # Bullish FVG: [i-2] high < [i] low
        if h[i - 2] < lo[i]:
            gap_lo, gap_hi = float(h[i - 2]), float(lo[i])
            filled = df["low"].values[i:].min() <= gap_lo
            if not filled:
                fvgs.append(("bullish", gap_lo, gap_hi, t[i]))
        # Bearish FVG: [i-2] low > [i] high
        if lo[i - 2] > h[i]:
            gap_lo, gap_hi = float(h[i]), float(lo[i - 2])
            filled = df["high"].values[i:].max() >= gap_hi
            if not filled:
                fvgs.append(("bearish", gap_lo, gap_hi, t[i]))

    # narxga eng yaqinlarini tanlaymiz
    fvgs.sort(key=lambda f: min(abs(price - f[1]), abs(price - f[2])))
    out = []
    for kind, glo, ghi, when in fvgs[:max_count]:
        rel = "yuqorida" if glo > price else ("pastda" if ghi < price else "narx ichida")
        out.append(f"{kind} FVG {glo:.5f}-{ghi:.5f} ({rel})")
    return out


def find_order_block(df: pd.DataFrame, of: str) -> str:
    """
    Oddiy OB: ekspansiyadan oldingi qarama-qarshi rangdagi oxirgi sham.
    Bullish OF'da - oxirgi down-close sham; bearish'da - oxirgi up-close.
    """
    recent = df.tail(20).reset_index(drop=True)
    o = recent["open"].values
    c = recent["close"].values
    hi = recent["high"].values
    lo = recent["low"].values
    if of.startswith("bullish"):
        # oxirgidan orqaga: oxirgi down-close (c<o) shamni topamiz
        for i in range(len(recent) - 2, -1, -1):
            if c[i] < o[i]:
                return f"bullish OB (oxirgi down-close): {lo[i]:.5f}-{hi[i]:.5f}"
    elif of.startswith("bearish"):
        for i in range(len(recent) - 2, -1, -1):
            if c[i] > o[i]:
                return f"bearish OB (oxirgi up-close): {lo[i]:.5f}-{hi[i]:.5f}"
    return "OB aniq emas (order flow neytral)"


# ---------------------------------------------------------------------------
# 4. SMT (korrelyatsion aktivlardan biri ekstremum oladi, ikkinchisi olmaydi)
# ---------------------------------------------------------------------------
def _recent_extreme(df: pd.DataFrame, window: int = 12):
    """Oxirgi `window` sham ichida: (eng yuqori high, eng past low) + yangi ekstremummi."""
    w = df.tail(window)
    hi_idx = w["high"].values.argmax()
    lo_idx = w["low"].values.argmin()
    # ekstremum oxirgi choragida shakllangan bo'lsa "yangi" deb hisoblaymiz
    fresh_high = hi_idx >= len(w) * 0.6
    fresh_low = lo_idx >= len(w) * 0.6
    return fresh_high, fresh_low


def dealing_range(df_h4: pd.DataFrame, lookback: int = 40):
    """H4 dealing range: so'nggi swing high/low ekstremumlari + 50%."""
    recent = df_h4.tail(lookback)
    highs, lows = _swings(recent)
    if not highs or not lows:
        return None
    dh = max(p for _, p in highs)
    dl = min(p for _, p in lows)
    if dh <= dl:
        return None
    return dh, dl, (dh + dl) / 2


def premium_discount_ok(entry: float, direction: str, df_h4: pd.DataFrame) -> bool:
    """
    MMXM/ICT: faqat DISCOUNT'da long (BUY), PREMIUM'da short (SELL).
    Dealing range 50% dan past = discount, yuqori = premium.
    Range aniqlanmasa filtrlamaydi (True qaytaradi).
    """
    dr = dealing_range(df_h4)
    if dr is None:
        return True
    _, _, mid = dr
    if direction == "bullish_sweep":   # BUY - discount'da bo'lsin
        return entry <= mid
    else:                              # SELL - premium'da bo'lsin
        return entry >= mid


def smt(symbol: str, connector, timeframe: str = "H4") -> list[str]:
    """Korrelyatsion juftliklar bilan SMT divergensiyasini tekshiradi."""
    out = []
    df_main = connector.get_candles(symbol, timeframe, count=30)
    if df_main.empty:
        return out
    main_fresh_high, main_fresh_low = _recent_extreme(df_main)

    for pair, inverse in SMT_PAIRS.get(symbol, []):
        df_pair = connector.get_candles(pair, timeframe, count=30)
        if df_pair.empty:
            continue
        p_fresh_high, p_fresh_low = _recent_extreme(df_pair)
        # inverse juft (masalan DXY): main high olganda pair low olishi kerak
        pair_high_equiv = p_fresh_low if inverse else p_fresh_high
        pair_low_equiv = p_fresh_high if inverse else p_fresh_low

        # Bearish SMT: main yangi high oldi, pair olmadi
        if main_fresh_high and not pair_high_equiv:
            out.append(f"BEARISH SMT ({symbol} vs {pair}): {symbol} yangi high oldi, "
                       f"{pair} tasdiqlamadi → yuqori reversal ehtimoli")
        # Bullish SMT: main yangi low oldi, pair olmadi
        if main_fresh_low and not pair_low_equiv:
            out.append(f"BULLISH SMT ({symbol} vs {pair}): {symbol} yangi low oldi, "
                       f"{pair} tasdiqlamadi → past reversal ehtimoli")
    return out
