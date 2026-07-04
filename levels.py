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

from config import SESSIONS_NY, CRT_KEY_TIMES


@dataclass
class Level:
    name: str            # masalan "PDH", "Asia_High", "CRT_9AM_High"
    price: float
    kind: str            # "high" yoki "low"
    session_date: str    # qaysi savdo kuniga tegishli (NY sanasi, YYYY-MM-DD)


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


def crt_range(df_h4: pd.DataFrame, model_name: str, for_date: datetime) -> list[Level]:
    """
    Berilgan CRT modeli (masalan "9AM_CRT") uchun H4 shamning
    high/low'ini (CRT High/Low) qaytaradi. Bu 3 candle CRT'dagi
    o'rtadagi ("manipulation"/ikkinchi) shamga mos keladi - PDF
    materiallaridagi "CRT High" / "CRT Low" atamalari shu.
    """
    key_time = CRT_KEY_TIMES[model_name]
    candle_open_t = _parse_hhmm(key_time["candle_open"])
    day = for_date.date()
    target_dt = datetime.combine(day, candle_open_t)

    df_naive = df_h4.copy()
    df_naive["time_ny_naive"] = df_naive["time_ny"].dt.tz_localize(None)
    match = df_naive[df_naive["time_ny_naive"] == target_dt]
    if match.empty:
        # eng yaqin shamni topishga urinib ko'ramiz (± 1 soat ichida)
        diffs = (df_naive["time_ny_naive"] - target_dt).abs()
        idx = diffs.idxmin()
        if diffs.loc[idx] > timedelta(hours=1):
            return []
        match = df_naive.loc[[idx]]

    row = match.iloc[0]
    date_str = day.strftime("%Y-%m-%d")
    return [
        Level(f"CRT_{model_name}_High", float(row["high"]), "high", date_str),
        Level(f"CRT_{model_name}_Low", float(row["low"]), "low", date_str),
    ]


def all_levels_for_symbol(df_intraday: pd.DataFrame, df_h4: pd.DataFrame,
                           df_d1: pd.DataFrame, for_date: datetime) -> list[Level]:
    """Bitta symbol uchun barcha yoqilgan turdagi darajalarni yig'ib qaytaradi."""
    levels: list[Level] = []
    levels += previous_day_high_low(df_d1)
    levels += session_high_low(df_intraday, "asia", for_date)
    levels += session_high_low(df_intraday, "london", for_date)
    for model_name in CRT_KEY_TIMES:
        levels += crt_range(df_h4, model_name, for_date)
    return levels
