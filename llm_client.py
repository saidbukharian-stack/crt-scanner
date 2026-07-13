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

import json
import logging
import os
import re

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


def load_knowledge_sections(prefixes: list[str]) -> str:
    """
    Bilim bazasidan faqat berilgan bo'limlarni ("## N." prefiksi bo'yicha)
    qaytaradi. Katta kontekstda muhim qoidalar yo'qolmasin degan maqsad —
    signal turiga tegishli 3-5 bo'limgina yuboriladi.
    """
    knowledge = load_knowledge()
    if not knowledge:
        return ""
    blocks = knowledge.split("\n## ")
    picked = ["## " + b for b in blocks[1:]
              if b.split(" ", 1)[0].rstrip() in prefixes]  # "4." / "21." aniq moslik
    return "\n".join(picked)


def _parse_json_block(text: str) -> dict:
    """LLM javobidan JSON'ni ajratadi (markdown ```json ... ``` ni tozalab)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        t = t[i:j + 1]
    return json.loads(t)


_CRITIC_SCHEMA = (
    '{"rule_compliance_score": <1-10 butun son>, '
    '"rules_satisfied": ["..."], '
    '"rules_violated_or_weak": ["..."], '
    '"counter_argument": "bu setup nima uchun ISHLAMASLIGI mumkin - majburiy, bo\'sh bo\'lmasin", '
    '"confidence": "low|medium|high"}'
)


def evaluate_signal_structured(signal_summary: str,
                               condition: str = "") -> dict | None:
    """
    LLM'ni TANQIDCHI sifatida ishlatadi: setup'ni himoya qilmaydi, zaif
    tomonlarni topadi. FAQAT JSON qaytarishi shart. Parse xatosida bitta
    qayta urinish. Muvaffaqiyatsiz bo'lsa None (signal baribir yuboriladi).
    """
    from config import LLM_SECTIONS_BY_CONDITION
    prefixes = LLM_SECTIONS_BY_CONDITION.get(
        condition, LLM_SECTIONS_BY_CONDITION["_default"])
    sections = load_knowledge_sections(prefixes)

    system = (
        "Sen CRT/ICT savdo metodologiyasi bo'yicha QATTIQ TANQIDCHISAN. "
        "Sen setup'ni HIMOYA QILMA. Sening vazifang - zaif tomonlarni topish. "
        "Kamida bitta jiddiy qarshi-argument keltirmasang, javob qabul "
        "qilinmaydi. Baholashda faqat quyidagi qoidalarga tayan.\n\n"
        "JAVOB FORMATI: FAQAT bitta JSON obyekt, boshqa HECH NARSA yozma "
        "(izoh yo'q, markdown yo'q):\n" + _CRITIC_SCHEMA +
        "\n\nMatn maydonlari o'zbek tilida bo'lsin.\n\n"
        "=== TEGISHLI QOIDALAR ===\n" + sections
    )
    user = (
        "Quyidagi signalni qoidalarga muvofiqligini tanqidiy baholab, "
        "faqat JSON qaytar:\n\n" + signal_summary
    )

    for attempt in (1, 2):
        raw = ask_llm(system, user if attempt == 1 else
                      user + "\n\nDIQQAT: oldingi javob JSON emas edi. "
                             "FAQAT to'g'ri JSON obyekt qaytar!",
                      max_tokens=600)
        if not raw:
            return None
        try:
            d = _parse_json_block(raw)
            score = int(d.get("rule_compliance_score", 0))
            counter = str(d.get("counter_argument", "")).strip()
            conf = str(d.get("confidence", "")).strip().lower()
            if not (1 <= score <= 10) or not counter:
                raise ValueError("score yoki counter_argument yaroqsiz")
            if conf not in ("low", "medium", "high"):
                conf = "low"
            return {
                "score": score,
                "satisfied": [str(x) for x in d.get("rules_satisfied", [])][:6],
                "weak": [str(x) for x in d.get("rules_violated_or_weak", [])][:6],
                "counter_argument": counter,
                "confidence": conf,
            }
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("LLM JSON parse xatosi (%d-urinish): %s | javob: %.120s",
                           attempt, exc, raw)
    return None


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
