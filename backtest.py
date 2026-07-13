"""
Backtest — tarixiy ma'lumotda jonli skaner mantig'ini yuritish
==============================================================
CLI:  python backtest.py --symbol EURUSD --from 2025-01-01 --to 2025-07-01

TAMOYILLAR
----------
1) BIR XIL KOD YO'LI: signal topish va filtrlar `scanner._scan_and_filter`
   (levels -> signals -> evaluate_signal_filters) orqali — jonli skaner bilan
   aynan bir xil funksiyalar. Savdo hayot sikli `outcome_tracker`ning o'sha
   funksiyalari (_try_activate_m5, _advance_ote, _walk_cisd, _walk_managed)
   bilan yuritiladi (fayl/Telegram yozuvchilari vaqtincha almashtiriladi).

2) LOOK-AHEAD YO'Q: har vaqt nuqtasida faqat o'sha paytgacha YOPILGAN barlar:
   - M5: joriy bar yopilgach skan (jonli skaner ham amalda shunday ko'radi)
   - H4/D1: yopilgan barlar + joriy QISMAN bar M5'dan qayta quriladi
     (tayyor H4/D1 barni olish = kelajakni ko'rish bo'lardi!)
   - CISD aniqlash: o'sish tartibidagi kesimlarda (jonli skanер har 2 daqiqada
     chaqirgani kabi) — to'liq df'da argmax kelajakni ko'rishi mumkin edi.

3) SPREAD: config.SPREAD_PRICE (narx birligida) har yakunlangan savdodan
   bir marta ayiriladi (konservativ).

4) DETERMINIZM: bir oraliq ikki marta yurgizilsa natija aynan bir xil
   (run_id ham sana oralig'idan hisoblanadi; joriy vaqt ishlatilmaydi).

Natija: results/backtest_results.csv (results_v3 ustunlari + signal_id,
filtr ustunlari, final_verdict, rejected_by, run_id, is_backtest).
"""

import argparse
import csv
import hashlib
import logging
import os
import sys
from datetime import datetime, time as dtime, timedelta, timezone

import pandas as pd

import ablation
import outcome_tracker as ot
from config import (BACKTEST_SPREAD_MULT, NY_TZ, PAPER_RISK_PCT,
                    PAPER_START_BALANCE, SPREAD_PRICE)
from signals import SweepSignal  # noqa: F401 (tip uchun)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backtest")

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
BACKTEST_CSV = os.path.join(RESULTS_DIR, "backtest_results.csv")

COLUMNS = ot._CSV_COLUMNS + [
    "signal_id", "final_verdict", "rejected_by",
    "filter_pd", "filter_qt", "filter_qt_phase", "filter_mo_bias", "filter_hrl",
    "run_id", "is_backtest",
]

VARIANTS = ("m5_cisd", "m5_managed", "m5_ote", "m5_sb", "m1_ote")


# ---------------------------------------------------------------------------
# Ma'lumot olish (MT5 -> Yahoo fallback)
# ---------------------------------------------------------------------------
def _fetch_all(symbol: str, start: datetime, end: datetime):
    """M5/H4/D1/M1 tarixini (warmup zaxiralari bilan) qaytaradi + manba nomi."""
    warm_m5 = start - timedelta(days=5)
    warm_h4 = start - timedelta(days=20)
    warm_d1 = start - timedelta(days=120)

    try:
        from mt5_connector import connector as mt5c
        if mt5c.connect():
            logger.info("Manba: MT5 (copy_rates_range)")
            m5 = mt5c.get_candles_range(symbol, "M5", warm_m5, end)
            h4 = mt5c.get_candles_range(symbol, "H4", warm_h4, end)
            d1 = mt5c.get_candles_range(symbol, "D1", warm_d1, end)
            m1 = mt5c.get_candles_range(symbol, "M1", start - timedelta(days=2), end)
            if m1.empty:
                logger.warning("M1 tarixi olinmadi — m1_ote varianti o'tkazib yuboriladi")
            if not m5.empty:
                return m5, h4, d1, m1, "mt5"
            logger.warning("MT5 M5 bo'sh qaytdi — Yahoo'ga o'tamiz")
    except Exception as exc:
        logger.warning("MT5 ishlamadi (%s) — Yahoo'ga o'tamiz", exc)

    logger.warning("YAHOO fallback: M5 chuqurligi ~60 kun bilan cheklangan, "
                   "M1 yo'q (m1_ote o'tkaziladi). Natijalar MT5 bilan taqqoslanmaydi!")
    from yahoo_connector import connector as yc
    yc.connect()
    m5 = yc.get_candles(symbol, "M5", count=20000)
    h4 = yc.get_candles(symbol, "H4", count=800)
    d1 = yc.get_candles(symbol, "D1", count=200)

    def _slice(df):
        if df.empty:
            return df
        s = pd.Timestamp(warm_d1, tz="UTC")
        e = pd.Timestamp(end, tz="UTC")
        return df[(df["time_utc"] >= s) & (df["time_utc"] < e)].reset_index(drop=True)

    m5, h4, d1 = _slice(m5), _slice(h4), _slice(d1)
    if not m5.empty:
        first = m5["time_ny"].iloc[0]
        if first.tz_localize(None) > pd.Timestamp(start).tz_localize(None):
            logger.warning("Yahoo M5 faqat %s dan bor — oraliq qisqartirildi", first)
    return m5, h4, d1, pd.DataFrame(), "yahoo"


