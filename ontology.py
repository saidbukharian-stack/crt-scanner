"""
Ontologiya dvigateli — bilim xaritasini MEXANIK kuchga aylantirish
=================================================================
docs/MODEL_KNOWLEDGE.md §23 (ontologiya) asosida to'rt qobiliyat
(treyder buyurtmasi, 2026-07-20):

1) confluence_score  — setup to'liqlik balli (0-100), deterministik.
   Zanjir bo'g'inlari: purge sifati, CISD, vaqt fazasi, zona, bias,
   yo'l tozaligi, RR. Rad ETMAYDI — saralaydi.
2) find_analogs      — setup "imzosi" (daraja_turi + yo'nalish + QT faza)
   bo'yicha tarixiy o'xshashlarni topadi (backtest + forward CSV'lardan).
3) validate_llm_eval — LLM bahosi mexanik ball bilan keskin zid bo'lsa
   ogohlantiradi (gallyutsinatsiya tutqichi v1).
4) chain_status      — /zanjir buyrug'i: jonli holatni sabab-oqibat
   zanjiri bo'ylab ko'rsatadi (qaysi bo'g'in bor/yo'q).
"""

from __future__ import annotations

import csv
import logging
import os

logger = logging.getLogger(__name__)

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


# ---------------------------------------------------------------------------
# 1) Setup to'liqlik balli
# ---------------------------------------------------------------------------
def confluence_score(sig, fr: dict, cisd_ok: bool) -> dict:
    """
    Ontologiya zanjiri (§23c) bo'g'inlarini ballaydi. Qaytaradi:
      {"score": 0-100, "parts": ["✓/✗ izoh", ...]}
    fr — scanner.evaluate_signal_filters natijasi.
    """
    parts = []
    score = 0

    # Purge sifati (rad-dumi ulushi)
    w = float(getattr(sig, "wick_pct", 0) or 0)
    if w >= 0.5:
        score += 15; parts.append(f"✓ purge kuchli (dum {w:.0%}) +15")
    elif w >= 0.4:
        score += 10; parts.append(f"✓ purge yaxshi (dum {w:.0%}) +10")
    else:
        score += 6; parts.append(f"△ purge minimal (dum {w:.0%}) +6")

    # CISD tasdig'i (kirish sharti)
    if cisd_ok:
        score += 20; parts.append("✓ CISD tasdiqlangan +20")
    else:
        parts.append("✗ CISD hali yo'q (kutilmoqda) +0")

    # Vaqt: QT fazasi
    if fr.get("qt"):
        score += 15; parts.append(f"✓ QT faza ma'qul ({fr.get('qt_phase','?')}) +15")
    else:
        parts.append(f"✗ QT faza noqulay ({fr.get('qt_phase','?')}) +0")

    # Zona: premium/discount
    if fr.get("pd"):
        score += 15; parts.append("✓ to'g'ri zonada (P/D) +15")
    else:
        parts.append("✗ noto'g'ri zona (P/D) +0")

    # Bias: Midnight Open
    if fr.get("mo"):
        score += 15; parts.append("✓ Midnight bias mos +15")
    else:
        parts.append("✗ Midnight bias qarshi +0")

    # Yo'l tozaligi (HRL)
    if fr.get("hrl"):
        score += 10; parts.append("✓ maqsadgacha yo'l toza +10")
    else:
        parts.append("✗ yo'lda qarshi FVG +0")

    # RR: likvidlikkacha masofa
    try:
        stop = sig.sweep_low if sig.direction == "bullish_sweep" else sig.sweep_high
        r = abs(sig.close_price - stop)
        if r > 0 and sig.liquidity_target is not None:
            rr = abs(sig.liquidity_target - sig.close_price) / r
            if rr >= 1.5:
                score += 10; parts.append(f"✓ RR yaxshi ({rr:.1f}R) +10")
            elif rr >= 1.0:
                score += 6; parts.append(f"△ RR o'rtacha ({rr:.1f}R) +6")
            else:
                parts.append(f"✗ RR past ({rr:.1f}R) +0")
    except Exception:
        pass

    return {"score": score, "parts": parts}


# ---------------------------------------------------------------------------
# 2) Analogiya qidiruv (imzo bo'yicha tarixiy statistika)
# ---------------------------------------------------------------------------
def setup_signature(level_name: str, direction: str, qt_phase: str) -> tuple:
    from ablation import level_type
    return (level_type(level_name or ""), direction, qt_phase)


def _phase_of(ts: str) -> str:
    try:
        import pandas as pd
        from qt import daily_quarter
        return daily_quarter(pd.Timestamp(ts))[2]
    except Exception:
        return "?"


