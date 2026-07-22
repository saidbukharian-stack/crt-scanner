"""
CRT Scanner - Konfiguratsiya
=============================
Barcha sozlamalar shu yerda. Instrumentlar, sessiya vaqtlari (killzone),
va risk-qulf parametrlari.

MUHIM: Barcha vaqtlar broker serveri vaqtida emas, NY (New York) vaqtida
hisoblanadi, chunki CRT modellari (1AM/5AM/9AM CRT) NY vaqtiga asoslangan.
Kod avtomatik ravishda broker server vaqtidan NY vaqtiga o'giradi.
"""

import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()  # loyiha papkasidagi .env faylini avtomatik o'qiydi

# ---------------------------------------------------------------------------
# Vaqt zonalari
# ---------------------------------------------------------------------------
NY_TZ = ZoneInfo("America/New_York")
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
UTC_TZ = ZoneInfo("UTC")

# ---------------------------------------------------------------------------
# Narx manbai: "mt5" (lokal Windows + MT5 terminal) yoki "oanda"
# (bepul demo API, istalgan OS/bulut serverda ishlaydi).
# .env faylida DATA_SOURCE=oanda deb o'zgartiriladi.
# ---------------------------------------------------------------------------
DATA_SOURCE = os.getenv("DATA_SOURCE", "mt5").strip().lower()

# Grafik manbai: 1 = TradingView screenshot (LOKAL, brauzer kerak),
# 0 = matplotlib (bulutда ishlaydi). Bulutда TV cloud IP'ni bloklaydi.
USE_TV_SCREENSHOT = os.getenv("USE_TV_SCREENSHOT", "0").strip() == "1"

# ---------------------------------------------------------------------------
# Kuzatiladigan instrumentlar
# MT5'dagi aniq symbol nomi brokerga qarab farq qilishi mumkin
# (masalan "XAUUSD" o'rniga "XAUUSDm" yoki "GOLD" bo'lishi mumkin).
# Terminalni ochib, Market Watch'da aniq nomni tekshirib, shu yerga yozing.
# ---------------------------------------------------------------------------
# Indekslar (USTEC/US500) OLIB TASHLANDI (2026-07-14, treyder qarori):
# faqat forex va metallar qoladi.
INSTRUMENTS = [
    "EURUSD",
    "GBPUSD",
    "USDCAD",
    "XAUUSD",
]

# OANDA instrument nomlari (DATA_SOURCE=oanda bo'lganda ishlatiladi).
# Kalitlar - yuqoridagi INSTRUMENTS ro'yxati bilan bir xil nomlar.
OANDA_SYMBOL_MAP = {
    "EURUSD": "EUR_USD",
    "GBPUSD": "GBP_USD",
    "USDCAD": "USD_CAD",
    "XAUUSD": "XAU_USD",
    "USTEC": "NAS100_USD",
    "US500": "SPX500_USD",
}

# OANDA demo (practice) hisob API tokeni - .env'dan o'qiladi
OANDA_API_TOKEN = os.getenv("OANDA_API_TOKEN", "")

# Yahoo Finance ticker nomlari (DATA_SOURCE=yahoo bo'lganda ishlatiladi).
# Hisob/token talab qilmaydi. Oltin va indekslar futures orqali -
# narx broker CFD'sidan biroz farq qiladi, harakat bir xil (validatsiya uchun yetarli).
YAHOO_SYMBOL_MAP = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDCAD": "USDCAD=X",
    "XAUUSD": "GC=F",     # COMEX oltin futures (Yahoo'da spot XAUUSD yo'q)
    "USTEC": "NQ=F",      # Nasdaq 100 futures (naqd ^NDX faqat kunduzi ochiq)
    "US500": "ES=F",      # S&P 500 futures
    # SMT juftliklari uchun qo'shimcha (INSTRUMENTS'da yo'q, lekin solishtirish uchun)
    "XAGUSD": "SI=F",     # kumush futures (oltinning SMT jufti)
    "DXY": "DX=F",        # dollar indeksi (forex SMT jufti)
}

