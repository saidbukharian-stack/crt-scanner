"""
Sinovlar jurnali — "uchinchi qonun" himoyasi
============================================
Manba: Lopez de Prado, AFML 11.5/14.7 — "har backtest natijasi uni ishlab
chiqarishda qilingan BARCHA sinovlar bilan birga e'lon qilinishi kerak;
aks holda 'yolg'on kashfiyot' ehtimolini baholab bo'lmaydi."

MUAMMO: biz o'nlab konfiguratsiya sinadik (NDOG, BE, HRL, Midnight,
5 variant...) va har safar "eng yaxshisini" tanladik — lekin sinovlar
sonini yozmadik. Shuning uchun natijalarga Deflated Sharpe tuzatmasini
qo'llash IMKONSIZ.

YECHIM: shu paytdan boshlab har sinov `results/experiments.csv` ga yoziladi.
Yetarli yozuv to'plangach `--summary` sinovlar sonini va oddiy ogohlantirish
chegarasini ko'rsatadi.

CLI:
  python experiments.py --add --gipoteza "HRL filtri zarar" \\
      --ozgarish "HRL_FILTER_ENABLED=0" --natija-r -6.4 --n 19 \\
      --izoh "62 signaldan 4 tasini o'tkazardi"
  python experiments.py --summary
"""

import argparse
import csv
import os
from datetime import datetime, timezone

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
EXPERIMENTS_CSV = os.path.join(RESULTS_DIR, "experiments.csv")

COLUMNS = ["sana", "gipoteza", "ozgarish", "natija_r", "namuna_n",
           "qabul_qilindi", "izoh"]


def log_experiment(gipoteza: str, ozgarish: str, natija_r=None,
                   namuna_n=None, qabul: bool = False, izoh: str = ""):
    """Bitta sinovni jurnalga qo'shadi (natija qanday bo'lishidan qat'i nazar)."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    exists = os.path.exists(EXPERIMENTS_CSV)
    row = {
        "sana": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gipoteza": gipoteza,
        "ozgarish": ozgarish,
        "natija_r": "" if natija_r is None else round(float(natija_r), 3),
        "namuna_n": "" if namuna_n is None else int(namuna_n),
        "qabul_qilindi": "ha" if qabul else "yo'q",
        "izoh": izoh,
    }
    with open(EXPERIMENTS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if not exists:
            w.writeheader()
        w.writerow(row)
    return row


def load_experiments() -> list[dict]:
    if not os.path.exists(EXPERIMENTS_CSV):
        return []
    try:
        with open(EXPERIMENTS_CSV, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error):
        return []


def summary() -> str:
    """Sinovlar soni va 'yolg'on kashfiyot' ogohlantirishi."""
    rows = load_experiments()
    n = len(rows)
    accepted = sum(1 for r in rows if r.get("qabul_qilindi") == "ha")
    out = ["# Sinovlar jurnali (AFML uchinchi qonuni)", "",
           f"Jami sinov: **{n}**", f"Qabul qilingan (modelga kiritilgan): **{accepted}**", ""]
    if n == 0:
        out.append("_Hali yozuv yo'q. Har konfiguratsiya sinovidan keyin "
                   "`--add` bilan qo'shing._")
        return "\n".join(out)

    # Oddiy ogohlantirish: N sinovda kutilgan maksimal "tasodifiy" natija o'sadi
    out.append("## Ogohlantirish darajasi\n")
    if n < 5:
        out.append("🟢 Sinov kam — tanlov tarafkashligi xavfi past.")
    elif n < 15:
        out.append("🟡 Sinov o'rtacha. Eng yaxshi natijaga ehtiyot bo'ling — "
                   "u qisman tasodif bo'lishi mumkin.")
    else:
        out.append(f"🔴 **{n} ta sinov** — 'eng yaxshi' natija katta ehtimol bilan "
                   "tasodifiy. Out-of-sample tekshiruvsiz ishonmang.")
    out.append("")
    out.append("## Barcha sinovlar\n")
    out.append("| Sana | Gipoteza | O'zgarish | Natija R | n | Qabul |")
    out.append("|---|---|---|---|---|---|")
    for r in rows:
        out.append(f"| {r['sana'][:10]} | {r['gipoteza'][:40]} | "
                   f"{r['ozgarish'][:30]} | {r['natija_r']} | {r['namuna_n']} | "
                   f"{r['qabul_qilindi']} |")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description="Sinovlar jurnali")
    p.add_argument("--add", action="store_true", help="yangi sinov qo'shish")
    p.add_argument("--summary", action="store_true", help="jurnal xulosasi")
    p.add_argument("--gipoteza", default="")
    p.add_argument("--ozgarish", default="")
    p.add_argument("--natija-r", dest="natija_r", type=float, default=None)
    p.add_argument("--n", dest="namuna_n", type=int, default=None)
    p.add_argument("--qabul", action="store_true", help="modelga kiritildimi")
    p.add_argument("--izoh", default="")
    a = p.parse_args()

    if a.add:
        if not a.gipoteza or not a.ozgarish:
            p.error("--gipoteza va --ozgarish majburiy")
        row = log_experiment(a.gipoteza, a.ozgarish, a.natija_r,
                             a.namuna_n, a.qabul, a.izoh)
        print("Qo'shildi:", row)
    else:
        print(summary())


if __name__ == "__main__":
    main()
