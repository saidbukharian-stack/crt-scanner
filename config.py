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

# ---------------------------------------------------------------------------
# Kuzatiladigan instrumentlar
# MT5'dagi aniq symbol nomi brokerga qarab farq qilishi mumkin
# (masalan "XAUUSD" o'rniga "XAUUSDm" yoki "GOLD" bo'lishi mumkin).
# Terminalni ochib, Market Watch'da aniq nomni tekshirib, shu yerga yozing.
# ---------------------------------------------------------------------------
INSTRUMENTS = [
    "EURUSD",
    "GBPUSD",
    "USDCAD",
    "XAUUSD",
    "USTEC",    # Nasdaq 100 (MetaQuotes-Demo'da shu nom; boshqa brokerlarda US100/NAS100 bo'lishi mumkin)
    "US500",    # S&P 500 CFD (broker: SPX500, US500 bo'lishi mumkin)
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
}

# ---------------------------------------------------------------------------
# CRT "key time" oynalari (NY vaqti, soat:daqiqa, 24h format)
# Loyihadagi PDF materiallardan olingan (9AM/5AM/1AM CRT qo'llanmalari)
# ---------------------------------------------------------------------------
CRT_KEY_TIMES = {
    "1AM_CRT": {
        "candle_open": "01:00",       # CRT shami ochilish vaqti
        "window_start": "02:00",      # Kirish oynasi boshlanishi
        "window_end": "03:00",        # Kirish oynasi tugashi
    },
    "5AM_CRT": {
        "candle_open": "05:00",
        "window_start": "06:00",
        "window_end": "08:30",        # London lunch (06-07) + NY opening (07-08:30)
    },
    "9AM_CRT": {
        "candle_open": "09:00",
        "window_start": "09:00",
        "window_end": "10:00",        # ba'zan 09:30-10:30 ham qo'llaniladi
    },
}

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
}

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
# Telegram sozlamalari (.env faylidan o'qiladi, kodga token yozilmaydi!)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Ma'lumotlar bazasi (savdo jurnali uchun, keyingi bosqichda ishlatiladi)
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "journal.db")
