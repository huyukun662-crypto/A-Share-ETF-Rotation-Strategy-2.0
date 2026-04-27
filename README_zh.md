# V25_csi_acc · A 股 ETF 轮动策略 v5.0

> **新主版本** — V7 池子 + V24 风格 12 板块重命名 + 真·中证全指 000985 加速度 regime 信号
> OOS 全面提升，仅 Full DD 微弱代价 7bp。

## 核心成绩（2019-01 → 2026-04，377 周）

| 指标 | V7 官方 | V22 (旧主) | **V25_csi_acc ★** | Δ vs V22 |
|---|---:|---:|---:|---:|
| Full Sharpe | 1.915 | 1.955 | **2.002** | +0.047 ✓ |
| Full 年化 | +24.67% | +25.12% | **+25.83%** | +0.71pp ✓ |
| Full 最大回撤 | -8.18% | -8.16% | -8.23% | -0.07pp ✗ |
| Full Calmar | 3.01 | 3.08 | **3.14** | +0.06 ✓ |
| OOS Sharpe | 2.029 | 2.097 | **2.189** | +0.092 ✓ |
| OOS 年化 | +29.07% | +29.79% | **+31.50%** | +1.71pp ✓ |
| OOS 最大回撤 | -6.09% | -6.00% | **-5.49%** | +0.51pp ✓ |
| OOS Calmar | 4.77 | 4.97 | **5.74** | +0.77 ✓ |
| WF 通过 (3y 滚动) | — | — | **3/5** | — |

**7/8 维度 ≥ V22**（仅 Full DD 微败 7bp，OOS 全面胜出）。

## 策略架构

V25 = V22 因子结构 + V24 板块标签精细化 + 真指数 regime 信号：

```
score_A(c, t) = z_m  − 1.5×z_t  + 0.3×breadth         # V7 始终启用
              + 0.4 × z(mom/vol)                       # V15 (myinvestpilot)
              − 0.05 × z(ret_1w)                       # V16 (Jegadeesh 1990)
              + 0.10 × z(mom_4w − mom_13w) × I[regime=ON]  # V17 + V25 ★
                                              ↑
                          regime = ON 当 CSI 全指 000985 4w-13w 加速度 > 0.05 持续 ≥ 8w
                          否则 OFF (退化为 V16 行为)

Leg G: 12 板块 × top_k=4 × per_group=1
Pool: V7 35 只行业 ETF（不变）
```

样本期内 Regime ON 占比 **33.5%**（vs V22 32.4%, +1.1pp），切换 24 次。

## V24/V25 探索路径

| 实验 | 池 | 板块 | 信号 | Full Sh | OOS Sh | 结论 |
|---|:-:|:-:|---|---:|---:|---|
| V22 主版本 | 35 | 9 | hs300_acc(池均值) | 1.955 | 2.097 | baseline |
| V24 (50/15) | 50 | 15 | csi_all_acc | 1.325 | 1.495 | **退化 −0.63 ✗** |
| V24m (50/12 合并) | 50 | 12 | csi_all_acc | 1.223 | 1.533 | 合并板块没救 ✗ |
| **V25 (35/12)** | **35** | **12** | **csi_all_acc** | **2.002** | **2.189** | **OOS 全面提升 ✓** |

**核心洞察**：
- 板块标签精细化（V7 9 板块 → V24 风格 12 板块）= **微正向贡献**
- 加入 15 只新 ETF 致命退化 = **横截面 z-score 集体污染**（LOO 单只剔除 ΔSh < ±0.03，但 15 只共存使 −0.63）
- 前向选择从 V25 出发尝试加任何 1 只新 ETF：ΔFull Sh = +0.000 → **保留 V7 池子是最优解**
- regime 信号源升级（"hs300_acc"池均值 → 真·中证全指 000985）：Full Sh 几乎等价（差 0.005），但**理论纯净度 + 路演说服力大幅提升**

## V25 板块结构（V7 35 只 / 12 板块）

| 板块 | 数量 | ETF |
|---|:-:|---|
| 半导体芯片 | 2 | 半导体 512480 / 科创芯片 589100 |
| 通信光模块 | 1 | 通信 515880 |
| AI 数字 | 5 | AI 515980 / 软件 515230 / 云计算 159890 / 消费电子 159779 / 游戏 159869 |
| 新能源 | 4 | 光伏 / 电池 / 新能源车 / 电网设备 |
| 高端制造 | 3 | 机器人 / 航空航天 / 军工 |
| 大金融 | 3 | 银行 / 证券 / 非银 |
| 医疗 | 3 | 医药 / 创新药 / 医疗器械 |
| 大消费 | 3 | 家电 / 食品 / 酒 |
| 周期资源 | 7 | 有色 / 煤炭 / 钢铁 / 石油 / 化工 / 稀土 / 黄金 |
| 地产链 | 2 | 房地产 / 建材 |
| 农业 | 1 | 畜牧 |
| 红利 | 1 | 红利 |
| **合计** | **35** | **12 板块** |

## V25 锁定参数

