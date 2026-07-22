# CRT natijalar hisoboti

Rejim: hammasi

---

## Manba: MT5 — FORWARD (11 yakunlangan qator)

### Variant taqqoslash (faqat qabul qilinganlar)

|  | savdo | samarali n | win% | o'rt R | CI95 | sof R | PF | maxDD(R) | mag'l.seriya | ishonch |
|---|---|---|---|---|---|---|---|---|---|---|
| m1_ote | 1 | +1.00 | +0.00 | -1.00 | - | -1.00 | +0.00 | -1.00 | 1 | ⚠ samarali n<30 — xulosa erta |
| m5_cisd | 4 | +4.00 | +25.00 | -0.35 | [-1.00,+0.94] | -1.41 | +0.53 | -3.00 | 3 | ⚠ samarali n<30 — xulosa erta |
| m5_managed | 4 | +4.00 | +25.00 | -0.71 | [-1.00,-0.13] | -2.84 | +0.05 | -3.00 | 3 | ⚠ samarali n<30 — xulosa erta |
| m5_ote | 1 | +1.00 | +0.00 | -1.00 | - | -1.00 | +0.00 | -1.00 | 1 | ⚠ samarali n<30 — xulosa erta |
| m5_sb | 1 | +1.00 | +0.00 | -1.00 | - | -1.00 | +0.00 | -1.00 | 1 | ⚠ samarali n<30 — xulosa erta |

### Kesim: Instrument

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| EURUSD | 4 | -1.00 | -4.00 | ⚠ kam |
| GBPUSD | 7 | -0.46 | -3.25 | ⚠ kam |

### Kesim: Sessiya (QT chorak)

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| London | 2 | -1.00 | -2.00 | ⚠ kam |
| NY_AM | 9 | -0.58 | -5.25 | ⚠ kam |

### Kesim: Hafta kuni

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| Monday | 5 | -0.25 | -1.25 | ⚠ kam |
| Wednesday | 6 | -1.00 | -6.00 | ⚠ kam |

### Kesim: Daraja turi

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| CRT | 6 | -1.00 | -6.00 | ⚠ kam |
| NDOG | 5 | -0.25 | -1.25 | ⚠ kam |

### Ablation: filtrlar rad etganlarning taqdiri

|  | faqat_shu_yiqitgan | o'rt_R(shadow) | jami_fail |
|---|---|---|---|
| pd | +1.00 | +1.79 | +32.00 |
| qt | 0 | - | 0 |
| mo_bias | +2.00 | +1.61 | +47.00 |
| hrl | +5.00 | -0.60 | +63.00 |

_hech bir filtr uchun 'zarar' belgisi yo'q (yoki namuna kichik)_

### Kalibratsiya: baholarimiz ishlayaptimi?


**To'liqlik balli**
|  | savdo | ort_R |
|---|---|---|
| 50-70 | +10.00 | -1.00 |

**Tarixiy analog win%**
|  | savdo | ort_R |
|---|---|---|
| <30% | +2.00 | -1.00 |
| 30-45% | +8.00 | -1.00 |

✅ Monoton: yuqori tarixiy analog win% = yaxshiroq natija

### LLM balli guruhlar bo'yicha natija (baho foydalimi?)

|  | savdo | ort_R |
|---|---|---|
| 8-10 | +6.00 | -1.00 |

---

## Manba: MT5 — BACKTEST (2639 yakunlangan qator)

### Variant taqqoslash (faqat qabul qilinganlar)

|  | savdo | samarali n | win% | o'rt R | CI95 | sof R | PF | maxDD(R) | mag'l.seriya | ishonch |
|---|---|---|---|---|---|---|---|---|---|---|
| m1_ote | 58 | +35.00 | +20.69 | -0.83 | [-1.21,-0.43] | -48.33 | +0.21 | -50.20 | 9 | OK |
| m5_cisd | 108 | +61.70 | +39.81 | -0.13 | [-0.41,+0.16] | -13.67 | +0.78 | -20.60 | 5 | OK |
| m5_managed | 108 | +61.70 | +40.74 | -0.14 | [-0.43,+0.13] | -15.44 | +0.74 | -22.60 | 5 | OK |
| m5_ote | 72 | +46.00 | +27.78 | -0.54 | [-0.84,-0.19] | -39.00 | +0.36 | -40.70 | 9 | OK |
| m5_sb | 21 | +18.00 | +33.33 | -0.43 | [-0.85,+0.01] | -9.12 | +0.34 | -12.90 | 7 | ⚠ samarali n<30 — xulosa erta |

