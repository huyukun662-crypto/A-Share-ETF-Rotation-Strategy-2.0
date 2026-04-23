# Round 9-10 · Bond fallback + fast gate

## Round 9 — 国债 ETF as true risk-off

Tested bond ETFs alongside gold:
- 511010.SH  国泰 5y 国债
- 511260.SH  华安 10y 国债

### 2022 stress test (critical year)

| Asset | 2022 return | 2022 DD |
|---|---:|---:|
| 黄金 (159934) | **+9.2%** | -8.28% (intra-year USD surge) |
| 5y bond (511010) | +2.1% | **-0.96%** |
| 10y bond (511260) | +2.7% | -1.18% |
| Copper / HK / Nasdaq | negative | -15% to -33% |

**Bonds are PERFECT risk-off**: low vol, small DD, positive return in bear years.

### Gold + bond combinations

| basket | Full Sh | Full Cal | Full DD | 2022 DD |
|---|---:|---:|---:|---:|
| V7_gold (baseline) | **1.91** | **3.22** | -8.89% | -8.3% |
| V7_gb_70_30 | 1.81 | 2.94 | -8.89% | **-5.7%** |
| V7_gb_50_50 | 1.72 | 2.75 | -8.89% | -3.9% |
| V7_gb_30_70 | 1.63 | 2.56 | -8.89% | -2.3% |
| V7_bond5 (pure bond) | 1.46 | 2.28 | -8.89% | **-0.96%** |
| V7_rp_g_b10 (risk-parity) | 1.60 | 2.52 | -8.89% | -1.3% |

**Full MaxDD stays at -8.89% for ALL variants.**
That DD comes from 2020 Q1 COVID, not 2022. Fallback doesn't activate during COVID because slow gate was still ON — strategy held stocks and ate the 4-week crash.

**Winner for 2022 compression**: V7_gb_70_30 (slight Pareto improvement: Cal 2.94 preserves most Sharpe while halving 2022 DD).

## Round 10 — fast gate to catch COVID

5 fast-gate designs tested. Only **FG4 (vol expansion)** catches COVID:

```
rolling_4w_vol > 2× rolling_26w_vol → risk-off for 6 weeks
```

| config | Full Sh | Full Cal | Full DD | 2020 DD | 2022 DD |
|---|---:|---:|---:|---:|---:|
| V7_gold (baseline) | 1.91 | 3.21 | -8.89% | -8.89% | -8.3% |
| V7_gold + FG4 | 1.91 | 2.79 | **-10.1%** ❌ | **-6.7%** | -8.3% |
| V7_gb7030 (baseline) | 1.81 | 2.94 | -8.89% | -8.89% | -5.7% |
| **V7_gb7030 + FG4(4,2.5,6)** ⭐ | **1.85** | **3.28** | **-8.11%** | **-8.11%** | -5.7% |

**V7_gold FG4 no clean Pareto**: catching COVID creates new DD elsewhere. Gold's own 2020 Q1 drawdown (-10% during USD surge) negates FG4's rescue.

**V7_gb7030 FG4 clean Pareto**:
- Sharpe 1.81 → **1.85**
- Calmar 2.94 → **3.28**
- Full DD -8.89% → **-8.11%**
- 2020 DD -8.89% → -8.11%
- AnnRet 26.1% → 26.6%

Bond 30% provides the clean buffer that lets FG4's rescue stick.

## Final options table

| Config | Sh | Cal | DD | AnnRet | When to use |
|---|---:|---:|---:|---:|---|
| **V7_gold** | **1.91** | 3.21 | -8.9% | **28.6%** | Max Sharpe / pure anti-cyclic |
| V7_gb7030 | 1.81 | 2.94 | -8.9% | 26.1% | Smoother 2022 |
| **V7_gb7030 + FG4** | 1.85 | **3.28** | **-8.1%** | 26.6% | Strict Pareto, best Calmar |

## Head-to-head: V7_gold vs V7_gb7030_FG4 (Sortino analysis)

| Metric | V7_gold | V7_gb_FG4 | Winner |
|---|---:|---:|:-:|
| Sharpe | **1.91** | 1.85 | gold |
| Sortino (MAR=0) | **3.31** | 3.06 | gold (+0.24) |
| Sortino (semi-dev) | **3.62** | 3.52 | gold |
| Calmar | 3.22 | **3.28** | gb_FG4 |
| MaxDD | -8.89% | **-8.11%** | gb_FG4 |
| Ulcer Index | 2.81% | **2.66%** | gb_FG4 |

**Sortino favors V7_gold** because numerator (ann_ret 28.6% vs 26.6%) is higher while downside vol is essentially equal (8.63% vs 8.69%) — the bond buffer reduces extreme MaxDD but doesn't reduce day-to-day downside variance.

## Remaining open problems

1. **2020 COVID DD -8% still irreducible without daily-freq gate**. Weekly data can't react fast enough to 4-week V-crashes.
2. **OOS Sharpe 2.0+ has gold 2024-2025 rally beta**. Long-run expected Sharpe likely 1.4-1.7.
3. **2018 deep bear untested** — universe doesn't go back that far.
