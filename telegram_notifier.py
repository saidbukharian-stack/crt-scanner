"""
Telegram Notifier
==================
Topilgan signallarni Telegram botga yuborish.

Sozlash:
1. @BotFather orqali yangi bot yarating, tokenni oling.
2. Botga o'zingiz yozing (yoki guruhga qo'shing), keyin
   https://api.telegram.org/bot<TOKEN>/getUpdates orqali chat_id ni toping.
3. Ikkalasini .env fayliga yozing (.env.example'ga qarang).
"""

import logging

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from signals import SweepSignal

logger = logging.getLogger(__name__)

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

_DIRECTION_LABEL = {
    "bullish_sweep": "🟢 BULLISH SWEEP (low supurildi)",
    "bearish_sweep": "🔴 BEARISH SWEEP (high supurildi)",
}

_CONDITION_LABEL = {
    "asia_hl_sweep": "Asia High/Low",
    "pdh_pdl_sweep": "Oldingi kun High/Low (PDH/PDL)",
    "crt_range_sweep": "CRT Range",
}


def format_signal_message(signal: SweepSignal) -> str:
    direction = _DIRECTION_LABEL.get(signal.direction, signal.direction)
    condition = _CONDITION_LABEL.get(signal.condition, signal.condition)
    return (
        f"⚡ <b>{signal.symbol}</b> — {condition}\n"
        f"{direction}\n\n"
        f"Daraja: <b>{signal.level_name}</b> = {signal.level_price:.5f}\n"
        f"Sham vaqti (NY): {signal.sweep_candle_time}\n"
        f"Sham High/Low: {signal.sweep_high:.5f} / {signal.sweep_low:.5f}\n"
        f"Close: {signal.close_price:.5f}\n\n"
        f"<i>Bu faqat mexanik shart bajarilgani haqida ogohlantirish.\n"
        f"Inducement, struktura va kontekstni o'zingiz tekshiring.</i>"
    )


def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error(
            "TELEGRAM_BOT_TOKEN yoki TELEGRAM_CHAT_ID sozlanmagan. "
            ".env faylini tekshiring."
        )
        return False

    url = _API_URL.format(token=TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error("Telegram xabar yuborishda xato: %s", exc)
        return False


def send_telegram_photo(photo_path: str, caption: str = "") -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            resp = requests.post(
                url,
                data={"chat_id": TELEGRAM_CHAT_ID,
                      "caption": caption[:1024], "parse_mode": "HTML"},
                files={"photo": f}, timeout=30,
            )
        resp.raise_for_status()
        return True
    except (requests.RequestException, OSError) as exc:
        logger.error("Telegram rasm yuborishda xato: %s", exc)
        return False


def format_llm_eval(ev: dict) -> str:
    """Strukturali LLM tanqidini ixcham Telegram matniga aylantiradi."""
    lines = [f"🧐 <b>LLM tanqidi:</b> {ev['score']}/10 (ishonch: {ev['confidence']})"]
    if ev.get("weak"):
        lines.append("Zaif: " + "; ".join(ev["weak"][:3]))
    lines.append(f"❗ <b>Qarshi-argument:</b> {ev['counter_argument']}")
    return "\n".join(lines)


def notify_signal(signal: SweepSignal, llm_eval: dict | None = None) -> bool:
    """
    llm_eval — scanner'da bir marta hisoblangan strukturali baho (Vazifa 4).
    Berilmasa LLM bo'limisiz yuboriladi (signal hech qachon kutmaydi).
    """
    message = format_signal_message(signal)

    # Mexanik kirish/stop/maqsad rejasi
    try:
        from signals import format_trade_plan
        plan = format_trade_plan(signal)
        if plan:
            message += f"\n\n{plan}"
    except Exception as exc:
        logger.warning("Reja qo'shilmadi: %s", exc)

    # LLM strukturali tanqid (erkin matn "sotuvchi" o'rniga - Vazifa 4)
    if llm_eval:
        try:
            message += "\n\n" + format_llm_eval(llm_eval)
        except Exception as exc:
            logger.warning("LLM baho qo'shilmadi: %s", exc)

    # Grafik-rasm (candlestick + kirish/stop/maqsad) - matn caption bilan.
    # Rasm chiqmasa yoki juda uzun bo'lsa - matnni alohida yuboramiz.
    try:
        from chart_image import render_signal_chart
        chart = render_signal_chart(signal)
        if chart:
            if len(message) <= 1024:
                return send_telegram_photo(chart, message)
            # matn uzun: rasmni yuboramiz, matnni alohida
            send_telegram_photo(chart, format_signal_message(signal))
            return send_telegram_message(message)
    except Exception as exc:
        logger.warning("Grafik yuborilmadi: %s", exc)

    return send_telegram_message(message)


def notify_risk_lock(reason: str) -> bool:
    text = f"🛑 <b>RISK-QULF FAOLLASHDI</b>\n\n{reason}\n\nBugun uchun savdo to'xtatilishi tavsiya etiladi."
    return send_telegram_message(text)
