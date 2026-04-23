# 复刻推送到 A-Share-ETF-Rotation-Strategy-2.0 的操作

目录 `/home/user/Factor_Zoo/deploy/A-Share-ETF-Rotation-Strategy-2.0/` 下是完整的项目,可以**直接作为独立 repo** 推到 `huyukun662-crypto/A-Share-ETF-Rotation-Strategy-2.0`。

## 最短路径(3 步)

```bash
# 1. 克隆目标空仓库(只有 LICENSE)
git clone https://github.com/huyukun662-crypto/A-Share-ETF-Rotation-Strategy-2.0.git
cd A-Share-ETF-Rotation-Strategy-2.0

# 2. 从 Factor_Zoo 拷贝所有文件(LICENSE 已存在,跳过)
cp -r /path/to/Factor_Zoo/deploy/A-Share-ETF-Rotation-Strategy-2.0/* .
cp -r /path/to/Factor_Zoo/deploy/A-Share-ETF-Rotation-Strategy-2.0/.gitignore .

# 3. 提交并推送
git add -A
git commit -m "Initial release: V7_gold — A-Share ETF Rotation Strategy 2.0"
git push origin main
```

## 项目结构

```
A-Share-ETF-Rotation-Strategy-2.0/
├── .gitignore
├── LICENSE                  (MIT,已含)
├── README.md                (顶层介绍 + 架构图 + quick start)
├── STRATEGY.md              (V7_gold 完整 factor card)
├── CHANGELOG.md             (10 轮研究历程)
├── requirements.txt         (pandas/numpy/tushare/pyarrow/scipy)
├── scripts/
│   ├── 01_fetch_data.py     (拉 34 ETF + 黄金,需要 TUSHARE_TOKEN)
│   ├── 02_build_panel.py    (构造周频面板)
│   ├── 03_run_strategy.py   (端到端回测 V7_gold)
│   └── 04_latest_picks.py   (最新一周目标持仓)
├── research/
│   ├── 01_sw_l1_baseline.md       (Round 1-3)
│   ├── 02_etf_universe_pivot.md   (Round 4-5)
│   ├── 03_rolling_robustness.md   (Round 6)
│   ├── 04_fallback_exploration.md (Round 7-8)
│   └── 05_bond_and_fast_gate.md   (Round 9-10)
├── results/
│   ├── peryear.csv          (8 年逐年)
│   ├── drawdowns.csv        (top-5 drawdown)
│   ├── holdings.csv         (持仓分布)
│   ├── monthly.csv          (月度收益)
│   ├── pnl.csv              (周频净值)
│   ├── sortino_comparison.json  (V7_gold vs V7_gb7030_FG4)
│   └── v3_v7_full_stats.json    (完整指标)
└── data_cache/              (tushare 缓存,空目录,运行时填充)
```

## 回测头条指标

- **Sharpe 1.91 · Sortino 3.31 · Calmar 3.21 · MaxDD -8.89% · AnnRet 28.57%**
- 样本 2019-01 → 2026-04(377 周),staggered join,delay=1,5bps/side
- 8/9 年 Sharpe ≥ 0.8(2022 熊市全年基本持黄金 +7.8%)
