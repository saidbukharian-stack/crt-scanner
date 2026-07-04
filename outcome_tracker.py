"""
Outcome Tracker (forward-test)
==============================
Har yuborilgan signal uchun XAYOLIY savdo ochib, natijasini keyingi
skanlarda avtomatik o'lchaydi - treyder ishtirokisiz signal sifatini baholash.

IKKI VARIANT parallel o'lchanadi (treyder bilan kelishilgan, 2026-07-05):
  - "raw"     : purge (sweep) shami yopilishida darrov kirish (M5 tasdiqsiz)
  - "m5_cisd" : purge'dan keyin M5 CISD tasdig'i shakllangach kirish
                (TTrades IC-CISD; kirish=CISD close, stop=swing high/low)
Maqsad: "M5 tasdig'i winrate'ni oshiradimi?" degan savolga oy oxirida
raqam bilan javob berish.

Umumiy qoidalar:
  Maqsadlar: CRT-50% (faqat CRT signali) + 1R/2R/3R (kirish-stop masofasi)
  Muddat  = kirish kuni 17:00 NY; yetmasa "expired"
  Bir sham ichida stop+maqsad = KONSERVATIV stop
  m5_cisd varianti muddatgacha CISD shakllanmasa = "no_m5_entry" (winrate'ga kirmaydi)

Natijalar: results/results.csv (repoga commit) + Telegram.
Holat: data/trades.json (Actions cache).
"""

import csv
import json
import logging
import os
from datetime import datetime, timedelta

from config import DB_PATH, NY_TZ
from signals import SweepSignal, detect_cisd
from telegram_notifier import send_telegram_message

logger = logging.getLogger(__name__)

