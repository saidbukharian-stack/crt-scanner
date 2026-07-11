"""
Market Snapshot — bozorning jonli holatini matn ko'rinishida jamlaydi
=====================================================================
LLM jonli tahlil qilishi uchun berilgan instrument bo'yicha hozirgi
holatni (narx, darajalar, order flow, killzone, so'nggi sweep) bitta
matnga yig'adi. Bu matn bilim bazasi bilan birga LLM'ga uzatiladi.

Ma'lumotlar allaqachon skaner hisoblaydigan modullardan olinadi
(levels.py, signals.py) - bu yerda faqat jamlanadi va formatlanadi.
"""

import logging
from datetime import datetime

from config import (
    DATA_SOURCE, INSTRUMENTS, NY_TZ, SIGNAL_CONDITIONS,
    MT5_TIMEFRAME_ENTRY, MT5_TIMEFRAME_HTF, CRT_MODELS, KILLZONES_NY,
)
from levels import all_levels_for_symbol, _parse_hhmm
from signals import scan_all_conditions
from analysis import (
    order_flow, draw_on_liquidity, find_fvgs, find_order_block, smt,
    irl_erl_map, equal_highs_lows, detect_double_purge, market_maker_context,
    midnight_open,
)

if DATA_SOURCE == "oanda":
    from oanda_connector import connector
elif DATA_SOURCE == "yahoo":
    from yahoo_connector import connector
else:
    from mt5_connector import connector

logger = logging.getLogger(__name__)


def _active_windows(now_ny: datetime) -> list[str]:
    """Hozir qaysi killzone / CRT oynasida ekanligimizni aniqlaydi."""
    t = now_ny.time()
    active = []
    for start, end in KILLZONES_NY:
        if _parse_hhmm(start) <= t < _parse_hhmm(end):
            active.append(f"Killzone {start}-{end}")
    for model, spec in CRT_MODELS.items():
        s, e = spec["window"]
        if _parse_hhmm(s) <= t < _parse_hhmm(e):
            active.append(f"{model} oynasi ({s}-{e})")
    return active


def _bias(df) -> str:
    """Oxirgi yopilgan sham oldingisiga nisbatan close yo'nalishi (CRT bias)."""
    if len(df) < 2:
        return "noma'lum"
    prev, last = df.iloc[-2], df.iloc[-1]
    if last["close"] > prev["high"]:
        return "bullish (oldingi high ustida yopildi)"
    if last["close"] < prev["low"]:
        return "bearish (oldingi low ostida yopildi)"
    if last["close"] > prev["close"]:
        return "bullish moyillik (yuqoriroq close)"
    if last["close"] < prev["close"]:
        return "bearish moyillik (pastroq close)"
    return "neytral"


