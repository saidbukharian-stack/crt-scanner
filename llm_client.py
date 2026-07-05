"""
LLM Client — Gemini + Groq (bepul), avtomatik fallback
======================================================
Ikki bepul provayder: avval Gemini, limitga/xatoga urilsa Groq (yoki teskari).
Ikkita bepul kvota birlashadi + biri tugasa ikkinchisi ishlaydi.

Kalitlar .env / GitHub Secrets'dan:
  GEMINI_API_KEY   — https://aistudio.google.com/apikey
  GROQ_API_KEY     — https://console.groq.com/keys
  LLM_PRIMARY      — "gemini" (default) yoki "groq" - qaysi biri birinchi

Bilim bazasi (docs/MODEL_KNOWLEDGE.md) butun holicha kontekstga joylashtiriladi —
RAG/vektor baza shart emas (hujjat ~10K token, ikki provayder ham ko'taradi).
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_PRIMARY = os.getenv("LLM_PRIMARY", "gemini").strip().lower()

# Bepul, tez modellar
_GEMINI_MODEL = "gemini-2.0-flash"
_GROQ_MODEL = "llama-3.3-70b-versatile"

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Bilim bazasi - bir marta o'qib keshlanadi (jarayon ichida)
_KNOWLEDGE_CACHE: str | None = None
_KNOWLEDGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "docs", "MODEL_KNOWLEDGE.md")


def load_knowledge() -> str:
    global _KNOWLEDGE_CACHE
    if _KNOWLEDGE_CACHE is None:
        try:
            with open(_KNOWLEDGE_PATH, encoding="utf-8") as f:
                _KNOWLEDGE_CACHE = f.read()
        except FileNotFoundError:
            logger.warning("Bilim bazasi topilmadi: %s", _KNOWLEDGE_PATH)
            _KNOWLEDGE_CACHE = ""
    return _KNOWLEDGE_CACHE


# ---------------------------------------------------------------------------
# Provayderlar
# ---------------------------------------------------------------------------
def _call_gemini(system: str, user: str, max_tokens: int) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY yo'q")
    url = _GEMINI_URL.format(model=_GEMINI_MODEL)
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.4},
    }
    resp = requests.post(
        url, params={"key": GEMINI_API_KEY}, json=payload, timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _call_groq(system: str, user: str, max_tokens: int) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY yo'q")
    payload = {
        "model": _GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    resp = requests.post(
        _GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json=payload, timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


_PROVIDERS = {"gemini": _call_gemini, "groq": _call_groq}


def ask_llm(system: str, user: str, max_tokens: int = 800) -> str | None:
    """
    Primary provayderni sinaydi, xato/limit bo'lsa ikkinchisiga o'tadi.
    Ikkalasi ham ishlamasa None qaytaradi.
    """
    order = [LLM_PRIMARY, "groq" if LLM_PRIMARY == "gemini" else "gemini"]
    last_err = None
    for name in order:
        fn = _PROVIDERS[name]
        try:
            text = fn(system, user, max_tokens)
            if text:
                logger.info("LLM javobi %s'dan olindi", name)
                return text
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            logger.warning("%s xato (HTTP %s), keyingisiga o'tilyapti", name, code)
            last_err = exc
        except Exception as exc:
            logger.warning("%s xato (%s), keyingisiga o'tilyapti", name, exc)
            last_err = exc
    logger.error("Barcha LLM provayderlar ishlamadi: %s", last_err)
    return None


# ---------------------------------------------------------------------------
# Tizim ko'rsatmasi (system prompt) - bilim bazasi bilan
# ---------------------------------------------------------------------------
def _system_prompt() -> str:
    knowledge = load_knowledge()
    return (
        "Sen CRT/Turtle Soup savdo metodologiyasi bo'yicha yordamchi "
        "instrumensan (savdo roboti EMAS, maslahatchi). Treyderga o'zbek "
        "tilida, qisqa va aniq javob ber. Faqat quyidagi bilim bazasiga "
        "tayan; unda yo'q narsani o'ylab topma, 'bilim bazasida yo'q' deb ayt. "
        "Moliyaviy maslahat berma - mexanik shartlar va model qoidalarini "
        "tushuntir, qaror treyderning o'zida.\n\n"
        "=== BILIM BAZASI ===\n" + knowledge
    )


def explain_signal(signal_summary: str) -> str | None:
    """Signal kelganda uni model qoidalari asosida tushuntiradi."""
    user = (
        "Quyidagi sweep signali keldi. Uni CRT modeli nuqtai nazaridan "
        "qisqa (3-5 jumla) tushuntir: qaysi model/shart, DOL va key level "
        "bilan qanday bog'liq, protokol nima deyishini eslat, treyder nimaga "
        "e'tibor berishi kerak.\n\n"
        f"SIGNAL:\n{signal_summary}"
    )
    return ask_llm(_system_prompt(), user, max_tokens=500)


def answer_question(question: str) -> str | None:
    """Treyderning Telegram'dagi savoliga bilim bazasidan javob beradi."""
    return ask_llm(_system_prompt(), question, max_tokens=800)


def analyze_market(snapshot: str) -> str | None:
    """
    Bozorning jonli holatini (snapshot) bilim bazasi asosida tahlil qiladi.
    Bu LLM'ning "jonli tahlilchi" rejimi - qoidalar + hozirgi holat.
    """
    user = (
        "Quyida bir instrumentning HOZIRGI jonli holati berilgan. Uni CRT/DOL "
        "metodologiyasi asosida qisqa tahlil qil:\n"
        "- Order flow/bias qaysi tomonda, DOL (draw on liquidity) ehtimol qayerda\n"
        "- Hozir qaysi oynadamiz va bu nima degani (masalan 9AM CRT oynasi)\n"
        "- Setup shakllanyaptimi yoki kutish kerakmi\n\n"
        "So'ngra SHARTLI KIRISH/CHIQISH REJASINI ber (mexanik, model qoidalari "
        "bo'yicha): agar setup shakllansa, qaysi darajada sweep kutiladi, kirish "
        "taxminan qayerda (purge close), stop qayerda (purge wick/swing), maqsad "
        "qayerda (CRT 50%, qarshi chet, yoki eng yaqin FVG/OB/daraja). Aniq "
        "narxlarni suratdagi darajalardan foydalanib ayt.\n\n"
        "Narx bashorat qilma, faqat mexanik holat va shartli rejani izohla. "
        "Bu moliyaviy maslahat emas.\n\n"
        f"=== JONLI HOLAT ===\n{snapshot}"
    )
    return ask_llm(_system_prompt(), user, max_tokens=900)
