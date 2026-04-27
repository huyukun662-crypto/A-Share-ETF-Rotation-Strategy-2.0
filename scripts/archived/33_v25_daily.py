# -*- coding: utf-8 -*-
"""V25 日频原型: 把 V25 周频结构 1:1 映射到日频
   窗口映射: 4w→20d / 13w→65d / 26w vol→130d / 1w rev→5d / 50w gate MA→250d
   规则: daily 调仓 + daily 5bps 单边成本
   对比: V25 周频 baseline"""
import os, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V7_ROOT = Path(__file__).resolve().parents[2] / 'A-Share-ETF-Rotation-Strategy-2.0'
CACHE = ROOT / 'data_cache'

DAILY_PATH = V7_ROOT / 'data_cache' / 'fund_daily_34.parquet'
UNI_PATH = CACHE / 'etf_universe_v24diag.csv'
SAMPLE_START = '2019-01-01'
GOLD = '159934.SZ'
COST_BPS = 5

# === 日频窗口（× 5 from 周频）===
MOM_W = 20            # 4w
LONGMOM_W = 65        # 13w
VOL_W = 130           # 26w
TURN_W = 20           # 4w
REV_W = 5             # 1w
GATE_MA = 250         # 50w
CSI_SHORT = 20
CSI_LONG = 65
CSI_KMIN = 8          # k_min 直接保留 8 (个观察点 = 8 个交易日)
CSI_THETA_ON = 0.05

LAM = 1.5
NU = 0.4
RW_REV = 0.05
ACCEL_W = 0.10
TOP_N_A = 4
TOP_K_GROUPS = 4
PER_GROUP = 1
VOL_TARGET = 0.12
SCALE_LOWER = 0.0

print('=== Phase 1: 加载日频数据 ===')
d = pd.read_parquet(DAILY_PATH)
d['trade_date'] = pd.to_datetime(d['trade_date'])
d = d[d['trade_date'] >= '2017-01-01'].sort_values(['trade_date', 'ts_code']).reset_index(drop=True)
uni = pd.read_csv(UNI_PATH, encoding='utf-8')
codes = list(uni['ts_code'])
d = d[d['ts_code'].isin(codes)].copy()

# 复权 close (前面已用 close 直接，这里 V7 数据 close 即不复权 — 用 pct_chg 重建复权链)
# pct_chg 已是日 pct (%), 转 ret
d['ret_d'] = d['pct_chg'] / 100.0
ret = d.pivot(index='trade_date', columns='ts_code', values='ret_d').sort_index()
turn = d.pivot(index='trade_date', columns='ts_code', values='vol').sort_index()  # 用成交量代理 turnover
ret = ret.reindex(columns=codes)
turn = turn.reindex(columns=codes)
ret = ret[ret.index >= '2017-01-01']
cum = (1 + ret.fillna(0)).cumprod()
print(f'  ret shape: {ret.shape} / {ret.index.min().date()} -> {ret.index.max().date()}')

# CSI 000985 daily
csi_path = CACHE / 'csi_all_weekly.parquet'
# 我们没存 csi daily, 用 weekly forward-fill 到 daily 是次优, 改抓
print('  抓 CSI 000985 日线 ...')
os.environ['TUSHARE_TOKEN'] = 'ddd1b26b20ff085ac9b60c9bd902ae76bbff60910863e8cc0168da53'
import tushare as ts
ts.set_token(os.environ['TUSHARE_TOKEN'])
pro = ts.pro_api()
csi_d = pro.index_daily(ts_code='000985.CSI', start_date='20170101', end_date='20260430')
csi_d['trade_date'] = pd.to_datetime(csi_d['trade_date'])
csi_d = csi_d.sort_values('trade_date').set_index('trade_date')
csi_close = csi_d['close']
print(f'  CSI daily {len(csi_close)} 行')

# === Phase 2: 因子计算 ===
print('=== Phase 2: 因子计算 (日频) ===')
mom20 = cum.pct_change(MOM_W)
mom65 = cum.pct_change(LONGMOM_W)
accel = mom20 - mom65
vol_d = ret.rolling(VOL_W, min_periods=int(VOL_W*0.5)).std() * np.sqrt(252)
turn_avg = turn.rolling(TURN_W).mean()
rev5 = ret.rolling(REV_W).sum()
ria = mom20 - NU * ((vol_d - vol_d.mean(axis=1).values.reshape(-1,1)) / vol_d.std(axis=1).values.reshape(-1,1))

# z-score helper (cross-sectional)
def zcs(df):
    m = df.mean(axis=1); s = df.std(axis=1).replace(0, np.nan)
    return df.sub(m, axis=0).div(s, axis=0)

