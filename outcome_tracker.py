"""
Outcome Tracker (forward-test)
==============================
Har yuborilgan signal uchun XAYOLIY savdo ochib, natijasini keyingi
skanlarda avtomatik o'lchaydi - treyder ishtirokisiz signal sifatini baholash.

UCH VARIANT parallel o'lchanadi:
  - "raw"        : purge (sweep) shami yopilishida darrov kirish (M5 tasdiqsiz)
  - "m5_cisd"    : purge'dan keyin M5 CISD tasdig'i shakllangach kirish
                   (TTrades IC-CISD; kirish=CISD close, stop=swing high/low)
  - "m5_managed" : m5_cisd bilan BIR XIL kirish/stop, lekin SAVDO BOSHQARUVI bilan:
                   qisman yopish + breakeven + STDV maqsadlari.
                   (qo'shildi 2026-07-08)

Nega uchinchi variant m5_cisd bilan bir xil kirishda? Chunki shunda
"boshqaruv natijani yaxshiladimi?" degan savolga TOZA A/B javob chiqadi —
kirish bir xil, faqat boshqaruv farq qiladi.

Umumiy qoidalar:
  Muddat  = kirish kuni 17:00 NY; yetmasa "expired" (qolgan ulush close'da yopiladi)
  Bir sham ichida stop+maqsad = KONSERVATIV stop
  m5 variantlari muddatgacha CISD shakllanmasa = "no_m5_entry" (winrate'ga kirmaydi)

raw / m5_cisd maqsadlari : CRT-50% (faqat CRT signali) + 1R/2R/3R
m5_managed maqsadlari    : MGMT_PARTIAL_AT_R da yarim yopish, qolgani STDV -4 gacha

BOSHQARUV MANTIG'I (m5_managed):
  1) Narx MGMT_PARTIAL_AT_R (1R) ga yetsa -> yarim pozitsiya yopiladi (foyda qulflandi)
  2) Breakeven: narx MGMT_BE_TRIGGER_R ga yetgach, kirish bilan joriy narx
     orasida TO'LDIRILMAGAN FVG qolmagan bo'lsa -> stop kirishga ko'chadi.
     Agar FVG qolgan bo'lsa, narx uni to'ldirish uchun qaytishi tabiiy —
     shuning uchun kutamiz (MGMT_BE_FORCE_R ga yetguncha).
  3) Qolgan ulush STDV -4 (yoki 3R) da yopiladi, yetmasa 17:00 NY close'da.

Natijalar: results/results.csv (repoga commit) + Telegram.
Holat: data/trades.json, data/paper_account.json (Actions cache).
"""

import csv
import json
import logging
import os
from datetime import datetime, timedelta

import paper_account
from analysis import _unfilled_fvgs
from config import (DB_PATH, MGMT_BE_FORCE_R, MGMT_BE_TRIGGER_R,
                    MGMT_PARTIAL_AT_R, MGMT_PARTIAL_FRAC, MGMT_RUNNER_TARGET,
                    NY_TZ)
from signals import SweepSignal, detect_cisd
from telegram_notifier import send_telegram_message

logger = logging.getLogger(__name__)

