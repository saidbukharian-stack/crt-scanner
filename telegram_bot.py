"""
Telegram Bot — savol-javob (Q&A)
================================
Treyder botga savol yozadi, LLM bilim bazasidan javob beradi.

GitHub Actions server emas (jadval bo'yicha ishlaydi), shuning uchun
webhook o'rniga POLLING: har ishga tushishda getUpdates orqali yangi
xabarlarni oladi, javob beradi. Oxirgi ko'rilgan update_id data/ da
saqlanadi (Actions cache) - xabar ikki marta javob olmaydi.

Buyruqlar:
  /start, /help    — yordam
  /tushuntir <matn>— berilgan holatni model bo'yicha tushuntir
  boshqa har qanday matn — savol sifatida qabul qilinadi

Ishga tushirish: python telegram_bot.py --poll
"""

import json
import logging
import os

import requests

from config import DB_PATH, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from llm_client import answer_question, GEMINI_API_KEY, GROQ_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telegram_bot")

_API = "https://api.telegram.org/bot{token}/{method}"
_OFFSET_PATH = os.path.join(os.path.dirname(DB_PATH), "tg_offset.json")

_HELP = (
    "🤖 <b>CRT yordamchi bot</b>\n\n"
    "Menga CRT/DOL/QT metodologiyasi bo'yicha savol yozing, bilim bazasidan "
    "javob beraman.\n\n"
    "Masalan:\n"
    "• 9AM CRT qoidalarini eslat\n"
    "• Turtle soup nima?\n"
    "• Model #1 qanday ishlaydi?\n"
    "• CRT qachon ishlamaydi?\n\n"
    "Eslatma: men maslahatchi instrumentman, savdo qarori o'zingizda."
)


def _tg(method: str, **params):
    url = _API.format(token=TELEGRAM_BOT_TOKEN, method=method)
    resp = requests.post(url, json=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _load_offset() -> int:
    try:
        with open(_OFFSET_PATH, encoding="utf-8") as f:
            return int(json.load(f).get("offset", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 0


def _save_offset(offset: int):
    os.makedirs(os.path.dirname(_OFFSET_PATH), exist_ok=True)
    with open(_OFFSET_PATH, "w", encoding="utf-8") as f:
        json.dump({"offset": offset}, f)


def _handle_text(text: str) -> str:
    stripped = text.strip()
    low = stripped.lower()
    if low in ("/start", "/help", "help", "start"):
        return _HELP
    if low.startswith("/tushuntir"):
        stripped = stripped[len("/tushuntir"):].strip() or "Joriy holatni tushuntir"
    if not (GEMINI_API_KEY or GROQ_API_KEY):
        return "⚠️ LLM hali sozlanmagan (GEMINI_API_KEY / GROQ_API_KEY yo'q)."
    answer = answer_question(stripped)
    return answer or "⚠️ Kechirasiz, hozir javob bera olmadim (LLM limiti yoki xato)."


def poll_once():
    """Yangi xabarlarni olib, har biriga javob beradi."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN yo'q")
        return
    offset = _load_offset()
    try:
        data = _tg("getUpdates", offset=offset + 1, timeout=0,
                   allowed_updates=["message"])
    except requests.RequestException as exc:
        logger.error("getUpdates xato: %s", exc)
        return

    updates = data.get("result", [])
    if not updates:
        logger.info("Yangi xabar yo'q.")
        return

    max_id = offset
    for upd in updates:
        max_id = max(max_id, upd["update_id"])
        msg = upd.get("message") or {}
        text = msg.get("text")
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if not text:
            continue
        # Faqat egaga javob beramiz (boshqalar botni ishlatib kvota yemasin)
        if TELEGRAM_CHAT_ID and chat_id != str(TELEGRAM_CHAT_ID):
            logger.info("Notanish chat_id %s - o'tkazildi", chat_id)
            continue
        logger.info("Savol: %s", text[:80])
        reply = _handle_text(text)
        try:
            _tg("sendMessage", chat_id=chat_id, text=reply, parse_mode="HTML")
        except requests.RequestException as exc:
            logger.error("Javob yuborilmadi: %s", exc)

    _save_offset(max_id)


if __name__ == "__main__":
    poll_once()
