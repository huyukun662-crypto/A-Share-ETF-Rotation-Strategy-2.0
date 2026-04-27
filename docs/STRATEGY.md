# V25 Strategy Specification

## 1. 策略定位

V25 = **V7 三段式冠军 + V15/V16/V17 多因子叠加 + V25 真·中证全指 regime**。

核心设计哲学：
- **V7 引擎不可破坏**: Leg A 个股 momentum + Leg G 板块轮动是基础, 任何修改都不能伤害此结构
- **多因子单变量迭代**: 每加一个因子 → 严格非劣判定 → 通过才保留
- **真指数 regime 优于池均值伪指数**: V22 的 hs300_acc 实际是池内均值, V25 升级为 000985.CSI 真指数

## 2. 完整因子方程

```python
# Leg A score
score_A(c, t) = z_m(c, t)                                                    # V7 momentum
              − 1.5 · z_t(c, t)                                              # V7 turnover penalty
              + 0.3 · breadth_z(t)                                           # V7 breadth boost
              + 0.4 · z_ria(c, t)                                            # V15 risk-adj
              − 0.05 · z_rev1w(c, t)                                         # V16 reversal
              + 0.10 · z_accel(c, t) · I[regime_csi_on(t)]                   # V17 + V25 ★

# 各项定义
z_m       = z(cum / cum.shift(4) - 1)                       # 4w 动量
z_t       = z(turnover_4w_avg)                              # 4w 平均成交量
breadth_z = z(% of pool with cum > cum.shift(4))            # 横截面广度
z_ria     = z(z_m − 0.4 · z_vol_26w)                        # 风险调整动量
z_rev1w   = z(ret_1w)                                       # 1 周收益 (反转方向)
z_accel   = z(mom_4w − mom_13w)                             # 加速度

# Regime
regime_csi_on(t) = (csi_acc.rolling(8).min() ≥ 0.05)
csi_acc           = (csi_4w_mom − csi_13w_mom).shift(1)
csi_4w_mom        = CSI_000985.cum / CSI_000985.cum.shift(4) - 1

# Leg G
group_mom(g, t) = mean(mom_4w[c] for c in pool if group[c]=g)
top_groups      = top_k=4 by group_mom
each_group_pick = argmax(score_A[c] for c in g) per top_group  (per_group=1)

# 合并
w_A(t) = (1/4) for top 4 individuals by score_A
w_G(t) = (1/4) for top 4 group picks
w_raw  = 0.5 · w_A + 0.5 · w_G
```

## 3. Gate + Vol Targeting

```python
# Gold 50w gate
cum_gold(t)  = cum[159934.SZ, t]
ma50_gold(t) = cum_gold.rolling(50).mean()
gate_on(t)   = (cum_gold(t) > ma50_gold(t)).shift(1)

if gate_on(t):
    w_gated = w_raw
else:
    w_gated = {159934.SZ: 1.0, others: 0.0}    # 100% 黄金避险

# Vol targeting
realized_vol(t) = port_pnl_raw.rolling(26).std() * sqrt(52)
scale(t)        = clip(0.12 / realized_vol(t), [0.0, 1.0])
w_final(t)      = w_gated(t) · scale(t)
```

## 4. 锁定参数 (V25_PARAMS)

```python
V25_PARAMS = dict(
    mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12,
    top_k_groups=4, per_group=1,
    risk_adj_nu=0.4,                       # V15 ν
    rev_w=0.05,                            # V16 ω_rev
    accel_w=0.10, longmom_window=13,       # V17 ω_accel + 13w 长动量
    regime_accel_signal='csi_all_acc',     # V25 ★
    regime_accel_theta_on=0.05,            # ON 触发阈值
    regime_accel_theta_off=0.0,            # OFF 复位阈值
    regime_accel_k_min=8,                  # 持续周数下限
    uni_path='cache/etf_universe_v24diag.csv',
    csi_path='cache/csi_all_weekly.parquet',
)
```

## 5. WF 3 年滚动验证

不再 expanding (从 2019 起逐年扩展), 改为**滚动 3 年训练窗口**:

| Test 年 | 训练窗口 (3y) | top_k (从 IS 选) | Test Sh |
|---|---|---|---|
| 2022 | 2019-2021 | 5 | 0.76 |
| 2023 | 2020-2022 | 4 | 1.65 ✓ |
| 2024 | 2021-2023 | 3 | 2.30 ✓ |
| 2025 | 2022-2024 | 3 | 2.30 ✓ |
| 2026 (YTD) | 2023-2025 | 3 | 0.67 |

通过率 3/5 (2026 仅 4 月数据).

## 6. 失败实验编年史

| 版本 | 实验 | 结果 | 教训 |
|---|---|---|---|
| V20 | 跨境/商品 ETF 加入 | OOS 退化 ≥ 0.5 | A 股板块逻辑不适用海外 |
| V24 | 50/15 池板块拆细 | Full Sh 1.955 → 1.325 | 横截面 z-score 集体污染 |
| V24m | 50/12 合并板块 | Full Sh 1.223 | 合并板块没救, 问题在池子 |
| V25_swap_588790 | 替换 515980 → 588790 | OOS Sh -0.174 | 588790 数据不足 (68 周) |
| V25_add_588790 | AI数字 5 → 6 只 | OOS Sh -0.096 | 挤占老 AI ETF |
| V25_daily | 日频化 (windows ×5) | Full Sh 0.754, DD -20% | 频率不能线性映射 |
| V25_scale_lower | scale 下限 0.5/0.7/0.8 | DD 恶化, Sh 跌 | vol target 下限破坏 alpha |

## 7. 防前视 Audit

| 模块 | 检查 |
|---|---|
| Score 计算 | ✓ shift(1), t-1 之前数据 |
| Regime 信号 | ✓ csi_acc.shift(1), rolling.min 不含未来 |
| Gold gate | ✓ (cum > MA50).shift(1) |
| Vol targeting | ✓ realized_vol 用过去 26w |
| 执行延迟 | ✓ delay=1 (T 信号 → T+1 执行) |
| ret 锚点 | ✓ ret_w 从 t-1 锚日 → t 锚日, 与 score 严格分离 |

## 8. 数据源

| 数据 | 文件 | 来源 | 频率 | 范围 |
|---|---|---|---|---|
| V7 35 池周线 | cache/etf_weekly.parquet | TuShare fund_daily + adj | 周 (W-FRI) | 2015-2026 |
| 30Y 国债 | cache/etf_weekly_v12.parquet | TuShare 511090 | 周 | 2015-2026 |
| OHLC 周线 | cache/etf_weekly_ohlc.parquet | TuShare fund_daily | 周 | 2018-2026 |
| 中证全指 | cache/csi_all_weekly.parquet | TuShare index_daily 000985.CSI | 周 | 2018-2026 |
| 日频 (研究) | cache/fund_daily_34.parquet | TuShare fund_daily | 日 | 2015-2026 |

## 9. 实操要点

- **每周五 15:00** 收盘后跑 daily_guide.ipynb cells 1-8 → 得到 holdings + actions
- **周末** 核对资金, 确认买卖清单
- **下周一 09:30-10:00** 集合竞价 / 开盘后 30 分钟分批执行
- **延后到周一 11:00** 执行 → 损失约 1-3 bp 滑点, 可接受
- **遇节假日** trade_week 自动退到当周最后交易日