_TRADES_PATH = os.path.join(os.path.dirname(DB_PATH), "trades.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
# v2 = uchinchi variant (m5_managed) + STDV + $ ustunlari qo'shilgan sxema.
# Eski results.csv o'z holicha qoladi (2026-07-06..08 ma'lumoti) - bulut eski
# kodda ishlayotgan paytda ikkalasi bir faylga yozib ustunlarni buzmasin.
RESULTS_CSV = os.path.join(RESULTS_DIR, "results_v2.csv")

_CSV_COLUMNS = [
    "variant", "entry_time_ny", "resolved_time_ny", "symbol", "condition",
    "level_name", "direction", "entry", "sl", "r_size", "outcome",
    "hit_crt_50", "hit_1r", "hit_2r", "hit_3r",
    "hit_stdv_2", "hit_stdv_2_5", "hit_stdv_4",
    # STDV maqsad narxlari - keyinchalik "runner -2 da chiqsa nima bo'lardi?"
    # kabi savollarni CSV'dan qayta hisoblash uchun
    "stdv_2_px", "stdv_2_5_px", "stdv_4_px",
    "mfe_r", "mae_r", "net_r", "risk_usd", "pnl_usd", "balance_after",
]

_EXPIRY_HOUR_NY = 17  # forex kuni yopilishi

_STDV_KEYS = ("stdv_2", "stdv_2_5", "stdv_4")


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


def _sign(direction: str) -> int:
    return 1 if direction == "bullish_sweep" else -1


def _build_targets(entry: float, stop: float, direction: str, crt_mid):
    """raw / m5_cisd uchun maqsad narxlari + R hajmi + yo'nalish belgisi."""
    sign = _sign(direction)
    r = (entry - stop) if sign == 1 else (stop - entry)
    targets = {
        "1r": entry + sign * r,
        "2r": entry + sign * 2 * r,
        "3r": entry + sign * 3 * r,
    }
    if crt_mid is not None and sign * (crt_mid - entry) > 0:
        targets["crt_50"] = crt_mid
    return targets, r, sign


def _valid_stdv_targets(stdv: dict | None, entry: float, sign: int) -> dict:
    """STDV darajalaridan faqat kirishdan OLDINDA turganlarini qaytaradi."""
    if not stdv:
        return {}
    return {k: px for k, px in stdv.get("levels", {}).items()
            if sign * (px - entry) > 0}


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
        "stdv": sig.stdv,
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
            "risk_usd": paper_account.risk_usd("raw"),
        })
        trades.append(raw)
    else:
        logger.warning("raw savdo ochilmadi (r<=0): %s %s", sig.symbol, sig.level_name)

    # 2-3) M5 variantlari: pending - CISD keyingi skanlarda qidiriladi
    for variant in ("m5_cisd", "m5_managed"):
        m5 = dict(common)
        m5.update({"variant": variant, "status": "pending",
                   "risk_usd": paper_account.risk_usd(variant)})
        trades.append(m5)

    _save_trades(trades)
    logger.info("Xayoliy savdo(lar) ochildi: %s %s %s (raw + m5_cisd + m5_managed)",
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
        df = connector.get_candles(symbol, "M5", count=400)
        if df.empty:
            still_open.extend(trs)  # ma'lumot yo'q - keyingi safar
            continue
        for tr in trs:
            if tr["status"] == "pending":
                if _try_activate_m5(tr, df) is None and tr["status"] != "active":
                    continue          # no_m5_entry / m5_bad_r - yozildi, yopildi
                still_open.append(tr)  # pending yoki yangi active
            else:  # active
                walker = _walk_managed if tr["variant"] == "m5_managed" else _walk_trade
                resolved = walker(tr, df)
                if resolved is None:
                    still_open.append(tr)
                else:
                    outcome, net_r = resolved
                    _record_result(tr, outcome, net_r)

    _save_trades(still_open)


def _try_activate_m5(tr: dict, df) -> dict | None:
    """
    Pending m5 savdo uchun CISD qidiradi (m5_cisd va m5_managed uchun bir xil).
    - CISD topilsa: tr'ni active qilib to'ldiradi, None qaytaradi.
    - Muddat o'tsa: no_m5_entry natijasini yozadi, None qaytaradi.
    - Hali shakllanmagan: tr'ni pending holicha qaytaradi.
    """
    purge_dt = datetime.fromisoformat(tr["entry_time"])
    expiry_dt = datetime.fromisoformat(tr["expiry_time"])

    cisd = detect_cisd(df, purge_dt, tr["direction"])
    if cisd is not None:
        entry, stop = cisd["entry"], cisd["stop"]
        targets, r, sign = _build_targets(entry, stop, tr["direction"], tr.get("crt_mid"))
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
        logger.info("M5 CISD tasdiq (%s): %s %s @ %.5f (SL %.5f)",
                    tr["variant"], tr["symbol"], tr["level_name"], entry, stop)
        return None

    # CISD hali yo'q - muddat o'tdimi?
    last_time = df["time_ny"].iloc[-1]
    if last_time >= expiry_dt:
        _record_noentry(tr, "no_m5_entry")
        return None
    return tr  # pending holicha qoladi


# ---------------------------------------------------------------------------
# Boshqaruvsiz yurish (raw, m5_cisd) - eski xatti-harakat
# ---------------------------------------------------------------------------
def _walk_trade(tr: dict, df) -> tuple[str, float] | None:
    """
    Savdoni kirishdan keyingi shamlar bo'ylab yuritadi (boshqaruvsiz).
    Qaytaradi: (outcome, net_r) yoki None (hali ochiq).
    """
    entry_dt = datetime.fromisoformat(tr["entry_time"])
    expiry_dt = datetime.fromisoformat(tr["expiry_time"])
    entry, r, sl = tr["entry"], tr["r"], tr["sl"]
    is_long = tr["direction"] == "bullish_sweep"
    sign = _sign(tr["direction"])

    after = df[df["time_ny"] > entry_dt]
    prev_close = entry
    for _, candle in after.iterrows():
        if candle["time_ny"] >= expiry_dt:
            return "expired", sign * (prev_close - entry) / r

        hi, low = float(candle["high"]), float(candle["low"])
        if is_long:
            tr["mfe"] = max(tr["mfe"], hi)
            tr["mae"] = min(tr["mae"], low)
        else:
            tr["mfe"] = min(tr["mfe"], low)
            tr["mae"] = max(tr["mae"], hi)

        # KONSERVATIV: avval stop
        if (is_long and low <= sl) or (not is_long and hi >= sl):
            return "stop", -1.0

        for name, price in tr["targets"].items():
            if tr["hits"][name]:
                continue
            if (is_long and hi >= price) or (not is_long and low <= price):
                tr["hits"][name] = True

        if all(tr["hits"].values()):
            return "all_targets", 3.0

        prev_close = float(candle["close"])

    return None


# ---------------------------------------------------------------------------
# Boshqaruvli yurish (m5_managed)
# ---------------------------------------------------------------------------
def _pullback_obstacle(seg, entry: float, price: float, is_long: bool) -> bool:
    """
    Kirish bilan joriy narx orasida narxni ORQAGA TORTADIGAN to'ldirilmagan
    FVG bormi?

    LONG'da yuqoriga ketgan impuls o'zidan pastda bullish FVG qoldiradi —
    narx uni to'ldirish uchun qaytishi juda ehtimolli. Bunday holda stopni
    breakeven'ga ko'chirsak, oddiy retracement bizni bekorga yopadi.

    ESLATMA: obyektiv Order Block shu imbalansni yaratgan shamning o'zi —
    ya'ni deyarli har doim FVG bilan bir joyda turadi. Shuning uchun FVG
    tekshiruvi OB'ni ham amalda qamrab oladi. Alohida OB tekshiruvi hozircha
    qo'shilmagan.
    """
    if len(seg) < 3:
        return False
    want = "bullish" if is_long else "bearish"
    lo_b, hi_b = (entry, price) if is_long else (price, entry)
    for kind, g_lo, g_hi in _unfilled_fvgs(seg):
        if kind != want:
            continue
        mid = (g_lo + g_hi) / 2
        if lo_b <= mid <= hi_b:
            return True
    return False


def _walk_managed(tr: dict, df) -> tuple[str, float] | None:
    """
    m5_managed: qisman yopish + breakeven + STDV maqsadlari.

    Har skanda kirishdan boshlab QAYTA yuriladi (holat saqlanmaydi), shuning
    uchun funksiya sof: bir xil shamlar -> bir xil natija, ikki marta
    hisoblanish xavfi yo'q.
    """
    entry_dt = datetime.fromisoformat(tr["entry_time"])
    expiry_dt = datetime.fromisoformat(tr["expiry_time"])
    entry, r = tr["entry"], tr["r"]
    is_long = tr["direction"] == "bullish_sweep"
    sign = _sign(tr["direction"])

    stdv_targets = _valid_stdv_targets(tr.get("stdv"), entry, sign)
    partial_px = entry + sign * MGMT_PARTIAL_AT_R * r

    runner_px = stdv_targets.get(MGMT_RUNNER_TARGET)
    # Yakuniy maqsad qisman-yopish darajasidan yaqinroq bo'lsa (nodir, lekin
    # kichik oyoqda uchraydi) - STDV'ga ishonmay 3R zaxirasiga qaytamiz.
    if runner_px is None or sign * (runner_px - partial_px) <= 0:
        runner_px = entry + sign * 3 * r

    sl = tr["sl"]
    remaining = 1.0
    realized = 0.0
    be_moved = False
    partial_done = False
    hits = {k: False for k in tr["targets"]}
    stdv_hits = {k: False for k in _STDV_KEYS}
    mfe, mae = entry, entry

    after = df[df["time_ny"] > entry_dt]
    entry_pos = df.index.get_indexer([after.index[0]])[0] - 1 if len(after) else -1
    prev_close = entry

    for pos, (_, candle) in enumerate(after.iterrows()):
        if candle["time_ny"] >= expiry_dt:
            realized += remaining * sign * (prev_close - entry) / r
            tr["mfe"], tr["mae"] = mfe, mae
            tr["hits"], tr["stdv_hits"] = hits, stdv_hits
            tr["partial_done"] = partial_done
            return "expired", realized

        hi, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])
        if is_long:
            mfe, mae = max(mfe, hi), min(mae, low)
        else:
            mfe, mae = min(mfe, low), max(mae, hi)

        # 1) KONSERVATIV: avval stop (B/E ko'chirilgan bo'lsa sl == entry)
        if (is_long and low <= sl) or (not is_long and hi >= sl):
            realized += remaining * sign * (sl - entry) / r
            tr["mfe"], tr["mae"] = mfe, mae
            tr["hits"], tr["stdv_hits"] = hits, stdv_hits
            tr["partial_done"] = partial_done
            if be_moved:
                outcome = "be_after_partial" if partial_done else "breakeven"
            else:
                outcome = "stop"
            return outcome, realized

        # 2) Qisman yopish
        if not partial_done and ((is_long and hi >= partial_px) or
                                 (not is_long and low <= partial_px)):
            realized += MGMT_PARTIAL_FRAC * MGMT_PARTIAL_AT_R
            remaining -= MGMT_PARTIAL_FRAC
            partial_done = True

        # 3) Maqsadlarni belgilash (hisobot uchun)
        for name, price in tr["targets"].items():
            if not hits[name] and ((is_long and hi >= price) or (not is_long and low <= price)):
                hits[name] = True
        for name, price in stdv_targets.items():
            if name in stdv_hits and not stdv_hits[name] and \
                    ((is_long and hi >= price) or (not is_long and low <= price)):
                stdv_hits[name] = True

        # 4) Qolgan ulushni yakuniy maqsadda yopish
        if (is_long and hi >= runner_px) or (not is_long and low <= runner_px):
            realized += remaining * sign * (runner_px - entry) / r
            tr["mfe"], tr["mae"] = mfe, mae
            tr["hits"], tr["stdv_hits"] = hits, stdv_hits
            tr["partial_done"] = partial_done
            return "runner_target", realized

        # 5) Breakeven qarori (stopdan KEYIN — bir shamda ikkalasi bo'lsa stop ustun)
        if not be_moved:
            mfe_r = sign * (mfe - entry) / r
            if mfe_r >= MGMT_BE_TRIGGER_R:
                if mfe_r >= MGMT_BE_FORCE_R:
                    sl, be_moved = entry, True
                else:
                    seg = df.iloc[max(0, entry_pos): entry_pos + pos + 2]
                    if not _pullback_obstacle(seg, entry, close, is_long):
                        sl, be_moved = entry, True

        prev_close = close

    tr["mfe"], tr["mae"] = mfe, mae
    tr["hits"], tr["stdv_hits"] = hits, stdv_hits
    return None


