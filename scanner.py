"""
CRT Scanner - Asosiy dastur
============================
Har SCAN_INTERVAL_MINUTES daqiqada barcha instrumentlarni tekshiradi:
  1. MT5'dan narx ma'lumotini oladi
  2. Darajalarni hisoblaydi (PDH/PDL, Asia H/L, CRT range)
  3. Sweep signallarni qidiradi (config'da yoqilgan shartlar bo'yicha)
  4. Yangi signal topilsa - Telegram'ga yuboradi

Ishga tushirish (doimiy loop):  python scanner.py
Bir martalik skan (cron/CI uchun): python scanner.py --once
To'xtatish: Ctrl+C
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta

from config import (
    DATA_SOURCE,
    DB_PATH,
    INSTRUMENTS,
    SCAN_INTERVAL_MINUTES,
    MT5_TIMEFRAME_ENTRY,
    MT5_TIMEFRAME_HTF,
    SIGNAL_CONDITIONS,
    NY_TZ,
    QT_FILTER_ENABLED,
    MIDNIGHT_BIAS_ENABLED,
    HRL_FILTER_ENABLED,
    ABLATION_LOG_ENABLED,
    SHADOW_TRACKING_ENABLED,
)

if DATA_SOURCE == "oanda":
    from oanda_connector import connector
elif DATA_SOURCE == "yahoo":
    from yahoo_connector import connector
else:
    from mt5_connector import connector
from levels import all_levels_for_symbol
from signals import scan_all_conditions, detect_cisd
from telegram_notifier import notify_signal
from outcome_tracker import (register_trade, update_trades,
                             register_shadow, update_shadows)
import ablation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("scanner")

# Bir xil signalni qayta-qayta yubormaslik uchun - allaqachon xabar
# qilingan (symbol, condition, level_name, sweep_candle_time) kombinatsiyasi.
# Faylga ham saqlanadi - --once rejimida (GitHub Actions/cron) har ishga
# tushish yangi jarayon bo'lgani uchun xotiradagi set yetarli emas.
_already_notified: set[tuple] = set()

_STATE_PATH = os.path.join(os.path.dirname(DB_PATH), "notified.json")


def _load_notified_state():
    global _already_notified
    try:
        with open(_STATE_PATH, encoding="utf-8") as f:
            _already_notified = {tuple(item) for item in json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        _already_notified = set()


def _save_notified_state():
    # Eski yozuvlarni tozalaymiz (3 kundan oshgan sweep endi qaytarilmaydi).
    # Dedup kaliti oxirgi element = sana (YYYY-MM-DD).
    cutoff = (datetime.now(NY_TZ) - timedelta(days=3)).strftime("%Y-%m-%d")
    fresh = [list(k) for k in _already_notified if str(k[-1])[:10] >= cutoff]
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(fresh), f, ensure_ascii=False, indent=0)


def evaluate_signal_filters(sig, df_m5, df_h4, mo) -> dict:
    """
    Signalning HAR filtrini ALOHIDA baholaydi (early-return yo'q).
    Toggle'lar faqat YAKUNIY verdictга ta'sir qiladi; xom pass/fail har doim
    qaytariladi (ablation tahlili uchun). Jonli skaner va backtest bir xil
    ishlatadi.
    """
    import pandas as pd
    from analysis import (premium_discount_ok, midnight_bias_ok,
                          low_resistance_to_target)
    from qt import qt_phase

    pd_ok = bool(premium_discount_ok(sig.close_price, sig.direction, df_h4))
    qp = qt_phase(pd.Timestamp(sig.sweep_candle_time))
    qt_ok = bool(qp["favored"])
    mo_ok = bool(midnight_bias_ok(sig.close_price, sig.direction, mo))
    hrl_ok = bool(low_resistance_to_target(df_m5, sig.close_price,
                                           sig.liquidity_target, sig.direction))

    # Verdict: faqat YOQILGAN filtrlar hisobga olinadi (P/D har doim yoqilgan)
    chain = [("pd", True, pd_ok),
             ("qt", QT_FILTER_ENABLED, qt_ok),
             ("mo_bias", MIDNIGHT_BIAS_ENABLED, mo_ok),
             ("hrl", HRL_FILTER_ENABLED, hrl_ok)]
    rejected_by = ""
    for name, enabled, ok in chain:
        if enabled and not ok:
            rejected_by = name
            break
    return {
        "pd": pd_ok, "qt": qt_ok, "qt_phase": qp["phase"],
        "mo": mo_ok, "hrl": hrl_ok,
        "verdict": "accepted" if not rejected_by else "rejected",
        "rejected_by": rejected_by,
    }


def _scan_and_filter(symbol, now_ny, df_m5, df_h4, df_d1):
    """
    SOF signal+filtr yo'li (Telegram/fayl yozishsiz) — jonli skaner ham,
    backtest ham shu funksiyani chaqiradi. Qaytaradi:
      (signals, mo, [(sig, filter_result), ...])
    """
    from analysis import midnight_open
    levels = all_levels_for_symbol(df_m5, df_h4, df_d1, now_ny)
    signals = scan_all_conditions(df_m5, levels, symbol, SIGNAL_CONDITIONS)
    mo = midnight_open(df_m5, now_ny)
    evaluated = [(s, evaluate_signal_filters(s, df_m5, df_h4, mo)) for s in signals]
    return signals, mo, evaluated


def scan_symbol(symbol: str, now_ny: datetime) -> list:
    # 400 M5 (~33 soat) — Asia/London sessiya darajalari (20:00-00:00 NY, ~20
    # soat oldin) to'liq qamrab olinishi uchun (200 sham yetarli emas edi)
    df_m5 = connector.get_candles(symbol, MT5_TIMEFRAME_ENTRY, count=400)
    df_h4 = connector.get_candles(symbol, MT5_TIMEFRAME_HTF, count=60)
    df_d1 = connector.get_candles(symbol, "D1", count=70)  # IPDA 60 kun uchun

    if df_m5.empty or df_h4.empty or df_d1.empty:
        logger.warning("Ma'lumot yetarli emas: %s", symbol)
        return []

    _, mo, evaluated = _scan_and_filter(symbol, now_ny, df_m5, df_h4, df_d1)

    accepted = []
    for sig, r in evaluated:
        if not ABLATION_LOG_ENABLED:
            # Log o'chirilgan: eski xatti-harakat — faqat qabul qilinganlar
            if r["verdict"] == "accepted":
                accepted.append(sig)
            continue

        sid = ablation.make_signal_id(sig.symbol, sig.condition,
                                      sig.level_name, sig.direction,
                                      sig.sweep_candle_time)
        if ablation.already_logged(sid):
            continue  # bu signal allaqachon ko'rilgan (dedup)

        import pandas as pd
        ts_utc = pd.Timestamp(sig.sweep_candle_time).tz_convert("UTC").isoformat()
        cisd_ok = detect_cisd(df_m5, pd.Timestamp(sig.sweep_candle_time),
                              sig.direction) is not None
        ablation.log_signal({
            "signal_id": sid, "timestamp_utc": ts_utc, "symbol": sig.symbol,
            "direction": sig.direction, "level_type": ablation.level_type(sig.level_name),
            "sweep_wick_pct": sig.wick_pct, "cisd_confirmed": cisd_ok,
            "filter_pd": "pass" if r["pd"] else "fail",
            "filter_qt": "pass" if r["qt"] else "fail",
            "filter_qt_phase": r["qt_phase"],
            "filter_mo_bias": "pass" if r["mo"] else "fail",
            "filter_hrl": "pass" if r["hrl"] else "fail",
            "final_verdict": r["verdict"], "rejected_by": r["rejected_by"],
            "source": DATA_SOURCE,
        })

        if r["verdict"] == "accepted":
            accepted.append(sig)
        elif SHADOW_TRACKING_ENABLED:
            # Rad etilgan: Telegram/paper YO'Q — faqat yengil shadow (m5_cisd)
            register_shadow(sig, sid)

    logger.info("%s: %d signal, %d qabul (%d rad)",
                symbol, len(evaluated), len(accepted), len(evaluated) - len(accepted))
    return accepted


def run_once():
    now_ny = datetime.now(NY_TZ)
    logger.info("Skanerlash boshlandi (NY vaqti: %s)", now_ny.strftime("%Y-%m-%d %H:%M"))

    for symbol in INSTRUMENTS:
        try:
            signals = scan_symbol(symbol, now_ny)
        except Exception:
            logger.exception("Xato: %s ni skanerlashda muammo", symbol)
            continue

        for sig in signals:
            # SPAM FIX: bir daraja + yo'nalish KUNIGA BIR MARTA signal beradi
            # (avval har M5 sham uchun signal edi - bir daraja 12 martagacha).
            day = str(sig.sweep_candle_time)[:10]
            key = (sig.symbol, sig.condition, sig.level_name, sig.direction, day)
            if key in _already_notified:
                continue
            _already_notified.add(key)
            logger.info(
                "SIGNAL: %s | %s | %s | %s",
                sig.symbol, sig.condition, sig.level_name, sig.direction,
            )
            notify_signal(sig)
            register_trade(sig)  # forward-test: xayoliy savdo ochiladi

    # Ochiq xayoliy savdolarni yangi shamlar bilan tekshirish
    try:
        update_trades(connector)
    except Exception:
        logger.exception("Forward-test yangilashda xato")

    # Rad etilgan signallarning shadow (m5_cisd) natijalarini yangilash
    if ABLATION_LOG_ENABLED and SHADOW_TRACKING_ENABLED:
        try:
            update_shadows(connector)
        except Exception:
            logger.exception("Shadow-tracking yangilashda xato")


def main():
    parser = argparse.ArgumentParser(description="CRT sweep skaneri")
    parser.add_argument(
        "--once", action="store_true",
        help="Bir marta skanerlab chiqib tugatish (cron/GitHub Actions uchun)",
    )
    args = parser.parse_args()

    logger.info("CRT Scanner ishga tushmoqda (manba: %s)...", DATA_SOURCE)
    if not connector.connect():
        logger.error(
            "Narx manbasiga (%s) ulanib bo'lmadi. MT5 bo'lsa terminal "
            "ochiqligini, OANDA bo'lsa .env'dagi tokenni tekshiring.",
            DATA_SOURCE,
        )
        raise SystemExit(1)

    # Interval va maksimal ish vaqti env'dan sozlanadi (bulut uchun)
    interval = int(os.getenv("SCAN_INTERVAL_MINUTES", str(SCAN_INTERVAL_MINUTES)))
    max_runtime = int(os.getenv("MAX_RUNTIME_SEC", "0"))  # 0 = cheksiz (lokal)

    _load_notified_state()
    start = time.monotonic()
    try:
        if args.once:
            run_once()
            _save_notified_state()
            return
        while True:
            run_once()
            _save_notified_state()
            if max_runtime and time.monotonic() - start >= max_runtime:
                logger.info("Ish vaqti tugadi, chiqilyapti (workflow qayta ishga tushiradi).")
                break
            logger.info("Keyingi tekshiruv %d daqiqadan so'ng...", interval)
            time.sleep(interval * 60)
    except KeyboardInterrupt:
        logger.info("To'xtatildi (Ctrl+C).")
    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()
