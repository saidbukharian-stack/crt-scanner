# CRT Scanner — Audit uchun to'liq texnik hujjat

**Sana:** 2026-07-22
**Repo:** https://github.com/saidbukharian-stack/crt-scanner (public)
**Holat:** ishlab turgan prototip, forward-test bosqichida
**Kod hajmi:** 5 795 satr Python (24 modul), 77 commit

---

# 0. AUDITORGA MUROJAAT — bizga nima kerak

Bu tizim **savdo roboti EMAS** — u ICT/CRT metodologiyasi bo'yicha savdo
setuplarini topib treyderga xabar beradigan **ogohlantirish tizimi**.
Falsafa: *"kod = ko'z, treyder = miya"*. Kod hech qachon savdo ochmaydi.

## 0.1 Bizning asosiy muammomiz (halol bayon)

**Tizim texnik jihatdan ishlaydi, lekin savdo natijalari MANFIY.**

- 6 oylik backtest (6 instrument, 2 639 simulyatsiya): barcha 5 variant minusda
- Jonli forward-test (47 yakunlangan savdo): ham minusda
- Filtrlar signal sonini keskin kamaytiradi, lekin **sifatni oshirmaydi**
  (qabul qilinganlar o'rtacha −0.127R, rad etilganlar −0.113R — farq yo'q)

**Savol:** muammo qayerda — (a) modelning o'zida, (b) bizning talqinimizda,
(c) implementatsiyada, (d) o'lchov metodologiyasida?

## 0.2 Auditordan aniq nima kutamiz

Quyidagi savollarga **dalilga asoslangan** javob:

### A. Metodologiya (eng muhim)
1. **Look-ahead bias** bormi? `backtest.py` da H4/D1 barlar M5'dan qayta
   quriladi, CISD o'suvchi kesimlarda qidiriladi — bu yetarlimi?
2. **Survivorship / selection bias**: NDOG filtrini aynan o'sha ma'lumotga
   qarab o'chirdik (in-sample tanlov). Bu qanchalik jiddiy xato?
3. **Namuna hajmi**: 19 qabul signal (yangi qoidalar bilan 6 oyda) —
   statistik xulosa uchun yetarlimi? Qancha kerak?
4. **Spread modeli**: har savdodan bir marta konstanta ayiriladi
   (EURUSD 0.8 pip). Realistikmi? Slippage/komissiya hisobga olinmagan.
5. **Bar-ichi (intrabar) taxminlar**: bir shamda ham stop, ham maqsadga
   tegilsa — biz KONSERVATIV stopni tanlaymiz. To'g'ri yondashuvmi?

### B. Savdo mantig'i
6. **Sweep ta'rifi** to'g'rimi? (wick darajani teshadi + close qaytadi +
   rad-dumi ≥30%)
