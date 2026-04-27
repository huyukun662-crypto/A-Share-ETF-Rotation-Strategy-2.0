# A-Share ETF Rotation Strategy V25

> **Production main version** — V7 35-pool + V24-style 12-sector taxonomy + true CSI All-Share 000985 acceleration regime signal.
> 7/8 dimensions strictly non-inferior to V22 baseline (Full DD only marginally worse by 7bp).

## Headline Performance (2019-01 → 2026-04, 377 weeks)

| Metric | V7 official | V22 (legacy main) | **V25 ★** | Δ vs V22 |
|---|---:|---:|---:|---:|
| Full Sharpe | 1.915 | 1.955 | **2.002** | +0.047 ✓ |
| Full Annualized | +24.67% | +25.12% | **+25.83%** | +0.71pp ✓ |
| Full MaxDD | -8.18% | -8.16% | -8.23% | -0.07pp ✗ |
| Full Calmar | 3.01 | 3.08 | **3.14** | +0.06 ✓ |
| OOS Sharpe | 2.029 | 2.097 | **2.189** | +0.092 ✓ |
| OOS Annualized | +29.07% | +29.79% | **+31.50%** | +1.71pp ✓ |
| OOS MaxDD | -6.09% | -6.00% | **-5.49%** | +0.51pp ✓ |
| OOS Calmar | 4.77 | 4.97 | **5.74** | +0.77 ✓ |
| WF pass rate (3y rolling) | — | — | **3/5** | — |

## Architecture

V25 = V22 factor stack + V24 sector relabeling + true CSI All-Share regime:

```
score_A(c, t) = z_m  − 1.5·z_t  + 0.3·breadth                    # V7 always-on
              + 0.4 · z(mom/vol)                                   # V15 risk-adj momentum
              − 0.05 · z(ret_1w)                                   # V16 short reversal
              + 0.10 · z(mom_4w − mom_13w) · I[regime=ON]         # V17 + V25 ★

  regime = ON when CSI All-Share 000985 4w-13w acceleration ≥ 0.05 for ≥ 8 weeks

Leg G: 12 sectors × top_k=4 × per_group=1
Pool: V7 35 industry ETFs (locked)
```

Regime ON share within sample: **33.5%** (24 switches).

## Locked Parameters

```python
V25_PARAMS = dict(
    mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12,
    top_k_groups=4, per_group=1,
    risk_adj_nu=0.4,                              # V15 risk-adjusted momentum
    rev_w=0.05,                                   # V16 short-term reversal
    accel_w=0.10, longmom_window=13,             # V17 momentum acceleration
    regime_accel_signal='csi_all_acc',           # ★ V25 true CSI All-Share
    regime_accel_theta_on=0.05,
    regime_accel_theta_off=0.0,
    regime_accel_k_min=8,
    uni_path='data_cache/etf_universe_v24diag.csv',
    csi_path='data_cache/csi_all_weekly.parquet',
)
```

## Repository Layout

```
ETF2.0/
├── README.md / README_zh.md
├── V25_daily_guide.ipynb              ★ Live trading notebook
├── data_cache/
│   ├── etf_weekly.parquet              # V7 35-pool weekly bars
│   ├── etf_weekly_v12.parquet          # 30Y bond
│   ├── etf_weekly_ohlc.parquet         # OHLC for V18 intraday factors
│   ├── etf_universe.csv                # V7 35 universe
│   ├── etf_universe_v24diag.csv        # V25 12-sector relabel
│   ├── csi_all_weekly.parquet          # CSI 000985 All-Share regime source
│   └── fund_daily_34.parquet           # daily bars (research)
├── scripts/
│   ├── _strategy_v15.py                # main engine
│   ├── 18_v22_final.py                 # V22 legacy main (kept for ref)
│   ├── 28_v25_csi_rolling_wf.py        ★ V25 main entry
│   ├── 29_v25_trading_log.py           ★ trading log generator
│   └── archived/                       # 12 failed/diagnostic experiments
├── results/
│   ├── v25_metrics_csi.json            ★ headline metrics
│   ├── v25_walk_forward_rolling3y.csv  ★ 3y rolling WF
│   ├── v22_metrics.json                # V22 legacy
│   └── ... (LOO / forward-select / scale_lower / daily diagnostics)
└── roadshow/
    ├── trading_log_v25_holdings.csv    ★ 1409 rows
    ├── trading_log_v25_actions.csv     ★ 1666 rows
    └── trading_log_v25_summary.csv     ★ 377 weekly rows
```

## Quick Start

```bash
pip install -r requirements.txt

# Headline backtest + walk-forward
python scripts/28_v25_csi_rolling_wf.py

# Generate full trading log (holdings/actions/summary)
python scripts/29_v25_trading_log.py

# Daily ops notebook
jupyter notebook V25_daily_guide.ipynb
```

## Walk-Forward (3-year rolling train window)

| Test Year | Train Window | Top-K | Train Sh | Test Sh | Test Ann | Test DD |
|:-:|:-:|:-:|---:|---:|---:|---:|
| 2022 | 2019-2021 | 5 | 2.35 | 0.76 | +7.10% | -8.28% |
| 2023 | 2020-2022 | 4 | 1.81 | **1.65 ✓** | +22.20% | -4.15% |
| 2024 | 2021-2023 | 3 | 1.58 | **2.30 ✓** | +37.98% | -4.08% |
| 2025 | 2022-2024 | 3 | 1.75 | **2.30 ✓** | +31.24% | -4.37% |
| 2026 (YTD) | 2023-2025 | 3 | 2.19 | 0.67 | +7.54% | -5.51% |

Pass rate **3/5** (2026 not a full year).

## Engineering Discipline Audit

| Dimension | Status |
|---|---|
| IS-only parameter selection / OOS read-only | ✓ enforced |
| Single-variable iteration | ✓ V22 → V24 (failed) → V25 (sector relabel + true CSI regime) |
| Strict 8-dim non-inferior gate | △ 7/8 ≥ V22, Full DD -7bp explicitly disclosed |
| LOO + forward-select diagnostics | ✓ 15 new ETFs evaluated; collective interaction confirmed |
| Look-ahead audit | ✓ shift(1) discipline strictly applied |
| WF 3y rolling | ✓ 3/5 folds pass, 2026 incomplete |
| Failure transparency | ✓ V24/V24m/v25_swap/v25_daily fully retained as evidence |

## Execution Timing

- **Signal time** = Friday close (T)
- **Execution time** = Following Monday open (T+1)
- All factors `shift(1)` to ensure no look-ahead
- Per-side cost = 5bps (covers commission + slippage on round trip)

## Academic References

- **myinvestpilot risk-adjusted momentum** — V15 ν=0.4
- **Jegadeesh (1990)** — Evidence of Predictable Behavior of Security Returns (V16)
- **Liu, Stambaugh, Yuan (2019)** — Size and Value in China (reversal in A-share)
- **Da, Gurun, Warachka (2014)** — Frog in the Pan: Continuous Information and Momentum (V17)

## Disclaimer

This repository is for research reference only. **Not investment advice.** Past performance does not guarantee future returns. Conduct independent risk assessment before live trading.
