# Round 7-8 · Fallback asset exploration

When MA50 gate is OFF, what should we hold?

## Round 7: red / ensemble / gold

### Red dividend ETF fallback — **FAILED**

| config | Full Sh | Full Cal | Full DD |
|---|---:|---:|---:|
| V1 BASE (cash) | 1.40 | 2.10 | -9.3% |
| V2 A + 红利 | 1.33 | 1.56 | **-13.4%** (worse) |

**Why**: 红利 ETF is **long-beta style exposure**, not risk-off:
- 2022 自身 -6.3%
- 2024 intra-year DD -8%
- Correlates with A-share market → fallback amplifies DD

### Gold ETF fallback (159934.SZ) — **MAJOR WIN**

| config | Full Sh | Full Cal | Full DD | AnnRet |
|---|---:|---:|---:|---:|
| V1 BASE (cash) | 1.40 | 2.10 | -9.3% | 19.5% |
| **V3 A + 黄金** | **1.96** | 2.99 | -9.8% | **29.2%** |
| **V7 Ensemble + 黄金** | **1.91** | **3.21** | -8.9% | **28.6%** |

**Why gold wins**:
- 2022 A-share -22%, gold **+9.2%** (真 anti-cyclic)
- 2024-2025 金价 +23%(美联储降息预期)
- China rate environment favors gold during risk-off

## Round 8: broader defensive basket — **COUNTERINTUITIVE**

Tested 5 basket compositions (gold + copper / silver / HK / Nasdaq / oil):

| basket | Full DD | 2022 DD | 2022 ret |
|---|---:|---:|---:|
| **V7_gold (baseline)** | **-8.9%** | **-8.3%** | **+7.8%** |
| V7_gold_half (50%g + spread) | -12.6% | -9.9% | -0.5% |
| V7_full_def (6 assets eq) | -14.0% | -14.0% | +2.0% |
| V7_global (g+silver+HK+US) | -17.7% | -14.4% | **-4.5%** |
| V7_metals (g+silver+copper) | -17.7% | -17.7% | +0.3% |

**Adding assets HURTS**. Why?

| Asset | 2022 return | Correlation with A-shares |
|---|---:|:-:|
| Gold (159934) | **+9.2%** | **negative** ✓ |
| Silver (161226) | +0.7% | weak |
| Copper (159981) | **-14%** | strong positive ✗ |
| Hang Seng (159920) | **-15%** | strong positive ✗ |
| Nasdaq (159941) | **-33%** | positive (global risk-on/off) ✗ |
| Oil (162411) | +37% (Russia-UA) | idiosyncratic |

**In a global-risk-off regime (2022 = Fed hiking + China zero-COVID + Russia-UA), all equity-linked assets drop together**. Only gold is true risk-off.

## Conclusion

Gold is irreplaceable as fallback. Don't dilute with other "defensives". Bond is the only remaining untested candidate — see Round 9.