7. **CISD algoritmi** (`signals.detect_cisd`) ICT/TTrades ta'rifiga mosmi?
8. **Maqsad tanlovi**: 50% (diapazon o'rtasi) + 100% (qarshi likvidlik) —
   mantiqan asoslimi? RR odatda 1.1–1.5R chiqadi, bu juda kammi?
9. **Stop joylashuvi**: CISD swing'i — juda tor emasmi? (win-rate 30-40%)
10. **BE o'chirilgani** to'g'ri qarormi? (o'lchov: BE@50% −15.4R,
    BE@1R −8.4R, BE'siz −13.7R — 108 juftlangan savdoda)

### C. Filtrlar
11. Premium/Discount, QT (Quarterly Theory), Midnight Open — bu filtrlar
    **haqiqatan edge beradimi**, yoki shunchaki namunani kamaytiradimi?
12. HRL (High Resistance Liquidity) filtrini o'chirdik (62 signaldan 4 tasini
    o'tkazardi). To'g'ri qarormi, yoki implementatsiya xatosimi?
13. Filtrlarni ketma-ket (AND) qo'llash o'rniga **ball tizimi** (bizda
    `confluence_score` bor) yaxshiroqmi?

### D. Kod sifati
14. Kritik xatolar, race condition, ma'lumot buzilishi xavfi
15. Vaqt zonalari bilan ishlash (NY/UTC/broker server) — ishonchlimi?
16. Xotira/resurs oqishi, uzoq ishlaganda barqarorlik

## 0.3 Auditor uchun tayyor ma'lumotlar

| Fayl | Nima bor | Hajm |
|---|---|---|
| `results/backtest_results.csv` | 6 oy × 6 instrument simulyatsiya | 2 790 qator, 35 ustun |
| `results/results_v3.csv` | jonli forward-test natijalari | 62 qator, 25 ustun |
| `results/signals_log.csv` | HAR signal + har filtr qarori + shadow | 67 qator, 22 ustun |
| `results/report.md` | avtomatik hisobot | — |
| Butun kod | GitHub'da public | 24 modul |

**Muhim:** `signals_log.csv` da **rad etilgan signallar ham** bor va ularning
"agar savdo ochilganda nima bo'lardi" (shadow) natijasi yozilgan — bu
filtrlarning foydaliligini bevosita o'lchash imkonini beradi.

---

# 1. MAHSULOT NIMA QILADI

## 1.1 Umumiy oqim

```
Narx (MT5/Yahoo)
   ↓
Likvidlik darajalari hisoblanadi (PDH/PDL, Asia, CRT, IPDA)
   ↓
Sweep (purge) qidiriladi — daraja teshildi va close qaytdi
   ↓
3 filtr (P/D → QT → Midnight bias)
   ↓
├─ QABUL: Telegram (grafik + reja + ball + analog + LLM tanqidi)
│         + 5 xayoliy savdo ochiladi
└─ RAD:   qisqa ⚪ xabar + jurnalga yoziladi + shadow kuzatuv
   ↓
Natijalar CSV → analyze_results.py → hisobot
```

## 1.2 Savdo setupi qanday quriladi (sabab-oqibat zanjiri)

1. **DARAJA** mavjud (likvidlik to'plangan joy: PDH/PDL, Asia H/L, CRT
   sham chegarasi, IPDA 20/40/60 kunlik ekstremum)
2. **PURGE**: narx darajani wick bilan teshadi, LEKIN close ichkariga
   qaytadi. Rad-dumi shamning ≥30% bo'lishi shart (`MIN_REJECT_TAIL_FRAC`)
3. **CISD** (Change in State of Delivery): M5'da qarshi yo'nalishdagi
   ketma-ket shamlar qatorining tanasi yopiladi → yetkazish holati o'zgardi
4. **KIRISH** = CISD shami close'i
5. **STOP** = CISD swing (bullish'da swing low, bearish'da swing high).
   **Hech qachon ko'chirilmaydi** (BE yo'q — 2026-07-14 qarori)
6. **MAQSAD A** = diapazon 50% (crt_mid) → yarim pozitsiya yopiladi
7. **MAQSAD B** = diapazon 100% (qarshi likvidlik) → qolgan yarmi
8. **Muddat**: 17:00 NY — yetmasa qolgani close'da yopiladi

Zanjirning istalgan bo'g'ini yo'q bo'lsa setup TO'LIQ EMAS:
- purge'siz CISD = oddiy trend o'zgarishi, bizniki emas
- CISD'siz purge = tasdiqlanmagan, kirish taqiqlangan
- vaqt oynasidan tashqari purge = shovqin

---

# 2. ARXITEKTURA

## 2.1 Modullar (24 fayl, 5 795 satr)

### Ma'lumot qatlami
| Modul | Satr | Vazifa |
|---|---|---|
| `mt5_connector.py` | 242 | MT5 terminal (lokal, aniq spot narx). Server vaqt offsetini avtomatik aniqlaydi, tarix eskirganda qayta yuklaydi, `get_candles_range` backtest uchun |
| `yahoo_connector.py` | 162 | Yahoo Finance (bulut, bepul, futures narx) |
| `oanda_connector.py` | 145 | OANDA demo API (zaxira, hozir ishlatilmaydi) |