_TRADES_PATH = os.path.join(os.path.dirname(DB_PATH), "trades.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
RESULTS_CSV = os.path.join(RESULTS_DIR, "results.csv")

_CSV_COLUMNS = [
    "variant", "entry_time_ny", "resolved_time_ny", "symbol", "condition",
    "level_name", "direction", "entry", "sl", "r_size", "outcome",
    "hit_crt_50", "hit_1r", "hit_2r", "hit_3r", "mfe_r", "mae_r",
]

_EXPIRY_HOUR_NY = 17  # forex kuni yopilishi


# ---------------------------------------------------------------------------
# Holat fayli
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


def _expiry_for(entry_dt: datetime) -> datetime:
    expiry = entry_dt.replace(hour=_EXPIRY_HOUR_NY, minute=0, second=0, microsecond=0)
    if entry_dt >= expiry:
        expiry += timedelta(days=1)
    return expiry


def _build_targets(entry: float, stop: float, direction: str, crt_mid):
    """Maqsad narxlari + R hajmi + yo'nalish belgisi."""
    if direction == "bullish_sweep":
        r = entry - stop
        sign = 1
    else:
        r = stop - entry
        sign = -1
    targets = {
        "1r": entry + sign * r,
        "2r": entry + sign * 2 * r,
        "3r": entry + sign * 3 * r,
    }
    if crt_mid is not None and sign * (crt_mid - entry) > 0:
        targets["crt_50"] = crt_mid
    return targets, r, sign


# ---------------------------------------------------------------------------
# Ro'yxatga olish - scanner signal yuborganda
# ---------------------------------------------------------------------------
def register_trade(sig: SweepSignal):
    entry_dt = datetime.fromisoformat(sig.sweep_candle_time)
    expiry = _expiry_for(entry_dt).isoformat()
    common = {
        "symbol": sig.symbol,
        "condition": sig.condition,
        "level_name": sig.level_name,
        "direction": sig.direction,
        "crt_mid": sig.crt_mid,
        "entry_time": sig.sweep_candle_time,   # purge vaqti (m5 uchun boshlanish nuqtasi)
        "expiry_time": expiry,
    }
    trades = _load_trades()

    # 1) RAW variant: purge close'ida darrov active
    entry = sig.close_price
    stop = sig.sweep_low if sig.direction == "bullish_sweep" else sig.sweep_high
    targets, r, _ = _build_targets(entry, stop, sig.direction, sig.crt_mid)
    if r > 0:
        raw = dict(common)
        raw.update({
            "variant": "raw", "status": "active",
            "entry": entry, "sl": stop, "r": r,
            "targets": targets, "hits": {k: False for k in targets},
            "mfe": entry, "mae": entry,
        })
        trades.append(raw)
    else:
        logger.warning("raw savdo ochilmadi (r<=0): %s %s", sig.symbol, sig.level_name)

    # 2) M5_CISD variant: hozircha pending - CISD keyingi skanlarda qidiriladi
    m5 = dict(common)
    m5.update({"variant": "m5_cisd", "status": "pending"})
    trades.append(m5)

    _save_trades(trades)
    logger.info("Xayoliy savdo(lar) ochildi: %s %s %s (raw + m5 pending)",
                sig.symbol, sig.level_name, sig.direction)


# ---------------------------------------------------------------------------
# Yangilash - har skan oxirida
# ---------------------------------------------------------------------------
def update_trades(connector):
    trades = _load_trades()
    if not trades:
        return

    by_symbol: dict[str, list[dict]] = {}
    for tr in trades:
        by_symbol.setdefault(tr["symbol"], []).append(tr)

    still_open: list[dict] = []
    for symbol, trs in by_symbol.items():
        df = connector.get_candles(symbol, "M5", count=300)
        if df.empty:
            still_open.extend(trs)  # ma'lumot yo'q - keyingi safar
            continue
        for tr in trs:
            if tr["status"] == "pending":
                kept = _try_activate_m5(tr, df)
                if kept is not None:
                    still_open.append(kept)
                # None => hal bo'ldi (activate yoki no_entry), _record ichida yozildi
                if tr.get("status") == "active":
                    still_open.append(tr)  # yangi active'ni ham kuzatishda qoldiramiz
            else:  # active
                resolved = _walk_trade(tr, df)
                if resolved is None:
                    still_open.append(tr)
                else:
                    _record_result(tr, resolved)

    _save_trades(still_open)


def _try_activate_m5(tr: dict, df) -> dict | None:
    """
    Pending m5 savdo uchun CISD qidiradi.
    - CISD topilsa: tr'ni active qilib to'ldiradi, None qaytaradi
      (chaqiruvchi active ro'yxatga qo'shadi).
    - Muddat o'tsa: no_m5_entry natijasini yozadi, None qaytaradi.
    - Hali shakllanmagan: tr'ni pending holicha qaytaradi.
    """
    purge_dt = datetime.fromisoformat(tr["entry_time"])
    expiry_dt = datetime.fromisoformat(tr["expiry_time"])

    cisd = detect_cisd(df, purge_dt, tr["direction"])
    if cisd is not None:
        entry, stop = cisd["entry"], cisd["stop"]
        targets, r, _ = _build_targets(entry, stop, tr["direction"], tr.get("crt_mid"))
        if r <= 0:
            _record_noentry(tr, "m5_bad_r")
            return None
        tr.update({
            "status": "active",
            "entry": entry, "sl": stop, "r": r,
            "entry_time": cisd["entry_time"],  # kirish vaqti = CISD close
            "targets": targets, "hits": {k: False for k in targets},
            "mfe": entry, "mae": entry,
        })
        logger.info("M5 CISD tasdiq: %s %s @ %.5f (SL %.5f)",
                    tr["symbol"], tr["level_name"], entry, stop)
        return None

    # CISD hali yo'q - muddat o'tdimi?
    last_time = df["time_ny"].iloc[-1]
    if last_time >= expiry_dt:
        _record_noentry(tr, "no_m5_entry")
        return None
    return tr  # pending holicha qoladi


def _walk_trade(tr: dict, df) -> str | None:
    """Savdoni kirishdan keyingi shamlar bo'ylab yuritadi."""
    entry_dt = datetime.fromisoformat(tr["entry_time"])
    expiry_dt = datetime.fromisoformat(tr["expiry_time"])
    is_long = tr["direction"] == "bullish_sweep"
    sl = tr["sl"]

    after = df[df["time_ny"] > entry_dt]
    for _, candle in after.iterrows():
        if candle["time_ny"] >= expiry_dt:
            return "expired"

        hi, low = float(candle["high"]), float(candle["low"])
        if is_long:
            tr["mfe"] = max(tr["mfe"], hi)
            tr["mae"] = min(tr["mae"], low)
        else:
            tr["mfe"] = min(tr["mfe"], low)
            tr["mae"] = max(tr["mae"], hi)

        # KONSERVATIV: avval stop
        if (is_long and low <= sl) or (not is_long and hi >= sl):
            return "stop"

        for name, price in tr["targets"].items():
            if tr["hits"][name]:
                continue
            if (is_long and hi >= price) or (not is_long and low <= price):
                tr["hits"][name] = True

        if all(tr["hits"].values()):
            return "all_targets"

    return None


# ---------------------------------------------------------------------------
# Natija yozish
# ---------------------------------------------------------------------------
def _write_row(row: dict):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    exists = os.path.exists(RESULTS_CSV)
    with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _record_noentry(tr: dict, outcome: str):
    """m5 varianti CISD shakllanmay muddati o'tgan holat."""
    _write_row({
        "variant": tr["variant"],
        "entry_time_ny": tr["entry_time"],
        "resolved_time_ny": datetime.now(NY_TZ).isoformat(timespec="seconds"),
        "symbol": tr["symbol"], "condition": tr["condition"],
        "level_name": tr["level_name"], "direction": tr["direction"],
        "entry": "", "sl": "", "r_size": "", "outcome": outcome,
        "hit_crt_50": "", "hit_1r": "", "hit_2r": "", "hit_3r": "",
        "mfe_r": "", "mae_r": "",
    })
    logger.info("%s: %s (CISD shakllanmadi)", tr["symbol"], outcome)


def _record_result(tr: dict, outcome: str):
    r = tr["r"]
    sign = 1 if tr["direction"] == "bullish_sweep" else -1
    mfe_r = sign * (tr["mfe"] - tr["entry"]) / r
    mae_r = sign * (tr["mae"] - tr["entry"]) / r

    _write_row({
        "variant": tr["variant"],
        "entry_time_ny": tr["entry_time"],
        "resolved_time_ny": datetime.now(NY_TZ).isoformat(timespec="seconds"),
        "symbol": tr["symbol"], "condition": tr["condition"],
        "level_name": tr["level_name"], "direction": tr["direction"],
        "entry": tr["entry"], "sl": tr["sl"], "r_size": r, "outcome": outcome,
        "hit_crt_50": tr["hits"].get("crt_50", ""),
        "hit_1r": tr["hits"]["1r"], "hit_2r": tr["hits"]["2r"],
        "hit_3r": tr["hits"]["3r"],
        "mfe_r": round(mfe_r, 2), "mae_r": round(mae_r, 2),
    })
    _notify_result(tr, outcome, mfe_r)


def _notify_result(tr: dict, outcome: str, mfe_r: float):
    reached = [k.upper() for k, v in tr["hits"].items() if v]
    if outcome == "stop":
        head = "❌ STOP urildi"
    elif outcome == "all_targets":
        head = "✅ Barcha maqsadlar olindi"
    else:
        head = "⏰ Muddati tugadi (17:00 NY)"
    variant = "Xom (purge)" if tr["variant"] == "raw" else "M5 CISD tasdiqli"

    text = (
        f"📊 <b>Forward-test yakuni</b> — {variant}\n\n"
        f"<b>{tr['symbol']}</b> | {tr['level_name']} | "
        f"{'LONG' if tr['direction'] == 'bullish_sweep' else 'SHORT'}\n"
        f"{head}\n"
        f"Yetilgan maqsadlar: {', '.join(reached) if reached else 'hech biri'}\n"
        f"Eng uzoq foyda nuqtasi: {mfe_r:+.2f}R\n"
        f"Kirish: {tr['entry']:.5f} | Stop: {tr['sl']:.5f}"
    )
    send_telegram_message(text)
