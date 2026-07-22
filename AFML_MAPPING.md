# AFML → CRT Scanner: usullar xaritasi

**Manba:** Marcos López de Prado, *Advances in Financial Machine Learning* (Wiley, 2018)
**Sana:** 2026-07-22
**Maqsad:** kitobning qaysi usuli bizning qaysi kodga tegishli, nima to'g'ri
qilingan, nima xato, nima qo'shilishi kerak.

> Eslatma: bu hujjat kitobni qayta chop etmaydi — faqat usullarni bizning
> kodga bog'laydi va sahifa raqamlarini ko'rsatadi.

---

## 1. Triple-Barrier Method (3.4-bo'lim, 45-49 bet) — ✅ BIZDA BOR

**Kitob usuli:** har savdo uchta to'siq bilan yopiladi:
- yuqori to'siq (foyda maqsadi)
- pastki to'siq (stop-loss)
- **vertikal to'siq** (maksimal ushlab turish muddati)

**Bizning kod:** `outcome_tracker._walk_cisd()` va `_walk_managed()`
- yuqori: `targets["liquidity"]` (100%) va `targets["50"]`
- pastki: `tr["sl"]`
- vertikal: `_expiry_for()` → 17:00 NY

**Baho:** to'g'ri qurilgan. Bitta farq — kitob to'siqlarni volatillikка
(`trgt` = kunlik std) moslashtiradi, bizda esa strukturaviy darajalar
(CRT 50%/100%). Bizning yondashuv model falsafasiga mos, lekin natijada
RR har savdoda har xil (1.0–2.0R) — kitob usulida u barqarorroq bo'lardi.

**Tekshirish uchun savol:** RR ning o'zgaruvchanligi statistikani buzayaptimi?

---

## 2. Meta-labeling (3.6-3.7, 50-54 bet) — ❌ YO'Q (taklif C3)

**Kitob usuli:** ikki bosqichli arxitektura
1. **Primary model** — garov TOMONINI beradi (long/short)
2. **Secondary (meta) model** — faqat "olish yoki o'tkazib yuborish"
   qarorini beradi, ehtimollik bilan. Tomonni O'RGANMAYDI.