### Model mantig'i
| Modul | Satr | Vazifa |
|---|---|---|
| `levels.py` | 200 | Barcha likvidlik darajalari: PDH/PDL, sessiya H/L, CRT diapazonlari, NWOG/NDOG, juftlash (paired_price) |
| `signals.py` | 276 | **Yadro**: `detect_sweep()` (purge aniqlash), `detect_cisd()` (tasdiq), `format_trade_plan()` |
| `analysis.py` | 475 | Order flow, DOL, FVG, Order Block, IRL/ERL, equal H/L, double-purge, SMT, MMxM faza, Midnight Open, HRL |
| `qt.py` | 80 | Quarterly Theory: kunlik choraklar (Asia/London/NYam/NYpm) va fazalar |
| `ote.py` | 124 | Optimal Trade Entry: 62-79% retracement zonasi, 08:30-11:00 oyna, institutsional darajalar |
| `stdv.py` | 124 | Standard Deviation proyeksiya (−2/−2.5/−4) — qo'shimcha ma'lumot |
| `ipda.py` | 54 | IPDA 20/40/60 kunlik ekstremum darajalari |
| `silver_bullet.py` | 70 | Silver Bullet: vaqt-oynali FVG kirish |
| `ontology.py` | 250 | To'liqlik balli, tarixiy analog, LLM validator, `/zanjir` |

### Ijro va kuzatuv
| Modul | Satr | Vazifa |
|---|---|---|
| `scanner.py` | 373 | Asosiy sikl: skan → filtrlar → xabar → forward-test yangilash |
| `outcome_tracker.py` | 694 | **Eng katta modul**: 5 variant hayot sikli, savdo yuritish, boshqaruv, natija yozish, shadow tracking |
| `paper_account.py` | 86 | Xayoliy balanslar ($5000, 1% risk), manba bo'yicha alohida |
| `ablation.py` | 163 | signals_log.csv boshqaruvi, signal_id, dedup, shadow yangilash |

### Chiqish va interfeys
| Modul | Satr | Vazifa |
|---|---|---|
| `telegram_notifier.py` | 150 | Xabar/rasm yuborish, signal formati |
| `telegram_bot.py` | 234 | Bot: `/holat`, `/zanjir`, `/hisob`, savol-javob |
| `chart_image.py` | 237 | Grafik chizish (matplotlib — chiziqlar bilan; TV screenshot /holat uchun) |
| `tv_screenshot.py` | 168 | TradingView screenshot (Playwright, lokal) |
| `market_snapshot.py` | 176 | Jonli holat matni (LLM uchun kontekst) |
| `llm_client.py` | 276 | Gemini→Groq fallback, strukturali tanqid, bilim bazasi |