### Kesim: Instrument

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| EURUSD | 44 | -0.38 | -16.85 | OK |
| GBPUSD | 57 | +0.19 | +10.77 | OK |
| US500 | 78 | -0.52 | -40.36 | OK |
| USDCAD | 54 | -0.55 | -29.82 | OK |
| USTEC | 89 | -0.36 | -32.12 | OK |
| XAUUSD | 45 | -0.38 | -17.18 | OK |

### Kesim: Sessiya (QT chorak)

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| London | 96 | -0.15 | -14.36 | OK |
| NY_AM | 259 | -0.43 | -112.36 | OK |
| NY_PM | 12 | +0.10 | +1.15 | ⚠ kam |

### Kesim: Hafta kuni

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| Friday | 84 | -0.62 | -52.00 | OK |
| Monday | 34 | -0.23 | -7.66 | OK |
| Thursday | 72 | -0.44 | -31.54 | OK |
| Tuesday | 48 | +0.06 | +2.68 | OK |
| Wednesday | 129 | -0.29 | -37.04 | OK |

### Kesim: Daraja turi

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| CRT | 62 | -0.13 | -8.05 | OK |
| NDOG | 268 | -0.40 | -106.37 | OK |
| NWOG | 37 | -0.30 | -11.15 | OK |

### Ablation: filtrlar rad etganlarning taqdiri

|  | faqat_shu_yiqitgan | o'rt_R(shadow) | jami_fail |
|---|---|---|---|
| pd | +95.00 | +0.24 | +977.00 |
| qt | 0 | - | 0 |
| mo_bias | +131.00 | -0.14 | +1805.00 |
| hrl | +218.00 | -0.15 | +1930.00 |

⚠ **pd** filtri yiqitganlarning o'rtacha shadow natijasi +0.24R (n=95) — bu filtr foyda emas, ZARAR keltirayotgan bo'lishi mumkin!

### Kalibratsiya: baholarimiz ishlayaptimi?

_signal jurnali bilan moslik topilmadi (backtest yozuvlarida signals_log bo'lmaydi — bu normal)_

---

## Manba: YAHOO — FORWARD (42 yakunlangan qator)

### Variant taqqoslash (faqat qabul qilinganlar)

|  | savdo | samarali n | win% | o'rt R | CI95 | sof R | PF | maxDD(R) | mag'l.seriya | ishonch |
|---|---|---|---|---|---|---|---|---|---|---|
| m5_cisd | 16 | +5.20 | +6.25 | -0.81 | [-1.14,-0.15] | -12.98 | +0.13 | -13.00 | 8 | ⚠ samarali n<30 — xulosa erta |
| m5_managed | 16 | +5.60 | +31.25 | -0.49 | [-1.02,+0.13] | -7.91 | +0.21 | -8.00 | 3 | ⚠ samarali n<30 — xulosa erta |
| m5_ote | 10 | +2.50 | +0.00 | -1.00 | [-1.00,-1.00] | -10.00 | +0.00 | -10.00 | 10 | ⚠ samarali n<30 — xulosa erta |

### Kesim: Instrument

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| GBPUSD | 4 | +0.59 | +2.37 | ⚠ kam |
| US500 | 15 | -0.90 | -13.45 | ⚠ kam |
| USDCAD | 17 | -0.81 | -13.80 | ⚠ kam |
| XAUUSD | 6 | -1.00 | -6.00 | ⚠ kam |

### Kesim: Sessiya (QT chorak)

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| London | 8 | -0.61 | -4.87 | ⚠ kam |
| NY_AM | 28 | -0.71 | -20.02 | ⚠ kam |
| NY_PM | 6 | -1.00 | -6.00 | ⚠ kam |

### Kesim: Hafta kuni

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| Friday | 40 | -0.75 | -29.94 | OK |
| Monday | 2 | -0.48 | -0.95 | ⚠ kam |

### Kesim: Daraja turi

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| CRT | 34 | -0.70 | -23.89 | OK |
| PD | 8 | -0.88 | -7.00 | ⚠ kam |

### Ablation: filtrlar rad etganlarning taqdiri

|  | faqat_shu_yiqitgan | o'rt_R(shadow) | jami_fail |
|---|---|---|---|
| pd | +1.00 | +1.79 | +32.00 |
| qt | 0 | - | 0 |
| mo_bias | +2.00 | +1.61 | +47.00 |
| hrl | +5.00 | -0.60 | +63.00 |

_hech bir filtr uchun 'zarar' belgisi yo'q (yoki namuna kichik)_

### Kalibratsiya: baholarimiz ishlayaptimi?

_signal jurnali bilan moslik topilmadi (backtest yozuvlarida signals_log bo'lmaydi — bu normal)_
