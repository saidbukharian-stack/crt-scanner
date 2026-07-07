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

from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # serverda (GUI yo'q) ishlashi uchun
import matplotlib.pyplot as plt

from config import DATA_SOURCE, MT5_TIMEFRAME_ENTRY, MT5_TIMEFRAME_HTF, NY_TZ
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
        ax.set_title(f"{sig.symbol}  [{MT5_TIMEFRAME_ENTRY}]  {yon}  |  "
                     f"{sig.condition}  |  sweep {str(sig.sweep_candle_time)[:16]} NY",
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


def _draw_candles(ax, df):
    for i, row in df.reset_index(drop=True).iterrows():
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        color = "#26a69a" if c >= o else "#ef5350"
        ax.plot([i, i], [l, h], color=color, linewidth=0.8, zorder=2)
        ax.add_patch(plt.Rectangle((i - 0.3, min(o, c)), 0.6,
                                   abs(c - o) or (h - l) * 0.001,
                                   facecolor=color, edgecolor=color, zorder=3))


def render_holat_chart(symbol: str, timeframe: str = "M15", bars: int = 96) -> str | None:
    """
    /holat uchun jonli grafik: narx + asosiy darajalar (PDH/PDL, Asia/London)
    + narxga yaqin FVG'lar. M15 (96 sham ~24 soat) - kunlik darajalar ko'rinadi.
    Xato bo'lsa None (matn baribir yuboriladi).
    """
    try:
        from levels import all_levels_for_symbol
        if not connector.connect():
            return None
        now_ny = datetime.now(NY_TZ)
        df = connector.get_candles(symbol, timeframe, count=bars)
        df_m5 = connector.get_candles(symbol, MT5_TIMEFRAME_ENTRY, count=400)
        df_h4 = connector.get_candles(symbol, MT5_TIMEFRAME_HTF, count=60)
        df_d1 = connector.get_candles(symbol, "D1", count=10)
        if df.empty or df_h4.empty or df_d1.empty:
            return None
        df = df.tail(bars).reset_index(drop=True)
        price = float(df.iloc[-1]["close"])
        last_bar_time = str(df.iloc[-1]["time_ny"])[:16]
        levels = all_levels_for_symbol(df_m5 if not df_m5.empty else df,
                                       df_h4, df_d1, now_ny)

        fig, ax = plt.subplots(figsize=(10, 6), dpi=110)
        _draw_candles(ax, df)
        n = len(df)

        # Asosiy darajalar (ko'plab CRT emas - shovqin kam bo'lsin)
        show = {"PDH": "#e53935", "PDL": "#1e88e5",
                "Asia_High": "#8e24aa", "Asia_Low": "#8e24aa",
                "London_High": "#f9a825", "London_Low": "#f9a825"}
        for lv in levels:
            if lv.name in show:
                ax.axhline(lv.price, color=show[lv.name], linestyle="--",
                           linewidth=1.0, alpha=0.8, zorder=1)
                ax.text(0, lv.price, f" {lv.name}", color=show[lv.name],
                        fontsize=7.5, va="bottom", ha="left")

        # Joriy narx
        ax.axhline(price, color="#111", linewidth=1.2, zorder=1)
        ax.text(n - 1, price, f" {price:.5f}", color="#111",
                fontsize=8, va="bottom", ha="right", fontweight="bold")

        # Narxga yaqin FVG'lar (soyali zona)
        for i in range(2, n):
            hi2, lo0 = df["high"].values, df["low"].values
            if hi2[i - 2] < lo0[i]:  # bullish FVG
                g_lo, g_hi = float(hi2[i - 2]), float(lo0[i])
                if df["low"].values[i:].min() > g_lo and abs((g_lo + g_hi) / 2 - price) < (df["high"].max() - df["low"].min()) * 0.5:
                    ax.axhspan(g_lo, g_hi, color="#26a69a", alpha=0.10, zorder=0)
            if lo0[i - 2] > hi2[i]:  # bearish FVG
                g_lo, g_hi = float(hi2[i]), float(lo0[i - 2])
                if df["high"].values[i:].max() < g_hi and abs((g_lo + g_hi) / 2 - price) < (df["high"].max() - df["low"].min()) * 0.5:
                    ax.axhspan(g_lo, g_hi, color="#ef5350", alpha=0.10, zorder=0)

        ax.set_title(f"{symbol}  [{timeframe}]  jonli holat  |  "
                     f"oxirgi sham {last_bar_time} NY",
                     fontsize=10, fontweight="bold")
        ax.set_xticks([])
        ax.grid(axis="y", alpha=0.15)
        ax.margins(x=0.02)
        fig.tight_layout()
        path = os.path.join(tempfile.gettempdir(), f"holat_{symbol}.png")
        fig.savefig(path)
        plt.close(fig)
        return path
    except Exception:
        logger.exception("Holat grafigini chizishda xato")
        return None
