"""
Natijalar tahlili — forward-test + backtest + ablation hisoboti
===============================================================
CLI:
  python analyze_results.py                 # hammasi
  python analyze_results.py --source mt5    # faqat MT5 ma'lumoti
  python analyze_results.py --backtest-only
  python analyze_results.py --forward-only

O'qiydi: results/results_v3.csv (forward), results/backtest_results.csv,
results/signals_log.csv (ablation + shadow).
Chiqaradi: konsol jadvallari + results/report.md.

QOIDALAR
--------
- MT5 va Yahoo natijalari HECH QACHON birlashtirilmaydi — hamma jadval
  source bo'yicha alohida (narx/sessiya farqlari sweep aniqlashga ta'sir qiladi).
- n < 30 bo'lsa "namuna yetarli emas" belgisi qo'yiladi.
- O'rtacha R yoniga bootstrap 95% ishonch oralig'i.
- Ma'lumot kam/yo'q bo'lsa yiqilmaydi — "yetarli emas" deb yozadi.
"""

import argparse
import logging
import os

import numpy as np
import pandas as pd

from ablation import level_type
from qt import daily_quarter

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("analyze")

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
FORWARD_CSV = os.path.join(RESULTS_DIR, "results_v3.csv")
BACKTEST_CSV = os.path.join(RESULTS_DIR, "backtest_results.csv")
SIGNALS_CSV = os.path.join(RESULTS_DIR, "signals_log.csv")
REPORT_MD = os.path.join(RESULTS_DIR, "report.md")

MIN_SAMPLE = 30
FILTERS = ("pd", "qt", "mo_bias", "hrl")
_FILTER_COL = {"pd": "filter_pd", "qt": "filter_qt",
               "mo_bias": "filter_mo_bias", "hrl": "filter_hrl"}

_out: list[str] = []  # report.md uchun to'planadigan satrlar


def _emit(text: str = ""):
    try:
        print(text)
    except UnicodeEncodeError:
        # Windows konsoli (cp1251) ba'zi belgilarni bilmaydi - report.md'da
        # to'liq qoladi, konsolga soddalashtirilgan ko'rinish chiqadi
        import sys
        enc = sys.stdout.encoding or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc))
    _out.append(text)


# ---------------------------------------------------------------------------
# Yuklash
# ---------------------------------------------------------------------------
def _read(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    except Exception as exc:
        logger.warning("O'qib bo'lmadi %s: %s", path, exc)
        return pd.DataFrame()


def load_trades(source: str | None, backtest_only: bool,
                forward_only: bool) -> pd.DataFrame:
    """Forward + backtest savdolarini bitta jadvalga yig'adi (is_backtest belgisi bilan)."""
    frames = []
    if not backtest_only:
        f = _read(FORWARD_CSV)
        if not f.empty:
            f["is_backtest"] = "false"
            for c in ("final_verdict",):
                if c not in f.columns:
                    f[c] = "accepted"  # forward CSV'da faqat qabul qilinganlar bor
            frames.append(f)
    if not forward_only:
        b = _read(BACKTEST_CSV)
        if not b.empty:
            frames.append(b)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)

    df["net_r_f"] = pd.to_numeric(df.get("net_r", ""), errors="coerce")
    df = df[df["net_r_f"].notna()].copy()          # faqat yakunlangan savdolar
    if df.empty:
        return df
    df["entry_ts"] = pd.to_datetime(df["entry_time_ny"], errors="coerce", utc=True)
    df["weekday"] = pd.to_datetime(
        df["entry_time_ny"].str[:10], errors="coerce").dt.day_name()
    df["level_type"] = df["level_name"].map(lambda x: level_type(x) if x else "?")
    df["session"] = df["entry_time_ny"].map(_session_of)
    if source:
        df = df[df["source"] == source]
    return df


def _session_of(ts: str) -> str:
    try:
        t = pd.Timestamp(ts)
        return daily_quarter(t)[1]  # Asia / London / NY_AM / NY_PM
    except Exception:
        return "?"


# ---------------------------------------------------------------------------
# Statistika yordamchilari
# ---------------------------------------------------------------------------
def _bootstrap_ci(x: np.ndarray, iters: int = 2000, seed: int = 42):
    """O'rtacha uchun oddiy bootstrap 95% ishonch oralig'i (deterministik seed)."""
    if len(x) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(iters, len(x)), replace=True).mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def _max_drawdown(net: np.ndarray) -> float:
    eq = np.cumsum(net)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    return float((eq - peak).min()) if len(eq) else 0.0