# ---------------------------------------------------------------------------
# SMT juftliklari (korrelyatsion aktivlar) - @Im-speculator/QT bo'yicha.
# "inverse": narx yo'nalishi teskari (EURUSD vs DXY) - solishtirishda hisobga olinadi.
# ---------------------------------------------------------------------------
SMT_PAIRS = {
    "EURUSD": [("GBPUSD", False)],
    "GBPUSD": [("EURUSD", False)],
    "XAUUSD": [("XAGUSD", False)],
}

# ---------------------------------------------------------------------------
# CRT modellari (NY vaqti) - @Im-speculator PDF seriyasiga mos.
#
# MUHIM MANTIQ: "9AM CRT" degani 9AM shamining O'Z diapazoni emas!
# Model bo'yicha 9AM (key) shami OLDINGI H4 shamlarning (CRT shamlar)
# diapazonini key time oynasida purge qiladi:
#   - range_candles: purge QILINADIGAN H4 shamlarning NY ochilish soatlari
#     (17 va 21 - oldingi NY kunida ochiladi, 1 va 5 - shu kunda)
#   - window: purge/kirish oynasi - sweep faqat shu oraliqda signal beradi
#
# PDF'lardan:
#   1AM CRT: CRT shamlar = 5PM (CBDR), 9PM (Asia); oyna 02:00-03:00
#   5AM CRT: CRT shamlar = 5PM, 9PM, 1AM (London); oyna 06:00-08:30
#            (London lunch 06-07 + NY opening 07-08:30)
#   9AM CRT: CRT shamlar = 9PM (Asia), 1AM (London), 5AM; oyna 09:00-10:00
#            (muqobil: 09:30-10:30)
# ---------------------------------------------------------------------------
CRT_MODELS = {
    "1AM_CRT": {
        "range_candles": [17, 21],
        "window": ("02:00", "03:00"),
    },
    "5AM_CRT": {
        "range_candles": [17, 21, 1],
        "window": ("06:00", "08:30"),
    },
    "9AM_CRT": {
        "range_candles": [21, 1, 5],
        "window": ("09:00", "10:00"),
    },
}

# H4 sham ochilish soatiga o'qiladigan nom (signal xabarlari uchun)
CRT_CANDLE_LABELS = {17: "5PM_CBDR", 21: "9PM_Asia", 1: "1AM_London", 5: "5AM"}

# ---------------------------------------------------------------------------
# Killzone oynalari (NY vaqti) - PDH/PDL va Asia H/L sweep signallari
# faqat shu oraliqlarda beriladi (tungi shovqinni kesish uchun)
# ---------------------------------------------------------------------------
KILLZONES_NY = [
    ("02:00", "05:00"),   # London killzone
    ("07:00", "11:00"),   # NY killzone
]

# CRT uchun H4 (4 soatlik) sham yopilgan vaqtlar (NY), shamlarni
# to'g'ri guruhlash uchun ishlatiladi: 1AM/5AM/9AM/1PM/5PM/9PM
H4_CANDLE_HOURS_NY = [1, 5, 9, 13, 17, 21]

# ---------------------------------------------------------------------------
# Sessiya vaqtlari (NY vaqti) - Asia/London/NY high-low hisoblash uchun
# YugiohFX materiallaridagi Forex killzone vaqtlari asosida
# ---------------------------------------------------------------------------
SESSIONS_NY = {
    "asia":        {"start": "20:00", "end": "00:00"},  # kechagi kundan boshlanadi
    "london":      {"start": "02:00", "end": "05:00"},
    "ny_am":       {"start": "07:00", "end": "10:00"},
    "london_close": {"start": "10:00", "end": "12:00"},
}

