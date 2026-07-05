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


def notify_signal(signal: SweepSignal) -> bool:
    message = format_signal_message(signal)

    # LLM tushuntirishi (Gemini/Groq sozlangan bo'lsa) - signalga qo'shiladi
    try:
        from llm_client import explain_signal, GEMINI_API_KEY, GROQ_API_KEY
        if GEMINI_API_KEY or GROQ_API_KEY:
            summary = (
                f"{signal.symbol} | {signal.condition} | {signal.level_name} | "
                f"{signal.direction} | daraja={signal.level_price:.5f} | "
                f"close={signal.close_price:.5f} | vaqt(NY)={signal.sweep_candle_time}"
            )
            explanation = explain_signal(summary)
            if explanation:
                message += f"\n\n🤖 <b>LLM izohi:</b>\n{explanation}"
    except Exception as exc:  # LLM ishlamasa signal baribir yuboriladi
        logger.warning("LLM tushuntirish qo'shilmadi: %s", exc)

    return send_telegram_message(message)


def notify_risk_lock(reason: str) -> bool:
    text = f"🛑 <b>RISK-QULF FAOLLASHDI</b>\n\n{reason}\n\nBugun uchun savdo to'xtatilishi tavsiya etiladi."
    return send_telegram_message(text)