# ---------------------------------------------------------------------------
# Look-ahead'siz H4/D1 ko'rinishlar
# ---------------------------------------------------------------------------
def _h4_open_for(t: pd.Timestamp) -> pd.Timestamp:
    """t tegishli bo'lgan H4 shamining ochilish vaqti (NY soatlari 1/5/9/13/17/21)."""
    h = (t.hour - 1) % 4
    return t.replace(minute=0, second=0, microsecond=0) - pd.Timedelta(hours=h)


def _day_open_for(t: pd.Timestamp) -> pd.Timestamp:
    """Joriy savdo kuni ochilishi (17:00 NY)."""
    base = t.replace(hour=17, minute=0, second=0, microsecond=0)
    return base if t.hour >= 17 else base - pd.Timedelta(days=1)


def _partial_bar(m5_slice: pd.DataFrame, open_time: pd.Timestamp):
    seg = m5_slice[m5_slice["time_ny"] >= open_time]
    if seg.empty:
        return None
    return {"time_ny": open_time,
            "open": float(seg["open"].iloc[0]),
            "high": float(seg["high"].max()),
            "low": float(seg["low"].min()),
            "close": float(seg["close"].iloc[-1]),
            "volume": float(seg.get("volume", pd.Series([0])).sum())}


def _htf_view(all_bars: pd.DataFrame, m5_slice: pd.DataFrame,
              t: pd.Timestamp, bar_open: pd.Timestamp, tail: int) -> pd.DataFrame:
    """Yopilgan HTF barlar (open < joriy bar open) + joriy qisman bar (M5'dan)."""
    done = all_bars[all_bars["time_ny"] < bar_open].tail(tail)
    part = _partial_bar(m5_slice, bar_open)
    if part is None:
        return done.reset_index(drop=True)
    return pd.concat([done, pd.DataFrame([part])], ignore_index=True)


# ---------------------------------------------------------------------------
# Savdo hayot siklini outcome_tracker funksiyalari bilan yuritish
# ---------------------------------------------------------------------------
class _Recorder:
    """_record_noentry ni vaqtincha almashtirib natijani ushlab oladi."""

    def __init__(self):
        self.noentry = None

    def __call__(self, tr, outcome):
        self.noentry = outcome


def _drive_variant(variant: str, sig, df_full: pd.DataFrame,
                   purge_iso: str, expiry_iso: str):
    """
    Bitta variant uchun to'liq hayot sikli. Qaytaradi (outcome, net_r, tr)
    yoki (outcome, None, tr) agar savdo ochilmagan bo'lsa,
    yoki None agar ma'lumot oralig'i tugab hal bo'lmagan bo'lsa.
    """
    tr = {
        "variant": variant, "symbol": sig.symbol, "source": "",
        "condition": sig.condition, "level_name": sig.level_name,
        "direction": sig.direction, "crt_mid": sig.crt_mid,
        "liquidity": sig.liquidity_target, "stdv": sig.stdv,
        "entry_time": purge_iso, "expiry_time": expiry_iso,
        "status": "pending",
    }
    rec = _Recorder()
    orig = ot._record_noentry
    ot._record_noentry = rec
    try:
        purge_t = pd.Timestamp(purge_iso)
        first = int((df_full["time_ny"] > purge_t).idxmax()) if \
            (df_full["time_ny"] > purge_t).any() else len(df_full)
        # CISD ni jonli kabi O'SUVCHI kesimlarda qidiramiz (look-ahead'siz)
        for pos in range(first, len(df_full)):
            ot._try_activate_m5(tr, df_full.iloc[:pos + 1])
            if rec.noentry:
                return (rec.noentry, None, tr)
            if tr["status"] in ("active", "ote_wait"):
                break
        if tr["status"] == "pending":
            return None  # ma'lumot tugadi, CISD topilmadi (oraliq cheti)
        if tr["status"] == "ote_wait":
            # zonaga qaytishni kutish: bar-tartibda ishlaydi, to'liq df bilan ekvivalent
            ot._advance_ote(tr, df_full)
            if rec.noentry:
                return (rec.noentry, None, tr)
            if tr["status"] != "active":
                return None  # oraliq cheti
        walker = ot._walk_cisd if variant == "m5_cisd" else ot._walk_managed
        res = walker(tr, df_full)
        if res is None:
            return None  # oraliq cheti
        outcome, net_r = res
        return (outcome, net_r, tr)
    finally:
        ot._record_noentry = orig


