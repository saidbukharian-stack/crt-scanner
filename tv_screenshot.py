"""
TradingView Screenshot — LOKAL rejim (Playwright brauzer avtomatlashtirish)
==========================================================================
TradingView grafigini brauzerda ochib screenshot oladi. Obuna SHART EMAS.

MUHIM CHEGARA: bu faqat LOKAL kompyuterда ishlaydi (brauzer kerak).
Bulutда (GitHub Actions) TradingView cloud IP'larni bloklaydi — u yerda
matplotlib grafik (chart_image.py) ishlatiladi.

Ikki rejim:
  1) Anonim (login yo'q) — oddiy TV grafigi, indikatorlarsiz. Darrov ishlaydi.
  2) Login bilan (cookie) — SIZNING layout (ICT-CRT indikatorlaringiz).
     docs/tradingview_cookies.txt bo'lsa avtomatik ishlatiladi.

Ishlatish:
    python tv_screenshot.py GBPUSD 15
"""

import logging
import os
import tempfile

logger = logging.getLogger(__name__)

# Bizning symbol -> TradingView symbol (broker prefiksi bilan)
TV_SYMBOL_MAP = {
    "EURUSD": "OANDA:EURUSD",
    "GBPUSD": "OANDA:GBPUSD",
    "USDCAD": "OANDA:USDCAD",
    "XAUUSD": "OANDA:XAUUSD",
    "USTEC": "OANDA:NAS100USD",
    "US500": "OANDA:SPX500USD",
}

_DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")


def _find_cookies_file() -> str | None:
    """docs/ ichidan istalgan tradingview cookie faylini topadi."""
    import glob
    hits = glob.glob(os.path.join(_DOCS_DIR, "*tradingview*cookies*.txt"))
    return hits[0] if hits else None


def _load_cookies():
    """Netscape cookies.txt -> Playwright cookie ro'yxati (bo'lmasa None)."""
    path = _find_cookies_file()
    if not path:
        return None
    cookies = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _flag, path, secure, expires, name, value = parts[:7]
            cookies.append({
                "name": name, "value": value, "domain": domain, "path": path,
                "expires": int(expires) if expires.isdigit() else -1,
                "httpOnly": False, "secure": secure.upper() == "TRUE",
            })
    return cookies or None


def capture(symbol: str, interval: str = "15", wait_ms: int = 9000) -> str | None:
    """
    TradingView grafigining screenshot'ini oladi, PNG yo'lini qaytaradi.
    interval: "5", "15", "60", "240", "D" (TradingView formati)
    """
    from playwright.sync_api import sync_playwright

    tv_symbol = TV_SYMBOL_MAP.get(symbol, f"OANDA:{symbol}")
    url = (f"https://www.tradingview.com/chart/"
           f"?symbol={tv_symbol.replace(':', '%3A')}&interval={interval}")
    out = os.path.join(tempfile.gettempdir(), f"tv_{symbol}_{interval}.png")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1600, "height": 900},
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0 Safari/537.36"),
            )
            cookies = _load_cookies()
            if cookies:
                ctx.add_cookies(cookies)
                logger.info("TradingView cookie yuklandi (sizning layout)")

            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass  # TV doim ulanib turadi - networkidle bo'lmasligi normal

            # Narx ma'lumoti kelguncha kutamiz (legend'da raqam paydo bo'lishi)
            for _ in range(6):
                page.wait_for_timeout(3000)
                try:
                    legend = page.locator(
                        '[class*="valuesWrapper"], [data-name="legend-series-item"]'
                    ).first.inner_text(timeout=3000)
                except Exception:
                    legend = ""
                if legend and any(ch.isdigit() for ch in legend):
                    logger.info("TV ma'lumoti keldi: %s", legend.replace("\n", " ")[:60])
                    break
            else:
                logger.warning("TV ma'lumoti kelmadi (bo'sh grafik bo'lishi mumkin)")

            # Modal/dialog chiqsa yopamiz (login taklifi va h.k.)
            for sel in ('button[aria-label="Close"]', '[data-name="close"]'):
                try:
                    if page.locator(sel).first.is_visible(timeout=800):
                        page.locator(sel).first.click(timeout=1500)
                        page.wait_for_timeout(400)
                except Exception:
                    pass

            # Suzuvchi panellarni yashiramiz (toza grafik uchun)
            try:
                page.add_style_tag(content="""
                    div[class*="floating-toolbar"],
                    div[class*="drawingToolbar"],
                    div[data-name="drawing-toolbar"],
                    div[class*="tv-floating-toolbar"] { display: none !important; }
                """)
                page.wait_for_timeout(600)
            except Exception:
                pass

            # Faqat grafik konteynerni suratga olamiz (butun sahifa emas)
            shot = None
            for sel in ('div.chart-gui-wrapper', 'div.chart-container',
                        'div[class*="chart-container"]'):
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1500):
                        el.screenshot(path=out)
                        shot = out
                        break
                except Exception:
                    continue
            if shot is None:
                page.screenshot(path=out, full_page=False)
                shot = out

            browser.close()
        return shot if os.path.exists(shot) and os.path.getsize(shot) > 15000 else None
    except Exception:
        logger.exception("TradingView screenshot xatosi")
        return None


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sym = sys.argv[1] if len(sys.argv) > 1 else "GBPUSD"
    itv = sys.argv[2] if len(sys.argv) > 2 else "15"
    path = capture(sym, itv)
    print("Screenshot:", path)
    if path:
        print("Hajm:", os.path.getsize(path), "bayt")
