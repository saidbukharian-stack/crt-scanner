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


def _unfilled_fvgs(df: pd.DataFrame):
    """To'ldirilmagan FVG'lar strukturasi: (kind, lo, hi) ro'yxati."""
    h = df["high"].values
    lo = df["low"].values
    out = []
    for i in range(2, len(df)):
        if h[i - 2] < lo[i]:  # bullish FVG
            g_lo, g_hi = float(h[i - 2]), float(lo[i])
            if df["low"].values[i:].min() > g_lo:
                out.append(("bullish", g_lo, g_hi))
        if lo[i - 2] > h[i]:  # bearish FVG
            g_lo, g_hi = float(h[i]), float(lo[i - 2])
            if df["high"].values[i:].max() < g_hi:
                out.append(("bearish", g_lo, g_hi))
    return out


# ---------------------------------------------------------------------------
# IRL/ERL — keyingi draw on liquidity (MMXM: ERL olinsa->IRL, IRL olinsa->ERL)
# IRL = FVG (imbalance), ERL = eski swing high/low
# ---------------------------------------------------------------------------
def irl_erl_map(df: pd.DataFrame, price: float) -> str:
    highs, lows = _swings(df)
    erl_above = min((p for _, p in highs if p > price), default=None)
    erl_below = max((p for _, p in lows if p < price), default=None)
    fvgs = _unfilled_fvgs(df)
    irl_above = min((lo for _, lo, hi in fvgs if lo > price), default=None)
    irl_below = max((hi for _, lo, hi in fvgs if hi < price), default=None)

    def f(x):
        return f"{x:.5f}" if x is not None else "yo'q"

    return (
        f"ERL (eski high/low): yuqorida {f(erl_above)}, pastda {f(erl_below)}. "
        f"IRL (FVG): yuqorida {f(irl_above)}, pastda {f(irl_below)}. "
        "Qoida: ERL olinsa keyingi draw IRL; IRL olinsa keyingi draw ERL."
    )


# ---------------------------------------------------------------------------
# Exact equal highs/lows — kuchli likvidlik magniti (2 alohida swing teng)
# ---------------------------------------------------------------------------
def equal_highs_lows(df: pd.DataFrame) -> list[str]:
    rng = (df["high"] - df["low"]).tail(30).median()
    tol = float(rng) * 0.15 if rng and rng > 0 else 0
    highs, lows = _swings(df)
    out = []
    # teng highlar (ikki alohida swing, tol ichida)
    for a in range(len(highs)):
        for b in range(a + 1, len(highs)):
            if abs(highs[a][1] - highs[b][1]) <= tol:
                lvl = max(highs[a][1], highs[b][1])
                out.append(f"Equal highs ~{lvl:.5f} (kuchli buy-side DOL magniti)")
                break
    for a in range(len(lows)):
        for b in range(a + 1, len(lows)):
            if abs(lows[a][1] - lows[b][1]) <= tol:
                lvl = min(lows[a][1], lows[b][1])
                out.append(f"Equal lows ~{lvl:.5f} (kuchli sell-side DOL magniti)")
                break
    return out[:4]


# ---------------------------------------------------------------------------
# Double Purge (bir-sham) — bitta sham high VA low'ni oladi, ichida yopiladi
# MMXM DPT: kuchli overbought/oversold reversal signature
# ---------------------------------------------------------------------------
def detect_double_purge(df: pd.DataFrame, lookback: int = 15) -> str | None:
    h = df["high"].values
    lo = df["low"].values
    c = df["close"].values
    t = df["time_ny"].values
    start = max(1, len(df) - lookback)
    for i in range(len(df) - 1, start - 1, -1):
        took_high = h[i] > h[i - 1]
        took_low = lo[i] < lo[i - 1]
        closed_within = lo[i - 1] <= c[i] <= h[i - 1]
        if took_high and took_low and closed_within:
            return (f"Bir-sham DOUBLE PURGE @ {str(t[i])[:16]}: high {h[i]:.5f} va "
                    f"low {lo[i]:.5f} ikkovi olindi, ichida yopildi "
                    f"(kuchli reversal signature — katta harakat ehtimoli)")
    return None


def find_order_block(df: pd.DataFrame, of: str, lookback: int = 30) -> str:
    """
    OBYEKTIV order block (Sham/CRT ta'rifi): likvidlikni PURGE qilib (eski
    swing high/low oldi) keyin ENGULF bo'lgan (narx ortiga yopildi) sham(lar).
    Oddiy "oxirgi qarshi sham" emas.

    Bullish OB: down-close sham eski swing LOW'ni purge qildi, keyin biror
      sham uning HIGH'i ustida yopildi (engulf).
    Bearish OB: up-close sham eski swing HIGH'ni purge qildi, keyin biror
      sham uning LOW'i ostida yopildi.
    """
    recent = df.tail(lookback).reset_index(drop=True)
    o = recent["open"].values
    c = recent["close"].values
    hi = recent["high"].values
    lo = recent["low"].values
    highs, lows = _swings(recent)
    swing_high_prices = [p for _, p in highs]
    swing_low_prices = [p for _, p in lows]
    n = len(recent)

    if of.startswith("bullish"):
        for i in range(n - 2, 0, -1):
            purged = any(lo[i] < slp < o[i] for slp in swing_low_prices) or \
                     (i >= 1 and lo[i] < lo[i - 1])
            if c[i] < o[i] and purged:  # down-close + sell-side purge
                engulfed = any(c[j] > hi[i] for j in range(i + 1, n))
                if engulfed:
                    return (f"bullish OB {lo[i]:.5f}-{hi[i]:.5f} "
                            f"(sell-side purge + engulf)")
    elif of.startswith("bearish"):
        for i in range(n - 2, 0, -1):
            purged = any(o[i] < shp < hi[i] for shp in swing_high_prices) or \
                     (i >= 1 and hi[i] > hi[i - 1])
            if c[i] > o[i] and purged:  # up-close + buy-side purge
                engulfed = any(c[j] < lo[i] for j in range(i + 1, n))
                if engulfed:
                    return (f"bearish OB {lo[i]:.5f}-{hi[i]:.5f} "
                            f"(buy-side purge + engulf)")
    return "obyektiv OB topilmadi (purge+engulf yo'q)"


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
