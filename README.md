# A-Share ETF Rotation Strategy 2.0 · V7_gold | A股 ETF 板块轮动策略 2.0

<p align="center">
  <a href="#zh"><img src="https://img.shields.io/badge/LANGUAGE-%E4%B8%AD%E6%96%87-E84D3D?style=for-the-badge&labelColor=3B3F47" alt="LANGUAGE 中文"></a>
  <a href="#en"><img src="https://img.shields.io/badge/LANGUAGE-ENGLISH-2F73C9?style=for-the-badge&labelColor=3B3F47" alt="LANGUAGE ENGLISH"></a>
</p>

<p align="center">
  <a href="#1-项目概览">概览</a> •
  <a href="#3-回测结果">回测结果</a> •
  <a href="#6-快速开始">快速开始</a> •
  <a href="#11-策略来源与参考文献">引用与来源</a>
</p>

<a id="zh"></a>

## 简体中文

当前语言：中文 | [Switch to English](#en)

> 这是一个面向 **A 股全市场 34 只主题行业 ETF** 的**低频、规则化、可复现**的周度板块轮动量化项目（**V7_gold** 版本）。
> 策略基于 **动量 × 拥挤惩罚 × 组轮动 Ensemble**，叠加 **50 周 MA 熊市滤波** 与 **黄金 ETF 避险 fallback**，并用 **15% 年化波动目标** 做杠杆约束。严格限定在 IS（2019-2023）上选参，独立在 OOS（2024-2026）上评估。

> **样本外亮点（OOS: 2024–2026）**：Sharpe **2.04** · 年化 **34.91%** · 最大回撤 **-7.73%** · Calmar **4.51**。
> **全样本（Full: 2019-01 → 2026-04, 377 周）**：Sharpe **1.91** · 年化 **28.57%** · 最大回撤 **-8.89%** · Calmar **3.21**。

### 1. 项目概览

在 A 股散户化、存量博弈、板块间切换极快的环境中，单一宽基 ETF 无法同时捕捉多条主线（新能源 → 半导体 → 红利 → 商品 → AI），而个股精选又面临极高信息成本与非系统性风险。

本项目提出一个中间方案：**用规则化的 ETF 轮动 + 拥挤惩罚 + 熊市现金化模型捕捉中短期板块主线趋势**。

核心思想：

- **Leg A** 使用 **动量 × 拥挤惩罚** 在 ETF 层面打分，避开「过热熄火」标的（2021 白酒 / 2023 CPO）；
- **Leg G** 使用 **9 组主线轮动** 在板块层面挑选领头羊，降低单 ETF 噪声；
- **50 周 MA 熊市 Gate** 在市场整体跌破长期均线时，**100% 切换到黄金 ETF（159934.SZ）** 避险；
- **15% 年化波动目标** 对总暴露做动态缩放，系统性管理尾部风险。

### 2. 策略逻辑

#### 2.1 截面评分框架（双腿 Ensemble）

**Leg A — 惩罚式单 ETF 打分：**

| 因子 | 计算逻辑 | 交易含义 |
| --- | --- | --- |
| `mom_4w` | 过去 4 周累计收益 | 中短期绝对动量 |
| `turn_4w` | 过去 4 周平均换手率（成交额/市值） | 拥挤度代理变量 |
| `breadth` | 全市场 above-MA20 占比的 52w z-score | 宏观广度修正项 |
| `score_A` | `z_cs(mom_4w) − 1.5·z_cs(turn_4w) + 0.3·breadth` | 等权 top-4，单只 25% |

**Leg G — 9 组主线轮动：**

```text
group_mom_4w[g,t] = 组内等权平均 4 周收益
top-3 组          = argmax(group_mom_4w)[:3]
for g in top-3: 选组内 4w mom 最高的 1 只 ETF
w_G = 等权 top-3 leaders（每只 33.3%）
```

**Ensemble：**

```text
w_raw[i,t] = 0.5 · w_A[i,t] + 0.5 · w_G[i,t]     # 每周最多 7 只 ETF
```

#### 2.2 熊市滤波与资金管理

- **Market Gate**：`mkt_cum[t] > mean(mkt_cum[t-50w..t])` 时保留 `w_raw`；否则 **100% 切换至黄金 ETF（159934.SZ）**；
- **Vol Target**：`scale[t] = min(1.0, 0.15 / rolling_vol_26w[t])`，对总暴露做动态杠杆约束；
- **执行**：周五收盘计算信号，**下周一开盘价 + 单边 5bps 滑点** 执行调仓（`delay=1`）；
- **Universe**：34 只主题 ETF，按 9 组（科技成长 / 新能源 / 高端制造 / 大金融 / 大消费 / 周期资源 / 地产链 / 农业 / 红利）分类；每只 ETF 需上市满 **12 周** 才进入截面。

### 3. 回测结果

> **工程纪律声明**：参数仅在 **IS 2019–2023** 上选择，OOS 2024–2026 **严格只读**；所有指标扣除单边 5bps 滑点，周度调仓。

| 核心指标 | IS（2019–2023） | **OOS（2024–2026）** | **全样本（2019–2026.4）** |
| --- | ---: | ---: | ---: |
| **年化收益** | 26.70% | **34.91%** | **28.57%** |
| **Sharpe 比率** | 1.93 | **2.04** | **1.91** |
| **Sortino 比率** | 2.85 | 4.26 | 3.31 |
| **Calmar 比率** | 2.73 | 4.51 | 3.21 |
| **最大回撤** | -8.89% | -7.73% | **-8.89%** |
| **周胜率** | 60.9% | 55.5% | 60.5% |

> 9 年里 **8 年 Sharpe ≥ 0.8**，唯一弱年是 2022（熊市全年基本持黄金 +7.8%）。完整指标表与交易流水见 `results/` 目录。

### 4. 仓库结构

```text
A-Share-ETF-Rotation-Strategy-2.0/
├─ scripts/       # 工程化核心源码（拉数 / 构面板 / 回测 / 实盘选股 / 统计）
│  ├─ 01_fetch_data.py
│  ├─ 02_build_panel.py
│  ├─ 03_run_strategy.py
│  ├─ 04_latest_picks.py
│  └─ 05_full_stats.py
├─ research/      # 10 轮研究历程，每轮一份独立 markdown 复盘
├─ results/       # [输出目录] 指标 JSON / 分年 / 回撤明细 / 持仓 / 周频 PnL / 净值
├─ STRATEGY.md    # V7_gold 详细定义（信号、门控、资金管理的数学描述）
├─ CHANGELOG.md   # 10 轮研究历程的变更摘要
└─ requirements.txt
```

推荐阅读路径：`README.md` → `STRATEGY.md` → `scripts/` → `results/` → `research/`

### 5. 核心流程

主入口为 `scripts/03_run_strategy.py`：

1. `01_fetch_data.py`：由 Tushare 拉取 34 主题 ETF + 黄金 ETF 行情，自动缓存至 `data_cache/`；
2. `02_build_panel.py`：构造周频截面面板（mom / turn / breadth / group_mom 等因子）；
3. `03_run_strategy.py`：执行 V7_gold 回测（Leg A + Leg G + Gate + Vol Target），输出全量指标与净值；
4. `04_latest_picks.py`：基于最新一周数据，输出 **下周一应调至的目标持仓**（实盘清单）；
5. `05_full_stats.py`：分年 / 回撤明细 / 周胜率等扩展指标计算。

### 6. 快速开始

#### 6.1 安装依赖

```bash
pip install -r requirements.txt
# 或最小依赖：pandas numpy tushare pyarrow
```

#### 6.2 设置 Tushare Token

本项目严格遵守安全规范，**不会将 Token 硬编码在仓库中**。

**Linux / macOS：**
```bash
export TUSHARE_TOKEN="your_tushare_pro_token"
```

**Windows PowerShell：**
```powershell
$env:TUSHARE_TOKEN="your_tushare_pro_token"
```

#### 6.3 运行完整回测

```bash
python scripts/01_fetch_data.py      # 拉取行情（首次运行）
python scripts/02_build_panel.py     # 构造周频面板
python scripts/03_run_strategy.py    # 回测 V7_gold
python scripts/05_full_stats.py      # 扩展统计
```

输出将落在 `results/`：`metrics.json` / `peryear.csv` / `drawdowns.csv` / `holdings.csv` / `pnl.csv` / `equity_curve.csv`。

#### 6.4 实盘下周持仓生成

```bash
python scripts/04_latest_picks.py
```

根据最新一周数据直接输出下周一开盘应调至的目标持仓清单。

### 7. 策略优势与特点

- **双腿 Ensemble 抗噪**：Leg A（单 ETF 层）+ Leg G（板块层）互补，降低单标的噪声；
- **拥挤惩罚显式建模**：用换手率 z-score 主动规避「过热赛道熄火」风险；
- **真正的反周期 fallback**：黄金是全局熊市中唯一稳定的 long-vol 资产（2022 A 股 -22% / 黄金 +9.2%；2024 美联储转向 +23%）；
- **IS/OOS 纪律严格**：全部参数在 IS 2019-2023 上选择，OOS 只读，避免回测过拟合；
- **工程白盒**：纯 pandas/numpy 实现，无 Backtrader / Zipline 重型框架依赖。

### 8. 现有局限性

- **2020 COVID 急跌无法完全规避**（-8.89%）：50 周 MA 慢 gate 对 4 周内的急跌反应偏慢；
- **OOS 高 Sharpe 包含黄金 β**：2024-2025 金价 +23% 贡献了可观部分，长期预期 Sharpe 更接近 **1.4–1.7**；
- **Long-beta 增强而非 market-neutral**：牛市表现好，熊市靠三重防御（gate + 黄金 + vol target），但不做空；
- **样本不含 2018 深熊**：2018 A 股 -25% 场景下策略表现未知；
- **主题 ETF 样本较短**：部分 2021+ 才上市，早期样本偏薄。

### 9. 后续优化方向

- **快 Gate（Fast Gate）**：在 50 周慢 gate 之外叠加 vol-expansion 快触发，参见 `research/06_fast_gate.md` 的 V7_gb7030_FG4 变体；
- **国债 fallback 混合**：gb7030（70% 黄金 + 30% 国债）在 2022 熊市有进一步 Pareto 改进；
- **目标波动率替代硬仓位上限**：用 realized vol 反向调节总杠杆；
- **实盘接口对接**：对齐至 vnpy / qmt 进行小资金灰度测试。

### 10. 项目贡献声明

本策略代码从底层数据对齐、因子组装、多腿 Ensemble、熊市 gate、vol target 到实盘选股均为手写构建，**未依赖 Backtrader / Zipline 等重型闭源/遗留框架**，所有细节白盒透明，适合作为 A 股主题 ETF 策略研究与二次开发的脚手架。

### 11. 策略来源与参考文献

1. **时间序列动量（Time-Series Momentum）**：Moskowitz, Ooi, & Pedersen (2012) *"Time Series Momentum"*，奠定了中期绝对动量的交易合理性。
2. **截面动量与拥挤惩罚**：Jegadeesh & Titman (1993) *"Returns to Buying Winners and Selling Losers"*；Lou & Polk (2013) *"Comomentum: Inferring Arbitrage Activity from Return Correlations"* 关于拥挤度对动量衰减的定价。
3. **板块轮动（Sector Rotation）**：Faber (2007) *"A Quantitative Approach to Tactical Asset Allocation"*；Gray & Vogel (2016) 关于动量 + 风控结合的组合方法。
4. **波动率目标（Volatility Targeting）**：Moreira & Muir (2017) *"Volatility-Managed Portfolios"*。
5. **黄金避险属性**：Baur & Lucey (2010) *"Is Gold a Hedge or a Safe Haven?"*。

### 12. 引用与开源许可

如果本项目对您的量化研究有帮助，欢迎引用：

```bibtex
@software{v7_gold_2026,
  title  = {A-Share ETF Rotation Strategy 2.0 — V7_gold: Momentum × Crowding Penalty × Group Rotation with Gold Fallback},
  author = {Derick Hu},
  year   = {2026},
  url    = {https://github.com/huyukun662-crypto/A-Share-ETF-Rotation-Strategy-2.0}
}
```

本项目基于 [MIT License](LICENSE) 开源。

---

<a id="en"></a>

## English

Current language: English | [切换到中文](#zh)

> A **low-frequency, rules-based, reproducible** weekly sector rotation quant project over **34 A-share thematic ETFs** (V7_gold).
> The strategy combines **momentum × crowding penalty × group rotation ensemble**, with a **50-week MA bear filter**, a **gold-ETF defensive fallback**, and **15% annualized volatility targeting**. Parameters are strictly tuned on IS (2019-2023) and evaluated on a held-out OOS window (2024-2026).

<p align="center">
  <a href="#1-overview">Overview</a> •
  <a href="#3-backtest-results">Results</a> •
  <a href="#6-quick-start">Quick Start</a> •
  <a href="#11-references--sources">References</a>
</p>

> **OOS Highlights (2024–2026)**: Sharpe **2.04** · Annualized **34.91%** · Max Drawdown **-7.73%** · Calmar **4.51**.
> **Full sample (2019-01 → 2026-04, 377 weeks)**: Sharpe **1.91** · Annualized **28.57%** · Max Drawdown **-8.89%** · Calmar **3.21**.

### 1. Overview

In the highly retail-driven A-share market where sector rotation is fast and brutal (new energy → semis → dividend → commodities → AI), a single broad-based ETF cannot capture shifting themes, while discretionary stock picking faces high information costs.

This repository implements a middle ground: **a rules-based ETF rotation model with crowding penalty and a bear-market cash-out gate**.

Core philosophy:

- **Leg A** scores ETFs by **momentum minus crowding**, avoiding overheated themes (2021 liquor, 2023 CPO);
- **Leg G** performs **9-group sector rotation**, picking leaders in top themes to cut single-ETF noise;
- **50-week MA gate** switches **100% into gold ETF (159934.SZ)** when the aggregate market breaks long-term trend;
- **15% volatility target** dynamically scales total exposure for tail-risk control.

### 2. Strategy Logic

#### 2.1 Cross-Sectional Scoring (Dual-Leg Ensemble)

**Leg A — penalized single-ETF score:**

| Factor | Formula | Meaning |
| --- | --- | --- |
| `mom_4w` | 4-week cumulative return | Short-to-mid-term absolute momentum |
| `turn_4w` | 4-week avg turnover (amount / mkt cap) | Crowding proxy |
| `breadth` | 52w z-score of % universe above MA20 | Macro breadth adjustment |
| `score_A` | `z_cs(mom_4w) − 1.5·z_cs(turn_4w) + 0.3·breadth` | Equal-weight top-4 (25% each) |

**Leg G — 9-group rotation:**

```text
group_mom_4w[g,t] = equal-weight avg 4w return within group
top-3 groups      = argmax(group_mom_4w)[:3]
for g in top-3: pick top-1 ETF by 4w mom inside group
w_G = equal-weight top-3 leaders (33.3% each)
```

**Ensemble:**

```text
w_raw[i,t] = 0.5 · w_A[i,t] + 0.5 · w_G[i,t]   # at most 7 ETFs/week
```

#### 2.2 Bear-Market Filter & Capital Management

- **Market Gate**: keep `w_raw` if `mkt_cum[t] > mean(mkt_cum[t-50w..t])`; otherwise **100% switch into gold ETF (159934.SZ)**;
- **Vol Target**: `scale[t] = min(1.0, 0.15 / rolling_vol_26w[t])`, scales total exposure;
- **Execution**: signals computed Friday close; executed at **Monday open + 5bps one-way slippage** (`delay=1`);
- **Universe**: 34 thematic ETFs across 9 groups (tech growth / new energy / advanced manufacturing / financials / consumer / cyclicals / real-estate chain / agri / dividend); each ETF must have ≥12 weeks of history to enter the cross section.

### 3. Backtest Results

> **Discipline**: parameters are selected ONLY on IS 2019–2023; OOS 2024–2026 is strictly read-only. All metrics include 5bps one-way slippage, weekly rebalance.

| Metric | IS (2019–2023) | **OOS (2024–2026)** | **Full (2019–2026.4)** |
| --- | ---: | ---: | ---: |
| **Annual Return** | 26.70% | **34.91%** | **28.57%** |
| **Sharpe Ratio** | 1.93 | **2.04** | **1.91** |
| **Sortino Ratio** | 2.85 | 4.26 | 3.31 |
| **Calmar Ratio** | 2.73 | 4.51 | 3.21 |
| **Max Drawdown** | -8.89% | -7.73% | **-8.89%** |
| **Weekly Hit Rate** | 60.9% | 55.5% | 60.5% |

> Across 9 years, **8 years have Sharpe ≥ 0.8**; the only weak year is 2022 (mostly holding gold, +7.8%). See `results/` for full metric tables and trade logs.

### 4. Repository Structure

```text
A-Share-ETF-Rotation-Strategy-2.0/
├─ scripts/       # Core engineering code (fetch / build panel / backtest / live picks / stats)
│  ├─ 01_fetch_data.py
│  ├─ 02_build_panel.py
│  ├─ 03_run_strategy.py
│  ├─ 04_latest_picks.py
│  └─ 05_full_stats.py
├─ research/      # 10-round research journey, one markdown post-mortem per round
├─ results/       # [Output Dir] metrics JSON / per-year / drawdowns / holdings / weekly PnL / NAV
├─ STRATEGY.md    # Detailed V7_gold definitions (signals, gate, capital management)
├─ CHANGELOG.md   # Change summary across 10 research rounds
└─ requirements.txt
```

Recommended reading path: `README.md` → `STRATEGY.md` → `scripts/` → `results/` → `research/`

### 5. Core Pipeline

The main entry point is `scripts/03_run_strategy.py`:

1. `01_fetch_data.py`: fetch 34 thematic ETFs + gold ETF via Tushare, auto-cached in `data_cache/`;
2. `02_build_panel.py`: build weekly cross-sectional panel (mom / turn / breadth / group_mom);
3. `03_run_strategy.py`: run V7_gold backtest (Leg A + Leg G + Gate + Vol Target), output full metrics and NAV;
4. `04_latest_picks.py`: given the latest week, print the **target portfolio to rebalance into next Monday**;
5. `05_full_stats.py`: extended metrics (per-year, drawdown breakdown, weekly hit rate, etc.).

### 6. Quick Start

#### 6.1 Install Dependencies

```bash
pip install -r requirements.txt
# or minimal: pandas numpy tushare pyarrow
```

#### 6.2 Set Tushare Token

For security, **no tokens are hardcoded in the repository**.

**Linux / macOS:**
```bash
export TUSHARE_TOKEN="your_tushare_pro_token"
```

**Windows PowerShell:**
```powershell
$env:TUSHARE_TOKEN="your_tushare_pro_token"
```

#### 6.3 Run Full Backtest

```bash
python scripts/01_fetch_data.py      # fetch market data (first run)
python scripts/02_build_panel.py     # build weekly panel
python scripts/03_run_strategy.py    # backtest V7_gold
python scripts/05_full_stats.py      # extended stats
```

Outputs land in `results/`: `metrics.json` / `peryear.csv` / `drawdowns.csv` / `holdings.csv` / `pnl.csv` / `equity_curve.csv`.

#### 6.4 Live Weekly Picks

```bash
python scripts/04_latest_picks.py
```

Prints the target holdings to rebalance into at the next Monday open, based on the most recent week of data.

### 7. Strategic Advantages & Highlights

- **Dual-leg ensemble denoising**: Leg A (ETF-level) + Leg G (group-level) are complementary and cut single-name noise;
- **Explicit crowding penalty**: turnover z-score actively avoids overheated themes (2021 liquor / 2023 CPO burnout);
- **Genuinely counter-cyclical fallback**: gold is the only asset consistently long-vol during global equity bear markets (2022 A-shares -22% / gold +9.2%; 2024 Fed pivot / gold +23%);
- **Strict IS/OOS discipline**: all parameters chosen on IS 2019-2023; OOS read-only, no overfitting;
- **White-box engineering**: pure pandas/numpy, no dependency on Backtrader / Zipline or other heavy legacy frameworks.

### 8. Current Limitations

- **2020 COVID crash is not fully mitigated** (-8.89%): the 50-week MA gate is too slow for 4-week flash crashes;
- **OOS Sharpe includes gold β**: 2024-2025 gold +23% contributed materially; long-run expected Sharpe is closer to **1.4–1.7**;
- **Long-beta enhancement, not market-neutral**: great in bull markets, defended in bear markets via triple guardrails (gate + gold + vol target), but never shorts;
- **Sample does not include 2018 deep bear**: performance under a -25% A-share year is unknown;
- **Thematic ETF series are short**: many listed only after 2021, early sample is thin.

### 9. Future Optimizations

- **Fast Gate**: overlay a vol-expansion fast trigger on top of the 50w slow gate; see the V7_gb7030_FG4 variant in `research/06_fast_gate.md`;
- **Treasury fallback mix**: gb7030 (70% gold + 30% CGB) shows a further Pareto improvement in 2022;
- **Volatility targeting as a replacement for hard exposure caps**: inverse scaling on realized vol;
- **Live paper trading**: hook into open-source terminals (vnpy / qmt) for small-capital forward testing.

### 10. Contribution Statement

This strategy codebase—from data alignment, factor assembly, dual-leg ensemble, bear-market gate, vol targeting to live-picks export—is entirely custom-built. It intentionally avoids heavy, closed-source legacy frameworks like Backtrader or Zipline, ensuring full white-box transparency. It serves as an excellent scaffold for A-share thematic ETF strategy research and secondary development.

### 11. References & Sources

1. **Time-Series Momentum**: Moskowitz, Ooi, & Pedersen (2012) *"Time Series Momentum"*, establishing the trading validity of medium-term absolute momentum.
2. **Cross-sectional momentum & crowding penalty**: Jegadeesh & Titman (1993) *"Returns to Buying Winners and Selling Losers"*; Lou & Polk (2013) *"Comomentum: Inferring Arbitrage Activity from Return Correlations"* on how crowding erodes momentum payoff.
3. **Sector Rotation**: Faber (2007) *"A Quantitative Approach to Tactical Asset Allocation"*; Gray & Vogel (2016) on momentum with risk control.
4. **Volatility Targeting**: Moreira & Muir (2017) *"Volatility-Managed Portfolios"*.
5. **Gold as a safe haven**: Baur & Lucey (2010) *"Is Gold a Hedge or a Safe Haven?"*.

### 12. Citation & License

If this repository aids your quantitative research, please consider citing:

```bibtex
@software{v7_gold_2026,
  title  = {A-Share ETF Rotation Strategy 2.0 — V7_gold: Momentum × Crowding Penalty × Group Rotation with Gold Fallback},
  author = {Derick Hu},
  year   = {2026},
  url    = {https://github.com/huyukun662-crypto/A-Share-ETF-Rotation-Strategy-2.0}
}
```

This project is open-sourced under the [MIT License](LICENSE).