# regime CSI
csi_close = csi_close.reindex(ret.index, method='ffill')
csi_acc = (csi_close.pct_change(CSI_SHORT) - csi_close.pct_change(CSI_LONG)).shift(1)
regime_on = (csi_acc.rolling(CSI_KMIN).min() >= CSI_THETA_ON)

# breadth (proportion above MA20)
ma20 = cum.rolling(MOM_W).mean()
breadth_per = (cum > ma20).astype(float)
breadth = breadth_per.mean(axis=1)
breadth_z = (breadth - breadth.rolling(60, min_periods=20).mean()) / breadth.rolling(60, min_periods=20).std()

# Leg A score
score_A = zcs(mom20) - LAM * zcs(turn_avg) + 0.3 * breadth_z.values.reshape(-1,1)
score_A = score_A + NU * zcs(ria) - RW_REV * zcs(rev5)
# regime-conditional accel
score_A = score_A.add(ACCEL_W * zcs(accel).where(regime_on, 0).fillna(0), fill_value=0)
score_A = score_A.shift(1)  # t-1 信号 → t 执行

# Leg G: 12 板块 mom
group_map = dict(zip(uni['ts_code'], uni['group']))
groups = sorted(set(group_map.values()))
group_mom = pd.DataFrame(index=mom20.index, columns=groups, dtype=float)
for g in groups:
    members = [c for c in codes if group_map[c] == g]
    group_mom[g] = mom20[members].mean(axis=1)
group_mom = group_mom.shift(1)

# Gate: 黄金 250d MA (vs cum)
if GOLD in cum.columns:
    gold_cum = cum[GOLD]
    gold_ma = gold_cum.rolling(GATE_MA).mean()
    gate_on = (gold_cum > gold_ma).shift(1).fillna(False)
else:
    gate_on = pd.Series(True, index=cum.index)

# === Phase 3: 每日构建权重 ===
print('=== Phase 3: 每日构建权重 ===')
date_idx = ret.index[ret.index >= SAMPLE_START]
score_A = score_A.reindex(date_idx)
group_mom = group_mom.reindex(date_idx)
gate_on = gate_on.reindex(date_idx).fillna(False)
regime_on_idx = regime_on.reindex(date_idx).fillna(False)

w_raw = pd.DataFrame(0.0, index=date_idx, columns=codes)
for t in date_idx:
    sc = score_A.loc[t].dropna()
    if len(sc) < TOP_N_A:
        continue
    # Leg A: top_n_a
    leg_a = sc.nlargest(TOP_N_A).index.tolist()
    # Leg G: top_k_groups by group_mom, per_group=1 by score_A
    gm = group_mom.loc[t].dropna()
    if len(gm) < TOP_K_GROUPS:
        leg_g = []
    else:
        top_grps = gm.nlargest(TOP_K_GROUPS).index.tolist()
        leg_g = []
        for g in top_grps:
            cands = [c for c in codes if group_map[c] == g and c in sc.index]
            if cands:
                pick = sc.loc[cands].idxmax()
                leg_g.append(pick)
    # 合并 (Leg A weight 1/2, Leg G weight 1/2 normalized)
    holdings = list(set(leg_a) | set(leg_g))
    if not holdings:
        continue
    # 等权两个 leg 分别 0.5
    wa = pd.Series(0.0, index=codes)
    wg = pd.Series(0.0, index=codes)
    if leg_a: wa[leg_a] = 1.0 / len(leg_a)
    if leg_g: wg[leg_g] = 1.0 / len(leg_g)
    w_raw.loc[t] = (0.5 * wa + 0.5 * wg).values

# Gate: defense → 黄金单仓
w_gated = w_raw.copy()
for t in date_idx:
    if not gate_on.get(t, False):
        w_gated.loc[t] = 0.0
        if GOLD in w_gated.columns:
            w_gated.at[t, GOLD] = 1.0

# vol target
port_ret_raw = (w_gated.shift(1) * ret).sum(axis=1)
realized_vol = port_ret_raw.rolling(VOL_W, min_periods=int(VOL_W*0.5)).std() * np.sqrt(252)
scale = (VOL_TARGET / realized_vol.replace(0, np.nan)).clip(lower=SCALE_LOWER, upper=1.0).fillna(1.0)
w_final = w_gated.mul(scale, axis=0)

# 成本
turnover = (w_final - w_final.shift(1).fillna(0)).abs().sum(axis=1)
cost = turnover * (COST_BPS / 1e4)
pnl_gross = (w_final.shift(1) * ret).sum(axis=1)
pnl_net = (pnl_gross - cost).loc[SAMPLE_START:]
turnover = turnover.loc[SAMPLE_START:]
cost = cost.loc[SAMPLE_START:]

