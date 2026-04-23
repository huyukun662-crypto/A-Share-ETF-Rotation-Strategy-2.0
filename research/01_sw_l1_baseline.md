# Round 1-3 · SW L1 baseline (2018-2026)

First three rounds on the SW L1 industry universe (31 broad industries, aggregated from stock cache).

## Setup
- Universe: 31 SW L1 industries, circ_mv-weighted from ~8M stock-days
- Sample: 2018-01 → 2026-04 (424 weeks)
- Benchmark: 31-industry equal weight

## 3 hypothesis families tested (8 specs each)

| Family | Mechanism | Top spec | Full Sharpe |
|---|---|---|---:|
| **A** penalized | `z(mom) - λ·z(turn) + μ·breadth` | A7 | **1.36** |
| **B** layered | Top-K mom filter → bottom-n turn | B6 | 1.20 |
| **C** reversal | `-mom_W` (buy losers) | C1 | 0.24 (fail) |

**Key insight**: C family's total failure (all 8 ≤ 0.25) confirms **A-share weekly industry has NO reversal effect**. Momentum direction is unique.

## Winner: `B6_m4_K10_t8`

Step 1: top-10 industries by 4w momentum
Step 2: within those, pick 3 with lowest 8w turnover

Full stats:
- Ann 23.3% / Sharpe 1.20 / MaxDD -14.5%
- 2018 Sharpe -0.13 (systematic bear, only year that fails)
- Placebo p=0.000

**De facto 红利价值轮动器**: 持仓分布是 银行 34% / 石油 33% / 食品 32% / 煤炭 24% — "momentum × low turnover" 机制下,实际变成 "追主线中冷门稳定的行业",匹配 A 股 2019-2026 中特估 + 高股息主导风格。

## 为何降级为 research only

- **6/7 audit 过**,唯一失败:worst-year Sharpe -0.13 < 0.5 floor (2018 系统性熊)
- Overlay 和市场 gate 都救不了 2018
- **结构性熊年是这族策略的天生痛点**

## 指向下一步

SW L1 策略是理论上限(广泛基准,干净 industry 切面);实战必须映射到可交易 ETF。那一步在 Round 4 展开。