def _longest_loss_streak(net: np.ndarray) -> int:
    best = cur = 0
    for x in net:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


def _variant_stats(g: pd.DataFrame) -> dict:
    g = g.sort_values("entry_ts")
    net = g["net_r_f"].to_numpy()
    wins = net[net > 0]
    losses = net[net < 0]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else float("inf")
    lo, hi = _bootstrap_ci(net)
    return {
        "savdo": len(net),
        "win%": 100 * (net > 0).mean() if len(net) else 0,
        "o'rt R": net.mean() if len(net) else 0,
        "CI95": f"[{lo:+.2f},{hi:+.2f}]" if not np.isnan(lo) else "-",
        "sof R": net.sum(),
        "PF": round(pf, 2) if np.isfinite(pf) else "inf",
        "maxDD(R)": round(_max_drawdown(net), 1),
        "mag'l.seriya": _longest_loss_streak(net),
        "ishonch": "OK" if len(net) >= MIN_SAMPLE else f"⚠ n<{MIN_SAMPLE} — xulosa erta",
    }


def _md_table(df: pd.DataFrame) -> str:
    """Markdown jadval (tabulate'siz, qo'shimcha dependency yo'q)."""
    def _fmt(v):
        if isinstance(v, float):
            return f"{v:+.2f}" if np.isfinite(v) else str(v)
        return str(v)
    header = [""] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join(["---"] * len(header)) + "|"]
    for idx, row in df.iterrows():
        lines.append("| " + " | ".join([str(idx)] + [_fmt(v) for v in row]) + " |")
    return "\n".join(lines)


def _table(df: pd.DataFrame, title: str):
    """DataFrame'ni konsol + markdown jadval qilib chiqaradi."""
    _emit(f"\n### {title}\n")
    if df.empty:
        _emit("_ma'lumot yetarli emas_")
        return
    _emit(_md_table(df))


# ---------------------------------------------------------------------------
# Hisobot bo'limlari (har biri source ichida chaqiriladi)
# ---------------------------------------------------------------------------
def section_variants(df: pd.DataFrame):
    rows = {}
    accepted = df[df["final_verdict"] == "accepted"]
    for v, g in accepted.groupby("variant"):
        rows[v] = _variant_stats(g)
    _table(pd.DataFrame(rows).T, "Variant taqqoslash (faqat qabul qilinganlar)")


def section_slices(df: pd.DataFrame):
    accepted = df[df["final_verdict"] == "accepted"]
    for col, name in (("symbol", "Instrument"), ("session", "Sessiya (QT chorak)"),
                      ("weekday", "Hafta kuni"), ("level_type", "Daraja turi")):
        if accepted.empty:
            _table(pd.DataFrame(), f"Kesim: {name}")
            continue
        g = accepted.groupby(col)["net_r_f"].agg(
            savdo="count", ort_R="mean", sof_R="sum").round(2)
        g["ishonch"] = np.where(g["savdo"] >= MIN_SAMPLE, "OK", "⚠ kam")
        _table(g, f"Kesim: {name}")


