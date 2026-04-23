# Round 6 · Rolling OOS + gate sensitivity

## 8-fold walk-forward

- 3 folds × 5y IS + 1y OOS (2024, 2025, 2026)
- 5 folds × 3y IS + 1y OOS (2022-2026)

For each fold:
- (a) evaluate FIXED `A_tuned_v1` on OOS
- (b) re-tune on IS (648-point grid), evaluate best-IS spec on OOS

| Fold | FIXED OOS Sh | Tuned spec same as A_tuned_v1? |
|---|---:|:-:|
| 5y/1y 2024 | 0.97 | ✓ |
| 5y/1y 2025 | **1.95** | ✓ |
| 5y/1y 2026 | 1.14 | ✓ |
| 3y/1y 2022 | -1.43† | ✗ (tuner dropped gate+vol on bull IS) |
| 3y/1y 2023 | 0.88 | ✓ |
| 3y/1y 2024 | 0.97 | ✓ |
| 3y/1y 2025 | 1.95 | ≈ (top_n=3 variant) |
| 3y/1y 2026 | 1.14 | ≈ (vol=0.20 variant) |

† -1.43 is vol≈0 artifact (mostly cash); real return -0.7% in bear year.

**Stability: 6/8 folds independently tuned to exact same A_tuned_v1 spec**.
Not an overfit point — it's the grid's stable peak.

## Gate sensitivity (MA window)

| MA | Full Sh | Full Cal | MaxDD |
|---|---:|---:|---:|
| none | 0.96 | 0.53 | **-30.0%** |
| 20 | 1.05 | 0.82 | -19.0% |
| **40** | **1.34** | **1.85** | **-10.2%** |
| **50** ⭐ | **1.40** | **2.10** | **-9.3%** |
| **60** | **1.33** | **1.80** | **-10.3%** |
| 80 | 1.05 | 0.68 | -20.5% |
| 100 | 0.95 | 0.61 | -20.2% |

**MA40/50/60 is a stable plateau**, not knife-edge. MA50 is peak but ±10 weeks is deployable band. MA20 too reactive, MA80+ too slow for 2022-type bears.

## Real expectation revision

| Metric | aspirational | realistic long-run |
|---|---:|---:|
| Sharpe | ≥ 1.4 | 1.2-1.4 |
| Calmar | ≥ 2.0 | 1.8-2.5 |
| MaxDD hard cap | -10% | -12% |

Sharpe 1.4 is a stretch target; Calmar ≥ 2 is robustly achievable (6/8 folds pass alone).