# ---------------------------------------------------------------------------
# Signal shartlari - hozircha bir nechtasi parallel yoqilgan
# Har birini alohida yoqib/o'chirib sinash mumkin
# ---------------------------------------------------------------------------
SIGNAL_CONDITIONS = {
    "asia_hl_sweep": True,       # Asia session high/low sweep
    "pdh_pdl_sweep": True,       # Oldingi kun high/low sweep
    "crt_range_sweep": True,     # CRT (1AM/5AM/9AM) range sweep
    "opening_gap_sweep": False,  # NWOG/NDOG o'chiq (2026-07-14, backtest zarari)
    "ipda_sweep": True,          # IPDA 20/40/60 kunlik ekstremum sweep (ICT)
}

# Opening-gap sweep qaysi darajalardan signal beradi. NDOG OLIB TASHLANDI
# (2026-07-14, treyder qarori): 6 oylik backtest'da n=78, o'rt -0.22R —
# eng katta zarar manbai edi. NWOG qoladi (n=11, -0.07R — neytral).
# Darajalar /holat tahlilida ko'rinaveradi, faqat signal bermaydi.
OPENING_GAP_SIGNAL_PREFIXES = tuple(
    p.strip() for p in os.getenv("OPENING_GAP_SIGNAL_PREFIXES", "NWOG").split(",")
    if p.strip())

# ---------------------------------------------------------------------------
# Skanerlash sozlamalari
# ---------------------------------------------------------------------------
SCAN_INTERVAL_MINUTES = 5        # har necha daqiqada tekshirish
MT5_TIMEFRAME_ENTRY = "M5"       # sweep'ni aniqlash uchun ishlatiladigan TF
MT5_TIMEFRAME_HTF = "H4"         # CRT range hisoblash uchun HTF

# ---------------------------------------------------------------------------
# Risk-qulf moduli (avvalgi suhbatda aytilgan asosiy zaif nuqtaga qarshi)
# ---------------------------------------------------------------------------
@dataclass
class RiskLock:
    max_trades_per_day: int = 2
    max_daily_loss_pct: float = 1.5     # kunlik hisobning necha % zarar
    risk_per_trade_pct: float = 0.5     # har bir savdo uchun risk %
    cooldown_after_loss_minutes: int = 60  # zarardan keyin majburiy tanaffus

RISK = RiskLock()

# ---------------------------------------------------------------------------
# Xayoliy (paper) hisob — forward-test natijasini DOLLARDA o'lchash uchun.
# Treyder bilan kelishilgan (2026-07-08).
# ---------------------------------------------------------------------------
PAPER_START_BALANCE = 5000.0   # boshlang'ich xayoliy balans, $
PAPER_RISK_PCT = 1.0           # har bir savdoga risk, balansning %

# ---------------------------------------------------------------------------
# Savdo boshqaruvi ("m5_managed" varianti uchun)
#
# MAQSAD = LIKVIDLIK (treyder aytgani, 2026-07-09):
#   • Maqsad 50%  = diapazon o'rtasi (crt_mid) -> shu yerda yarim pozitsiya olib,
#     breakeven'ga o'tamiz.
#   • Maqsad 100% = diapazonning QARSHI cheti (qarshi likvidlik) -> qolgan yarmi.
#   STDV -4 endi MAQSAD emas, faqat qo'shimcha ma'lumot sifatida ko'rsatiladi.
#
# Muammo (o'lchangan): savdolarning ~53% foydaga chiqib, keyin qaytib stopga
# tushardi. Yechim: 50%'da yarim olish + breakeven (agar orqaga tortadigan
# to'ldirilmagan FVG/OB qolmagan bo'lsa).
# ---------------------------------------------------------------------------
MGMT_PARTIAL_FRAC = 0.5        # 50% maqsadda qancha ulush yopiladi (0.5 = yarmi)
MGMT_BE_FORCE_R = 2.0          # narx shu R'ga yetsa, to'siq bo'lsa ham majburiy B/E

