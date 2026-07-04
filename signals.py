"""
Signals
=======
"Sweep" (likvidlik supurilishi) ni aniqlash mantig'i.

Sweep ta'rifi (loyiha materiallaridagi TS/CRT mantig'iga mos):
  - Narx bir darajani (high yoki low) teshib o'tadi (wick bilan),
  - LEKIN o'sha shamning close'i darajaning ORQASIGA qaytadi
    (ya'ni darajadan tashqarida yopilmaydi).
  Bu "false breakout" / "liquidity grab" - CRT/TS metodologiyasining asosi.

Bu modul FAQAT eng sodda mexanik shartni tekshiradi (config.py'dagi
kelishuvga ko'ra: "keng to'r" - inducement sifati, struktura, kontekst
kabi nozik narsalar TREYDERNING o'zida qoladi, kodda emas).
"""

from dataclasses import dataclass

import pandas as pd

from levels import Level


@dataclass
class SweepSignal:
    symbol: str
    condition: str        # "asia_hl_sweep" | "pdh_pdl_sweep" | "crt_range_sweep"
    level_name: str        # masalan "Asia_High", "PDH", "CRT_9AM_CRT_High"
    level_price: float
    sweep_candle_time: str
    sweep_high: float
    sweep_low: float
    close_price: float
    direction: str          # "bullish_sweep" (low supurildi) | "bearish_sweep" (high supurildi)


def detect_sweep(df_recent: pd.DataFrame, level: Level, condition_name: str,
                  symbol: str, lookback_candles: int = 12) -> list[SweepSignal]:
    """
    `df_recent` ichidagi so'nggi `lookback_candles` shamlar orasida
    berilgan `level` sweep qilinganmi tekshiradi.

    df_recent - vaqt bo'yicha o'sish tartibida saralangan bo'lishi kerak
    (eng oxirgi qator - eng yangi sham).
    """
    signals: list[SweepSignal] = []
    window = df_recent.tail(lookback_candles)

    for _, candle in window.iterrows():
        if level.kind == "high":
            # High sweep: wick darajadan yuqoriga chiqadi, close pastda yopiladi
            wicked_above = candle["high"] > level.price
            closed_below = candle["close"] < level.price
            if wicked_above and closed_below:
                signals.append(SweepSignal(
                    symbol=symbol,
                    condition=condition_name,
                    level_name=level.name,
                    level_price=level.price,
                    sweep_candle_time=str(candle["time_ny"]),
                    sweep_high=float(candle["high"]),
                    sweep_low=float(candle["low"]),
                    close_price=float(candle["close"]),
                    direction="bearish_sweep",
                ))
        else:  # level.kind == "low"
            wicked_below = candle["low"] < level.price
            closed_above = candle["close"] > level.price
            if wicked_below and closed_above:
                signals.append(SweepSignal(
                    symbol=symbol,
                    condition=condition_name,
                    level_name=level.name,
                    level_price=level.price,
                    sweep_candle_time=str(candle["time_ny"]),
                    sweep_high=float(candle["high"]),
                    sweep_low=float(candle["low"]),
                    close_price=float(candle["close"]),
                    direction="bullish_sweep",
                ))

    return signals


def scan_all_conditions(df_recent: pd.DataFrame, levels: list[Level],
                         symbol: str, enabled_conditions: dict) -> list[SweepSignal]:
    """
    Barcha yoqilgan shartlarni (config.SIGNAL_CONDITIONS) tekshirib,
    topilgan sweep signallarini birlashtirib qaytaradi.
    """
    all_signals: list[SweepSignal] = []

    condition_prefix_map = {
        "asia_hl_sweep": "Asia_",
        "pdh_pdl_sweep": "PD",       # PDH / PDL
        "crt_range_sweep": "CRT_",
    }

    for condition_name, is_enabled in enabled_conditions.items():
        if not is_enabled:
            continue
        prefix = condition_prefix_map.get(condition_name)
        if prefix is None:
            continue
        matching_levels = [lv for lv in levels if lv.name.startswith(prefix)]
        for level in matching_levels:
            all_signals.extend(
                detect_sweep(df_recent, level, condition_name, symbol)
            )

    return all_signals
