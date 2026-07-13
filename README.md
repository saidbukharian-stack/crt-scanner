# CRT Scanner — Telegram Ogohlantirish Tizimi

CRT/DOL metodologiyasi asosida narx darajalarini (Asia H/L, PDH/PDL, CRT range)
kuzatib, sweep aniqlanganda Telegram'ga xabar yuboruvchi lokal skaner.

**Bu savdo roboti EMAS.** Faqat mexanik shartlarni tekshiradi va ogohlantiradi.
Kirish qarori, inducement sifati, struktura tahlili — treyderning o'zida.

## 1. Talablar

- Windows kompyuter (MetaTrader5 python paketi faqat Windows'da ishlaydi)
- [MetaTrader 5 terminali](https://www.metatrader5.com/) o'rnatilgan
- Python 3.10+

## 2. O'rnatish

```bash
# 1. MT5 terminalini oching, "MetaQuotes-Demo" serverida demo hisob oching
#    (File > Open an Account > MetaQuotes Software Corp > Demo)
#    Terminal ochiq va shu hisobga ulangan holda qolishi kerak.

# 2. Python kutubxonalarini o'rnating
pip install -r requirements.txt

# 3. .env faylini sozlang
copy .env.example .env
# .env faylini oching, TELEGRAM_BOT_TOKEN va TELEGRAM_CHAT_ID ni kiriting
```

### Telegram bot yaratish
1. Telegram'da [@BotFather](https://t.me/BotFather) ga yozing, `/newbot` buyrug'i bilan bot yarating.
2. Bergan tokenni `.env` fayliga yozing.
3. O'zingiz yaratgan botga istalgan xabar yozing (masalan "salom").
4. Brauzerda oching: `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Javobdagi `"chat":{"id": ...}` qiymatini `.env` fayliga `TELEGRAM_CHAT_ID` sifatida yozing.

## 3. Instrumentlarni tekshirish

MT5 terminalida Market Watch oynasini oching, kerakli instrumentlarning
**aniq nomini** ko'ring (brokerga qarab farq qilishi mumkin: `XAUUSD` o'rniga
`XAUUSDm`, `NAS100` o'rniga `USTEC` bo'lishi mumkin). `config.py` ichidagi
`INSTRUMENTS` ro'yxatini shunga moslab tuzating.

## 4. Ishga tushirish

```bash
python scanner.py
```

Skaner har `SCAN_INTERVAL_MINUTES` (config.py, standart 5) daqiqada barcha
instrumentlarni tekshiradi va yangi sweep signal topilsa Telegram'ga yuboradi.

To'xtatish uchun: `Ctrl+C`

## 5. Loyiha strukturasi

| Fayl | Vazifasi |
|---|---|
| `config.py` | Instrumentlar, sessiya/CRT vaqtlari, risk sozlamalari |
| `mt5_connector.py` | MT5 bilan ulanish, narx ma'lumotini olish |
| `levels.py` | PDH/PDL, sessiya H/L, CRT range hisoblash |
| `signals.py` | Sweep aniqlash mantig'i |
| `telegram_notifier.py` | Telegram xabar formatlash va yuborish |
| `scanner.py` | Asosiy loop — hammasini birlashtiradi |

## 6. Keyingi bosqichlar (hali qo'shilmagan)

- [ ] Risk-qulf modulini scanner.py bilan bog'lash (kunlik limit, cooldown)
- [ ] SQLite jurnal — har bir signalni bazaga yozish
- [ ] Backtest skripti — tarixiy Dukascopy/MT5 data'da statistik tekshirish
- [ ] SMT divergence moduli — korrelyatsion juftliklarni solishtirish

## 7. Muhim eslatmalar

- `_already_notified` xotirasi dastur qayta ishga tushirilganda tozalanadi —
  hozircha shu sodda holatda, keyinroq SQLite'ga o'tkazish rejalashtirilgan.
- CRT range hisob-kitobi H4 shamning **aniq** NY vaqtidagi ochilish soatiga
  bog'liq (`config.CRT_KEY_TIMES`). Broker server vaqti bilan NY vaqti
  orasidagi farq avtomatik aniqlanadi (`mt5_connector._detect_server_offset`),
  lekin yozgi/qishki vaqt (DST) o'zgarishlarida birinchi bir necha kun
  natijalarni tekshirib turing.

## Manba izolyatsiyasi (MUHIM)

**MT5 va Yahoo natijalari TAQQOSLANMAYDI** — narx (spot vs futures) va sessiya
chegaralari farqi sweep aniqlashga bevosita ta'sir qiladi. Shu sabab:

- Har savdo/signal `source` maydoni bilan belgilanadi (mt5/yahoo/oanda)
- `update_trades`/`update_shadows` faqat O'Z manbasida ochilgan savdolarni
  yangilaydi — boshqa manba savdosi o'z holicha kutadi
- Xayoliy balans har manba uchun alohida: `data/paper_account_<source>.json`
- Dedup kalitlari (notified.json, signal_id) manbani o'z ichiga oladi
- `analyze_results.py` hisobotlari manbalarni hech qachon birlashtirmaydi
