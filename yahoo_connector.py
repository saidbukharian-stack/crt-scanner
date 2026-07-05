"""
Yahoo Finance Connector
=======================
Yahoo Finance (yfinance) orqali narx olish - HECH QANDAY hisob, token,
karta talab qilmaydi. Istalgan OS/bulut serverda ishlaydi.

Kamchiliklari (validatsiya bosqichi uchun qabul qilingan):
- Norasmiy manba: Yahoo ba'zan so'rovlarni cheklashi mumkin
- Oltin spot emas, futures (GC=F); indekslar ham futures (NQ=F, ES=F) -
  narxlar broker CFD'sidan biroz farq qiladi, lekin harakat bir xil
- H4 shamlar tayyor kelmaydi - 1 soatlik shamlardan lokal yig'iladi
  (NY 17:00 kun almashinuviga hizalab, natija: 1/5/9/13/17/21 NY - CRT mos)

Interfeys mt5_connector/oanda_connector bilan bir xil:
    connect() -> bool
    get_candles(symbol, timeframe, count) -> DataFrame[time_ny, time_utc,
                                                open, high, low, close, volume]
"""

import logging
import time as _time
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf

from config import NY_TZ, YAHOO_SYMBOL_MAP

logger = logging.getLogger(__name__)

# Yahoo'da to'g'ridan-to'g'ri bor intervallar. H4/D1 - 1h'dan yig'iladi.
_NATIVE_INTERVALS = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h"}

_PERIOD_FOR = {"M1": "2d", "M5": "5d", "M15": "5d", "M30": "1mo", "H1": "1mo"}

_TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}


class YahooConnector:
    def __init__(self):
        self._connected = False
        # Bir skan siklida H4 va D1 ikkalasi ham 1h ma'lumotdan yig'ilgani
        # uchun 1h so'rovni qisqa muddat keshlaymiz (ortiqcha HTTP so'rov bo'lmasin)
        self._h1_cache: dict[str, tuple[float, pd.DataFrame]] = {}
        self._h1_cache_ttl_sec = 120

    def connect(self) -> bool:
        """Yahoo token talab qilmaydi - shunchaki bitta sinov so'rovi."""
        try:
            probe = yf.Ticker("EURUSD=X").history(interval="1d", period="5d")
        except Exception as exc:
            logger.error("Yahoo Finance'ga ulanib bo'lmadi: %s", exc)
            return False
        if probe.empty:
            logger.error("Yahoo Finance bo'sh javob qaytardi.")
            return False
        self._connected = True
        logger.info("Yahoo Finance'ga muvaffaqiyatli ulanildi.")
        return True

    def disconnect(self):
        self._connected = False

    # ------------------------------------------------------------------
    def _fetch(self, ticker: str, interval: str, period: str) -> pd.DataFrame:
        """Yahoo'dan xom ma'lumot: NY tz'ga o'girilgan OHLCV DataFrame."""
        try:
            df = yf.Ticker(ticker).history(interval=interval, period=period)
        except Exception as exc:
            logger.warning("Yahoo so'rov xato: %s %s (%s)", ticker, interval, exc)
            return pd.DataFrame()
        if df.empty:
            return pd.DataFrame()
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        df.index = df.index.tz_convert(NY_TZ)
        return df[["open", "high", "low", "close", "volume"]]

    def _get_h1(self, ticker: str) -> pd.DataFrame:
        now = _time.monotonic()
        cached = self._h1_cache.get(ticker)
        if cached is not None and now - cached[0] < self._h1_cache_ttl_sec:
            return cached[1]
        df = self._fetch(ticker, "1h", "1mo")
        self._h1_cache[ticker] = (now, df)
        return df

    @staticmethod
    def _resample(df_h1: pd.DataFrame, rule: str, offset: str) -> pd.DataFrame:
        if df_h1.empty:
            return pd.DataFrame()
        agg = df_h1.resample(rule, offset=offset).agg(
            {"open": "first", "high": "max", "low": "min",
             "close": "last", "volume": "sum"}
        )
        return agg.dropna(subset=["open"])  # dam olish kunlari bo'sh binlar

    # ------------------------------------------------------------------
    def get_candles(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        ticker = YAHOO_SYMBOL_MAP.get(symbol)
        if ticker is None:
            logger.warning("Yahoo'da symbol mapping topilmadi: %s", symbol)
            return pd.DataFrame()

        if timeframe == "H4":
            # 1h -> 4h, NY yarim tundan +1h siljitib: 01/05/09/13/17/21 NY
            df = self._resample(self._get_h1(ticker), "4h", "1h")
        elif timeframe == "D1":
            # 1h -> kunlik, forex kuni NY 17:00 da almashadi.
            # '1D' bilan offset ishlamaydi (pandas cheklovi), shuning uchun '24h'.
            h1 = self._get_h1(ticker)
            df = self._resample(h1, "24h", "17h")
            if not df.empty:
                # Yahoo juma yopilishida bitta "sayoz" qator qoldiradi (masalan
                # 17:00 dagi yolg'iz tick) - undan yasalgan 1-2 qatorli soxta
                # kunlik sham keyinchalik PDH/PDL hisobini buzadi. Shuning
                # uchun juda kam manba-qatorli binlarni tashlaymiz, faqat
                # HOZIR shakllanayotgan (joriy kun) bin bundan mustasno.
                counts = h1["close"].resample("24h", offset="17h").count()
                counts = counts.reindex(df.index, fill_value=0)
                now_ny = pd.Timestamp.now(tz=NY_TZ)
                is_current = (df.index <= now_ny) & (
                    now_ny < df.index + pd.Timedelta(hours=24)
                )
                df = df[(counts >= 3) | is_current]
        elif timeframe in _NATIVE_INTERVALS:
            df = self._fetch(ticker, _NATIVE_INTERVALS[timeframe],
                             _PERIOD_FOR[timeframe])
            # Hali yopilmagan oxirgi shamni tashlaymiz - yopilmagan close
            # bilan sweep aniqlash yolg'on signal beradi (M5 va h.k. uchun)
            if not df.empty:
                tf_min = _TF_MINUTES[timeframe]
                now_utc = datetime.now(timezone.utc)
                closes_at = df.index.tz_convert("UTC") + timedelta(minutes=tf_min)
                df = df[closes_at <= now_utc]
        else:
            logger.warning("Noma'lum timeframe: %s", timeframe)
            return pd.DataFrame()

        if df.empty:
            logger.warning("Ma'lumot olinmadi: %s %s", symbol, timeframe)
            return pd.DataFrame()

        df = df.tail(count).copy()
        df["time_ny"] = df.index
        df["time_utc"] = df.index.tz_convert("UTC")
        return df.reset_index(drop=True)[
            ["time_ny", "time_utc", "open", "high", "low", "close", "volume"]
        ]

    def get_current_price(self, symbol: str) -> dict:
        df = self.get_candles(symbol, "M5", count=1)
        if df.empty:
            return {}
        last = df.iloc[-1]
        return {"bid": last["close"], "ask": last["close"], "time": last["time_utc"]}


# Modul darajasidagi yagona instance (boshqa connectorlar bilan bir xil uslub)
connector = YahooConnector()