# === 变体B: turnover band (只在权重变化 > 50bp 时实际调) ===
BAND = 0.005  # 50bp threshold per name
w_held = w_final.copy()
prev = pd.Series(0.0, index=codes)
for t in w_held.index:
    target = w_final.loc[t]
    diff = (target - prev).abs()
    keep_old = diff < BAND
    actual = target.copy()
    actual[keep_old] = prev[keep_old]
    w_held.loc[t] = actual
    prev = actual.copy()
turnover_b = (w_held - w_held.shift(1).fillna(0)).abs().sum(axis=1)
cost_b = turnover_b * (COST_BPS / 1e4)
pnl_b = ((w_held.shift(1) * ret).sum(axis=1) - cost_b).loc[SAMPLE_START:]
turnover_b = turnover_b.loc[SAMPLE_START:]

# === Phase 4: 统计 ===
def stats_d(r):
    r = r.dropna()
    if len(r) < 2: return dict(n=0, sharpe=np.nan, ann=np.nan, mdd=np.nan, calmar=np.nan)
    nav = (1 + r).cumprod()
    ann = nav.iloc[-1] ** (252/len(r)) - 1
    sd = r.std() * np.sqrt(252)
    sh = ann / sd if sd > 0 else np.nan
    dd = (nav / nav.cummax() - 1).min()
    cal = ann / abs(dd) if dd < 0 else np.nan
    return dict(n=len(r), sharpe=sh, ann=ann, mdd=dd, calmar=cal)

def seg(r):
    return dict(
        Full=stats_d(r),
        IS=stats_d(r[r.index <= '2022-12-31']),
        OOS=stats_d(r[r.index >= '2024-01-01']),
    )

ssA = seg(pnl_net)
ssB = seg(pnl_b)
print(f'\n=== V25 日频结果 (sample {pnl_net.index.min().date()} → {pnl_net.index.max().date()}, {len(pnl_net)} 交易日) ===')
print('[A] 全日频调仓 (无容差)')
print(f'{"段":<6} {"Sh":>8} {"年化":>10} {"DD":>10} {"Cal":>8}')
for s in ['Full','IS','OOS']:
    print(f'{s:<6} {ssA[s]["sharpe"]:>8.3f} {ssA[s]["ann"]*100:>9.2f}% {ssA[s]["mdd"]*100:>9.2f}% {ssA[s]["calmar"]:>8.2f}')
print('\n[B] 日频信号 + 50bp 容差 (减少抖动)')
print(f'{"段":<6} {"Sh":>8} {"年化":>10} {"DD":>10} {"Cal":>8}')
for s in ['Full','IS','OOS']:
    print(f'{s:<6} {ssB[s]["sharpe"]:>8.3f} {ssB[s]["ann"]*100:>9.2f}% {ssB[s]["mdd"]*100:>9.2f}% {ssB[s]["calmar"]:>8.2f}')

# === V25 周频对照（cached）===
print('\n=== 对照: V25 周频 baseline (V22_REF) ===')
print(f'{"段":<6} {"Sh":>8} {"年化":>10} {"DD":>10} {"Cal":>8}')
print(f'{"Full":<6} {2.002:>8.3f} {25.83:>9.2f}% {-8.23:>9.2f}% {3.14:>8.2f}')
print(f'{"OOS":<6}  {2.189:>8.3f} {31.50:>9.2f}% {-5.49:>9.2f}% {5.74:>8.2f}')

years = len(pnl_net) / 252
print(f'\n[A] 总换手 = {turnover.sum():.1f}× / 年换手 = {turnover.sum()/years:.1f}× / 年成本 = {cost.sum()/years*100:.2f}%')
print(f'[B] 总换手 = {turnover_b.sum():.1f}× / 年换手 = {turnover_b.sum()/years:.1f}× / 年成本 = {turnover_b.sum()*COST_BPS/1e4/years*100:.2f}%')
print(f'平均日权重和: {w_final.sum(axis=1).mean():.3f}')
print(f'Gate ON 比例: {gate_on.mean()*100:.1f}%')
print(f'Regime CSI ON 比例: {regime_on_idx.mean()*100:.1f}%')

# 保存
out = pd.DataFrame({'pnl_net': pnl_net, 'pnl_gross': pnl_gross, 'cost': cost,
                     'scale': scale, 'gate_on': gate_on, 'regime_on': regime_on_idx,
                     'turnover': turnover})
out.to_csv(ROOT / 'results' / 'v25_daily_pnl.csv', encoding='utf-8-sig')
print(f'\n[saved] results/v25_daily_pnl.csv')
