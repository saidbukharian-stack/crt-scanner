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
    level_name: str        # masalan "Asia_High", "PDH", "CRT_9AM_CRT_9PM_Asia_High"
    level_price: float
    sweep_candle_time: str
    sweep_high: float
    sweep_low: float
    close_price: float
    direction: str          # "bullish_sweep" (low supurildi) | "bearish_sweep" (high supurildi)
    # CRT signallari uchun: diapazon o'rtasi (50% maqsad). Boshqalarda None.
    crt_mid: float | None = None


def _candle_in_windows(candle_time, windows) -> bool:
    """Sham ochilish vaqti (tz-aware NY) darajaning oynalaridan biriga tushadimi."""
    if windows is None:
        return True
    t = candle_time.tz_localize(None)  # aware -> naive NY devoriy vaqti
    return any(ws <= t < we for ws, we in windows)


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

    crt_mid = None
    if level.paired_price is not None:
        crt_mid = (level.price + level.paired_price) / 2

    for _, candle in window.iterrows():
        # Daraja vaqt oynasiga ega bo'lsa (CRT key time, killzone) -
        # oynadan tashqaridagi sweep signal hisoblanmaydi
        if not _candle_in_windows(candle["time_ny"], level.windows):
            continue

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
                    crt_mid=crt_mid,
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
                    crt_mid=crt_mid,
                ))

    return signals


def detect_cisd(df_m5: pd.DataFrame, after_time, direction: str) -> dict | None:
    """
    M5 CISD (Change in State of Delivery) tasdig'ini aniqlaydi.

    TTrades ta'rifiga ko'ra (IC-CISD): purge shamidan keyin narx qarshi
    trendning ketma-ket shamlar qatorini yopib o'tsa - trend o'zgardi.

    Bearish (purged high, pastga kutamiz): purge'dan keyingi M5'da eng
    yuqori high topiladi; o'sha high'ga olib kelgan ketma-ket UP-close
    shamlar qatorining eng past low'i = CISD darajasi; keyin biror sham
    o'sha darajaning OSTIGA yopilsa - tasdiq. Kirish=o'sha close, stop=swing high.

    Bullish - to'liq teskari.

    after_time - purge shami vaqti (tz-aware NY).
    Qaytaradi: {"entry", "entry_time", "stop"} yoki None (hali shakllanmagan).
    """
    after = df_m5[df_m5["time_ny"] > after_time].reset_index(drop=True)
    if len(after) < 2:
        return None
    o = after["open"].values
    c = after["close"].values
    h = after["high"].values
    lo = after["low"].values
    t = after["time_ny"]

    if direction == "bearish_sweep":
        hi_idx = int(h.argmax())
        # high'ga olib kelgan up-close shamlar qatorining eng past low'i
        start = hi_idx if c[hi_idx] >= o[hi_idx] else hi_idx - 1
        run_low = lo[hi_idx]
        k = start
        while k >= 0 and c[k] >= o[k]:
            run_low = min(run_low, lo[k])
            k -= 1
        swing_high = float(h[hi_idx])
        for m in range(hi_idx + 1, len(after)):
            if c[m] < run_low:
                return {"entry": float(c[m]), "entry_time": str(t.iloc[m]),
                        "stop": swing_high}
        return None
    else:  # bullish_sweep
        lo_idx = int(lo.argmin())
        start = lo_idx if c[lo_idx] <= o[lo_idx] else lo_idx - 1
        run_high = h[lo_idx]
        k = start
        while k >= 0 and c[k] <= o[k]:
            run_high = max(run_high, h[k])
            k -= 1
        swing_low = float(lo[lo_idx])
        for m in range(lo_idx + 1, len(after)):
            if c[m] > run_high:
                return {"entry": float(c[m]), "entry_time": str(t.iloc[m]),
                        "stop": swing_low}
        return None


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
