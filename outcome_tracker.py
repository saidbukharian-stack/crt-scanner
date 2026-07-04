"""
Outcome Tracker (forward-test)
==============================
Har yuborilgan signal uchun XAYOLIY savdo ochib, uning natijasini
keyingi skanlarda avtomatik o'lchaydi - treyder ishtirokisiz signal
sifatini baholash uchun.

Qoidalar (treyder bilan kelishilgan, 2026-07-05):
  Kirish  = purge (sweep) shamining yopilish narxi
  Stop    = purge shamining uchi (bullish'da low, bearish'da high)
  Maqsadlar (parallel o'lchanadi):
    - CRT_50: CRT diapazonining o'rtasi (faqat CRT signallari)
    - 1R / 2R / 3R: kirish-stop masofasining karralari
  Muddat  = kirish kuni 17:00 NY (forex kun yopilishi); yetmasa "expired"
  Bir sham ichida ham stop, ham maqsad bo'lsa - KONSERVATIV: stop birinchi
  (statistikani sun'iy oshirmaslik uchun).

Natijalar:
  - results/results.csv - doimiy jurnal (GitHub Actions'da repoga commit
    qilinadi, telefondan ko'rish mumkin)
  - Telegram'ga yakuniy xabar

Ochiq savdolar data/trades.json da saqlanadi (Actions cache).
"""

import csv
import json
import logging
import os
from datetime import datetime, time as dtime, timedelta

from config import DB_PATH, NY_TZ
from signals import SweepSignal
from telegram_notifier import send_telegram_message

logger = logging.getLogger(__name__)

