# CRT Skaner — o'zim ishga tushirish qo'llanmasi

> Bu fayl treyder uchun. Hech qanday dasturlash bilim talab qilinmaydi —
> faqat ketma-ketlikni bajarish kifoya.

---

## 1. Har safar ishga tushirish (asosiy yo'l)

### 1-qadam: MT5 terminalni oching
- Ish stolidagi **MetaTrader 5** yorlig'ini bosing
- **Kuting** — pastki o'ng burchakda internet belgisi ko'k/yashil bo'lsin
  (narx raqamlari jonli o'zgara boshlashi kerak)
- ⚠️ MT5 ulanmagan bo'lsa skaner "Server offset aql bovar qilmas qiymat"
  degan xato beradi — 30 soniya kutib qayta urinib ko'ring

### 2-qadam: Skanerni yoqing
Ikki usuldan biri:

**A) Sichqoncha bilan (osonroq):**
1. `D:\Tap\crt_scanner` papkasini oching
2. `run_local.ps1` faylига **o'ng tugma** → **Run with PowerShell**

**B) Terminal orqali:**
1. `Win + X` → **Terminal** (yoki PowerShell)
2. Quyidagini yozing:
```powershell
cd D:\Tap\crt_scanner
.\run_local.ps1
```

### 3-qadam: Ishlayotganini tekshiring
Ekranda shunday chiqishi kerak:
```
CRT Scanner — LOKAL rejim
  Narx manbai   : MT5 terminal (ochiq bo'lsin!)
  Grafik        : TradingView screenshot
[INFO] MT5'ga muvaffaqiyatli ulanildi.
[INFO] Skanerlash boshlandi (NY vaqti: ...)
[INFO] EURUSD: 0 signal, 0 qabul (0 rad)
[INFO] Keyingi tekshiruv 2 daqiqadan so'ng...
```
✅ **"Keyingi tekshiruv 2 daqiqadan so'ng"** ko'rinsa — hammasi joyida.

### 4-qadam: Oynani YOPMANG
Skaner shu oyna ochiq turganда ishlaydi. Oynani kichraytirish mumkin,
lekin yopish yoki `Ctrl+C` bosish skanerni to'xtatadi.

---

## 2. O'chirish

- Skaner oynasida **`Ctrl + C`** bosing
- Yoki oynani yoping

Kompyuterni o'chirishdan oldin shuni qiling (majburiy emas, lekin toza).

---

## 3. Telegram bot (savol-javob uchun, ixtiyoriy)

Skanerdan **alohida** oyna kerak:
```powershell
cd D:\Tap\crt_scanner
.\run_local_bot.ps1
```

Bot yoqilgach Telegram'da yozishingiz mumkin:
| Buyruq | Nima qiladi |
|---|---|
| `/holat EURUSD` | Jonli tahlil + grafik |
| `/zanjir EURUSD` | Setup zanjiri (✓/✗ bo'g'inlar) |
| `/hisob` | Xayoliy balanslar |
| `/help` | Buyruqlar ro'yxati |
| istalgan savol | CRT/ICT bo'yicha javob |

⚠️ Bot yoqilmasa Telegram'ga savol yozsangiz javob kelmaydi — lekin
**signallar baribir keladi** (ular skanerdan chiqadi, botdan emas).

---

## 4. Natijalarni ko'rish

Skanerni to'xtatib (yoki yangi oynada):
```powershell
cd D:\Tap\crt_scanner
python analyze_results.py
```
Natija: ekranda jadval + `results\report.md` fayli.

Boshqa variantlar:
```powershell
python analyze_results.py --source mt5        # faqat lokal natijalar
python analyze_results.py --forward-only      # faqat jonli savdolar
```

---

## 5. Tez-tez uchraydigan holatlar

| Muammo | Yechim |
|---|---|
| `Server offset aql bovar qilmas qiymat: -13h` | MT5 hali serverga ulanmagan. 30 soniya kutib qayta yoqing |
| `Symbol topilmadi: EURUSD` | MT5 qayta ishga tushirilgan — skanerni ham qayta yoqing |
| `MT5 initialize xato` | MT5 terminal umuman ochiq emas |
| Signal kelmayapti | Normal — kuniga 0-3 ta signal. Log'da "0 signal" chiqsa tizim ishlayapti |
| Skaner oynasi yopilib qoldi | Qaytadan `run_local.ps1` |

---

## 6. Muhim eslatmalar

- **Kompyuter o'chsa** — skaner ham o'chadi. Signallar kelmaydi.
- **MT5 yopilsa** — skaner xato beradi, qayta yoqish kerak.
- **Internet uzilsa** — skaner xatolikni log'ga yozadi, internet qaytgach
  o'zi davom etadi.
- Signal kelganда Telegram'ga: **chizilgan grafik + reja + to'liqlik balli
  + tarixiy analog + LLM tanqidi** keladi.
- Rad etilgan signal uchun bitta qatorli ⚪ xabar keladi (tizim tirikligi belgisi).

---

## 7. Sozlamalarni o'zgartirish (ixtiyoriy)

`.env` faylini Notepad'да ochib, qator qo'shing:

```
SCAN_INTERVAL_MINUTES=1          # tez-tez tekshirish (default 2)
NOTIFY_REJECTED_ENABLED=0        # rad etilgan signal xabarlarini o'chirish
HRL_FILTER_ENABLED=1             # HRL filtrini qaytarish
MIDNIGHT_BIAS_TOLERANCE_FRAC=0.20 # Midnight filtrini yanada yumshatish
```

O'zgarishdan keyin skanerni qayta yoqish kerak.

---

## 8. Bulut rejimi (kompyutersiz 24/7)

Hozir **o'chirilgan**. Yoqish uchun terminal'да:
```powershell
cd D:\Tap\crt_scanner
gh workflow enable scan.yml
gh workflow enable bot.yml
gh workflow run scan.yml
gh workflow run bot.yml
```
Bulut Yahoo narxidan foydalanadi (MT5 emas) — natijalari alohida saqlanadi.
O'chirish: `gh workflow disable scan.yml` va `gh workflow disable bot.yml`