# ---------------------------------------------------------------------------
# Natija yozish
# ---------------------------------------------------------------------------
def _ensure_header():
    """CSV sxemasi o'zgargan bo'lsa, eskisini arxivlab yangisini boshlaydi."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if not os.path.exists(RESULTS_CSV):
        return
    with open(RESULTS_CSV, encoding="utf-8") as f:
        header = f.readline().strip()
    if header == ",".join(_CSV_COLUMNS):
        return
    n = 1
    while os.path.exists(archive := os.path.join(RESULTS_DIR, f"results_v{n}.csv")):
        n += 1
    os.rename(RESULTS_CSV, archive)
    logger.warning("results.csv sxemasi yangilandi; eskisi %s ga saqlandi",
                   os.path.basename(archive))


def _write_row(row: dict):
    _ensure_header()
    exists = os.path.exists(RESULTS_CSV)
    with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _record_noentry(tr: dict, outcome: str):
    """m5 varianti CISD shakllanmay muddati o'tgan holat (P&L yo'q)."""
    row = {c: "" for c in _CSV_COLUMNS}
    row.update({
        "variant": tr["variant"],
        "entry_time_ny": tr["entry_time"],
        "resolved_time_ny": datetime.now(NY_TZ).isoformat(timespec="seconds"),
        "symbol": tr["symbol"], "condition": tr["condition"],
        "level_name": tr["level_name"], "direction": tr["direction"],
        "outcome": outcome,
    })
    _write_row(row)
    logger.info("%s (%s): %s (CISD shakllanmadi)", tr["symbol"], tr["variant"], outcome)


def _record_result(tr: dict, outcome: str, net_r: float):
    r = tr["r"]
    sign = _sign(tr["direction"])
    mfe_r = sign * (tr["mfe"] - tr["entry"]) / r
    mae_r = sign * (tr["mae"] - tr["entry"]) / r

    variant = tr["variant"]
    risk = tr.get("risk_usd") or paper_account.risk_usd(variant)
    pnl, bal = paper_account.apply_pnl(variant, net_r, risk)

    stdv_hits = tr.get("stdv_hits", {})
    stdv_px = (tr.get("stdv") or {}).get("levels", {})
    row = {c: "" for c in _CSV_COLUMNS}
    row.update({
        "variant": variant,
        "entry_time_ny": tr["entry_time"],
        "resolved_time_ny": datetime.now(NY_TZ).isoformat(timespec="seconds"),
        "symbol": tr["symbol"], "condition": tr["condition"],
        "level_name": tr["level_name"], "direction": tr["direction"],
        "entry": tr["entry"], "sl": tr["sl"], "r_size": r, "outcome": outcome,
        "hit_crt_50": tr["hits"].get("crt_50", ""),
        "hit_1r": tr["hits"].get("1r", ""),
        "hit_2r": tr["hits"].get("2r", ""),
        "hit_3r": tr["hits"].get("3r", ""),
        "hit_stdv_2": stdv_hits.get("stdv_2", ""),
        "hit_stdv_2_5": stdv_hits.get("stdv_2_5", ""),
        "hit_stdv_4": stdv_hits.get("stdv_4", ""),
        "stdv_2_px": stdv_px.get("stdv_2", ""),
        "stdv_2_5_px": stdv_px.get("stdv_2_5", ""),
        "stdv_4_px": stdv_px.get("stdv_4", ""),
        "mfe_r": round(mfe_r, 2), "mae_r": round(mae_r, 2),
        "net_r": round(net_r, 3), "risk_usd": risk,
        "pnl_usd": pnl, "balance_after": bal,
    })
    _write_row(row)
    _notify_result(tr, outcome, mfe_r, net_r, pnl, bal)


_OUTCOME_HEAD = {
    "stop": "❌ STOP urildi",
    "all_targets": "✅ Barcha maqsadlar olindi",
    "runner_target": "✅ Yakuniy maqsad (STDV) olindi",
    "breakeven": "➖ Breakeven (zararsiz)",
    "be_after_partial": "🟡 Yarmi olindi, qolgani breakeven",
    "expired": "⏰ Muddati tugadi (17:00 NY)",
}

_VARIANT_LABEL = {
    "raw": "Xom (purge)",
    "m5_cisd": "M5 CISD tasdiqli",
    "m5_managed": "M5 CISD + boshqaruv",
}


def _notify_result(tr: dict, outcome: str, mfe_r: float, net_r: float,
                   pnl: float, bal: float):
    reached = [k.upper() for k, v in tr["hits"].items() if v]
    reached += [k.replace("stdv_", "STDV-").replace("_", ".")
                for k, v in tr.get("stdv_hits", {}).items() if v]
    head = _OUTCOME_HEAD.get(outcome, outcome)
    variant = _VARIANT_LABEL.get(tr["variant"], tr["variant"])

    lines = [
        f"📊 <b>Forward-test yakuni</b> — {variant}",
        "",
        f"<b>{tr['symbol']}</b> | {tr['level_name']} | "
        f"{'LONG' if tr['direction'] == 'bullish_sweep' else 'SHORT'}",
        head,
        f"Yetilgan maqsadlar: {', '.join(reached) if reached else 'hech biri'}",
        f"Eng uzoq foyda nuqtasi (MFE): {mfe_r:+.2f}R",
        f"<b>Yakuniy natija: {net_r:+.2f}R = {pnl:+.2f}$</b>",
        f"Kirish: {tr['entry']:.5f} | Stop: {tr['sl']:.5f}",
        f"Balans ({variant}): ${bal:,.2f}",
    ]
    if tr["variant"] == "m5_managed" and tr.get("partial_done"):
        lines.insert(5, f"Yarim pozitsiya {MGMT_PARTIAL_AT_R:g}R da yopilgan")
    send_telegram_message("\n".join(lines))
