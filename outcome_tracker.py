"""
Outcome Tracker (forward-test)
==============================
Har yuborilgan signal uchun XAYOLIY savdo ochib, natijasini keyingi
skanlarda avtomatik o'lchaydi - treyder ishtirokisiz signal sifatini baholash.

IKKI VARIANT (treyder bilan kelishilgan, 2026-07-09):
  - "m5_cisd"    : M5 CISD tasdig'idan keyin kirish, boshqaruvsiz
                   (to'liq pozitsiya likvidlikkacha yoki stopgacha ushlanadi)
  - "m5_managed" : BIR XIL kirish, lekin SAVDO BOSHQARUVI bilan:
                   50%'da yarim olish + breakeven + qolgani likvidlikkacha

"raw" (xom purge) variant OLIB TASHLANDI: barcha o'lchovlarda minusda edi,
treyder "xom signalda savdo ochilmasin" dedi. Endi faqat M5 CISD tasdiqli
kirish o'lchanadi.

MAQSAD = LIKVIDLIK (STDV emas):
  • 50%  = diapazon o'rtasi (crt_mid) - yarim olish + breakeven nuqtasi
  • 100% = diapazonning qarshi cheti (qarshi likvidlik) - asosiy maqsad
  STDV -2/-2.5/-4 faqat QO'SHIMCHA ma'lumot sifatida yoziladi (maqsad emas).

Umumiy qoidalar:
  Muddat  = kirish kuni 17:00 NY; yetmasa "expired" (qolgan ulush close'da yopiladi)
  Bir sham ichida stop+maqsad = KONSERVATIV stop
  Muddatgacha CISD shakllanmasa = "no_m5_entry" (winrate'ga kirmaydi)

Natijalar: results/results_v3.csv (repoga commit) + Telegram.
Har savdoga `source` ustuni (mt5 / yahoo) yoziladi - lokal va bulutni ajratish uchun.
Holat: data/trades.json, data/paper_account.json (Actions cache).
"""

import csv
import json
import logging
import os
from datetime import datetime, timedelta

import paper_account
from analysis import _unfilled_fvgs
from config import (DATA_SOURCE, DB_PATH, MGMT_BE_FORCE_R, MGMT_PARTIAL_FRAC,
                    NY_TZ, OTE_REQUIRE_ROUND, OTE_REQUIRE_WINDOW)
from ote import in_ote_window, near_institutional_level, ote_zone
from silver_bullet import in_sb_window, sb_fvg_zone
from signals import SweepSignal, detect_cisd
from telegram_notifier import send_telegram_message

logger = logging.getLogger(__name__)