# ---------------------------------------------------------------------------
# Asosiy backtest
# ---------------------------------------------------------------------------
def run_backtest(symbol: str, start: datetime, end: datetime) -> list[dict]:
    import scanner  # kech import: connector tanlovi shu yerda muhim emas

    m5, h4_all, d1_all, m1, source = _fetch_all(symbol, start, end)
    if m5.empty:
        logger.error("M5 ma'lumot yo'q — backtest to'xtatildi")
        return []
    logger.info("Barlar: M5=%d, H4=%d, D1=%d, M1=%d",
                len(m5), len(h4_all), len(d1_all), len(m1))

    run_id = hashlib.sha1(
        f"{symbol}|{start:%Y-%m-%d}|{end:%Y-%m-%d}".encode()).hexdigest()[:10]
    spread = SPREAD_PRICE.get(symbol, 0.0) * BACKTEST_SPREAD_MULT

    start_ny = pd.Timestamp(start, tz="UTC").tz_convert(NY_TZ)
    scan_from = m5.index[m5["time_ny"] >= start_ny]
    if len(scan_from) == 0:
        logger.error("Oraliqda M5 bar yo'q")
        return []

    seen: set = set()
    rows: list[dict] = []
    balances = {v: PAPER_START_BALANCE for v in VARIANTS}
    unresolved = 0
    first_pos = m5.index.get_loc(scan_from[0])

    for pos in range(first_pos, len(m5)):
        bar_t = m5["time_ny"].iloc[pos]
        t = bar_t + pd.Timedelta(minutes=5)  # bar YOPILGAN payt
        m5_view = m5.iloc[max(0, pos - 399):pos + 1]

        h4_view = _htf_view(h4_all, m5_view, t, _h4_open_for(t), 60)
        d1_view = _htf_view(d1_all, m5_view, t, _day_open_for(t), 70)
        if len(h4_view) < 5 or len(d1_view) < 3:
            continue

        now_ny = t.to_pydatetime()
        try:
            _, mo, evaluated = scanner._scan_and_filter(
                symbol, now_ny, m5_view, h4_view, d1_view)
        except Exception:
            logger.exception("Skan xatosi @ %s", t)
            continue

        if (pos - first_pos) % 5000 == 0:
            logger.info("... %s (%d/%d bar, %d signal)",
                        bar_t.strftime("%Y-%m-%d"), pos - first_pos,
                        len(m5) - first_pos, len(rows))

        for sig, fr in evaluated:
            day = str(sig.sweep_candle_time)[:10]
            key = (sig.symbol, sig.condition, sig.level_name, sig.direction, day)
            if key in seen:
                continue
            seen.add(key)

            sid = ablation.make_signal_id(sig.symbol, sig.condition,
                                          sig.level_name, sig.direction,
                                          sig.sweep_candle_time)
            purge_iso = sig.sweep_candle_time
            entry_dt = datetime.fromisoformat(purge_iso)
            expiry_iso = ot._expiry_for(entry_dt).isoformat()
            accepted = fr["verdict"] == "accepted"
            variants = VARIANTS if accepted else ("m5_cisd",)  # rad -> shadow uslubi

            base = {
                "signal_id": sid, "final_verdict": fr["verdict"],
                "rejected_by": fr["rejected_by"],
                "filter_pd": "pass" if fr["pd"] else "fail",
                "filter_qt": "pass" if fr["qt"] else "fail",
                "filter_qt_phase": fr["qt_phase"],
                "filter_mo_bias": "pass" if fr["mo"] else "fail",
                "filter_hrl": "pass" if fr["hrl"] else "fail",
                "run_id": run_id, "is_backtest": "true",
            }

            purge_ts = pd.Timestamp(purge_iso)
            expiry_ts = pd.Timestamp(expiry_iso)
            for variant in variants:
                src_df = m1 if variant.startswith("m1") else m5
                if variant.startswith("m1") and (m1 is None or m1.empty):
                    continue
                # Samaradorlik: faqat purge..expiry(+3 kun, dam olishga zaxira)
                # oynasi kerak — savdo shu oraliqda tug'ilib hal bo'ladi.
                df_win = src_df[
                    (src_df["time_ny"] >= purge_ts - pd.Timedelta(minutes=5)) &
                    (src_df["time_ny"] <= expiry_ts + pd.Timedelta(days=3))
                ].reset_index(drop=True)
                res = _drive_variant(variant, sig, df_win, purge_iso, expiry_iso)
                if res is None:
                    unresolved += 1
                    continue
                outcome, net_r, tr = res

                row = {c: "" for c in COLUMNS}
                row.update(base)
                row.update({
                    "variant": variant, "source": source,
                    "entry_time_ny": tr.get("entry_time", purge_iso),
                    "resolved_time_ny": "",  # determinizm: joriy vaqt yozilmaydi
                    "symbol": sig.symbol, "condition": sig.condition,
                    "level_name": sig.level_name, "direction": sig.direction,
                    "outcome": outcome,
                })
                if net_r is not None and tr.get("r"):
                    r = tr["r"]
                    net_r = net_r - (spread / r if r > 0 else 0)  # spread jarima
                    sign = 1 if sig.direction == "bullish_sweep" else -1
                    mfe_r = sign * (tr["mfe"] - tr["entry"]) / r
                    mae_r = sign * (tr["mae"] - tr["entry"]) / r
                    hits = tr.get("hits", {})
                    tgt = tr.get("targets", {})
                    stdv_px = (sig.stdv or {}).get("levels", {})
                    row.update({
                        "entry": tr["entry"], "sl": tr["sl"], "r_size": r,
                        "hit_50": hits.get("50", ""),
                        "hit_liquidity": hits.get("liquidity", ""),
                        "t50_px": tgt.get("50", ""),
                        "t100_px": tgt.get("liquidity", ""),
                        "stdv_2_px": stdv_px.get("stdv_2", ""),
                        "stdv_2_5_px": stdv_px.get("stdv_2_5", ""),
                        "stdv_4_px": stdv_px.get("stdv_4", ""),
                        "mfe_r": round(mfe_r, 2), "mae_r": round(mae_r, 2),
                        "net_r": round(net_r, 3),
                    })
                    if accepted:  # balans faqat qabul qilinganlarda yuritiladi
                        risk = round(balances[variant] * PAPER_RISK_PCT / 100, 2)
                        pnl = round(risk * net_r, 2)
                        balances[variant] = round(balances[variant] + pnl, 2)
                        row.update({"risk_usd": risk, "pnl_usd": pnl,
                                    "balance_after": balances[variant]})
                rows.append(row)

    logger.info("Backtest tugadi: %d qator, %d hal bo'lmagan (oraliq cheti)",
                len(rows), unresolved)
    for v in VARIANTS:
        logger.info("  yakuniy balans %-11s: $%s", v, f"{balances[v]:,.2f}")
    return rows


def _write(rows: list[dict], run_id: str):
    """Bir xil run_id qatorlarini almashtirib yozadi (determinizm/qayta yurgizish)."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    old: list[dict] = []
    if os.path.exists(BACKTEST_CSV):
        with open(BACKTEST_CSV, encoding="utf-8-sig", newline="") as f:
            old = [r for r in csv.DictReader(f) if r.get("run_id") != run_id]
    with open(BACKTEST_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in old + rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    logger.info("Yozildi: %s (%d yangi, %d eski qator)",
                BACKTEST_CSV, len(rows), len(old))


def main():
    p = argparse.ArgumentParser(description="CRT skaner backtesti")
    p.add_argument("--symbol", required=True)
    p.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    a = p.parse_args()
    start = datetime.strptime(a.date_from, "%Y-%m-%d")
    end = datetime.strptime(a.date_to, "%Y-%m-%d")
    rows = run_backtest(a.symbol, start, end)
    if rows:
        _write(rows, rows[0]["run_id"])


if __name__ == "__main__":
    main()
