# 10 manba tahlili — bizga nima beradi?

**Sana:** 2026-07-22
**Maqsad:** treyder yuborgan 10 manbani ko'rib chiqib, CRT loyihasiga
qanchalik foydali ekanini aniqlash.

---

## 0. QISQA JAVOB

Manbalar **ikki guruhga** bo'linadi:

| Guruh | Manbalar | Bizga foydasi |
|---|---|---|
| **A. Savdo qoidalarini ilmiy sinash** | Aronson (EBTA), López de Prado ×2, Carver | ⭐⭐⭐ **Hozir kerak** |
| **B. Umumiy ML darsliklari** | Géron, Burkov ×2, Huyen ×2 | ⭐ Keyinroq (ma'lumot yig'ilgach) |

**Eng muhim topilma:** Aronson **6 402 ta texnik tahlil qoidasini** S&P 500'da
sinab, data-mining tarafkashligini hisobga olgach — **birortasi ham statistik
ahamiyatli chiqmagan**.

---

## 1. Evidence-Based Technical Analysis — Aronson (528 bet) ⭐⭐⭐

**Bizga eng mos kitob.** Bu bizning muammoni AYNAN ko'rib chiqadi:
texnik tahlil qoidalarini ilmiy usul bilan sinash.

### Asosiy natija (9-bob, 444-447 bet)

Aronson S&P 500'da **6 402 ta qoida** sinadi:
- **Oddiy (naiv) test** bilan: ~320 ta qoida "ahamiyatli" ko'rinadi
  → bu **aynan tasodif kutgan miqdor** (6402 × 0.05 ≈ 320)
- **Data-mining tuzatmasi** bilan (White's Reality Check, Monte Carlo
  permutation): **birortasi ham ahamiyatli emas**
- Eng yaxshi qoida: +10.25% yillik, p=0.0005 (tuzatmasiz)
  → tuzatma bilan: ahamiyatsiz

**Bizga tegishli xulosa:** biz o'nlab konfiguratsiya sinadik va "eng yaxshisini"
tanladik. Aronson ko'rsatadiki, bu jarayonda **tasodif muqarrar ravishda
"kashfiyot"ga o'xshab ko'rinadi**.

### Kitobning boshqa foydali qismlari