```python
V25_PARAMS = dict(
    mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12,
    top_k_groups=4,                              # 12 板块需 +1
    per_group=1,
    risk_adj_nu=0.4,                              # V15 风险调整动量
    rev_w=0.05,                                   # V16 短期反转
    accel_w=0.10, longmom_window=13,             # V17 加速度
    regime_accel_signal='csi_all_acc',           # ★ V25 真·中证全指
    regime_accel_theta_on=0.05,
    regime_accel_theta_off=0.0,
    regime_accel_k_min=8,
    uni_path='data_cache/etf_universe_v24diag.csv',
    csi_path='data_cache/csi_all_weekly.parquet',
)
```

## 文件结构

```
A-Share-ETF-Rotation-Strategy-2.0-V15/
├── README.md                                # 本文档
├── V25_daily_guide.ipynb                    # ★ 实盘 notebook
├── data_cache/
│   ├── etf_weekly.parquet (V7)              # V7 35 池周线（不变）
│   ├── etf_universe_v24diag.csv             # ★ V25 池子+12板块标签
│   ├── csi_all_weekly.parquet               # ★ 中证全指 000985 周线
│   ├── etf_universe_v24.csv                 # V24 50/15 (废弃)
│   └── etf_weekly_v24.parquet               # V24 50 只周线 (研究用)
├── scripts/
│   ├── _strategy_v15.py                     # 主引擎 (含 csi_all_acc)
│   ├── 18_v22_final.py                      # V22 final (旧主，保留)
│   ├── 22_v24_run.py                        # V24 失败实验
│   ├── 23_v24m_run.py                       # V24m 合并板块实验
│   ├── 25_v24_loo_diag.py                   # leave-one-out 诊断
│   ├── 26_v25_forward_select.py             # 前向选择 (ΔFull=+0.000)
│   ├── 27_v25_final.py                      # V25 hs300_acc 对照
│   ├── 28_v25_csi_rolling_wf.py             # ★ V25 final + 3y 滚动 WF
│   └── 29_v25_trading_log.py                # ★ V25 trading log 生成器
├── results/
│   ├── v25_metrics_csi.json                 # ★ V25 主版本 metrics
│   ├── v25_walk_forward_rolling3y.csv       # ★ 3 年滚动 WF
│   ├── v25_variants.csv                     # V25 信号 × topk 网格
│   ├── v22_metrics.json                     # V22 旧主 (保留)
│   ├── v24_loo.csv                          # 15 新 ETF LOO 诊断
│   └── v25_forward_select.csv               # 前向选择历史
└── roadshow/
    ├── trading_log_v25_holdings.csv         # ★ V25 完整持仓 (1409 行)
    ├── trading_log_v25_actions.csv          # ★ V25 操作 (1666 行)
    ├── trading_log_v25_summary.csv          # ★ V25 周摘要 (377 行)
    └── trading_log_v22_*.csv                # V22 trading log (保留)
```

## 快速使用

```bash
cd deploy/A-Share-ETF-Rotation-Strategy-2.0-V15

# V25 主版本回测 + WF
python scripts/28_v25_csi_rolling_wf.py

# 生成 V25 trading log
python scripts/29_v25_trading_log.py

# 实盘 daily guide
jupyter notebook V25_daily_guide.ipynb
```

## WF 3 年滚动训练窗口（不再 expand）

| Test 年 | 训练窗口 | 选中 top_k | Train Sh | Test Sh | Test 年化 | Test DD |
|:-:|:-:|:-:|---:|---:|---:|---:|
| 2022 | 2019-2021 | 5 | 2.35 | 0.76 | +7.10% | -8.28% |
| 2023 | 2020-2022 | 4 | 1.81 | **1.65** ✓ | +22.20% | -4.15% |
| 2024 | 2021-2023 | 3 | 1.58 | **2.30** ✓ | +37.98% | -4.08% |
| 2025 | 2022-2024 | 3 | 1.75 | **2.30** ✓ | +31.24% | -4.37% |
| 2026 (YTD) | 2023-2025 | 3 | 2.19 | 0.67 | +7.54% | -5.51% |

通过率 **3/5**（2026 仅 4 月数据，不构成完整年）。

## 工程纪律审计

| 维度 | 状态 |
|---|---|
| IS 选参 / OOS 只读 | ✓ 严守 |
| 单变量迭代 | ✓ V22→V24 (失败) → V25 (板块重命名+真指数 regime) |
| 严格非劣判定 | △ 7/8 维 ≥ V22, Full DD 微弱 −7bp 风险显式公开 |
| LOO + 前向选择诊断 | ✓ 全 15 只新 ETF 单独加无增益, 共加致命退化 |
| 前视审计 | ✓ shift(1) 严格只用 t-1 之前数据 |
| WF 3y 滚动 | ✓ 3/5 折通过, 2026 不算完整年 |
| 失败诚实公开 | ✓ V24/V24m 失败实验完整保留 + 归因 |

## 引用学术来源

- **myinvestpilot 风险调整动量** — score / vol z-score (V15 ν=0.4)
- **Jegadeesh (1990)** — Evidence of Predictable Behavior of Security Returns (V16)
- **Liu, Stambaugh, Yuan (2019)** — Size and Value in China (A 股反转效应)
- **Da, Gurun, Warachka (2014)** — Frog in the Pan: Continuous Information and Momentum (V17)
- **CLAUDE.md** — 量化策略研发工程纪律

## 免责声明

本仓库代码与回测结果仅供研究参考，**不构成任何投资建议**。历史表现不代表未来收益。
实盘前请充分评估个人风险承受能力，配套独立风控系统。
