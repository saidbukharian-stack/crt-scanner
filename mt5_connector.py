"""
MT5 Connector
=============
MetaTrader 5 terminali bilan ulanish va narx ma'lumotlarini olish.

ESLATMA: Bu modul faqat Windows'da, MT5 terminali o'rnatilgan va ochiq
holatda ishlaydi (MetaTrader5 python paketi shunday talab qiladi).
Demo hisob bilan ishlash uchun broker demo hisob ochish shart emas -
MetaQuotes'ning o'zining demo serverini tanlash mumkin (terminal ochilganda
"MetaQuotes-Demo" serverini tanlang).
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # Linux/Mac ustida kod tuzilmasini tekshirish uchun None qoldiriladi

from config import NY_TZ, UTC_TZ

logger = logging.getLogger(__name__)

# MT5 timeframe nomlarini kutubxona konstantalariga moslash
_TIMEFRAME_MAP = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}

# Sham davomiyligi (sekund) - tarix yangiligini tekshirish uchun
_TIMEFRAME_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "D1": 86400,
}


class MT5Connector:
    def __init__(self):
        self._connected = False
        self._server_utc_offset_hours = None  # broker server vaqti UTC'dan farqi

    def connect(self) -> bool:
        """MT5 terminaliga ulanadi. Terminal oldindan ochiq bo'lishi kerak."""
        if mt5 is None:
            raise RuntimeError(
                "MetaTrader5 python paketi topilmadi. Bu skript faqat Windows'da, "
                "MT5 terminali o'rnatilgan holda ishlaydi. "
                "O'rnatish: pip install MetaTrader5"
            )
        if not mt5.initialize():
            logger.error("MT5 initialize xato: %s", mt5.last_error())
            return False
        self._connected = True
        self._detect_server_offset()
        logger.info("MT5'ga muvaffaqiyatli ulanildi.")
        return True

    def disconnect(self):
        if mt5 is not None and self._connected:
            mt5.shutdown()
            self._connected = False

    def _detect_server_offset(self):
        """
        Broker server vaqti bilan UTC orasidagi farqni aniqlaydi.
        Buni CRT/killzone vaqtlarini (NY vaqtida berilgan) broker vaqtiga
        to'g'ri o'girish uchun ishlatamiz.

        MT5 tick.time - epoch ko'rinishida, lekin server devoriy soatini
        ifodalaydi. Shuning uchun uni UTC deb o'qib, haqiqiy UTC bilan
        solishtirsak, farq = server offset bo'ladi. datetime.fromtimestamp()
        ni tz'siz ishlatish MUMKIN EMAS - u lokal (Toshkent) vaqtga o'girib,
        offsetni +5 soatga buzadi.

        Dam olish kunlari (forex yopiq: juma ~22:00 UTC - yakshanba 21:00 UTC)
        ticklar juma kunidan qolgan bo'ladi va offsetni tick orqali aniqlab
        BO'LMAYDI - bu holda ogohlantirish bilan fallback (UTC+3 yoki oldingi
        aniqlangan qiymat) ishlatiladi.
        """
        utc_now = datetime.now(timezone.utc)

        wd = utc_now.weekday()  # dushanba=0 ... yakshanba=6
        market_closed = (
            wd == 5
            or (wd == 4 and utc_now.hour >= 22)
            or (wd == 6 and utc_now.hour < 21)
        )
        if market_closed:
            fallback = self._server_utc_offset_hours
            if fallback is None:
                fallback = 3  # ko'p forex brokerlar UTC+3 (EET yoz vaqti)
            self._server_utc_offset_hours = fallback
            logger.warning(
                "Bozor yopiq (dam olish kuni) - server offsetni tick orqali "
                "aniqlab bo'lmaydi, UTC%+d deb olindi. Bozor ochilganda "
                "skanerni qayta ishga tushiring.", fallback,
            )
            return

        # ENG YANGI tick = eng KATTA tick.time (epoch).
        # DIQQAT: "|age| eng kichigi" deb tanlash XATO edi - musbat offsetda
        # (masalan UTC+3) eskirgan tick kichikroq |age| beradi va eng eskisi
        # "eng yangi" deb tanlanardi -> offset 1 soatga kam chiqardi.
        latest_tick = 0
        symbols = mt5.symbols_get()
        if not symbols:
            raise RuntimeError("MT5'da hech qanday symbol topilmadi.")
        for sym in symbols[:200]:
            tick = mt5.symbol_info_tick(sym.name)
            if tick is None or tick.time == 0:
                continue
            if tick.time > latest_tick:
                latest_tick = tick.time

        if latest_tick == 0:
            raise RuntimeError("Hech bir symbolda tick topilmadi.")

        server_wall = datetime.fromtimestamp(latest_tick, tz=timezone.utc)
        offset = round((server_wall - utc_now).total_seconds() / 3600)
        if not (-12 <= offset <= 14):
            raise RuntimeError(
                f"Server offset aql bovar qilmas qiymat chiqdi: {offset:+d}h. "
                "Ticklar eskirgan bo'lishi mumkin - bozor ochiqligini tekshiring."
            )
        self._server_utc_offset_hours = offset
        logger.info("Broker server vaqti UTC%+d ekanligi aniqlandi.", offset)

    def ensure_symbol(self, symbol: str) -> bool:
        """Symbol Market Watch'da yoqilganligini tekshiradi, yo'q bo'lsa yoqadi."""
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.warning("Symbol topilmadi: %s (broker nomini tekshiring)", symbol)
            return False
        if not info.visible:
            mt5.symbol_select(symbol, True)
        return True

    def get_candles(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        """
        Berilgan symbol va timeframe uchun oxirgi `count` ta shamni oladi.
        Natija: DataFrame ustunlari - time_ny, open, high, low, close, tick_volume
        time_ny - NY vaqtiga o'girilgan vaqt (CRT hisob-kitoblari shu ustunga tayanadi).
        """
        if not self.ensure_symbol(symbol):
            return pd.DataFrame()

        tf_const = getattr(mt5, _TIMEFRAME_MAP[timeframe])
        bar_sec = _TIMEFRAME_SECONDS[timeframe]

        # MT5 tarixni ASINXRON yuklaydi: symbol yangi tanlangan bo'lsa
        # birinchi so'rov eski keshni qaytaradi. Yangi ma'lumot kelguncha
        # qayta urinamiz (oxirgi sham tick vaqtidan juda orqada qolmasin).
        rates = None
        for attempt in range(6):
            rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, count)
            if rates is None or len(rates) == 0:
                time.sleep(1.0)
                continue
            tick = mt5.symbol_info_tick(symbol)
            if tick is None or tick.time == 0:
                break  # tick yo'q (bozor yopiq) - bor ma'lumot bilan ketamiz
            lag = tick.time - int(rates[-1]["time"])
            if lag <= 3 * bar_sec:
                break  # yangi
            logger.info("%s %s tarixi eskirgan (%.0f daq), yuklanmoqda...",
                        symbol, timeframe, lag / 60)
            time.sleep(1.5)

        if rates is None or len(rates) == 0:
            logger.warning("Ma'lumot olinmadi: %s %s", symbol, timeframe)
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        # MT5 vaqti broker server vaqtida keladi (odatda UTC+2/+3, epoch sifatida)
        df["time_utc"] = pd.to_datetime(df["time"], unit="s", utc=True) - timedelta(
            hours=self._server_utc_offset_hours
        )
        df["time_ny"] = df["time_utc"].dt.tz_convert(NY_TZ)
        df = df.rename(columns={"tick_volume": "volume"})
        return df[["time_ny", "time_utc", "open", "high", "low", "close", "volume"]]

    def get_current_price(self, symbol: str) -> dict:
        """Symbol uchun joriy bid/ask narxini qaytaradi."""
        if not self.ensure_symbol(symbol):
            return {}
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {}
        return {"bid": tick.bid, "ask": tick.ask, "time": tick.time}


# Modul darajasidagi yagona instance (scanner.py shundan foydalanadi)
connector = MT5Connector()
