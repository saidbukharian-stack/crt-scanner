"""
OANDA Connector
===============
OANDA v20 REST API (bepul practice/demo hisob) orqali narx ma'lumotlarini olish.

MT5'ga muqobil manba: Windows ham, terminal ham talab qilmaydi — shuning
uchun bulutli Linux serverda (Oracle Cloud va h.k.) ishlaydi.

Interfeys mt5_connector.MT5Connector bilan bir xil:
    connect() -> bool
    get_candles(symbol, timeframe, count) -> DataFrame[time_ny, time_utc,
                                                        open, high, low, close, volume]
scanner.py va levels.py uchun manba farqi sezilmaydi.

Sozlash:
1. https://www.oanda.com da bepul demo (practice) hisob oching
2. Hisob kabinetida "Manage API Access" -> tokenni oling
3. .env fayliga yozing:
     DATA_SOURCE=oanda
     OANDA_API_TOKEN=...

Vaqt haqida: OANDA barcha vaqtlarni UTC (RFC3339) formatida beradi —
MT5'dagi kabi server-offset topish SHART EMAS. H4/D shamlar
dailyAlignment=17 + alignmentTimezone=America/New_York bilan so'raladi,
natijada H4 shamlar NY vaqtida [1, 5, 9, 13, 17, 21] da ochiladi —
CRT sham guruhlash (config.H4_CANDLE_HOURS_NY) bilan to'liq mos.
"""

import logging

import pandas as pd
import requests

from config import NY_TZ, OANDA_API_TOKEN, OANDA_SYMBOL_MAP

logger = logging.getLogger(__name__)

_BASE_URL = "https://api-fxpractice.oanda.com"

# Loyihadagi timeframe nomlarini OANDA granularity'ga moslash
_GRANULARITY_MAP = {
    "M1": "M1",
    "M5": "M5",
    "M15": "M15",
    "M30": "M30",
    "H1": "H1",
    "H4": "H4",
    "D1": "D",
}


class OandaConnector:
    def __init__(self):
        self._session = requests.Session()
        self._connected = False

    def connect(self) -> bool:
        """Token to'g'riligini /v3/accounts so'rovi bilan tekshiradi."""
        if not OANDA_API_TOKEN:
            logger.error(
                "OANDA_API_TOKEN sozlanmagan. .env faylini tekshiring "
                "(demo hisob: oanda.com -> Manage API Access)."
            )
            return False
        self._session.headers.update(
            {"Authorization": f"Bearer {OANDA_API_TOKEN}"}
        )
        try:
            resp = self._session.get(f"{_BASE_URL}/v3/accounts", timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("OANDA'ga ulanib bo'lmadi: %s", exc)
            return False
        self._connected = True
        logger.info("OANDA'ga muvaffaqiyatli ulanildi.")
        return True

    def disconnect(self):
        self._session.close()
        self._connected = False

    def get_candles(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        """
        Oxirgi `count` ta YOPILGAN shamni qaytaradi (hali shakllanayotgan
        sham tashlab yuboriladi - sweep'ni yopilmagan sham close'ida
        aniqlash yolg'on signal beradi).
        """
        instrument = OANDA_SYMBOL_MAP.get(symbol)
        if instrument is None:
            logger.warning("OANDA'da symbol mapping topilmadi: %s", symbol)
            return pd.DataFrame()

        gran = _GRANULARITY_MAP[timeframe]
        params = {
            "granularity": gran,
            # +1: shakllanayotgan sham tushib qolgach ham `count` ta qolsin
            "count": min(count + 1, 5000),
            "price": "M",  # mid-price (bid/ask o'rtasi)
        }
        if gran in ("H4", "D"):
            # Kunlik sham NY 17:00 da ochiladi (forex kun almashinuvi),
            # H4 shamlar shundan kelib chiqib 17/21/1/5/9/13 NY bo'ladi
            params["dailyAlignment"] = 17
            params["alignmentTimezone"] = "America/New_York"

        try:
            resp = self._session.get(
                f"{_BASE_URL}/v3/instruments/{instrument}/candles",
                params=params, timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Ma'lumot olinmadi: %s %s (%s)", symbol, timeframe, exc)
            return pd.DataFrame()

        candles = [c for c in resp.json().get("candles", []) if c["complete"]]
        if not candles:
            logger.warning("Ma'lumot bo'sh: %s %s", symbol, timeframe)
            return pd.DataFrame()

        df = pd.DataFrame(
            {
                "time_utc": pd.to_datetime([c["time"] for c in candles], utc=True),
                "open": [float(c["mid"]["o"]) for c in candles],
                "high": [float(c["mid"]["h"]) for c in candles],
                "low": [float(c["mid"]["l"]) for c in candles],
                "close": [float(c["mid"]["c"]) for c in candles],
                "volume": [c["volume"] for c in candles],
            }
        )
        df["time_ny"] = df["time_utc"].dt.tz_convert(NY_TZ)
        return df[["time_ny", "time_utc", "open", "high", "low", "close", "volume"]]

    def get_current_price(self, symbol: str) -> dict:
        """Joriy bid/ask (pricing endpoint account talab qilgani uchun
        oxirgi M1 sham close'i bilan taxminiy qaytaramiz)."""
        df = self.get_candles(symbol, "M1", count=1)
        if df.empty:
            return {}
        last = df.iloc[-1]
        return {"bid": last["close"], "ask": last["close"], "time": last["time_utc"]}


# Modul darajasidagi yagona instance (mt5_connector bilan bir xil uslub)
connector = OandaConnector()
