# CRT natijalar hisoboti

Rejim: faqat backtest, manba: mt5

---

## Manba: MT5 — BACKTEST (2639 yakunlangan qator)

### Variant taqqoslash (faqat qabul qilinganlar)

|  | savdo | win% | o'rt R | CI95 | sof R | PF | maxDD(R) | mag'l.seriya | ishonch |
|---|---|---|---|---|---|---|---|---|---|
| m1_ote | 58 | +20.69 | -0.83 | [-1.13,-0.52] | -48.33 | +0.21 | -50.20 | 9 | OK |
| m5_cisd | 108 | +39.81 | -0.13 | [-0.34,+0.09] | -13.67 | +0.78 | -20.60 | 5 | OK |
| m5_managed | 108 | +40.74 | -0.14 | [-0.36,+0.06] | -15.44 | +0.74 | -22.60 | 5 | OK |
| m5_ote | 72 | +27.78 | -0.54 | [-0.78,-0.26] | -39.00 | +0.36 | -40.70 | 9 | OK |
| m5_sb | 21 | +33.33 | -0.43 | [-0.82,-0.02] | -9.12 | +0.34 | -12.90 | 7 | ⚠ n<30 — xulosa erta |

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
