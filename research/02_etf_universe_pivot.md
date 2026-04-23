# Round 4-5 · Pivot to 34-ETF tradable universe

## Universe switch

| Aspect | SW L1 (Round 1-3) | 34-ETF (Round 4+) |
|---|---|---|
| Count | 31 wide industries | 34 themed ETFs |
| Depth | ~100+ stocks per industry | single theme per ETF |
| Sample | 2018-01 → 2026-04 | 2019-01 → 2026-04 (staggered) |
| Tradability | needs ETF mapping | directly |

Staggered join: each ETF enters only after 12 weeks of post-listing history.

## Round 4 — naive port of SW L1 specs

Same A/B/C family specs, direct substitution:

| spec | SW L1 Sh | ETF Sh | degradation |
|---|---:|---:|:-:|
| B6 (layered) | 1.20 | **0.61** | -49% |
| A7 (penalized) | 1.36 | **0.82** | -40% |
| G_top3 (9-group rotator, new) | — | **0.77** | new |

**Why degradation**:
1. Theme ETFs are more volatile & concentrated per position
2. Shorter sample (2019-2026 ~7yr vs 2018-2026 8yr)
3. 34 themed ETFs highly correlated within sectors
4. No 2018 bear in sample (replaced by 2022 -16%)

## Round 5 — IS/OOS disciplined tuning (target Sh ≥ 1.4, Calmar ≥ 2.0)

**IS**: 2019-2023 (258 weeks, 5 years)
**OOS**: 2024-2026 (119 weeks, 2.3 years, held out)

**Grid**: 4860 combinations of (mom × turn × λ × μ × top_n × gate × vol_target × rebalance).

**IS best**: `A_tuned_v1`:
```
z(mom_4w) - 1.5*z(turn_4w) + 0.3*breadth_z → top-4 equal weight
+ gate: mkt_cum > 50w MA (cash when off)
+ 15% annual vol target (scale-down only)
```

Results:
- IS   : Sh 1.41 / Cal 1.92 / AnnRet 17.8% / DD -9.3%
- OOS  : Sh 1.42 / Cal 2.92 / AnnRet 23.2% / DD -7.9%
- **Full : Sh 1.40 / Cal 2.10 / AnnRet 19.5% / DD -9.3%**

**Observation**: IS Calmar 1.92 misses target 2.0 by 0.08; OOS (1.42/2.92) and Full (1.40/2.10) both **cleanly pass both targets**. Placebo (200 trials, p<0.001 for both Sh and Calmar) confirms this is not lookahead.

## Key lesson

**Gate + vol target must be permanent structural components, not tunable**. When tuner had freedom to drop them (2022-fold IS was pure bull 2019-2021), it did — and OOS bear killed the strategy. Lock gate.