Label: `bin ∈ {0,1}` (oddiy labellashda `{-1,0,1}` bo'lardi).

**Bizga moslashtirish:**
| Kitob | Bizda |
|---|---|
| Primary model | CRT/ICT qoidalari (`signals.detect_sweep` + `detect_cisd`) |
| Side | `sig.direction` (bullish/bearish) |
| Meta-model kirishi | `confluence_score` komponentlari, `wick_pct`, QT faza, rejim, LLM balli |
| Meta-label | savdo foydali tugadimi (net_r > 0) → 1, aks holda 0 |
| Chiqish | P(foyda) → pozitsiya hajmi yoki "o'tkazib yuborish" |

**Kitobning muhim gapi (3.7):** meta-labeling'da overfitting ta'siri
**cheklangan**, chunki ML tomonni emas, faqat hajmni hal qiladi.
Bu mening avvalgi "C3 juda xavfli" bahomni yumshatadi.

**Yana bir muhim tuzatish:** kitob "avval yuqori **recall** (ko'p signal),
keyin meta-model bilan **precision**" deydi. Biz teskarisini qildik —
4 ta qattiq filtr recall'ni o'ldirdi (62 signaldan 0 qabul).

**Xulosa:** arxitektura to'g'ri, lekin namuna hajmi (hozir ~19 qabul
qilingan savdo) yetarli emas. Kamida 200-300 kerak.

---

## 3. Sample Uniqueness / Concurrent Labels (4-bob, 59-72 bet) — 🔴 BIZDA KAMCHILIK

**Bu eng muhim yangi topilma.**

**Muammo (kitob 4.2-4.3):** moliyaviy labellar vaqt bo'yicha **ustma-ust
tushadi**. Agar savdo A 10:00-14:00 oralig'ida, savdo B 11:00-15:00
oralig'ida bo'lsa — ular umumiy narx harakatidan hosil bo'ladi va
**mustaqil emas**. Kitobning taqqoslashi: 10 bemorning qonini bir-biriga
aralashtirib, keyin har birining xolesterinini aniqlashga urinish.

**Bizdagi holat — TASDIQLANDI:**
- Bir vaqtda 5 variant (m5_cisd, m5_managed, m5_ote, m5_sb, m1_ote)
  **bir xil signaldan** ochiladi → deyarli to'liq korrelyatsiya
- Turli signallar ham ustma-ust tushadi (bir kunda bir necha daraja
  supurilishi mumkin, savdolar 17:00 gacha ochiq turadi)

**Oqibati:**
1. `analyze_results.py` dagi **bootstrap ishonch oralig'i juda tor** —
   u kuzatuvlar mustaqil deb hisoblaydi
2. "108 savdo" aslida statistik jihatdan **ancha kam** mustaqil kuzatuv
3. Ya'ni bizning xulosalarimiz ko'ringanidan **kamroq ishonchli**

**Kitob yechimi (4.4-4.5):**
- `getNumCoEvents()` — har momentда nechta savdo bir vaqtda ochiq
- `getAvgUniqueness()` — har savdoning o'rtacha "yolg'izligi" (0-1)
- Sample weight = shu yolg'izlik → statistikada og'irlik sifatida
- `getIndMatrix` + sequential bootstrap

**Bizga kerak bo'lgan minimal qadam:**
`analyze_results.py` ga o'rtacha uniqueness hisoblash va **samarali
namuna hajmini** (effective sample size) ko'rsatish. Bu C4 dan ham
oldin turishi mumkin — chunki u mavjud barcha xulosalarimizga ta'sir
qiladi.

**AUDIT.md ga qo'shilishi kerak:** bu bizning 7.1 bo'limidagi
metodologik xavflar ro'yxatida YO'Q edi.

---

## 4. Purged K-Fold CV + Embargo (7-bob, 103-110 bet) — ❌ YO'Q (B3 o'rniga)

**Muammo:** oddiy k-fold CV moliyaviy ma'lumotda ishlamaydi, chunki
ustma-ust tushgan labellar o'quv va test to'plamiga ikkalasiga tushadi
→ ma'lumot sizib chiqadi (leakage) → yolg'on natija.

**Kitob yechimi:**
1. **Purging** — test to'plamidagi label bilan vaqt bo'yicha ustma-ust
   tushgan barcha o'quv kuzatuvlarini olib tashlash
2. **Embargo** — test to'plamidan keyingi qisqa oraliqni ham chiqarib
   tashlash (serial korrelyatsiya uchun)

**Walk-forward (bizning B3) haqida kitob ogohlantirishi (11.6):**
bitta sinov yo'li bor → uni yolg'on natija chiqquncha qayta-qayta
yurgizish mumkin. Shuning uchun **Combinatorial Purged CV** afzal.

**Bizga:** hozircha ML yo'q, shuning uchun CV kerak emas. **Lekin C3
(meta-labeling) qilinsa — bu MAJBURIY shart.**

---

## 5. Deflated Sharpe Ratio + PBO (11.6, 14.7 — 155-157, 204-205 bet) — ❌ YO'Q (B2)

**Uchinchi qonun (kitobdan, 14.7.3):** har backtest natijasi **uni ishlab
chiqarishda qilingan barcha sinovlar bilan birga** e'lon qilinishi kerak.
Bu ma'lumotsiz "yolg'on kashfiyot" ehtimolini baholab bo'lmaydi.

**DSR formulasi:** kutilgan maksimal SR (null gipoteza ostida) sinovlar
soni `N` va ular orasidagi dispersiya `V[SR]` bilan o'sadi. Ya'ni ko'p
sinov qilsangiz — **nol edge ham yaxshi ko'rinadi**.

**PBO (CSCV usuli, 11.6):** in-sample eng yaxshi tanlangan strategiya
out-of-sample'da qanday ishlaganini o'lchaydi. Kitob misolida PBO = 0.74.

**Bizning holat:** biz **sinovlar sonini umuman yozmaganmiz**. Qancha
konfiguratsiya sinaganimizni bilmaymiz (taxminan: 5 variant × filtr
kombinatsiyalari × BE sozlamalari × daraja turlari ≈ o'nlab). Ya'ni
hozirgi natijalarga DSR tuzatmasini qo'llash **imkonsiz** — ma'lumot yo'q.

**Minimal qadam:** shu paytdan boshlab `results/experiments.csv` yuritish:
`sana, gipoteza, o'zgartirilgan_parametr, natija_R, namuna_n, izoh`.

---

## 6. Bet Sizing (10-bob, 141-148 bet) — ❌ YO'Q

Kitob: bashorat ehtimolidan pozitsiya hajmini hisoblash (`getSignal`,
o'rtachalash, diskretizatsiya).

**Bizga:** hozir qat'iy 1% risk. `confluence_score` bor, lekin hajmga
bog'lanmagan. **Faqat C4 (kalibratsiya) dan keyin ma'noga ega** — kalibrlanmagan
ehtimollikdan hajm hisoblash zarar keltiradi.

---

## 7. Backtest falsafasi (11-bob, 151-158 bet) — 🔴 BIZ BUZGANMIZ

Kitobning asosiy tezisi: backtest — **tadqiqot vositasi emas**. Uning
maqsadi yomon modellarni rad etish, yaxshilash emas. Modelni backtest
natijasiga qarab sozlash = tasodifiy tarixiy naqshlarni pulga aylantirish.

**Biz nima qildik:**
| Qaror | Asos | Kitob bo'yicha |
|---|---|---|
| NDOG o'chirildi | backtest n=78, −0.22R | ⚠️ in-sample tanlov |
| BE o'chirildi | 108 juftlangan savdo | ⚠️ o'sha ma'lumotda tanlov |
| HRL o'chirildi | jonli 62 signal | ⚠️ o'sha ma'lumotda tanlov |
| Midnight yumshatildi | jonli 62 signal | ⚠️ o'sha ma'lumotda tanlov |

Hammasi **bir xil ma'lumotga qarab** qilingan. Bu overfitting'ning
klassik ko'rinishi.

**Yana bir ogohlantirish (11.5, 1-tavsiya):** modelni butun aktiv sinfi
uchun ishlab chiqing, bitta instrument uchun emas. Agar naqsh faqat bitta
qog'ozda topilsa — bu yolg'on kashfiyot.

**Bizga tegishli:** "GBPUSD +10.3R, qolganlari minusda" — aynan shu
tavsif. Uni "GBPUSD ga e'tibor beraylik" deb o'qish **xato bo'lardi**.

---

## 8. Bizga KERAK EMAS

| Bo'lim | Nega |
|---|---|
| Dollar/volume/tick bars (2-bob) | Forex majors uchun hajm ishonchsiz |
| Fractional differentiation (5-bob) | ML xususiyatlari uchun; bizda ML yo'q |
| Ensemble/RF/boosting (6-bob) | C3 dan keyin ko'riladi |
| Feature importance (8-bob) | ML bo'lgach |
| Hierarchical Risk Parity (16-bob) | Portfel; bizda 4 instrument, qat'iy 1% |
| Structural breaks (17-bob) | C1 (rejim) uchun foydali bo'lishi mumkin, keyinroq |
| Microstructural features (19-bob) | Order book kerak — yo'q |
| HPC (20-22-bob) | Bizning hajmda keraksiz |

---

## 9. Yangilangan ustuvorlik (kitob asosida)

| № | Vazifa | Manba | Nega shu tartibda |
|---|---|---|---|
| **0** | **Sample uniqueness o'lchovi** | 4-bob | Barcha mavjud xulosalarimizga ta'sir qiladi — avval buni bilishimiz kerak |
| 1 | C4 — kalibratsiya | 14-bob | Ma'lumot tayyor, 0.5 kun |
| 2 | B2 — experiments.csv + DSR | 11.6, 14.7 | Uchinchi qonun; kelgusi sozlashlarni himoya qiladi |
| 3 | C1 — rejim aniqlash | 17-bob (qisman) | C3 uchun xususiyat sifatida kerak |
| 4 | E4 — risk guardrails | 15-bob | Yarim tayyor, arzon |
| 5 | C3 — meta-labeling | 3.6-3.7 | Arxitektura to'g'ri, lekin namuna kutiladi |
| 6 | Purged CV | 7-bob | C3 bilan birga MAJBURIY |

**Eng katta o'zgarish:** "Sample uniqueness" 0-o'rinda paydo bo'ldi —
u avvalgi ro'yxatda umuman yo'q edi va u bizning **barcha hozirgi
statistikamizning ishonchliligiga** ta'sir qiladi.

---

## 11. O'LCHANDI: bizning ustma-ust tushish darajasi (2026-07-22)

`backtest_results.csv` dagi 367 qabul qilingan savdo bo'yicha haqiqiy o'lchov
(savdo davomiyligi ~8 soat deb olindi — kirish→17:00 NY):

| Ko'rsatkich | Qiymat |
|---|---|
| O'rtacha bir vaqtda ochiq savdolar | **8.5** |
| Maksimal bir vaqtda | 20 |
| Butunlay yolg'iz savdolar | **0 / 367** |
| **Samarali namuna hajmi** | **61** (nominal 367) |
| Kamayish | **83%** |

**Variant bo'yicha** (bir variant ichida, 5 variantning o'zaro korrelyatsiyasisiz):

| Variant | Nominal | Samarali | O'rt. bir vaqtda |
|---|---|---|---|
| m5_cisd | 108 | **62** | 2.4 |
| m5_managed | 108 | **62** | 2.4 |
| m5_ote | 72 | 46 | 2.1 |
| m1_ote | 58 | 35 | 2.2 |
| m5_sb | 21 | 18 | 1.3 |

**Oqibatlari:**

1. `analyze_results.py` bootstrap CI **~2.45 marta tor** ko'rsatyapti
   (butun to'plam uchun). Variant ichida ~1.3 marta.
2. "n<30 — xulosa erta" chegarasi **samarali** namunaga qo'llanishi kerak,
   nominalga emas. m5_sb: nominal 21 → samarali 18 (baribir kam).
3. 5 variant bir signaldan ochilgani uchun ular **deyarli to'liq
   korrelyatsiyalangan** — 367 qatorni bitta to'plam sifatida o'rtachalash
   statistik jihatdan noto'g'ri.

**Xulosa:** bizning xulosalarimiz noto'g'ri emas, lekin **ko'ringanidan
ancha kam ishonchli**. Bu AUDIT.md ga qo'shilishi shart.

---

## 12. Auditorga qo'shimcha savol (AUDIT.md ga qo'shilsin)

> **17.** Bizning kuzatuvlarimiz vaqt bo'yicha ustma-ust tushadi
> (5 variant bir signaldan + savdolar 17:00 gacha ochiq). `analyze_results.py`
> bootstrap ishonch oralig'ini mustaqillik faraziga asoslanib hisoblaydi.
> Samarali namuna hajmi qanchalik kichik va xulosalarimiz qanchalik
> ishonchsiz? (AFML 4-bob: sample uniqueness)