# Boshqaruv kalibrlash (2026-07-14 juftlangan tahlil: barvaqt BE g'oliblarni
# o'ldirardi, himoya esa deyarli ishlamasdi):
#   MGMT_BE_ENABLED - TREYDER QARORI (2026-07-14): BE UMUMAN O'CHIQ.
#     Qoida: 50% maqsadda yarim yopiladi, qolgan yarmi 100% likvidlikkacha
#     boradi, stop joyida qoladi (hech qachon ko'chirilmaydi).
#   MGMT_PARTIAL_ENABLED - 50% maqsadda yarim yopish yoqiq/o'chiq
#   MGMT_BE_AT_R - faqat BE yoqilganda: bo'sh = 50%-tegishda, son = shu R'da
MGMT_BE_ENABLED = os.getenv("MGMT_BE_ENABLED", "0").strip() == "1"
MGMT_PARTIAL_ENABLED = os.getenv("MGMT_PARTIAL_ENABLED", "1").strip() == "1"
_be_at = os.getenv("MGMT_BE_AT_R", "").strip()
MGMT_BE_AT_R = float(_be_at) if _be_at else None

# ---------------------------------------------------------------------------
# OTE (Optimal Trade Entry) varianti - ICT tutoriallaridan (2026-07-09).
# CISD (MSS) shakllangач darrov kirmay, impuls oyog'iga fib tortib narx
# 62-79% retracement'ga qaytishini kutamiz. Maqsad=likvidlik (bir xil),
# faqat KIRISH aniqroq -> m5_cisd bilan toza A/B.
# ---------------------------------------------------------------------------
OTE_REQUIRE_WINDOW = True      # kirish 08:30-11:00 NY oynasida bo'lishi shart (ICT qoidasi)
OTE_REQUIRE_ROUND = False      # institutsional yaxlit daraja filtri (hozircha yumshoq)

# ---------------------------------------------------------------------------
# QT (Quarterly Theory) filtri - Daye. Signal faqat "ma'qul" fazada (kunlik
# Manipulation=London yoki Distribution=NY AM) ochiladi. Accumulation (Osiyo,
# tor diapazon) va Continuation (NY PM, chalkash) chetlab o'tiladi.
# Killzone'lar allaqachon shu fazalarга to'g'ri keladi - bu aniq QT qatlami
# (killzone o'zgarsa ham ishlaydi) + Telegram/logda faza ko'rsatiladi.
# ---------------------------------------------------------------------------
QT_FILTER_ENABLED = True

# ---------------------------------------------------------------------------
# Midnight Open bias filtri (ICT) - signal yo'nalishi 00:00 NY ochilish
# narxiga mos bo'lsin: bullish faqat MO ustida, bearish faqat ostida.
# ---------------------------------------------------------------------------
MIDNIGHT_BIAS_ENABLED = True
# Midnight bias bag'rikengligi: kunlik diapazonning ulushi (0.15 = 15%).
# Purge shami narxni MO'dan ozgina o'tkazib yuborishi tabiiy - qattiq
# shart 62 signaldan 45 tasini yiqitardi (jonli o'lchov 2026-07-22).
MIDNIGHT_BIAS_TOLERANCE_FRAC = float(
    os.getenv("MIDNIGHT_BIAS_TOLERANCE_FRAC", "0.15"))

# ---------------------------------------------------------------------------
# Ablation logging - HAR signal (qabul + rad) results/signals_log.csv ga
# yoziladi, har filtr alohida baholanadi. Rad etilganlar Telegram/paper'ga
# BORMAYDI, faqat logga + yengil shadow-tracking (m5_cisd) uchun kuzatiladi.
# Default yoqilgan (faqat qo'shimcha log; qabul/rad xatti-harakati o'zgarmaydi).
# ---------------------------------------------------------------------------
ABLATION_LOG_ENABLED = os.getenv("ABLATION_LOG_ENABLED", "1").strip() == "1"
SHADOW_TRACKING_ENABLED = os.getenv("SHADOW_TRACKING_ENABLED", "1").strip() == "1"

