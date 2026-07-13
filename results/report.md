# CRT natijalar hisoboti

Rejim: hammasi

---

## Manba: MT5 — FORWARD (5 yakunlangan qator)

### Variant taqqoslash (faqat qabul qilinganlar)

|  | savdo | win% | o'rt R | CI95 | sof R | PF | maxDD(R) | mag'l.seriya | ishonch |
|---|---|---|---|---|---|---|---|---|---|
| m1_ote | 1 | +0.00 | -1.00 | - | -1.00 | +0.00 | -1.00 | 1 | ⚠ n<30 — xulosa erta |
| m5_cisd | 1 | +100.00 | +1.59 | - | +1.59 | inf | +0.00 | 0 | ⚠ n<30 — xulosa erta |
| m5_managed | 1 | +100.00 | +0.16 | - | +0.16 | inf | +0.00 | 0 | ⚠ n<30 — xulosa erta |
| m5_ote | 1 | +0.00 | -1.00 | - | -1.00 | +0.00 | -1.00 | 1 | ⚠ n<30 — xulosa erta |
| m5_sb | 1 | +0.00 | -1.00 | - | -1.00 | +0.00 | -1.00 | 1 | ⚠ n<30 — xulosa erta |

### Kesim: Instrument

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| GBPUSD | 5 | -0.25 | -1.25 | ⚠ kam |

### Kesim: Sessiya (QT chorak)

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| NY_AM | 5 | -0.25 | -1.25 | ⚠ kam |

### Kesim: Hafta kuni

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| Monday | 5 | -0.25 | -1.25 | ⚠ kam |

### Kesim: Daraja turi

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| NDOG | 5 | -0.25 | -1.25 | ⚠ kam |

### Ablation: filtrlar rad etganlarning taqdiri

|  | faqat_shu_yiqitgan | o'rt_R(shadow) | jami_fail |
|---|---|---|---|
| pd | 0 | - | 9 |
| qt | 0 | - | 0 |
| mo_bias | +1.00 | +1.55 | +8.00 |
| hrl | +1.00 | -1.00 | +13.00 |

_hech bir filtr uchun 'zarar' belgisi yo'q (yoki namuna kichik)_

---

## Manba: MT5 — BACKTEST (463 yakunlangan qator)

### Variant taqqoslash (faqat qabul qilinganlar)

|  | savdo | win% | o'rt R | CI95 | sof R | PF | maxDD(R) | mag'l.seriya | ishonch |
|---|---|---|---|---|---|---|---|---|---|
| m1_ote | 6 | +50.00 | -0.25 | [-1.38,+0.89] | -1.49 | +0.70 | -4.90 | 3 | ⚠ n<30 — xulosa erta |
| m5_cisd | 14 | +35.71 | -0.22 | [-0.84,+0.54] | -3.12 | +0.69 | -6.60 | 6 | ⚠ n<30 — xulosa erta |
| m5_managed | 14 | +28.57 | -0.30 | [-0.89,+0.43] | -4.17 | +0.59 | -6.60 | 6 | ⚠ n<30 — xulosa erta |
| m5_ote | 8 | +12.50 | -0.88 | [-1.32,-0.14] | -7.05 | +0.19 | -7.60 | 6 | ⚠ n<30 — xulosa erta |
| m5_sb | 2 | +50.00 | -0.51 | [-1.06,+0.03] | -1.02 | +0.03 | -1.10 | 1 | ⚠ n<30 — xulosa erta |

### Kesim: Instrument

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| EURUSD | 44 | -0.38 | -16.85 | OK |

### Kesim: Sessiya (QT chorak)

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| London | 20 | -0.10 | -1.96 | ⚠ kam |
| NY_AM | 24 | -0.62 | -14.89 | ⚠ kam |

### Kesim: Hafta kuni

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| Friday | 19 | -0.67 | -12.69 | ⚠ kam |
| Thursday | 13 | -0.52 | -6.74 | ⚠ kam |
| Tuesday | 6 | -0.47 | -2.81 | ⚠ kam |
| Wednesday | 6 | +0.90 | +5.39 | ⚠ kam |

### Kesim: Daraja turi

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| CRT | 2 | +0.48 | +0.97 | ⚠ kam |
| NDOG | 38 | -0.37 | -14.04 | OK |
| NWOG | 4 | -0.95 | -3.78 | ⚠ kam |

### Ablation: filtrlar rad etganlarning taqdiri

|  | faqat_shu_yiqitgan | o'rt_R(shadow) | jami_fail |
|---|---|---|---|
| pd | +26.00 | -0.03 | +183.00 |
| qt | 0 | - | 0 |
| mo_bias | +33.00 | -0.20 | +332.00 |
| hrl | +33.00 | +0.05 | +342.00 |

_hech bir filtr uchun 'zarar' belgisi yo'q (yoki namuna kichik)_

---

## Manba: YAHOO — FORWARD (40 yakunlangan qator)

### Variant taqqoslash (faqat qabul qilinganlar)

|  | savdo | win% | o'rt R | CI95 | sof R | PF | maxDD(R) | mag'l.seriya | ishonch |
|---|---|---|---|---|---|---|---|---|---|
| m5_cisd | 15 | +6.67 | -0.80 | [-1.00,-0.40] | -11.98 | +0.14 | -12.00 | 8 | ⚠ n<30 — xulosa erta |
| m5_managed | 15 | +26.67 | -0.53 | [-0.86,-0.14] | -7.96 | +0.20 | -8.00 | 3 | ⚠ n<30 — xulosa erta |
| m5_ote | 10 | +0.00 | -1.00 | [-1.00,-1.00] | -10.00 | +0.00 | -10.00 | 10 | ⚠ n<30 — xulosa erta |

### Kesim: Instrument

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| GBPUSD | 4 | +0.59 | +2.37 | ⚠ kam |
| US500 | 15 | -0.90 | -13.45 | ⚠ kam |
| USDCAD | 15 | -0.86 | -12.85 | ⚠ kam |
| XAUUSD | 6 | -1.00 | -6.00 | ⚠ kam |

### Kesim: Sessiya (QT chorak)

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| London | 6 | -0.65 | -3.92 | ⚠ kam |
| NY_AM | 28 | -0.71 | -20.02 | ⚠ kam |
| NY_PM | 6 | -1.00 | -6.00 | ⚠ kam |

### Kesim: Hafta kuni

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| Friday | 40 | -0.75 | -29.94 | OK |

### Kesim: Daraja turi

|  | savdo | ort_R | sof_R | ishonch |
|---|---|---|---|---|
| CRT | 32 | -0.72 | -22.94 | OK |
| PD | 8 | -0.88 | -7.00 | ⚠ kam |

### Ablation: filtrlar rad etganlarning taqdiri

|  | faqat_shu_yiqitgan | o'rt_R(shadow) | jami_fail |
|---|---|---|---|
| pd | 0 | - | 9 |
| qt | 0 | - | 0 |
| mo_bias | +1.00 | +1.55 | +8.00 |
| hrl | +1.00 | -1.00 | +13.00 |

_hech bir filtr uchun 'zarar' belgisi yo'q (yoki namuna kichik)_
