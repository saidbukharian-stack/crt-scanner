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
)

if DATA_SOURCE == "oanda":
    from oanda_connector import connector
elif DATA_SOURCE == "yahoo":
    from yahoo_connector import connector
else:
    from mt5_connector import connector
from levels import all_levels_for_symbol
from signals import scan_all_conditions
from telegram_notifier import notify_signal
from outcome_tracker import register_trade, update_trades

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


def scan_symbol(symbol: str, now_ny: datetime) -> list:
    # 400 M5 (~33 soat) — Asia/London sessiya darajalari (20:00-00:00 NY, ~20
    # soat oldin) to'liq qamrab olinishi uchun (200 sham yetarli emas edi)
    df_m5 = connector.get_candles(symbol, MT5_TIMEFRAME_ENTRY, count=400)
    df_h4 = connector.get_candles(symbol, MT5_TIMEFRAME_HTF, count=60)
    df_d1 = connector.get_candles(symbol, "D1", count=10)

    if df_m5.empty or df_h4.empty or df_d1.empty:
        logger.warning("Ma'lumot yetarli emas: %s", symbol)
        return []

    levels = all_levels_for_symbol(df_m5, df_h4, df_d1, now_ny)
    signals = scan_all_conditions(df_m5, levels, symbol, SIGNAL_CONDITIONS)

    # SIFAT FILTRI: premium/discount (faqat discount'da BUY, premium'da SELL)
    from analysis import premium_discount_ok
    filtered = [s for s in signals
                if premium_discount_ok(s.close_price, s.direction, df_h4)]
    if len(filtered) < len(signals):
        logger.info("%s: P/D filtri %d dan %d signalни o'tkazdi",
                    symbol, len(signals), len(filtered))
    return filtered


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