**Objective vs Subjective TA (1-bob):** faqat **obyektiv** (aniq ta'riflangan)
qoidalarni sinash mumkin. Subyektiv usullar tekshirib bo'lmaydi va shuning
uchun "afsonalar uchun unumdor tuproq".

✅ **Bizda to'g'ri:** CRT qoidalarimiz obyektiv (kod bilan aniqlangan).

**Detrending (1-bob):** long-bias qoidalarni baholashda bozor trendini
olib tashlash kerak — aks holda "ko'tarilayotgan bozorda hamma long
strategiya yaxshi ko'rinadi".

⚠️ **Bizda YO'Q:** biz detrend qilmaymiz. Forex majors uchun trend
kuchsiz (aksiya indeksiga nisbatan), lekin XAUUSD 2026'da kuchli
ko'tarilgan — bizning XAUUSD natijalarimizga ta'sir qilishi mumkin.

**Benchmark (1-bob):** qoida natijasi faqat **benchmark bilan solishtirganda**
ma'noga ega. Aronson eng past benchmark ishlatadi: bashorat qobiliyati
bo'lmagan tasodifiy signal.

⚠️ **Bizda YO'Q:** biz "−0.13R" deymiz, lekin **tasodifiy signal nima
beradi?** — bilmaymiz. Bu oson qo'shiladigan va juda foydali o'lchov.

**Look-ahead bias (9-bob):** Aronson signal kunining **keyingi** kuni
ochilish narxida kiradi — chunki close narxi signal hisoblashda ishlatilgan.

⚠️ **Bizda tekshirish kerak:** biz CISD **close** narxida kiramiz. Lekin
o'sha close signalni hosil qiladi. Real savdoda close narxida kirish
mumkin emas — faqat keyingi shamda. Bu **optimistik tarafkashlik**.

---

## 2. Machine Learning for Asset Managers — López de Prado (45/136 bet) ⭐⭐

**Diqqat:** bu to'liq kitob emas — 136 betdan 45 tasi (preview).

AFML'ning qisqartirilgan va amaliyroq versiyasi. Bizga muhim bo'limlar:
- **8-bob: Testing Set Overfitting** — "False Strategy Theorem", DSR
- **5-bob: Financial Labels** — triple-barrier (bizda bor)
- **6-bob: Feature Importance** — p-value o'rniga ML usullari

**Bizga yangi narsa:** AFML'da o'qiganimizdan tashqari ko'p emas.
"False Strategy Theorem" (B ilova) — DSR ning matematik asosi.

**Qaror:** AFML'ni o'qiganimiz yetarli. Bu qo'shimcha manba.

---

## 3. Causal Factor Investing — López de Prado (92 bet) ⭐⭐

**Asosiy tezis:** faktor investitsiya adabiyotidagi deyarli barcha maqolalar
**assotsiativ** (korrelyatsion) da'volar qiladi, lekin ularni **sababiy**
(kauzal) kabi talqin qiladi.

**Mundarija:** Association vs Causation → Causal Inference → Monte Carlo

**Bizga tegishliligi:** biz "CRT darajasi supurilsa narx qaytadi" deymiz.
Bu **sababiy da'vo**. Lekin bizda faqat **korrelyatsion dalil** bor
(ba'zan shunday bo'ladi). Kitob shuni ajratishni o'rgatadi.

⚠️ **Lekin:** bu kitob asosan **faktor investitsiya** (aksiya portfellari,
Fama-French faktorlari) haqida. Bizning intraday sweep modelimizga
metodologiya darajasida tegishli, amaliy retsept darajasida emas.

**Qaror:** falsafiy foydali, amaliy kod bermaydi. O'rta prioritet.

---

## 4. Systematic Trading — Carver (256 bet) ⭐⭐

**Diqqat:** bu **Bookey xulosasi**, Carver'ning asl kitobi emas
(birinchi sahifada "Written by Bookey" yozilgan).

Asl kitobning asosiy g'oyalari (xulosadan):
- Sodda, mustahkam tizimlar murakkabdan yaxshi
- Pozitsiya hajmi volatillikка moslashtiriladi (volatility targeting)
- Overfitting'dan qochish: parametrlarni "yaxshi" emas, "mustahkam" tanlash
- Diversifikatsiya — ko'p instrument, ko'p strategiya

**Bizga eng foydali g'oya: volatility targeting.** Hozir bizda qat'iy 1% risk,
lekin R hajmi (kirish−stop masofasi) har savdoda har xil. Carver usuli:
pozitsiya hajmini shunday tanlash-ki, **har savdoning kutilgan pul-riski
bir xil** bo'lsin.

⚠️ Aslida bizda bu qisman bor (risk = balansning 1%, R ga bog'lanmagan).

**Advanced Futures Trading Strategies (.enw)** — bu faqat **iqtibos fayli**
(bibliografiya yozuvi), kitobning o'zi emas.

---

## 5-9. Umumiy ML darsliklari ⭐

| Manba | Hajm | Holat |
|---|---|---|
| Hands-on ML (Géron) | 510 bet | To'liq kitob |
| The Hundred-Page ML (Burkov) | 135 bet | To'liq |
| The Hundred-Page ML (2-nusxa) | 152 bet | **Takror** — bir xil kitob |
| AI Engineering (Huyen) | 21 bet | Faqat maqtovlar/so'zboshi |
| Проектирование систем МО (Huyen) | 370 bet | To'liq (ruscha) |

### Bizga hozir kerakmi?

**Yo'q.** Sabab oddiy: **bizda ML yo'q va hozircha bo'lishi ham kerak emas.**

Biz AFML tahlilida aniqladik: samarali namunamiz **61 ta savdo**.
Har qanday ML modeli bu hajmda **shovqinni yodlaydi**, qonuniyat topmaydi.

### Qachon kerak bo'ladi?

Agar meta-labeling (C3) qilsak — o'shanda:
- **Géron 2-3-bob** (end-to-end loyiha, model baholash) — amaliy
- **Géron 7-bob** (Random Forest, ensemble) — meta-model uchun
- **Huyen "Проектирование"** — ishlab chiqarishda monitoring, ma'lumot
  siljishi (data drift) — bizning "model eskirdimi?" savoliga
- **Burkov** — tez ma'lumotnoma

**Bitta amaliy eslatma:** Burkov kitobining **ikki nusxasi** bor
(`the-hundred-page...` va `2019Burkov...`) — bir xil kitob, birini
o'chirsa bo'ladi.

---

## 10. XULOSA: nima qilamiz?

### Darhol qo'shsa bo'ladigan 3 narsa (Aronson'dan)

**1. BENCHMARK — tasodifiy signal** ⭐⭐⭐
Hozir "−0.13R yomon" deymiz, lekin nimaga nisbatan? Tasodifiy
kirish/chiqish bilan bir xil sonda savdo ochib, natijasini o'lchash kerak.
Agar tasodifiy ham −0.13R bersa — bizning model **hech narsa qo'shmayapti**.
Agar tasodifiy −0.5R bersa — bizda **edge bor**, lekin kichik.

Mehnat: yarim kun. Qiymat: juda yuqori (mavjud ma'lumot bilan ishlaydi).

**2. Look-ahead tekshiruvi — CISD close'da kirish** ⭐⭐⭐
Biz signal hosil qilgan shamning **close** narxida kiramiz. Aronson
buni **look-ahead bias** deb ataydi. Real savdoda o'sha close'da kirib
bo'lmaydi — keyingi shamda kirish kerak.

Tekshirish: backtest'ni "keyingi sham ochilishida kirish" bilan qayta
yurgizish. Agar natija sezilarli yomonlashsa — bizning barcha
o'lchovlarimiz optimistik edi.

Mehnat: 1 kun. Qiymat: **kritik** (butun natijaga ta'sir qilishi mumkin).

**3. Detrending — XAUUSD uchun** ⭐⭐
Oltin kuchli trendda. Long-biasli natijalarimiz shu trenddan foyda
ko'rgan bo'lishi mumkin.

Mehnat: yarim kun. Qiymat: o'rta.

### Hozircha kerak emas

- ML darsliklari (namuna yetarli emas)
- Causal Factor Investing (falsafiy, amaliy retsept yo'q)
- ML for Asset Managers (AFML bilan takrorlanadi)
- Carver xulosasi (asl kitob emas)

---

## 11. ENG MUHIM GAP

Aronson 6 402 qoidani sinab **birortasida ham** ustunlik topmadi.
Bu bizning natijalarimiz (−0.13R, ishonch oralig'i nolni o'z ichiga oladi)
**g'ayrioddiy emas** — aksincha, **kutilgan** natija ekanini ko'rsatadi.

Bu tushkunlikka tushish uchun sabab emas. Bu shuni bildiradi:
**ustunlik topish uchun oddiy qoida sinashdan ko'ra ko'proq narsa kerak** —
va birinchi navbatda **halol o'lchov**. Biz aynan shuni quryapmiz.
