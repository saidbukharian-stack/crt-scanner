# CRT Scanner — Loyiha Holati va Reja
*Claude Code'da davom ettirish uchun kontekst hujjati*

---

## 1. LOYIHA MAQSADI (qisqacha)

Savdo roboti EMAS — **ogohlantirish (alert) tizimi**. Treyder 7 ta FundingPips
challenge tajribasidan xulosa: strategiya ishlaydi, muammo intizomda
(qasos-savdo, SL'siz pozitsiya, overtrading). Yechim: "kod = ko'z, treyder = miya."

Uch qatlam (kelishilgan):
1. **Setup skaneri** — mexanik shartlarni (sweep) kuzatib Telegram'ga signal
2. **Risk-qulf** — kunlik limit, cooldown (asosiy zaif nuqtaga qarshi himoya)
3. **LLM yordamchi** — hali qo'shilmagan, quyida alohida bo'lim bor (bo'lim 4)

---

## 2. HOZIRGACHA QILINGAN ISHLAR

### Qabul qilingan qarorlar
| Savol | Qaror |
|---|---|
| Narx manbai | **MT5 demo terminal** (lokal, bepul, 100% qonuniy) |
| Instrumentlar | EURUSD, GBPUSD, USDCAD, XAUUSD, NAS100, US500 |
| Signal shartlari | **Bir nechtasi parallel**: Asia H/L sweep, PDH/PDL sweep, CRT range sweep |
| ISC modeli | Loyihadan **olib tashlandi** — faqat CRT/DOL/QT qoladi |
| Byudjet | 0 so'm, hammasi lokal |

### Yaratilgan kod (`crt_scanner/` papkasi)
| Fayl | Holati | Vazifasi |
|---|---|---|
| `config.py` | ✅ Tayyor | Instrumentlar, CRT/sessiya vaqt oynalari (NY vaqti), risk sozlamalari, `.env` yuklash |
| `mt5_connector.py` | ✅ Tayyor (Windows'da sinalmagan) | MT5 ulanish, server↔NY vaqt farqini avtomatik aniqlash, shamlarni olish |
| `levels.py` | ✅ Tayyor va sinalgan | PDH/PDL, Asia/London session H/L, CRT range (1AM/5AM/9AM H4 shamlar) |
| `signals.py` | ✅ Tayyor va sinalgan | Sweep aniqlash: wick daraja o'tadi + close orqaga qaytadi |
| `telegram_notifier.py` | ✅ Tayyor (token sinalmagan) | Signalni formatlab Telegram'ga yuborish |
| `scanner.py` | ✅ Tayyor | Asosiy loop — barchasini bog'laydi, 5 daqiqada bir tekshiradi |
| `README.md` | ✅ Tayyor | O'rnatish/ishga tushirish qo'llanmasi |

### Sinovdan o'tgan narsalar
- Barcha modullar Python sintaksis xatosiz import bo'ladi
- `signals.detect_sweep()` sun'iy ma'lumotda to'g'ri ishlashi tasdiqlandi
  (wick daraja o'tib, close orqaga qaytgan holatni to'g'ri aniqladi)

### Sinovdan o'tgan narsalar (2026-07-04, Windows'da, Claude Code)
- MT5 terminal qayta o'rnatildi, MetaQuotes-Demo hisob avtomatik ochildi
  (login 5052617259, $100,000 demo, server: MetaQuotes-Demo)
- `pip install -r requirements.txt` — Python 3.14 bilan muammosiz
- MT5'ga real ulanish (`mt5.initialize()`) ishladi
- Symbol nomlari tekshirildi: hammasi bor, faqat `NAS100` → `USTEC` deb
  o'zgartirildi (config.py tuzatildi)
- Butun zanjir (ulanish → shamlar → darajalar → skan) real ma'lumotda ishladi
- H4 shamlar NY vaqtida aynan [1,5,9,13,17,21] soatlarda ochilishi tasdiqlandi
  (MetaQuotes-Demo = UTC+3, CRT sham guruhlash to'g'ri)
- `_detect_server_offset`dagi JIDDIY XATO topilib tuzatildi:
  `datetime.fromtimestamp()` lokal (Toshkent) vaqtga o'girib, offsetni +5
  soatga buzardi. Endi tz-aware hisoblanadi. Qo'shimcha: dam olish kunlari
  ticklar eskirgani uchun offset aniqlanmaydi — fallback UTC+3 + warning.

- Telegram bot yaratildi va sinaldi (2026-07-04): @FromBukhara_bot ("TAP Lab."),
  chat_id 484301636. `.env` to'ldirildi, `telegram_notifier.send_telegram_message()`
  real xabar yubordi (True qaytdi).
- YANGI YO'NALISH (2026-07-04): treyder oy oxirigacha xizmat safarida, komp
  ochilmaydi. Qaror: narx manbai broker-agnostik (validatsiya bosqichi,
  FundingPips unutildi), tizim bepul bulut serverga ko'chiriladi.
- `DATA_SOURCE` konfiguratsiyasi qo'shildi: mt5 | oanda | yahoo.
  Uchta connector bir xil interfeys: connect(), get_candles() -> DataFrame.
- `oanda_connector.py` yozildi (token kutmoqda - OANDA'ga kirish muammosi,
  hozircha to'xtatildi). `yahoo_connector.py` yozildi VA REAL SINALDI -
  hisob/token umuman kerak emas. Ticker xaritasi: forex to'g'ridan-to'g'ri,
  XAUUSD->GC=F, USTEC->NQ=F, US500->ES=F (futures). H4 1 soatlikdan NY
  17:00 hizalanish bilan yig'iladi - [1,5,9,13,17,21] NY tasdiqlandi.
  D1 NY 17:00 forex kuniga hizalangan; Yahoo'ning juma yopilishidagi
  "sayoz qator" artefakti filtrlangan (PDH/PDL buzilmasin deb).
- BULUTGA JOYLANDI (2026-07-04): GitHub Actions, repo
  github.com/saidbukharian-stack/crt-scanner (public). Jadval: ish kunlari
  har 10 daqiqada + yakshanba 21:00 UTC dan (workflow: .github/workflows/scan.yml).
  Token/chat_id GitHub Secrets'da. Yuborilgan signallar ro'yxati Actions
  cache'da (data/notified.json) saqlanadi - takror xabar yo'q. Birinchi
  sinov ishga tushishi muvaffaqiyatli o'tdi. Lokal komp endi SHART EMAS.
- scanner.py'ga --once rejimi qo'shildi (cron/CI uchun) va notified holati
  faylga saqlanadigan bo'ldi (3 kundan eski yozuvlar tozalanadi).
- MODEL ANIQLANDI (2026-07-05): docs/ dagi PDF'lar (@Im-speculator CRT/DOL
  seriyasi, Triad QT, Arden CRT) o'rganildi. MUHIM TUZATISH: CRT modeli
  bo'yicha 9AM (key) shami OLDINGI H4 shamlar (9PM/1AM/5AM) diapazonini
  key time'da purge qiladi - skaner avval key shamning o'z diapazonini
  kuzatgan (xato). config.CRT_MODELS ga qayta qurildi:
  1AM: [5PM,9PM] oyna 02-03; 5AM: [5PM,9PM,1AM] oyna 06-08:30;
  9AM: [9PM,1AM,5AM] oyna 09-10. PDH/PDL va Asia sweep endi faqat
  killzone'larda (London 02-05, NY 07-11).
- FORWARD-TEST qo'shildi (outcome_tracker.py): har signal uchun xayoliy
  savdo (kirish=purge close, stop=purge wick), maqsadlar CRT-50% + 1R/2R/3R
  parallel, muddat 17:00 NY, bir shamda stop+maqsad = konservativ stop.
  Natijalar results/results.csv ga (workflow repoga commit qiladi) +
  Telegram xabar. Sinovlar: real Juma ma'lumotida haqiqiy 9AM CRT signal
  topildi (Asia high purge 09:05), tracker 3 ssenariyda to'g'ri ishladi.
- MODEL TO'LIQ O'RGANILDI (2026-07-05): 23 video transkript yuklandi
  (docs/transcripts/). Asoschi = Romeotpt (CRT secrets ep.1-10), qo'shimcha
  = TTrades. "Model #1" = turtle soup sweep (teshib qaytish + close trigger).
  M5 tasdiq = IC-CISD (TTrades): narx POI'ga tegib, qarshi trend shamlar
  qatorini yopib o'tishi.
- M5 CISD FORWARD-TEST'GA QO'SHILDI: har purge uchun IKKI xayoliy savdo
  parallel o'lchanadi -> "raw" (purge close'ida xom kirish) va "m5_cisd"
  (M5 CISD tasdig'i bilan kirish, stop=swing high/low). results.csv da
  "variant" ustuni. Maqsad: M5 tasdiq winrate'ni oshiradimi - raqam bilan
  ko'rish. signals.detect_cisd() + outcome_tracker qayta yozildi, sinovlardan
  o'tdi, bulutda ishladi.
- MODEL BILIM HUJJATI (2026-07-05): docs/MODEL_KNOWLEDGE.md yaratildi - 11
  transkript + PDF chuqur o'qib, 16 bo'limli tuzilgan baza (falsafa, fraktal,
  power-of-three, turtle soup, Model #1, key level, candle 3, CISD, ideal
  formation, targets, SMT, time theory, weekly profiles, bias, failed CRT).
  Bu LLM/RAG bazasining asosi.
- Keyingi qadamlar: (1) dushanba jonli signal+forward-test kuzatuvi,
  (2) Notion trade jurnal, (3) LLM bilim bazasi (docs/ PDF + transcripts/ +
  MODEL_KNOWLEDGE.md dan RAG) + Telegram savol-javob - markaziy uzoq maqsad.
  Aniqlangan kelajak skaner yaxshilanishlari: SMT filtri, weekly profile
  bias, key level (OB/FVG) aniqlash, DOL avtomatik.

### Sinovdan o'TMAGAN narsalar
- Bozor ochiq paytdagi jonli skanerlash (test shanba kuni o'tkazildi, shu
  sabab Asia/London/CRT darajalari bo'sh chiqdi — dushanba tekshirish kerak)
- PDH/PDL eslatmasi: dam olish kunlari `iloc[-2]` payshanba shamini oladi
  (juma o'rniga) — savdo soatlarida to'g'ri ishlaydi, faqat weekendda chalg'itadi

---

## 3. KEYINGI QADAMLAR (ustuvorlik tartibida)

### A) Darhol — ishga tushirish va debug (Claude Code, Windows)
1. MT5 terminal o'rnatish, MetaQuotes-Demo hisob ochish
2. `pip install -r requirements.txt`
3. `.env` sozlash (Telegram bot yaratish, token+chat_id)
4. Market Watch'da aniq symbol nomlarini tekshirib `config.py`ni tuzatish
5. `python scanner.py` ishga tushirish, loglarni kuzatish, xatolarni tuzatish
6. Bir necha kun kuzatib, signal chastotasini baholash (juda kam/juda ko'p emasmi)

### B) Risk-qulf modulini ulash
- Hozir `config.RiskLock` dataclass sifatida bor, lekin `scanner.py` bilan bog'lanmagan
- Kerak: kunlik savdo hisoblagich, `-1.5%` limitga yetganda Telegram'ga
  `notify_risk_lock()` yuborish (funksiya `telegram_notifier.py`da tayyor turibdi)
- Bu ma'lumot qayerdan keladi — MT5 hisob balansi/tarixidanmi, yoki treyder
  qo'lda "savdo qildim" deb botga yozadimi — aniqlashtirish kerak

### C) SQLite jurnal
- Har bir yuborilgan signalni bazaga yozish (vaqt, symbol, condition, daraja)
- Treyder keyinchalik "shu signal asosida kirdimmi, natija qanday" deb
  qo'lda belgilashi mumkin bo'lgan mexanizm (Telegram tugmalari orqali?)
- Haftalik statistika: qaysi shart/instrument/sessiya ko'proq signal berayapti

### D) Backtest
- Tarixiy ma'lumotda (MT5 yoki Dukascopy) CRT/DOL mexanik yadrosini tekshirish
- Statistika: winrate, RR, sessiya bo'yicha taqsimot
- Maqsad: strategiyaga ishonchni raqam bilan tiklash (ISC'dagi cherry-picked
  27-32RR misollariga ishonmaslik saboqi hisobga olingan holda)

### E) SMT divergence moduli
- Korrelyatsion juftliklarni (EURUSD/GBPUSD, XAUUSD/XAGUSD va h.k.)
  avtomatik solishtirish — ekstremumlardan biri sweep, ikkinchisi sweep
  qilmasa = signal

---

## 4. ⚠️ LLM INTEGRATSIYASI — HALI BOSHLANMAGAN, LEKIN LOYIHANING ASOSIY QISMI

Foydalanuvchi eslatdi: **bu loyihaning markaziy g'oyasi** — CRT/DOL/QT
bilimlarini LLM bilan birlashtirib, Telegram'da haqiqiy "yordamchi instrument"
yaratish (Bloomberg terminal emas, lekin shunga o'xshash funksiya).

LLM qayerda ishlatiladi (taxminiy, aniqlashtirish kerak):

1. **Signal tushuntirish** — sweep signal yuborilganda, LLM shu kontekstni
   (qaysi daraja, qaysi sessiya, PDF materiallardagi qoidalar) tabiiy tilda
   tushuntirib berishi mumkin: "Bu 9AM CRT sweep, DOL bilan mos keladimi
   tekshiring, protokolga ko'ra Asia/London high-low himoyalangan bo'lishi
   kerak."
2. **Savol-javob** — treyder Telegram'da botga savol yozadi ("XAUUSD hozir
   qanday holatda?", "9AM CRT qoidalarini eslatib ber"), LLM loyiha
   fayllaridagi (Friday CRT, 9AM/5AM/1AM CRT, DOL, QT Education) bilimlar
   asosida javob beradi — bu RAG (Retrieval-Augmented Generation) kerak
   bo'ladi: PDF'lardagi qoidalarni bilim bazasiga aylantirish.
3. **Haftalik jurnal tahlili** — SQLite'dagi savdo tarixini LLM tahlil qilib,
   naqshlar va qoida buzilishlarini hisobot qiladi (asl rejada aytilgan edi).

**Texnik variant:** Claude API (arzon) yoki lokal Ollama (bepul) — avvalgi
suhbatda ikkalasi ham muhokama qilingan, hali tanlanmagan.

**Hal qilinishi kerak bo'lgan savollar:**
- LLM Telegram botining har xabariga javob beradimi, yoki faqat maxsus
  buyruqlarga (`/tushuntir`, `/holat EURUSD`)?
- Bilim bazasi qanday tayyorlanadi — PDF'lar qo'lda qisqacha qoidalar
  matniga aylantiriladimi, yoki embeddings/vector DB kerakmi?
- Claude API tanlansa — byudjet "0 so'm" tamoyiliga qanday mos keladi
  (API pullik, garchi arzon bo'lsa ham)?

---

## 5. FAYLLAR RO'YXATI (loyiha ichida)

```
crt_scanner/
├── config.py
├── mt5_connector.py
├── levels.py
├── signals.py
├── telegram_notifier.py
├── scanner.py
├── requirements.txt
├── .env.example
├── README.md
└── data/            (bo'sh, SQLite jurnal uchun keyinroq)
```

Manba materiallar (loyiha Files bo'limida): Friday_CRT_Model.pdf, 9_AM_CRT.pdf,
5AM_CRT.pdf, 1AM_CRT.pdf, Draw_on_Liquidity_DOL_1.pdf, CRT__TS_Guide.pdf,
EU_4h_CRTs.pdf, QT_Education.pdf, va YugiohFX rasmlari (OTE, DOL, SMT tushunchalari).