_TRADES_PATH = os.path.join(os.path.dirname(DB_PATH), "trades.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
# v3 = raw olib tashlandi + likvidlik maqsadlari + source ustuni.
RESULTS_CSV = os.path.join(RESULTS_DIR, "results_v3.csv")

_CSV_COLUMNS = [
    "variant", "source", "entry_time_ny", "resolved_time_ny", "symbol",
    "condition", "level_name", "direction", "entry", "sl", "r_size", "outcome",
    "hit_50", "hit_liquidity", "t50_px", "t100_px",
    # STDV - qo'shimcha ma'lumot (maqsad emas)
    "stdv_2_px", "stdv_2_5_px", "stdv_4_px",
    "mfe_r", "mae_r", "net_r", "risk_usd", "pnl_usd", "balance_after",
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


def _sign(direction: str) -> int:
    return 1 if direction == "bullish_sweep" else -1


def _targets_for(entry: float, stop: float, direction: str,
                 crt_mid, liquidity) -> tuple[dict, float, int]:
    """
    Likvidlik maqsadlarini quradi:
      t50  = crt_mid (diapazon o'rtasi)
      t100 = liquidity (qarshi cheti)
    Faqat kirishdan OLDINDA (foyda tomonida) turganlarini oladi.
    Agar t100 yo'q bo'lsa - oxirgi chora sifatida 2R.
    Qaytaradi: (targets{name:px}, r, sign)
    """
    sign = _sign(direction)
    r = (entry - stop) if sign == 1 else (stop - entry)
    targets: dict[str, float] = {}
    if crt_mid is not None and sign * (crt_mid - entry) > 0:
        targets["50"] = crt_mid
    if liquidity is not None and sign * (liquidity - entry) > 0:
        targets["liquidity"] = liquidity
    if "liquidity" not in targets:
        # juftlanmagan daraja - oxirgi chora
        targets["liquidity"] = entry + sign * 2 * r
    return targets, r, sign


# ---------------------------------------------------------------------------
# Ro'yxatga olish - scanner signal yuborganda
# ---------------------------------------------------------------------------
def register_trade(sig: SweepSignal):
    entry_dt = datetime.fromisoformat(sig.sweep_candle_time)
    expiry = _expiry_for(entry_dt).isoformat()
    common = {
        "symbol": sig.symbol,
        "source": DATA_SOURCE,
        "condition": sig.condition,
        "level_name": sig.level_name,
        "direction": sig.direction,
        "crt_mid": sig.crt_mid,
        "liquidity": sig.liquidity_target,
        "stdv": sig.stdv,
        "entry_time": sig.sweep_candle_time,   # purge vaqti (m5 boshlanish nuqtasi)
        "expiry_time": expiry,
    }
    trades = _load_trades()
    # Besh variant ham CISD kutadi (pending). Xom purge'da hech narsa ochilmaydi.
    #   m5_cisd    - M5 CISD close'da darrov, boshqaruvsiz
    #   m5_managed - M5 CISD close'da, boshqaruv bilan
    #   m5_ote     - M5 CISD'dan keyin OTE retracement (62-79%) kutib, boshqaruv
    #   m5_sb      - M5 CISD'dan keyin Silver Bullet FVG'ga (SB oynasida) kirish
    #   m1_ote     - M1 (micro) CISD + OTE retracement, aniqroq stop, boshqaruv
    for variant in ("m5_cisd", "m5_managed", "m5_ote", "m5_sb", "m1_ote"):
        tr = dict(common)
        tr.update({"variant": variant, "status": "pending",
                   "risk_usd": paper_account.risk_usd(variant)})
        trades.append(tr)
    _save_trades(trades)
    logger.info("Xayoliy savdo(lar) kutilmoqda: %s %s %s (5 variant)",
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
        df5 = connector.get_candles(symbol, "M5", count=400)
        # M1 faqat m1_* variant bo'lsa yuklanadi (micro-kirish uchun ~13h)
        need_m1 = any(t["variant"].startswith("m1") for t in trs)
        df1 = connector.get_candles(symbol, "M1", count=800) if need_m1 else None
        for tr in trs:
            df = df1 if tr["variant"].startswith("m1") else df5
            if df is None or df.empty:
                still_open.append(tr)  # ma'lumot yo'q - keyingi safar
                continue
            if tr["status"] == "pending":
                if _try_activate_m5(tr, df) is None and tr["status"] not in ("active", "ote_wait"):
                    continue          # no_entry / bad_r - yozildi, yopildi
                still_open.append(tr)  # pending / ote_wait / yangi active
            elif tr["status"] == "ote_wait":
                # CISD bo'ldi, endi zonaga (OTE retracement yoki SB FVG) qaytishни kutamiz
                if _advance_ote(tr, df) is None and tr["status"] != "active":
                    continue          # no_ote_entry - yozildi, yopildi
                still_open.append(tr)
            else:  # active
                # Migratsiya himoyasi: eski sxemadagi ochiq savdolar / olib tashlangan
                # "raw" varianti - jim tashlab yuboramiz (crash bo'lmasin).
                if tr["variant"] == "raw" or "liquidity" not in tr.get("targets", {}):
                    logger.info("Eski sxemadagi ochiq savdo tashlandi: %s %s",
                                tr.get("symbol"), tr.get("variant"))
                    continue
                # m5_cisd'dan boshqasi boshqaruvli
                walker = _walk_cisd if tr["variant"] == "m5_cisd" else _walk_managed
                resolved = walker(tr, df)
                if resolved is None:
                    still_open.append(tr)
                else:
                    outcome, net_r = resolved
                    _record_result(tr, outcome, net_r)

    _save_trades(still_open)


def _try_activate_m5(tr: dict, df) -> dict | None:
    """
    Pending savdo uchun CISD qidiradi (m5_cisd va m5_managed uchun bir xil).
    CISD topilsa active qiladi; muddat o'tsa no_m5_entry yozadi.
    """
    purge_dt = datetime.fromisoformat(tr["entry_time"])
    expiry_dt = datetime.fromisoformat(tr["expiry_time"])

    cisd = detect_cisd(df, purge_dt, tr["direction"])
    if cisd is not None:
        # Ikki-bosqichli variantlar: darrov kirmaymiz - zona (OTE retracement yoki
        # Silver Bullet FVG) hisoblab, narx qaytishini kutamiz.
        #   m5_ote, m1_ote -> OTE 62-79% zonasi, oyna = 08:30-11:00
        #   m5_sb          -> Silver Bullet FVG zonasi, oyna = SB soatlari
        if tr["variant"] in ("m5_ote", "m1_ote", "m5_sb"):
            if tr["variant"] == "m5_sb":
                zone = sb_fvg_zone(df, purge_dt, tr["direction"], cisd)
                window_kind = "sb"
                zlabel = "SB FVG"
            else:
                zone = ote_zone(df, purge_dt, tr["direction"], cisd)
                window_kind = "ote"
                zlabel = "OTE 62%"
            if zone is None:
                _record_noentry(tr, "no_ote_zone")
                return None
            tr.update({
                "status": "ote_wait",
                "ote": zone,
                "window_kind": window_kind,
                "cisd_time": cisd["entry_time"],
            })
            logger.info("Zona tayyor (%s, %s): %s %s kirish~%.5f SL %.5f",
                        tr["variant"], zlabel, tr["symbol"], tr["level_name"],
                        zone["entry"], zone["stop"])
            return None

        entry, stop = cisd["entry"], cisd["stop"]
        targets, r, _ = _targets_for(entry, stop, tr["direction"],
                                      tr.get("crt_mid"), tr.get("liquidity"))
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

    last_time = df["time_ny"].iloc[-1]
    if last_time >= expiry_dt:
        _record_noentry(tr, "no_m5_entry")
        return None
    return tr  # pending holicha qoladi


def _advance_ote(tr: dict, df) -> dict | None:
    """
    ote_wait holatidagi savdo: narx 62-79% OTE zonasiga qaytishini kutadi.
    - Zonaga tegsa (va OTE oynasida bo'lsa): 62% narxda active qiladi.
    - Likvidlik OTE'siz olinsa yoki muddat o'tsa: no_ote_entry.
    """
    oz = tr["ote"]
    expiry_dt = datetime.fromisoformat(tr["expiry_time"])
    cisd_dt = datetime.fromisoformat(tr["cisd_time"])
    is_long = tr["direction"] == "bullish_sweep"
    # Oyna turi: SB (Silver Bullet soatlari) yoki OTE (08:30-11:00)
    is_sb = tr.get("window_kind") == "sb"
    window_ok = in_sb_window if is_sb else in_ote_window

    after = df[df["time_ny"] > cisd_dt]
    for _, candle in after.iterrows():
        if candle["time_ny"] >= expiry_dt:
            _record_noentry(tr, "no_ote_entry")
            return None

        hi, low = float(candle["high"]), float(candle["low"])
        # Retracement zonaga tegdimi?
        touched = (is_long and low <= oz["zone_hi"]) or (not is_long and hi >= oz["zone_lo"])
        if touched:
            # SB har doim oyna talab qiladi; OTE config'ga qarab
            if (is_sb or OTE_REQUIRE_WINDOW) and not window_ok(candle["time_ny"]):
                continue  # zonaga tegdi, lekin oynadan tashqarida - kutamiz
            if OTE_REQUIRE_ROUND and not near_institutional_level(oz["entry"]):
                _record_noentry(tr, "no_ote_round")
                return None
            entry, stop = oz["entry"], oz["stop"]
            targets, r, _ = _targets_for(entry, stop, tr["direction"],
                                          tr.get("crt_mid"), tr.get("liquidity"))
            if r <= 0:
                _record_noentry(tr, "ote_bad_r")
                return None
            tr.update({
                "status": "active",
                "entry": entry, "sl": stop, "r": r,
                "entry_time": str(candle["time_ny"]),  # OTE retracement kirish vaqti
                "targets": targets, "hits": {k: False for k in targets},
                "mfe": entry, "mae": entry,
            })
            logger.info("OTE kirish (%s): %s %s @ %.5f (SL %.5f)",
                        tr["variant"], tr["symbol"], tr["level_name"], entry, stop)
            return None

    return tr  # hali zonaga qaytmadi, kutishда qoladi


# ---------------------------------------------------------------------------
# Boshqaruvsiz yurish (m5_cisd): to'liq pozitsiya likvidlikkacha yoki stopgacha
# ---------------------------------------------------------------------------
def _walk_cisd(tr: dict, df) -> tuple[str, float] | None:
    entry_dt = datetime.fromisoformat(tr["entry_time"])
    expiry_dt = datetime.fromisoformat(tr["expiry_time"])
    entry, r, sl = tr["entry"], tr["r"], tr["sl"]
    is_long = tr["direction"] == "bullish_sweep"
    sign = _sign(tr["direction"])
    liq = tr["targets"]["liquidity"]

    after = df[df["time_ny"] > entry_dt]
    prev_close = entry
    for _, candle in after.iterrows():
        if candle["time_ny"] >= expiry_dt:
            return "expired", sign * (prev_close - entry) / r

        hi, low = float(candle["high"]), float(candle["low"])
        if is_long:
            tr["mfe"] = max(tr["mfe"], hi); tr["mae"] = min(tr["mae"], low)
        else:
            tr["mfe"] = min(tr["mfe"], low); tr["mae"] = max(tr["mae"], hi)

        # KONSERVATIV: avval stop
        if (is_long and low <= sl) or (not is_long and hi >= sl):
            return "stop", -1.0

        for name, price in tr["targets"].items():
            if not tr["hits"][name] and ((is_long and hi >= price) or (not is_long and low <= price)):
                tr["hits"][name] = True

        # Likvidlik olindi - to'liq yopamiz
        if (is_long and hi >= liq) or (not is_long and low <= liq):
            return "liquidity", sign * (liq - entry) / r

        prev_close = float(candle["close"])

    return None


# ---------------------------------------------------------------------------
# Boshqaruvli yurish (m5_managed): 50% da yarim + breakeven + likvidlik
# ---------------------------------------------------------------------------
def _pullback_obstacle(seg, entry: float, price: float, is_long: bool) -> bool:
    """
    Kirish bilan joriy narx orasida narxni ORQAGA TORTADIGAN to'ldirilmagan
    FVG bormi? (Obyektiv OB imbalansni yaratgan shamning o'zi, ya'ni FVG bilan
    bir joyda turadi - FVG tekshiruvi OB'ni ham qamrab oladi.)
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
    50% (crt_mid) da yarim yopish + breakeven, qolgani likvidlik (100%) da.
    Har skanda kirishdan qayta yuriladi (sof funksiya, ikki marta hisob xavfsiz).
    """
    entry_dt = datetime.fromisoformat(tr["entry_time"])
    expiry_dt = datetime.fromisoformat(tr["expiry_time"])
    entry, r = tr["entry"], tr["r"]
    is_long = tr["direction"] == "bullish_sweep"
    sign = _sign(tr["direction"])

    t50 = tr["targets"].get("50")            # yarim olish + breakeven nuqtasi
    liq = tr["targets"]["liquidity"]         # qolgan yarmi
    be_force_px = entry + sign * MGMT_BE_FORCE_R * r

    sl = tr["sl"]
    remaining = 1.0
    realized = 0.0
    be_moved = False
    partial_done = False
    hits = {k: False for k in tr["targets"]}
    mfe, mae = entry, entry

    after = df[df["time_ny"] > entry_dt]
    if len(after) == 0:
        return None
    entry_pos = df.index.get_indexer([after.index[0]])[0] - 1
    prev_close = entry

    for pos, (_, candle) in enumerate(after.iterrows()):
        if candle["time_ny"] >= expiry_dt:
            realized += remaining * sign * (prev_close - entry) / r
            tr["mfe"], tr["mae"], tr["hits"] = mfe, mae, hits
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
            tr["mfe"], tr["mae"], tr["hits"] = mfe, mae, hits
            tr["partial_done"] = partial_done
            outcome = ("be_after_partial" if partial_done else "breakeven") if be_moved else "stop"
            return outcome, realized

        # 2) 50% maqsad -> yarim yopish + breakeven ko'rib chiqish
        if t50 is not None and not partial_done and \
                ((is_long and hi >= t50) or (not is_long and low <= t50)):
            realized += MGMT_PARTIAL_FRAC * sign * (t50 - entry) / r
            remaining -= MGMT_PARTIAL_FRAC
            partial_done = True
            hits["50"] = True
            # breakeven: orqaga tortadigan FVG/OB qolmagan bo'lsa
            seg = df.iloc[max(0, entry_pos): entry_pos + pos + 2]
            if not _pullback_obstacle(seg, entry, close, is_long):
                sl, be_moved = entry, True

        # 3) Likvidlik (100%) -> qolgan ulushni yopamiz
        if (is_long and hi >= liq) or (not is_long and low <= liq):
            hits["liquidity"] = True
            realized += remaining * sign * (liq - entry) / r
            tr["mfe"], tr["mae"], tr["hits"] = mfe, mae, hits
            tr["partial_done"] = partial_done
            return "liquidity", realized

        # 4) Majburiy breakeven (2R) - to'siq bo'lsa ham
        if not be_moved and ((is_long and hi >= be_force_px) or
                             (not is_long and low <= be_force_px)):
            sl, be_moved = entry, True

        prev_close = close

    tr["mfe"], tr["mae"], tr["hits"] = mfe, mae, hits
    tr["partial_done"] = partial_done
    return None


# ---------------------------------------------------------------------------
# Natija yozish
# ---------------------------------------------------------------------------
def _ensure_header():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if not os.path.exists(RESULTS_CSV):
        return
    with open(RESULTS_CSV, encoding="utf-8") as f:
        header = f.readline().strip().lstrip("﻿")
    if header == ",".join(_CSV_COLUMNS):
        return
    n = 1
    while os.path.exists(archive := os.path.join(RESULTS_DIR, f"results_v3_old{n}.csv")):
        n += 1
    os.rename(RESULTS_CSV, archive)
    logger.warning("results_v3.csv sxemasi yangilandi; eskisi %s ga saqlandi",
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
    row = {c: "" for c in _CSV_COLUMNS}
    row.update({
        "variant": tr["variant"], "source": tr.get("source", ""),
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

    stdv_px = (tr.get("stdv") or {}).get("levels", {})
    tgt = tr.get("targets", {})
    hits = tr.get("hits", {})
    row = {c: "" for c in _CSV_COLUMNS}
    row.update({
        "variant": variant, "source": tr.get("source", ""),
        "entry_time_ny": tr["entry_time"],
        "resolved_time_ny": datetime.now(NY_TZ).isoformat(timespec="seconds"),
        "symbol": tr["symbol"], "condition": tr["condition"],
        "level_name": tr["level_name"], "direction": tr["direction"],
        "entry": tr["entry"], "sl": tr["sl"], "r_size": r, "outcome": outcome,
        "hit_50": hits.get("50", ""), "hit_liquidity": hits.get("liquidity", ""),
        "t50_px": tgt.get("50", ""), "t100_px": tgt.get("liquidity", ""),
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
    "liquidity": "✅ Likvidlik olindi (100%)",
    "be_after_partial": "🟡 50% olindi, qolgani breakeven",
    "breakeven": "➖ Breakeven (zararsiz)",
    "stop": "❌ STOP urildi",
    "expired": "⏰ Muddati tugadi (17:00 NY)",
}

_VARIANT_LABEL = {
    "m5_cisd": "M5 CISD (boshqaruvsiz)",
    "m5_managed": "M5 CISD + boshqaruv",
    "m5_ote": "M5 OTE (62-79% retracement)",
    "m5_sb": "M5 Silver Bullet (FVG oyna)",
    "m1_ote": "M1 OTE (micro-kirish)",
}


def _notify_result(tr: dict, outcome: str, mfe_r: float, net_r: float,
                   pnl: float, bal: float):
    hits = tr.get("hits", {})
    reached = []
    if hits.get("50"):
        reached.append("50%")
    if hits.get("liquidity"):
        reached.append("Likvidlik(100%)")
    head = _OUTCOME_HEAD.get(outcome, outcome)
    variant = _VARIANT_LABEL.get(tr["variant"], tr["variant"])
    src = tr.get("source", "?").upper()

    lines = [
        f"📊 <b>Forward-test yakuni</b> — {variant} <i>({src})</i>",
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
    send_telegram_message("\n".join(lines))