def build_snapshot(symbol: str) -> str | None:
    """Bitta instrument uchun jonli holat matnini quradi."""
    if not connector.connect():
        return None
    now_ny = datetime.now(NY_TZ)

    df_m5 = connector.get_candles(symbol, MT5_TIMEFRAME_ENTRY, count=400)
    df_h4 = connector.get_candles(symbol, MT5_TIMEFRAME_HTF, count=60)
    df_d1 = connector.get_candles(symbol, "D1", count=70)  # IPDA 60 kun uchun
    if df_m5.empty or df_h4.empty or df_d1.empty:
        return None

    price = float(df_m5.iloc[-1]["close"])
    levels = all_levels_for_symbol(df_m5, df_h4, df_d1, now_ny)
    signals = scan_all_conditions(df_m5, levels, symbol, SIGNAL_CONDITIONS)

    lines = [
        f"INSTRUMENT: {symbol}",
        f"Hozirgi narx: {price:.5f}",
        f"NY vaqti: {now_ny.strftime('%Y-%m-%d %H:%M')} ({now_ny.strftime('%A')})",
    ]

    windows = _active_windows(now_ny)
    lines.append("Faol oyna: " + (", ".join(windows) if windows else "hech qaysi (savdo oynasidan tashqari)"))

    lines.append(f"Kunlik (D1) bias: {_bias(df_d1)}")
    lines.append(f"H4 bias: {_bias(df_h4)}")

    # Order flow (H4 struktura)
    of = order_flow(df_h4)
    lines.append(f"Order flow (H4): {of}")

    # MMxM faza + Midnight Open bias (ICT konteksti)
    lines.append(f"Market Maker faza (H4): {market_maker_context(df_h4)}")
    mo = midnight_open(df_m5, now_ny)
    if mo is not None:
        rel = "ustида (bullish bias)" if price >= mo else "ostида (bearish bias)"
        lines.append(f"Midnight Open (00:00 NY): {mo:.5f} — narx {rel}")

    # DOL (draw on liquidity)
    pdh = next((lv.price for lv in levels if lv.name == "PDH"), None)
    pdl = next((lv.price for lv in levels if lv.name == "PDL"), None)
    lines.append(f"DOL: {draw_on_liquidity(df_d1, of, pdh, pdl)}")

    # IRL/ERL keyingi draw (H4)
    lines.append(f"IRL/ERL: {irl_erl_map(df_h4, price)}")

    # Bir-sham double purge (M5 - kuchli reversal signature)
    dp = detect_double_purge(df_m5)
    if dp:
        lines.append(f"⚡ {dp}")

    # Exact equal highs/lows (kuchli DOL magniti)
    eqs = equal_highs_lows(df_h4)
    if eqs:
        lines.append("KUCHLI DOL (equal highs/lows):")
        for e in eqs:
            lines.append(f"  {e}")

    # Darajalar va narxning ularga nisbati
    lines.append("\nDARAJALAR (narx ularga nisbatan):")
    for lv in levels:
        rel = "ustida" if price > lv.price else "ostida"
        dist_pips = abs(price - lv.price)
        lines.append(f"  {lv.name:<28} {lv.price:.5f}  (narx {rel}, farq {dist_pips:.5f})")

    # Key level: FVG va OB (H4 va M5)
    fvgs = find_fvgs(df_h4, price, max_count=3) + find_fvgs(df_m5, price, max_count=2)
    if fvgs:
        lines.append("\nKEY LEVEL (to'ldirilmagan FVG'lar, narxga yaqin):")
        for f in fvgs[:5]:
            lines.append(f"  {f}")
    lines.append(f"Order block (H4): {find_order_block(df_h4, of)}")

    # SMT (korrelyatsion juftliklar)
    smt_signals = smt(symbol, connector, "H4")
    if smt_signals:
        lines.append("\nSMT (korrelyatsion divergensiya):")
        for s in smt_signals:
            lines.append(f"  {s}")
    else:
        lines.append("\nSMT: juftliklarda divergensiya yo'q (yoki ma'lumot yetarli emas).")

    # So'nggi sweep'lar (oynalar ichida)
    if signals:
        lines.append("\nSO'NGGI SWEEP'LAR (oyna ichida):")
        for s in signals[-6:]:
            lines.append(
                f"  {s.condition} | {s.level_name} | {s.direction} | "
                f"sham vaqti {s.sweep_candle_time}"
            )
    else:
        lines.append("\nSo'nggi sweep yo'q (oynalar ichida).")

    return "\n".join(lines)


def resolve_symbol(text: str) -> str | None:
    """Matndan instrument nomini topadi (masalan 'XAUUSD hozir qanday')."""
    up = text.upper()
    for sym in INSTRUMENTS:
        if sym in up:
            return sym
    # ba'zi taxalluslar
    aliases = {"GOLD": "XAUUSD", "OLTIN": "XAUUSD", "NASDAQ": "USTEC",
               "NAS100": "USTEC", "SP500": "US500", "SPX": "US500"}
    for alias, sym in aliases.items():
        if alias in up:
            return sym
    return None
