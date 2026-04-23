# Changelog — A-Share ETF Rotation 2.0 research journey

10 rounds of iteration, 2026-04-22 session.

## v2.0 · V7_gold final (2026-04-22)

Full-sample (2019-01 → 2026-04, 377 weeks):
- **Sharpe 1.91 · Sortino 3.31 · Calmar 3.22 · MaxDD -8.89% · AnnRet 28.57%**

Published as main deployment candidate.

## Round 10 (2026-04-22) — Fast gate exploration

Added vol-expansion fast gate (FG4) to catch COVID-style V-crashes.

Key result: `V7_gb7030 + FG4(4, 2.5, 6)` achieves strict Pareto improvement:
- Sharpe 1.81 → 1.85
- Calmar 2.94 → 3.28
- MaxDD -8.89% → -8.11%

Documented as alternative config; V7_gold remains main for raw Sharpe.

## Round 9 — Gold + bond fallback

Bond (511010 / 511260) is textbook risk-off:
- 2022 DD only -0.96% (vs gold's -8.28%)
- Risk-parity gold+bond gives 2022 Sharpe 1.33

But full-sample MaxDD locked at 2020 COVID (-8.89%) — can't be fixed by fallback choice.

Produced V7_gb7030 (70% gold + 30% 5y bond) as a Pareto-balanced variant.

## Round 8 — Broader defensive basket

Tested gold + copper/silver/HK/Nasdaq/oil. **Counterintuitive result**: adding defensive assets HURTS performance.

All equity-linked "defensives" are long-beta in global risk-off (2022). Only gold is true anti-cyclic.

Confirmed pure gold fallback as optimal.

## Round 7 — Red / Ensemble / Gold

- Dividend ETF fallback: **failed** (DD -13.4%, worse than cash)
- Ensemble (A + G): marginal DD improvement (-0.4pp)
- **Gold fallback: breakthrough** (Sharpe 1.40 → 1.91, AnnRet 19.5% → 29.2%)

V3_gold (pure A + gold) and V7_ensemble_gold (A + G + gold) both deployable.

## Round 6 — Robustness

- 8-fold rolling OOS: 6/8 folds independently tune to exact same `A_tuned_v1` spec (not overfit)
- Gate MA sensitivity: MA40/50/60 is stable plateau (Sh 1.33-1.40, Cal 1.80-2.10)
- **Realistic long-run expectation**: Sharpe 1.2-1.4, Calmar 1.8-2.5

## Round 5 — IS/OOS disciplined tuning

Grid search (4860 combos) on IS 2019-2023, OOS 2024-2026 held out.

Winner: `A_tuned_v1`
- IS  Sh 1.41 / Cal 1.92 / DD -9.3%
- OOS Sh 1.42 / Cal 2.92 / DD -7.9%
- Full Sh 1.40 / Cal 2.10 (passes target)

Placebo p=0.000 for both Sharpe and Calmar.

## Round 4 — Pivot to 34 tradable ETFs

- Staggered join (12-week minimum post-listing)
- Strategy degrades vs SW L1 (theme ETFs more volatile)
- A7 wins on ETF universe (0.82) — penalized > layered here
- Introduced G_top3 (9-group rotator) as #2 (0.77)

## Round 1-3 — SW L1 baseline

31-industry universe, 3 hypothesis families:
- A (penalized): all 8 specs beat bench, top Sh 1.36
- B (layered): all 8 specs beat bench, top Sh 1.20 (B6 winner)
- C (reversal): **all fail** — A-share weekly industry has no reversal

B6 de facto = 红利价值轮动器 (银行 34% / 石油 33% / 食品 32% / 煤炭 24%).

## Key research insights

1. **A-share weekly industry momentum works; reversal doesn't** (C family complete failure)
2. **"Momentum + crowding penalty" captures 'quietly rising' sectors**, avoiding overheated themes
3. **Industry-level signals are less noisy than single-ETF**, hence Leg G group rotator
4. **Gold is irreplaceable as anti-cyclic fallback** — not red, not silver, not copper, not overseas
5. **Bond compresses bear-year DD** but can't fix sudden-crash MaxDD
6. **Vol target + gate + fallback three-tier defense** is the operational core; none alone sufficient
7. **MA50 slow gate is a stable plateau** (MA40-60 all work), not knife-edge overfit
8. **Weekly frequency cannot respond to V-shaped crashes** (2020 COVID); daily-freq gate needed for sub -6% MaxDD

## Versions

- v1.0: original A_tuned_v1 (Round 5)
- v1.5: V3_gold (A + gold, Round 7)
- **v2.0: V7_gold (Ensemble A+G + gold, Round 7)** ← THIS RELEASE
- v2.1 (optional): V7_gb7030_FG4 (+ bond 30% + fast gate, Round 10)