### Tahlil vositalari
| Modul | Satr | Vazifa |
|---|---|---|
| `backtest.py` | 381 | Tarixiy simulyatsiya (jonli bilan bir xil kod yo'li) |
| `analyze_results.py` | 330 | Hisobot: variantlar, kesimlar, ablation, bootstrap CI |
| `config.py` | 325 | Barcha sozlamalar (env bilan override) |

## 2.2 Fayl tuzilishi

```
crt_scanner/
├── *.py (24 modul)                    — kod
├── config.py                          — barcha sozlamalar
├── .env                               — SIRLAR (gitignore'da)
├── .env.example                       — namuna
├── docs/                              — GITIGNORE'DA (mualliflik huquqi)
│   ├── MODEL_KNOWLEDGE.md             — 25 bo'lim, 32KB bilim bazasi
│   ├── *.pdf                          — o'quv materiallari
│   └── transcripts/                   — YouTube transkriptlari
├── results/                           — natijalar (repoga commit qilinadi)
│   ├── backtest_results.csv           — 2 790 qator
│   ├── results_v3.csv                 — jonli forward-test
│   ├── signals_log.csv                — ablation jurnali
│   └── report.md                      — avtomatik hisobot
├── data/                              — GITIGNORE'DA (lokal holat)
│   ├── trades.json                    — ochiq xayoliy savdolar
│   ├── shadow_trades.json             — rad etilganlar kuzatuvi
│   ├── paper_account_mt5.json         — balanslar (manba bo'yicha)
│   └── notified.json                  — dedup holati
├── .github/workflows/                 — bulut (scan.yml, bot.yml)
├── scripts/                           — status.ps1, stop.ps1, stop_bot.ps1
├── .vscode/tasks.json                 — VS Code tugmalari
├── *.bat                              — CMD tugmalari
├── run_local.ps1, run_local_bot.ps1   — ishga tushirish
├── README.md, QOLLANMA.md             — hujjatlar
└── AUDIT.md                           — shu fayl
```

## 2.3 Ishga tushirish rejimlari

| Rejim | Narx manbai | Grafik | Qachon |
|---|---|---|---|
| **Lokal** | MT5 (spot, aniq) | TradingView screenshot | Kompyuter yoniq |
| **Bulut** | Yahoo (futures) | matplotlib | GitHub Actions 24/7 |

**Muhim:** ikkala manba natijalari **hech qachon birlashtirilmaydi** —
narx (spot vs futures) va sessiya chegaralari farqi sweep aniqlashga
bevosita ta'sir qiladi. Har savdoda `source` maydoni bor, `update_trades`
faqat o'z manbasidagi savdolarni yangilaydi, balanslar alohida fayllarda.

---

# 3. JORIY KONFIGURATSIYA (2026-07-22)

```python
INSTRUMENTS = ['EURUSD', 'GBPUSD', 'USDCAD', 'XAUUSD']   # forex + oltin
DATA_SOURCE = 'mt5'
SCAN_INTERVAL_MINUTES = 2 (env), config default 5
MT5_TIMEFRAME_ENTRY = 'M5'    # sweep/CISD aniqlash
MT5_TIMEFRAME_HTF = 'H4'      # CRT diapazonlari

SIGNAL_CONDITIONS = {
    'asia_hl_sweep':     True,
    'pdh_pdl_sweep':     True,
    'crt_range_sweep':   True,
    'opening_gap_sweep': False,   # NDOG/NWOG o'chirildi (backtest zarari)
    'ipda_sweep':        True,
}

# Filtrlar
QT_FILTER_ENABLED = True              # faqat Manipulation/Distribution fazasi
MIDNIGHT_BIAS_ENABLED = True          # tolerance 15% kunlik diapazon
HRL_FILTER_ENABLED = False            # O'CHIRILDI (62 dan 4 tasini o'tkazardi)

# Boshqaruv
MGMT_BE_ENABLED = False               # BREAKEVEN YO'Q
MGMT_PARTIAL_ENABLED = True           # 50% maqsadda yarim yopish
MGMT_PARTIAL_FRAC = 0.5

# Xayoliy hisob
PAPER_START_BALANCE = 5000.0
PAPER_RISK_PCT = 1.0                  # har savdoga 1%

# Backtest
SPREAD_PRICE = {'EURUSD': 0.00008, 'GBPUSD': 0.0001,
                'USDCAD': 0.00012, 'XAUUSD': 0.3}

# CRT modellari (NY vaqti)
CRT_MODELS = {
  '1AM_CRT': {range_candles: [17,21],  window: 02:00-03:00},
  '5AM_CRT': {range_candles: [17,21,1], window: 06:00-08:30},
  '9AM_CRT': {range_candles: [21,1,5],  window: 09:00-10:00},
}
KILLZONES_NY = [('02:00','05:00'), ('07:00','11:00')]
```

## 3.1 Muhit o'zgaruvchilari (.env)

Sirlar: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GROQ_API_KEY`,
`GEMINI_API_KEY`, `OANDA_API_TOKEN`

Sozlamalar: `DATA_SOURCE`, `USE_TV_SCREENSHOT`, `SCAN_INTERVAL_MINUTES`,
`MAX_RUNTIME_SEC`, `HRL_FILTER_ENABLED`, `MIDNIGHT_BIAS_TOLERANCE_FRAC`,
`MGMT_BE_ENABLED`, `MGMT_PARTIAL_ENABLED`, `MGMT_BE_AT_R`,
`OPENING_GAP_SIGNAL_PREFIXES`, `ABLATION_LOG_ENABLED`,
`SHADOW_TRACKING_ENABLED`, `NOTIFY_REJECTED_ENABLED`,
`LLM_STRUCTURED_ENABLED`, `BACKTEST_SPREAD_MULT`, `LLM_PRIMARY`

---

# 4. SAVDO VARIANTLARI (A/B tajriba)

Har signal uchun **5 xayoliy savdo** ochiladi. Kirish uslubi har xil,
**maqsad bir xil** (50% + likvidlik) → toza taqqoslash.

| Variant | Kirish | Boshqaruv |
|---|---|---|
| `m5_cisd` | M5 CISD close'i, darrov | yo'q (to'liq pozitsiya) |
| `m5_managed` | M5 CISD close'i | 50%'da yarim yopish |
| `m5_ote` | OTE 62-79% retracement (08:30-11:00) | 50%'da yarim |
| `m5_sb` | Silver Bullet FVG (03-04/10-11/14-15) | 50%'da yarim |
| `m1_ote` | M1 (micro) CISD + OTE | 50%'da yarim |

Har variant **alohida $5000 balans** yuritadi.
`P&L = risk_usd × net_R` (lot hisoblanmaydi — instrumentdan mustaqil).

## 4.1 Savdo holat mashinasi

```
pending (CISD kutilmoqda)
   ├─ CISD topildi → active  (m5_cisd, m5_managed)
   ├─ CISD topildi → ote_wait (m5_ote, m5_sb, m1_ote — zona kutiladi)
   │                    └─ zona teginildi → active
   └─ 17:00 NY o'tdi → no_m5_entry (natijaga kirmaydi)

active → yakun:
   liquidity  — 100% maqsad olindi
   stop       — stopga tegdi (−1R, yoki yarim yopilgan bo'lsa ≈0R)
   expired    — 17:00 NY, qolgani close'da
```

---

# 5. MA'LUMOT SXEMALARI

## 5.1 results_v3.csv (jonli forward-test) — 25 ustun
```
variant, source, entry_time_ny, resolved_time_ny, symbol, condition,
level_name, direction, entry, sl, r_size, outcome, hit_50, hit_liquidity,
t50_px, t100_px, stdv_2_px, stdv_2_5_px, stdv_4_px, mfe_r, mae_r, net_r,
risk_usd, pnl_usd, balance_after
```

## 5.2 signals_log.csv (ablation jurnali) — 22 ustun
```
signal_id, timestamp_utc, symbol, direction, level_type, sweep_wick_pct,
cisd_confirmed, filter_pd, filter_qt, filter_qt_phase, filter_mo_bias,
filter_hrl, final_verdict, rejected_by, source, shadow_outcome_r,
llm_score, llm_confidence, llm_counter_argument,
confluence_score, analog_n, analog_win_pct
```
**Muhim:** har filtr ALOHIDA baholanadi (early-return yo'q) — filtr yiqilsa
ham qolganlari tekshiriladi. Bu "agar shu filtrni o'chirsak nima bo'lardi"
degan savolga javob beradi.

## 5.3 backtest_results.csv — 35 ustun
results_v3 ustunlari + `signal_id, final_verdict, rejected_by, filter_*,
run_id, is_backtest`

---

# 6. NATIJALAR (halol, to'liq)

## 6.1 Backtest: 6 instrument × 6 oy (2026-01-01 → 07-01)

**2 639 yakunlangan simulyatsiya** (367 qabul + 2 272 rad-shadow)

| Variant | n | Win% | O'rt R | Sof R |
|---|---|---|---|---|
| m5_cisd | 108 | 39.8% | −0.13 | −13.7 |
| m5_managed | 108 | 40.7% | −0.14 | −15.4 |
| m5_ote | 72 | 27.8% | −0.54 | −39.0 |
| m5_sb | 21 | 33.3% | −0.43 | −9.1 |
| m1_ote | 58 | 20.7% | −0.83 | −48.3 |

**Yangi qoidalar bilan (NDOG'siz, BE'siz) qayta hisoblash:** 19 savdo,
m5_cisd +4.0R, m5_managed +1.6R — lekin bu **in-sample** (filtrni aynan
shu ma'lumotga qarab o'chirganmiz).

## 6.2 Jonli forward-test (results_v3.csv)

47 yakunlangan savdo: m5_cisd −11.4R, m5_managed −7.7R, m5_ote −11.0R

## 6.3 Kesimlar (backtest, m5_cisd)

**Instrument:** GBPUSD +10.3R (yagona musbat), qolganlari minusda
**Daraja turi:** CRT +0.21R o'rt (musbat), NDOG −0.22R (o'chirildi)
**Hafta kuni:** chorshanba +0.90R, juma −0.67R
**Sessiya:** London −0.10R, NY_AM −0.62R

## 6.4 Ablation (filtrlar foydalimi?)

Marginal tahlil ("faqat shu filtr yiqitganlar"ning shadow natijasi):
- P/D: −0.03R (n=26)
- Midnight: −0.20R (n=33)
- HRL: +0.05R (n=33) ← filtr yaxshi signallarni ham o'ldirardi

**Xulosa:** filtrlar zarar keltirmaydi, lekin **edge ham bermaydi**.
Qabul qilinganlar (−0.127R) ≈ rad etilganlar (−0.113R).

## 6.5 Boshqaruv tajribasi (108 juftlangan savdo, bir xil kirish)

| Sozlama | Win% | Sof R |
|---|---|---|
| BE@50%-tegish (eski) | 41% | **−15.4R** |
| BE@1R | 40% | −8.4R |
| Partial'siz + BE@1R | 37% | **−6.4R** |
| BE@1.5R | 40% | −13.3R |
| Boshqaruvsiz | 40% | −13.7R |

Treyder qarori: **BE butunlay o'chirildi** (50%'da yarim + 100%'gacha).

---

# 7. MA'LUM MUAMMOLAR VA CHEKLOVLAR

## 7.1 Metodologik xavflar (auditor e'tibori uchun)

1. **In-sample tanlov (overfitting)**: NDOG o'chirish va filtr kalibrlash
   aynan test ma'lumotiga qarab qilingan. Out-of-sample tekshiruv yo'q.
2. **Kichik namuna**: yangi qoidalar bilan 6 oyda 19 savdo. n<30 —
   `analyze_results.py` buni belgilaydi, lekin qaror baribir shunga
   asoslangan.
3. **Backtest chegaralari**: M1 tarixi ~13 soat bilan cheklangan (MT5),
   Yahoo fallback M5'da ~60 kun.
4. **Intrabar noaniqlik**: bir shamda stop va maqsad ikkalasiga tegilsa —
   konservativ stop tanlanadi. Real natija boshqacha bo'lishi mumkin.
5. **Spread konstanta**: dinamik spread, slippage, komissiya, swap yo'q.
6. **Yakshanba gap**: alohida ishlov berilmagan.
7. **Yangiliklar (NFP/CPI)**: filtr yo'q — yuqori ta'sirli yangilik
   paytidagi signallar oddiy signal kabi qabul qilinadi.

## 7.2 Texnik cheklovlar

8. **Lokal rejim kompyuterga bog'liq** — o'chsa signal kelmaydi.
9. **MT5 qayta ishga tushirilsa** skaner ham qayta yoqilishi kerak
   (aks holda "Symbol topilmadi" xatosi).
10. **LLM bepul kvota**: Groq HTTP 413 (kontekst 32KB'dan oshganda) —
    hozir yadro bo'limlargina yuboriladi (12.6KB).
11. **TradingView screenshot** faqat lokal (bulut IP bloklanadi), cookie
    kerak, sahifa yuklanishiga 30-40 soniya ketadi.
12. **Bir jarayonli**: skaner va bot alohida jarayon, umumiy holat
    fayllari orqali (JSON) — bir vaqtda yozish nazorati yo'q.

## 7.3 Ataylab qilinmagan narsalar

- Avtomatik savdo (broker API orqali order qo'yish) — **printsipial rad**
- Real pul bilan ishlash — faqat xayoliy hisob
- Optimizatsiya/parametr qidirish (grid search) — overfitting xavfi

---

# 8. TAKRORLASH (auditor uchun)

## 8.1 O'rnatish
```bash
git clone https://github.com/saidbukharian-stack/crt-scanner
cd crt-scanner
pip install -r requirements.txt
cp .env.example .env    # tokenlarni to'ldiring
```

## 8.2 Backtest takrorlash
```bash
python backtest.py --symbol EURUSD --from 2026-01-01 --to 2026-07-01
```
**Determinizm:** bir oraliq ikki marta yurgizilsa natija AYNAN bir xil
(tasdiqlangan: hash bir xil chiqadi). MT5 terminal ochiq bo'lishi kerak;
bo'lmasa Yahoo fallback (ogohlantirish bilan).

## 8.3 Tahlil
```bash
python analyze_results.py                    # hammasi
python analyze_results.py --backtest-only
python analyze_results.py --source mt5
```
Chiqish: konsol jadvallari + `results/report.md`

## 8.4 Jonli ishga tushirish
```bash
python scanner.py          # doimiy sikl
python scanner.py --once   # bir marta
python telegram_bot.py --serve
```

---

# 9. QAROR TARIXI (nima uchun shunday)

| Sana | Qaror | Asos |
|---|---|---|
| 07-08 | "Xom purge" varianti o'chirildi | Barcha o'lchovda minusda |
| 07-09 | Maqsad = likvidlik (STDV emas) | Treyder qarori: 50% + 100% |
| 07-11 | NWOG/NDOG, Midnight, HRL qo'shildi | ICT kurikulumi tahlili |
| 07-11 | IPDA, Silver Bullet, M1, MMxM qo'shildi | Treyder buyurtmasi |
| 07-13 | Ablation logging + backtest + tahlil | O'lchov infratuzilmasi |
| 07-14 | **BE butunlay o'chirildi** | 108 juftlangan savdo tahlili |
| 07-14 | NDOG/NWOG signal'dan o'chirildi | Backtest: n=78, −0.22R |
| 07-14 | Indekslar olib tashlandi | Treyder qarori (forex+metall) |
| 07-20 | Ontologiya dvigateli | Bilim xaritasini mexanik kuchga |
| 07-22 | **HRL o'chirildi, Midnight yumshatildi** | Jonli: 62 signal, 0 qabul |

---

# 10. XAVFSIZLIK

- `.env` va `docs/` **gitignore'da** (sirlar va mualliflik materiallari)
- Bilim bazasi bulutga GitHub Secret (`KNOWLEDGE_MD`) orqali uzatiladi
- Telegram bot **faqat egasining chat_id'siga** javob beradi
- Repo **public** (treyder ruxsati bilan) — kodda sir yo'q
- ⚠️ **Auditorga:** `.env` faylini HECH QACHON yubormang. Kerak bo'lsa
  `.env.example` yetarli.

---

# 11. XULOSA

**Nima ishlaydi:**
- Texnik infratuzilma barqaror (77 commit, xatosiz ishlaydi)
- O'lchov tizimi kuchli: har signal, har filtr qarori, shadow natija yozilади
- Backtest determinstik va jonli kod yo'lini ishlatadi
- Qarorlar taxminga emas, o'lchovga asoslanadi

**Nima ishlamaydi:**
- **Savdo natijalari manfiy** — barcha variant, barcha instrument (GBPUSD'dan
  tashqari)
- Filtrlar edge bermaydi (qabul ≈ rad)
- Namuna kichik, in-sample tanlov xavfi bor

**Auditordan asosiy kutish:** muammo modelning talqinidami, kodning
implementatsiyasidami, yoki o'lchov metodologiyasidami — shuni aniqlash.
