"""
Chart Image — signal uchun candlestick grafik chizadi (Telegram rasm)
====================================================================
Signal kelganda M5 shamlarni chizib, sweep darajasi + kirish/stop/maqsad
chiziqlari bilan PNG yasaydi. Telegram'ga rasm qilib yuboriladi — treyder
skrinshotdek vizual savdo g'oyasini oladi.
"""

import logging
import os
import tempfile

import matplotlib
matplotlib.use("Agg")  # serverda (GUI yo'q) ishlashi uchun
import matplotlib.pyplot as plt

from config import DATA_SOURCE, MT5_TIMEFRAME_ENTRY
from signals import SweepSignal

if DATA_SOURCE == "oanda":
    from oanda_connector import connector
elif DATA_SOURCE == "yahoo":
    from yahoo_connector import connector
else:
    from mt5_connector import connector

logger = logging.getLogger(__name__)


def _plan_levels(sig: SweepSignal):
    """Kirish/stop/maqsad narxlarини qaytaradi (format_trade_plan bilan bir xil)."""
    entry = sig.close_price
    if sig.direction == "bullish_sweep":
        stop = sig.sweep_low
        sign = 1
    else:
        stop = sig.sweep_high
        sign = -1
    r = abs(entry - stop)
    targets = {
        "1R": entry + sign * r,
        "2R": entry + sign * 2 * r,
        "3R": entry + sign * 3 * r,
    }
    if sig.crt_mid is not None:
        targets["CRT50"] = sig.crt_mid
    return entry, stop, targets


def render_signal_chart(sig: SweepSignal, bars: int = 70) -> str | None:
    """
    Signal uchun candlestick grafik PNG yasaydi, fayl yo'lini qaytaradi.
    Xato bo'lsa None (signal baribir matn bilan yuboriladi).
    """
    try:
        df = connector.get_candles(sig.symbol, MT5_TIMEFRAME_ENTRY, count=bars)
        if df.empty:
            return None
        df = df.tail(bars).reset_index(drop=True)

        fig, ax = plt.subplots(figsize=(10, 6), dpi=110)

        # Candlestick chizish (haftaoxiri bo'shliqlarсиз - butun indeks)
        for i, row in df.iterrows():
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            up = c >= o
            color = "#26a69a" if up else "#ef5350"  # yashil/qizil
            ax.plot([i, i], [l, h], color=color, linewidth=0.8, zorder=2)   # wick
            ax.add_patch(plt.Rectangle(
                (i - 0.3, min(o, c)), 0.6, abs(c - o) or (h - l) * 0.001,
                facecolor=color, edgecolor=color, zorder=3))

        entry, stop, targets = _plan_levels(sig)
        n = len(df)

        # Sweep darajasi (qora punktir)
        ax.axhline(sig.level_price, color="#333", linestyle=":", linewidth=1.2, zorder=1)
        ax.text(0, sig.level_price, f" sweep: {sig.level_name}", color="#333",
                fontsize=8, va="bottom", ha="left")

        # Kirish (ko'k), stop (qizil), maqsadlar (yashil punktir)
        ax.axhline(entry, color="#1e88e5", linewidth=1.3, zorder=1)
        ax.text(n - 1, entry, f" kirish {entry:.5f}", color="#1e88e5",
                fontsize=8, va="bottom", ha="right")
        ax.axhline(stop, color="#e53935", linewidth=1.3, zorder=1)
        ax.text(n - 1, stop, f" STOP {stop:.5f}", color="#e53935",
                fontsize=8, va="top", ha="right")
        for name, price in targets.items():
            ax.axhline(price, color="#43a047", linestyle="--", linewidth=1.0, zorder=1)
            ax.text(n - 1, price, f" {name} {price:.5f}", color="#43a047",
                    fontsize=7.5, va="center", ha="right")

        # Sweep shamini belgilash (o'q)
        try:
            mask = df["time_ny"].astype(str) == str(sig.sweep_candle_time)
            if mask.any():
                idx = df.index[mask][0]
                y = sig.sweep_high if sig.direction == "bearish_sweep" else sig.sweep_low
                ax.annotate("sweep", (idx, y),
                            xytext=(idx, y + (df["high"].max() - df["low"].min()) *
                                    (0.06 if sig.direction == "bearish_sweep" else -0.06)),
                            fontsize=8, color="#6a1b9a", ha="center",
                            arrowprops=dict(arrowstyle="->", color="#6a1b9a"))
        except Exception:
            pass

        yon = "LONG" if sig.direction == "bullish_sweep" else "SHORT"
        tcolor = "#26a69a" if sig.direction == "bullish_sweep" else "#ef5350"
        ax.set_title(f"{sig.symbol}   {yon}   |   {sig.condition}   |   "
                     f"{str(sig.sweep_candle_time)[:16]} NY",
                     fontsize=10, color=tcolor, fontweight="bold")
        ax.set_xticks([])
        ax.grid(axis="y", alpha=0.15)
        ax.margins(x=0.02)
        fig.tight_layout()

        path = os.path.join(tempfile.gettempdir(),
                            f"sig_{sig.symbol}_{str(sig.sweep_candle_time)[:10]}_"
                            f"{sig.direction}.png")
        fig.savefig(path)
        plt.close(fig)
        return path
    except Exception:
        logger.exception("Grafik chizishda xato")
        return None