def find_analogs(level_name: str, direction: str, qt_phase: str) -> dict | None:
    """
    Bir xil imzoli tarixiy m5_cisd savdolarini (backtest + forward, qabul ham
    rad-shadow ham — setup taqdiri filtrga bog'liq emas) yig'ib statistika beradi.
    """
    sig_key = setup_signature(level_name, direction, qt_phase)
    nets = []
    from ablation import level_type

    bt = os.path.join(RESULTS_DIR, "backtest_results.csv")
    if os.path.exists(bt):
        try:
            with open(bt, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("variant") != "m5_cisd" or not r.get("net_r"):
                        continue
                    key = (level_type(r.get("level_name", "")), r.get("direction", ""),
                           r.get("filter_qt_phase", "") or _phase_of(r.get("entry_time_ny", "")))
                    if key == sig_key:
                        nets.append(float(r["net_r"]))
        except (OSError, ValueError, csv.Error) as exc:
            logger.warning("Analog (backtest) o'qilmadi: %s", exc)

    fw = os.path.join(RESULTS_DIR, "results_v3.csv")
    if os.path.exists(fw):
        try:
            with open(fw, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("variant") != "m5_cisd" or not r.get("net_r"):
                        continue
                    key = (level_type(r.get("level_name", "")), r.get("direction", ""),
                           _phase_of(r.get("entry_time_ny", "")))
                    if key == sig_key:
                        nets.append(float(r["net_r"]))
        except (OSError, ValueError, csv.Error) as exc:
            logger.warning("Analog (forward) o'qilmadi: %s", exc)

    if not nets:
        return None
    wins = sum(1 for x in nets if x > 0)
    return {"n": len(nets), "win_pct": round(100 * wins / len(nets)),
            "avg_r": round(sum(nets) / len(nets), 2),
            "signature": " + ".join(str(s) for s in sig_key)}


def analog_text(a: dict | None) -> str:
    if not a:
        return "📊 Tarixiy analog: bu imzo bo'yicha ma'lumot hali yo'q"
    caution = "" if a["n"] >= 10 else " (namuna kichik!)"
    return (f"📊 Tarixiy analog [{a['signature']}]: {a['n']} marta, "
            f"{a['win_pct']}% yutuq, o'rt {a['avg_r']:+.2f}R{caution}")


# ---------------------------------------------------------------------------
# 3) LLM bahosini ontologiya bilan solishtirish
# ---------------------------------------------------------------------------
def validate_llm_eval(llm_eval: dict | None, conf: dict) -> str | None:
    """
    LLM balli (1-10) mexanik to'liqlik balli (0-100) bilan keskin zid bo'lsa —
    ogohlantirish matni. Aks holda None.
    """
    if not llm_eval:
        return None
    gap = abs(llm_eval["score"] * 10 - conf["score"])
    if gap >= 40:
        return (f"⚠️ Ziddiyat: LLM {llm_eval['score']}/10 deydi, mexanik ball esa "
                f"{conf['score']}/100 — biri adashyapti, ehtiyot bo'ling")
    return None


# ---------------------------------------------------------------------------
# 4) /zanjir — jonli sabab-oqibat zanjiri holati
# ---------------------------------------------------------------------------
def chain_status(symbol: str, connector) -> str | None:
    """Instrument uchun setup zanjirining joriy holati (✓/✗ bo'g'inlar)."""
    from datetime import datetime

    import pandas as pd

    import scanner as sc
    from config import NY_TZ
    from signals import detect_cisd

    now_ny = datetime.now(NY_TZ)
    df_m5 = connector.get_candles(symbol, "M5", count=400)
    df_h4 = connector.get_candles(symbol, "H4", count=60)
    df_d1 = connector.get_candles(symbol, "D1", count=70)
    if df_m5.empty or df_h4.empty or df_d1.empty:
        return None

    price = float(df_m5["close"].iloc[-1])
    from qt import qt_phase as qtp
    phase = qtp(pd.Timestamp(now_ny))

    lines = [f"🔗 <b>{symbol} — setup zanjiri</b> (narx {price:.5f})", ""]

    # 1-bo'g'in: vaqt fazasi
    ok = phase["favored"]
    lines.append(f"{'✓' if ok else '✗'} 1. Vaqt: Q{phase['quarter']} {phase['session']} "
                 f"— {phase['phase']}" + ("" if ok else " (signal taqiqlangan faza)"))

    # 2-bo'g'in: yaqin darajalar
    from levels import all_levels_for_symbol
    levels = all_levels_for_symbol(df_m5, df_h4, df_d1, now_ny)
    near = sorted(levels, key=lambda l: abs(l.price - price))[:3]
    lines.append("✓ 2. Yaqin darajalar: " +
                 ", ".join(f"{l.name} {l.price:.5f}" for l in near))

    # 3-bo'g'in: purge bormi (oxirgi 12 sham, oynalar hisobda)
    _, mo, evaluated = sc._scan_and_filter(symbol, now_ny, df_m5, df_h4, df_d1)
    if not evaluated:
        lines.append("✗ 3. Purge: oxirgi shamlarda YO'Q → kutish bosqichi")
        lines.append("· 4. CISD: purge bo'lmaguncha ahamiyatsiz")
        return "\n".join(lines)

    sig, fr = evaluated[-1]  # eng so'nggi sweep
    lines.append(f"✓ 3. Purge: {sig.level_name} "
                 f"({'LONG' if sig.direction == 'bullish_sweep' else 'SHORT'}, "
                 f"dum {sig.wick_pct:.0%}, {str(sig.sweep_candle_time)[11:16]})")

    # 4-bo'g'in: CISD
    cisd = detect_cisd(df_m5, pd.Timestamp(sig.sweep_candle_time), sig.direction)
    if cisd:
        lines.append(f"✓ 4. CISD: tasdiqlangan, kirish ~{cisd['entry']:.5f}, "
                     f"stop {cisd['stop']:.5f}")
    else:
        lines.append("✗ 4. CISD: hali shakllanmagan → kirish taqiqlangan")

    # 5-bo'g'in: filtrlar + ball
    conf = confluence_score(sig, fr, cisd is not None)
    fl = [("P/D", fr["pd"]), ("QT", fr["qt"]), ("Midnight", fr["mo"]), ("HRL", fr["hrl"])]
    lines.append("5. Filtrlar: " + " ".join(f"{'✓' if v else '✗'}{n}" for n, v in fl))
    lines.append(f"🧩 To'liqlik balli: <b>{conf['score']}/100</b>")
    if sig.crt_mid and sig.liquidity_target:
        lines.append(f"6. Maqsadlar: 50%={sig.crt_mid:.5f}, 100%={sig.liquidity_target:.5f}")
    return "\n".join(lines)
