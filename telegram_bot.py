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

import argparse
import json
import logging
import os
import time

import requests

from config import DB_PATH, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from llm_client import answer_question, analyze_market, GEMINI_API_KEY, GROQ_API_KEY
from market_snapshot import build_snapshot, resolve_symbol

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telegram_bot")

_API = "https://api.telegram.org/bot{token}/{method}"
_OFFSET_PATH = os.path.join(os.path.dirname(DB_PATH), "tg_offset.json")

_HELP = (
    "🤖 <b>CRT yordamchi bot</b>\n\n"
    "<b>1) Savol-javob</b> — CRT/DOL/QT bo'yicha savol yozing:\n"
    "• 9AM CRT qoidalarini eslat\n"
    "• Turtle soup nima?\n"
    "• CRT qachon ishlamaydi?\n\n"
    "<b>2) Jonli tahlil</b> — instrument holatini so'rang:\n"
    "• /holat XAUUSD\n"
    "• EURUSD hozir qanday?\n"
    "• USTEC holati\n\n"
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


def _is_status_query(text_low: str) -> bool:
    """Savol jonli holat so'rovimi (tahlil kerak)?"""
    if text_low.startswith("/holat"):
        return True
    triggers = ("hozir qanday", "holati", "holat", "tahlil", "qanday ahvolda",
                "nima gap", "setup bormi")
    return any(t in text_low for t in triggers)


def _handle_text(text: str) -> str:
    stripped = text.strip()
    low = stripped.lower()
    if low in ("/start", "/help", "help", "start"):
        return _HELP
    if not (GEMINI_API_KEY or GROQ_API_KEY):
        return "⚠️ LLM hali sozlanmagan (GEMINI_API_KEY / GROQ_API_KEY yo'q)."

    # Jonli tahlil rejimi: instrument holati so'ralsa
    if _is_status_query(low):
        symbol = resolve_symbol(stripped)
        if symbol is None:
            return ("Qaysi instrument? Masalan: /holat XAUUSD\n"
                    "Mavjud: EURUSD, GBPUSD, USDCAD, XAUUSD, USTEC, US500")
        snapshot = build_snapshot(symbol)
        if snapshot is None:
            return f"⚠️ {symbol} bo'yicha ma'lumot olinmadi (bozor yopiq yoki manba xatosi)."
        analysis = analyze_market(snapshot)
        if not analysis:
            return "⚠️ Tahlil qilib bo'lmadi (LLM limiti yoki xato)."
        return f"📈 <b>{symbol} — jonli tahlil</b>\n\n{analysis}"

    # Aks holda: bilim bazasidan savol-javob
    if low.startswith("/tushuntir"):
        stripped = stripped[len("/tushuntir"):].strip() or "Joriy holatni tushuntir"
    answer = answer_question(stripped)
    return answer or "⚠️ Kechirasiz, hozir javob bera olmadim (LLM limiti yoki xato)."


def _process_updates(updates: list, offset: int) -> int:
    """Xabarlarga javob beradi, yangi offset qaytaradi."""
    max_id = offset
    for upd in updates:
        max_id = max(max_id, upd["update_id"])
        msg = upd.get("message") or {}
        text = msg.get("text")
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if not text:
            continue
        # Faqat egaga javob (boshqalar botni ishlatib kvota yemasin)
        if TELEGRAM_CHAT_ID and chat_id != str(TELEGRAM_CHAT_ID):
            logger.info("Notanish chat_id %s - o'tkazildi", chat_id)
            continue
        logger.info("Savol: %s", text[:80])
        reply = _handle_text(text)
        try:
            _tg("sendMessage", chat_id=chat_id, text=reply, parse_mode="HTML")
        except requests.RequestException as exc:
            logger.error("Javob yuborilmadi: %s", exc)
    return max_id


def poll_once():
    """Bir marta yangi xabarlarni olib javob beradi (cron rejimi)."""
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
    _save_offset(_process_updates(updates, offset))


def serve(max_runtime_sec: int = 21000):
    """
    Uzluksiz long-polling: savol kelishi bilan bir necha soniyada javob beradi.
    ~5h50m ishlaydi (GitHub Actions 6 soatlik limitidan xavfsiz kam), keyin
    chiqadi - workflow uni qayta ishga tushiradi.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN yo'q")
        return
    logger.info("Bot serve rejimida ishga tushdi (long-polling).")
    start = time.monotonic()
    offset = _load_offset()
    while time.monotonic() - start < max_runtime_sec:
        try:
            # timeout=25: Telegram xabar kelguncha 25s kutadi (near-instant javob)
            data = _tg_long("getUpdates", offset=offset + 1, timeout=25,
                            allowed_updates=["message"])
        except requests.RequestException as exc:
            logger.warning("getUpdates xato: %s - 5s dan keyin qayta", exc)
            time.sleep(5)
            continue
        updates = data.get("result", [])
        if updates:
            offset = _process_updates(updates, offset)
            _save_offset(offset)
    logger.info("Serve muddati tugadi, chiqilyapti (workflow qayta ishga tushiradi).")


def _tg_long(method: str, **params):
    """Long-polling uchun _tg (HTTP timeout > polling timeout)."""
    url = _API.format(token=TELEGRAM_BOT_TOKEN, method=method)
    resp = requests.post(url, json=params, timeout=40)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRT Telegram bot")
    parser.add_argument("--serve", action="store_true",
                        help="Uzluksiz long-polling (tez javob). Aks holda bir marta poll.")
    args = parser.parse_args()
    if args.serve:
        serve()
    else:
        poll_once()
