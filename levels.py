"""
Levels
======
Narx darajalarini hisoblash: PDH/PDL, sessiya (Asia/London/NY) high-low,
va CRT range (1AM/5AM/9AM shamlarining high-low'i).

Barcha hisob-kitoblar NY vaqtiga asoslangan `time_ny` ustunidan foydalanadi.
"""

from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta

import pandas as pd

from config import SESSIONS_NY, CRT_MODELS, CRT_CANDLE_LABELS, KILLZONES_NY


@dataclass
class Level:
    name: str            # masalan "PDH", "Asia_High", "CRT_9AM_CRT_9PM_Asia_High"
    price: float
    kind: str            # "high" yoki "low"
    session_date: str    # qaysi savdo kuniga tegishli (NY sanasi, YYYY-MM-DD)
    # Sweep faqat shu vaqt oynalarida signal beradi (naive NY datetime juftlari).
    # None = vaqt cheklovi yo'q.
    windows: list[tuple[datetime, datetime]] | None = None
    # CRT darajalari uchun: diapazonning QARSHI cheti (50% maqsadni
    # hisoblash uchun). Boshqa darajalarda None.
    paired_price: float | None = None


def _parse_hhmm(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


def previous_day_high_low(df_d1: pd.DataFrame) -> list[Level]:
    """
    D1 (kunlik) shamlar asosida PDH/PDL (oldingi kun high/low) ni hisoblaydi.
    df_d1 - eng kamida 2 ta oxirgi kunlik sham bo'lishi kerak.
    """
    if len(df_d1) < 2:
        return []
    prev = df_d1.iloc[-2]  # oxirgisi hali yopilmagan joriy kun bo'lishi mumkin
    date_str = prev["time_ny"].strftime("%Y-%m-%d")
    return [
        Level("PDH", float(prev["high"]), "high", date_str),
        Level("PDL", float(prev["low"]), "low", date_str),
    ]


def session_high_low(df_intraday: pd.DataFrame, session_name: str,
                      for_date: datetime) -> list[Level]:
    """
    Berilgan sessiya (masalan "asia") uchun shu kungi (yoki oldingi kechadan
    boshlanadigan) high/low ni intraday (M5/M15) shamlar asosida hisoblaydi.
    """
    session = SESSIONS_NY[session_name]
    start_t = _parse_hhmm(session["start"])
    end_t = _parse_hhmm(session["end"])

    day = for_date.date()
    start_dt = datetime.combine(day, start_t)
    end_dt = datetime.combine(day, end_t)

    # Asia sessiyasi kabi kechadan boshlanib, ertalab tugaydigan holatlar
    if end_t <= start_t:
        end_dt += timedelta(days=1)
        start_dt -= timedelta(days=1)

    mask = (df_intraday["time_ny"].dt.tz_localize(None) >= start_dt) & (
        df_intraday["time_ny"].dt.tz_localize(None) < end_dt
    )
    window = df_intraday[mask]
    if window.empty:
        return []

    date_str = day.strftime("%Y-%m-%d")
    label = session_name.replace("_", " ").title().replace(" ", "_")
    return [
        Level(f"{label}_High", float(window["high"].max()), "high", date_str),
        Level(f"{label}_Low", float(window["low"].min()), "low", date_str),
    ]


def crt_levels_for_model(df_h4: pd.DataFrame, model_name: str,
                          for_date: datetime) -> list[Level]:
    """
    Berilgan CRT modeli uchun purge QILINADIGAN oldingi H4 shamlarning
    (config.CRT_MODELS[...]['range_candles']) high/low darajalarini
    qaytaradi. Har daraja modelning key time oynasi bilan bog'lanadi -
    sweep faqat shu oynada signal hisoblanadi.

    Masalan 9AM CRT: 9PM(Asia)/1AM(London)/5AM shamlarining chegaralarini
    09:00-10:00 oralig'ida purge qilinishini kutamiz (PDF mantig'i).
    """
    spec = CRT_MODELS[model_name]
    day = for_date.date()
    w_start = datetime.combine(day, _parse_hhmm(spec["window"][0]))
    w_end = datetime.combine(day, _parse_hhmm(spec["window"][1]))
    window = [(w_start, w_end)]

    df_naive = df_h4.copy()
    df_naive["time_ny_naive"] = df_naive["time_ny"].dt.tz_localize(None)

    levels: list[Level] = []
    date_str = day.strftime("%Y-%m-%d")
    for hour in spec["range_candles"]:
        # 17:00 va 21:00 shamlari oynadan OLDINGI NY kunida ochiladi
        candle_day = day - timedelta(days=1) if hour >= 12 else day
        target_dt = datetime.combine(candle_day, dtime(hour, 0))
        match = df_naive[df_naive["time_ny_naive"] == target_dt]
        if match.empty:
            continue  # dam olish/bayram - bu sham yo'q
        row = match.iloc[0]
        label = CRT_CANDLE_LABELS[hour]
        base = f"CRT_{model_name}_{label}"
        hi, lo = float(row["high"]), float(row["low"])
        levels.append(Level(f"{base}_High", hi, "high", date_str, window, lo))
        levels.append(Level(f"{base}_Low", lo, "low", date_str, window, hi))
    return levels


def killzone_windows(for_date: datetime) -> list[tuple[datetime, datetime]]:
    """config.KILLZONES_NY dan shu kun uchun naive NY oynalar ro'yxati."""
    day = for_date.date()
    return [
        (datetime.combine(day, _parse_hhmm(s)), datetime.combine(day, _parse_hhmm(e)))
        for s, e in KILLZONES_NY
    ]


def all_levels_for_symbol(df_intraday: pd.DataFrame, df_h4: pd.DataFrame,
                           df_d1: pd.DataFrame, for_date: datetime) -> list[Level]:
    """Bitta symbol uchun barcha yoqilgan turdagi darajalarni yig'ib qaytaradi."""
    kz = killzone_windows(for_date)

    levels: list[Level] = []
    # PDH/PDL va Asia H/L - faqat killzone (London/NY) oynalarida signal beradi
    for lv in previous_day_high_low(df_d1):
        lv.windows = kz
        levels.append(lv)
    for lv in session_high_low(df_intraday, "asia", for_date):
        lv.windows = kz
        levels.append(lv)
    levels += session_high_low(df_intraday, "london", for_date)
    for model_name in CRT_MODELS:
        levels += crt_levels_for_model(df_h4, model_name, for_date)
    return levels