# Rad etilgan signal haqida ham QISQA xabar yuborish (treyder tanlovi,
# 2026-07-16): tizim tirikligini ko'rsatadi, kuniga ~3 ta qo'shimcha xabar.
# Reja/LLM/grafik YO'Q - bir qatorlik ogohlantirish xolos.
NOTIFY_REJECTED_ENABLED = os.getenv("NOTIFY_REJECTED_ENABLED", "1").strip() == "1"

# ---------------------------------------------------------------------------
# Backtest: konservativ spread/slippage (NARX BIRLIGIDA, pip emas - chalkashlik
# bo'lmasin). Har simulyatsiya qilingan savdodan bir marta ayiriladi.
# BACKTEST_SPREAD_MULT env bilan umumiy ko'paytiriladi (default 1.0).
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# LLM strukturali baho (Vazifa 4): signal xabarida erkin matn o'rniga qat'iy
# JSON tanqid. Kontekst qisqartiriladi - butun bilim bazasi emas, signal
# turiga tegishli bo'limlargina yuboriladi (bo'lim raqami prefikslari,
# docs/MODEL_KNOWLEDGE.md dagi "## N." sarlavhalariga mos).
# ---------------------------------------------------------------------------
LLM_STRUCTURED_ENABLED = os.getenv("LLM_STRUCTURED_ENABLED", "1").strip() == "1"

LLM_SECTIONS_BY_CONDITION = {
    # CRT range sweep: falsafa, Po3, turtle soup, Model#1, CISD, maqsad, failed CRT
    "crt_range_sweep": ["1.", "3.", "4.", "5.", "8.", "10.", "15.", "23."],
    # PDH/PDL: sweep, key level, CISD, maqsad, bias, failed
    "pdh_pdl_sweep": ["4.", "6.", "8.", "10.", "14.", "15.", "23."],
    # Asia/London sessiya: sweep, CISD, maqsad, vaqt nazariyasi, failed
    "asia_hl_sweep": ["4.", "8.", "10.", "12.", "15.", "23."],
    # NWOG/NDOG: sweep, CISD, maqsad, ICT opening gap bo'limi
    "opening_gap_sweep": ["4.", "8.", "10.", "21.", "23."],
    # IPDA: sweep, CISD, maqsad, IPDA bo'limi
    "ipda_sweep": ["4.", "8.", "10.", "22.", "23."],
    # noma'lum shart uchun zaxira
    "_default": ["1.", "4.", "8.", "10.", "23."],
}

SPREAD_PRICE = {
    "EURUSD": 0.00008,   # ~0.8 pip
    "GBPUSD": 0.00010,
    "USDCAD": 0.00012,
    "XAUUSD": 0.30,      # ~30 sent
    "USTEC": 2.0,        # ~2 indeks punkti
    "US500": 0.5,
}
BACKTEST_SPREAD_MULT = float(os.getenv("BACKTEST_SPREAD_MULT", "1.0"))

# ---------------------------------------------------------------------------
# High-Resistance-Liquidity filtri (ICT) - kirish bilan likvidlik maqsadi
# orasida qarshi FVG (yuqori qarshilik) bo'lsa signal o'tkazilmaydi.
# ---------------------------------------------------------------------------
# O'CHIRILDI (2026-07-22): jonli o'lchov - 62 signaldan faqat 4 tasini
# o'tkazardi (6%), chunki M5'da 400 shamda doim qandaydir qarshi FVG bor.
# Backtest ablation'da ham foyda bermagan (rad etganlari o'rt +0.05R).
# Endi rad ETMAYDI, lekin ontologiya to'liqlik balliga hissa qo'shadi.
HRL_FILTER_ENABLED = os.getenv("HRL_FILTER_ENABLED", "0").strip() == "1"

# ---------------------------------------------------------------------------
# Telegram sozlamalari (.env faylidan o'qiladi, kodga token yozilmaydi!)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Ma'lumotlar bazasi (savdo jurnali uchun, keyingi bosqichda ishlatiladi)
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "journal.db")