_TRADES_PATH = os.path.join(os.path.dirname(DB_PATH), "trades.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
RESULTS_CSV = os.path.join(RESULTS_DIR, "results.csv")

_CSV_COLUMNS = [
    "entry_time_ny", "resolved_time_ny", "symbol", "condition", "level_name",
    "direction", "entry", "sl", "r_size", "outcome",
    "hit_crt_50", "hit_1r", "hit_2r", "hit_3r", "mfe_r", "mae_r",
]

_EXPIRY_HOUR_NY = 17  # forex kuni yopilishi


# ---------------------------------------------------------------------------
# Holat (ochiq savdolar) fayli
# ---------------------------------------------------------------------------
def _load_trades() -> list[dict]:
    try:
        with open(_TRADES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_trades(trades: list[dict]):
    os.makedirs(os.path.dirname(_TRADES_PATH), exist_ok=True)
    with open(_TRADES_PATH, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------------------
# Ro'yxatga olish - scanner signal yuborganda chaqiradi
# ---------------------------------------------------------------------------
def register_trade(sig: SweepSignal):
    entry = sig.close_price
    if sig.direction == "bullish_sweep":
        sl = sig.sweep_low
        r = entry - sl
        sign = 1
    else:
        sl = sig.sweep_high
        r = sl - entry
        sign = -1
    if r <= 0:
        logger.warning("Savdo ro'yxatga olinmadi (r<=0): %s %s", sig.symbol, sig.level_name)
        return

    targets = {
        "1r": entry + sign * r,
        "2r": entry + sign * 2 * r,
        "3r": entry + sign * 3 * r,
    }
    # CRT 50% - faqat foyda yo'nalishida bo'lsa ma'noli
    if sig.crt_mid is not None and sign * (sig.crt_mid - entry) > 0:
        targets["crt_50"] = sig.crt_mid

    entry_dt = datetime.fromisoformat(sig.sweep_candle_time)
    expiry = entry_dt.replace(hour=_EXPIRY_HOUR_NY, minute=0, second=0, microsecond=0)
    if entry_dt >= expiry:
        expiry += timedelta(days=1)

    trade = {
        "symbol": sig.symbol,
        "condition": sig.condition,
        "level_name": sig.level_name,
        "direction": sig.direction,
        "entry": entry,
        "sl": sl,
        "r": r,
        "entry_time": sig.sweep_candle_time,
        "expiry_time": expiry.isoformat(),
        "targets": targets,
        "hits": {k: False for k in targets},
        "mfe": entry,   # foyda tomonga eng uzoq nuqta
        "mae": entry,   # zarar tomonga eng uzoq nuqta
    }
    trades = _load_trades()
    trades.append(trade)
    _save_trades(trades)
    logger.info("Xayoliy savdo ochildi: %s %s %s @ %.5f (SL %.5f)",
                sig.symbol, sig.level_name, sig.direction, entry, sl)


# ---------------------------------------------------------------------------
# Yangilash - har skan oxirida chaqiriladi
# ---------------------------------------------------------------------------
def update_trades(connector):
    trades = _load_trades()
    if not trades:
        return

    still_open: list[dict] = []
    by_symbol: dict[str, list[dict]] = {}
    for tr in trades:
        by_symbol.setdefault(tr["symbol"], []).append(tr)

    for symbol, trs in by_symbol.items():
        df = connector.get_candles(symbol, "M5", count=300)
        if df.empty:
            still_open.extend(trs)  # ma'lumot yo'q - keyingi safar
            continue
        for tr in trs:
            resolved = _walk_trade(tr, df)
            if resolved is None:
                still_open.append(tr)
            else:
                _record_result(tr, resolved)

    _save_trades(still_open)


def _walk_trade(tr: dict, df) -> str | None:
    """
    Savdoni kirishdan keyingi shamlar bo'ylab yuritadi.
    Qaytaradi: "stop" | "expired" | "all_targets" | None (hali ochiq).
    """
    entry_dt = datetime.fromisoformat(tr["entry_time"])
    expiry_dt = datetime.fromisoformat(tr["expiry_time"])
    is_long = tr["direction"] == "bullish_sweep"
    sl = tr["sl"]

    after = df[df["time_ny"] > entry_dt]
    for _, candle in after.iterrows():
        if candle["time_ny"] >= expiry_dt:
            return "expired"

        hi, lo = float(candle["high"]), float(candle["low"])
        # MFE/MAE (ma'lumot uchun)
        if is_long:
            tr["mfe"] = max(tr["mfe"], hi)
            tr["mae"] = min(tr["mae"], lo)
        else:
            tr["mfe"] = min(tr["mfe"], lo)
            tr["mae"] = max(tr["mae"], hi)

        # KONSERVATIV: avval stop tekshiriladi
        if (is_long and lo <= sl) or (not is_long and hi >= sl):
            return "stop"

        for name, price in tr["targets"].items():
            if tr["hits"][name]:
                continue
            if (is_long and hi >= price) or (not is_long and lo <= price):
                tr["hits"][name] = True

        if all(tr["hits"].values()):
            return "all_targets"

    return None  # hali yopilmadi


def _record_result(tr: dict, outcome: str):
    r = tr["r"]
    sign = 1 if tr["direction"] == "bullish_sweep" else -1
    mfe_r = sign * (tr["mfe"] - tr["entry"]) / r
    mae_r = sign * (tr["mae"] - tr["entry"]) / r

    row = {
        "entry_time_ny": tr["entry_time"],
        "resolved_time_ny": datetime.now(NY_TZ).isoformat(timespec="seconds"),
        "symbol": tr["symbol"],
        "condition": tr["condition"],
        "level_name": tr["level_name"],
        "direction": tr["direction"],
        "entry": tr["entry"],
        "sl": tr["sl"],
        "r_size": r,
        "outcome": outcome,
        "hit_crt_50": tr["hits"].get("crt_50", ""),
        "hit_1r": tr["hits"]["1r"],
        "hit_2r": tr["hits"]["2r"],
        "hit_3r": tr["hits"]["3r"],
        "mfe_r": round(mfe_r, 2),
        "mae_r": round(mae_r, 2),
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    file_exists = os.path.exists(RESULTS_CSV)
    with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    _notify_result(tr, outcome, mfe_r)


def _notify_result(tr: dict, outcome: str, mfe_r: float):
    hits = tr["hits"]
    reached = [k.upper() for k, v in hits.items() if v]
    if outcome == "stop":
        head = "❌ STOP urildi"
    elif outcome == "all_targets":
        head = "✅ Barcha maqsadlar olindi"
    else:
        head = "⏰ Muddati tugadi (17:00 NY)"

    text = (
        f"📊 <b>Forward-test yakuni</b>\n\n"
        f"<b>{tr['symbol']}</b> | {tr['level_name']} | "
        f"{'LONG' if tr['direction'] == 'bullish_sweep' else 'SHORT'}\n"
        f"{head}\n"
        f"Yetilgan maqsadlar: {', '.join(reached) if reached else 'hech biri'}\n"
        f"Eng uzoq foyda nuqtasi: {mfe_r:+.2f}R\n"
        f"Kirish: {tr['entry']:.5f} | Stop: {tr['sl']:.5f}"
    )
    send_telegram_message(text)