def section_ablation(df: pd.DataFrame, signals: pd.DataFrame):
    """
    Har filtr uchun: shu filtr(gina) rad etgan signallarning natijasi qanday edi?
    Shadow manba: forward -> signals_log.shadow_outcome_r,
                  backtest -> rejected qatorlarning net_r (m5_cisd).
    Musbat o'rtacha = filtr foydali signallarni o'ldirayapti (OGOHLANTIRISH).
    """
    frames = []
    rej_b = df[(df["final_verdict"] == "rejected") & (df["variant"] == "m5_cisd")]
    if not rej_b.empty:
        frames.append(rej_b[["filter_pd", "filter_qt", "filter_mo_bias",
                             "filter_hrl", "net_r_f"]])
    if not signals.empty and "shadow_outcome_r" in signals.columns:
        s = signals[signals["final_verdict"] == "rejected"].copy()
        s["net_r_f"] = pd.to_numeric(s["shadow_outcome_r"], errors="coerce")
        s = s[s["net_r_f"].notna()]
        if not s.empty:
            frames.append(s[["filter_pd", "filter_qt", "filter_mo_bias",
                             "filter_hrl", "net_r_f"]])
    _emit("\n### Ablation: filtrlar rad etganlarning taqdiri\n")
    if not frames:
        _emit("_shadow ma'lumot hali yo'q_")
        return
    rej = pd.concat(frames, ignore_index=True)

    rows = {}
    warns = []
    for f in FILTERS:
        col = _FILTER_COL[f]
        others = [_FILTER_COL[o] for o in FILTERS if o != f]
        only_f = rej[(rej[col] == "fail") &
                     np.logical_and.reduce([rej[o] == "pass" for o in others])]
        any_f = rej[rej[col] == "fail"]
        net = only_f["net_r_f"].to_numpy()
        avg = net.mean() if len(net) else float("nan")
        rows[f] = {
            "faqat_shu_yiqitgan": len(net),
            "o'rt_R(shadow)": round(avg, 2) if len(net) else "-",
            "jami_fail": len(any_f),
        }
        if len(net) >= 10 and avg > 0.1:
            warns.append(f"⚠ **{f}** filtri yiqitganlarning o'rtacha shadow "
                         f"natijasi {avg:+.2f}R (n={len(net)}) — bu filtr foyda "
                         f"emas, ZARAR keltirayotgan bo'lishi mumkin!")
    _emit(_md_table(pd.DataFrame(rows).T))
    for w in warns:
        _emit("\n" + w)
    if not warns:
        _emit("\n_hech bir filtr uchun 'zarar' belgisi yo'q (yoki namuna kichik)_")


def section_llm(df: pd.DataFrame, signals: pd.DataFrame):
    """LLM balli guruhlar bo'yicha o'rtacha R (Vazifa 4 ma'lumoti kelgach ishlaydi)."""
    if signals.empty or "llm_score" not in signals.columns:
        return
    s = signals.copy()
    s["llm_score_f"] = pd.to_numeric(s["llm_score"], errors="coerce")
    s = s[s["llm_score_f"].notna()]
    if s.empty:
        return
    acc = df[df["final_verdict"] == "accepted"]
    merged = acc.merge(s[["signal_id", "llm_score_f"]], on="signal_id", how="inner")
    if merged.empty:
        return
    merged["guruh"] = pd.cut(merged["llm_score_f"], [0, 4, 7, 10],
                             labels=["1-4", "5-7", "8-10"])
    g = merged.groupby("guruh", observed=True)["net_r_f"].agg(
        savdo="count", ort_R="mean").round(2)
    _table(g, "LLM balli guruhlar bo'yicha natija (baho foydalimi?)")


# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="CRT natijalar tahlili")
    p.add_argument("--source", choices=["mt5", "yahoo", "oanda"])
    p.add_argument("--backtest-only", action="store_true")
    p.add_argument("--forward-only", action="store_true")
    a = p.parse_args()

    df = load_trades(a.source, a.backtest_only, a.forward_only)
    signals = _read(SIGNALS_CSV)
    if a.source and not signals.empty and "source" in signals.columns:
        signals = signals[signals["source"] == a.source]

    _emit("# CRT natijalar hisoboti")
    _emit(f"\nRejim: {'faqat backtest' if a.backtest_only else 'faqat forward' if a.forward_only else 'hammasi'}"
          f"{', manba: ' + a.source if a.source else ''}")

    if df.empty:
        _emit("\n_Yakunlangan savdo topilmadi — ma'lumot yetarli emas._")
    else:
        # MT5 va Yahoo HECH QACHON aralashmaydi: har manba alohida blok
        for src, sdf in df.groupby("source"):
            for bt, bdf in sdf.groupby("is_backtest"):
                mode = "BACKTEST" if str(bt).lower() == "true" else "FORWARD"
                _emit(f"\n---\n\n## Manba: {src.upper()} — {mode} "
                      f"({len(bdf)} yakunlangan qator)")
                section_variants(bdf)
                section_slices(bdf)
                # FORWARD'da shadow signals_log'dan, BACKTEST'da rejected qatorlardan
                section_ablation(bdf, signals if mode == "FORWARD" else pd.DataFrame())
                section_llm(bdf, signals)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(_out) + "\n")
    print(f"\nHisobot yozildi: {REPORT_MD}")


if __name__ == "__main__":
    main()
