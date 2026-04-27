# -*- coding: utf-8 -*-
"""V25 full sample trading log (中文标签 + Regime 状态 + 12 板块)
   V25 = V7 35-pool + V24 12-板块 + topk=4 + csi_all_acc (000985.CSI) regime"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from strategy_v25 import run_strategy

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'cache'
OUT = ROOT / 'docs' / 'roadshow'
OUT.mkdir(exist_ok=True)

V25_PARAMS = dict(
    mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12,
    top_k_groups=4, per_group=1,
    risk_adj_nu=0.4, rev_w=0.05,
    accel_w=0.10, longmom_window=13,
    regime_accel_signal='csi_all_acc',
    regime_accel_theta_on=0.05, regime_accel_theta_off=0.0,
    regime_accel_k_min=8,
    uni_path=CACHE / 'etf_universe_v24diag.csv',
    csi_path=CACHE / 'csi_all_weekly.parquet',
)

print('运行 V25 回测 ...')
res = run_strategy(**V25_PARAMS, return_full=True)
w_final = res['w_final']
scale = res['scale']
gate_on = res['gate_on']
pnl_net = res['pnl_net']
cost = res['cost']
uni = res['uni']
regime_log = res['regime_accel_log']

code2name = dict(zip(uni['ts_code'], uni['name']))
code2group = dict(zip(uni['ts_code'], uni['group']))

# 1. holdings
print('生成 holdings ...')
records = []
for t in w_final.index:
    nz = w_final.loc[t][w_final.loc[t] > 1e-5].sort_values(ascending=False)
    for c, w in nz.items():
        records.append({
            'trade_week': t.date().isoformat(),
            'ETF名称': code2name.get(c, '?'),
            'ts_code': c, '板块': code2group.get(c, '?'),
            '权重(%)': round(w*100, 2),
            'Gate': 'RISK-ON' if gate_on.get(t, False) else 'RISK-OFF',
            'Regime_csi': 'ON' if (regime_log is not None and regime_log.get(t, False)) else 'OFF',
            'scale': round(scale.get(t, 0), 4),
        })
hd = pd.DataFrame(records)
hd.to_csv(OUT / 'trading_log_v25_holdings.csv', index=False, encoding='utf-8-sig')

# 2. actions
print('生成 actions ...')
ar = []
prev = pd.Series(0.0, index=w_final.columns)
for t in w_final.index:
    cur = w_final.loc[t]
    d = cur - prev
    nz = d[d.abs() > 1e-4]
    for c, dw in nz.items():
        pp = prev[c]*100; cp = cur[c]*100
        if pp < 1e-3 and cp > 1e-3: action = '🟢 BUY'
        elif pp > 1e-3 and cp < 1e-3: action = '🔴 SELL'
        else: action = '🟡 REBAL'
        ar.append({
            'trade_week': t.date().isoformat(), '操作': action,
            'ETF名称': code2name.get(c, '?'), 'ts_code': c,
            '板块': code2group.get(c, '?'),
            '上周权重(%)': round(pp, 2), '本周权重(%)': round(cp, 2),
            'Δ权重(pp)': round(dw*100, 2),
            'Gate': 'RISK-ON' if gate_on.get(t, False) else 'RISK-OFF',
            'Regime_csi': 'ON' if (regime_log is not None and regime_log.get(t, False)) else 'OFF',
        })
    prev = cur.copy()
ad = pd.DataFrame(ar)
ad.to_csv(OUT / 'trading_log_v25_actions.csv', index=False, encoding='utf-8-sig')

# 3. summary
print('生成 summary ...')
nav = (1 + pnl_net.fillna(0)).cumprod()
prev = pd.Series(0.0, index=w_final.columns)
sr = []
for t in w_final.index:
    cur = w_final.loc[t]
    delta = (cur - prev).abs().sum() / 2
    nz = cur[cur > 1e-5]
    grp_w = {}
    for c, wt in nz.items():
        g = code2group.get(c, '?')
        grp_w[g] = grp_w.get(g, 0) + wt
    top_grp = max(grp_w, key=grp_w.get) if grp_w else '—'
    sr.append({
        'trade_week': t.date().isoformat(),
        'Gate': 'RISK-ON' if gate_on.get(t, False) else 'RISK-OFF',
        'Regime_csi': 'ON' if (regime_log is not None and regime_log.get(t, False)) else 'OFF',
        'scale': round(scale.get(t, 0), 4),
        '持仓数': int((cur > 1e-5).sum()),
        '总仓位(%)': round(cur.sum()*100, 2),
        '换手率(%)': round(delta*100, 2),
        '主导板块': top_grp,
        '主导板块权重(%)': round(grp_w.get(top_grp, 0)*100, 2),
        '周收益(%)': round(pnl_net.get(t, 0)*100, 4),
        '成本(bps)': round(cost.get(t, 0)*1e4, 2),
        'NAV': round(nav.get(t, 1), 4),
    })
    prev = cur.copy()
sd = pd.DataFrame(sr)
sd.to_csv(OUT / 'trading_log_v25_summary.csv', index=False, encoding='utf-8-sig')

# 速览
print('\n=== V25 Trading Log 统计速览 ===')
print(f'  样本: {sd["trade_week"].iloc[0]} → {sd["trade_week"].iloc[-1]}')
print(f'  总周数: {len(sd)}')
print(f'  Gate RISK-ON 占比: {(sd["Gate"]=="RISK-ON").mean()*100:.1f}%')
print(f'  Regime CSI ON 占比: {(sd["Regime_csi"]=="ON").mean()*100:.1f}%')
print(f'  平均持仓: {sd["持仓数"].mean():.1f} 只')
print(f'  平均总仓位: {sd["总仓位(%)"].mean():.2f}%')
print(f'  平均周换手: {sd["换手率(%)"].mean():.2f}%')
print(f'  最终 NAV: {sd["NAV"].iloc[-1]:.3f}×')
buys = (ad['操作'].str.contains('BUY')).sum()
sells = (ad['操作'].str.contains('SELL')).sum()
rebs = (ad['操作'].str.contains('REBAL')).sum()
print(f'  操作: BUY {buys} / SELL {sells} / REBAL {rebs}')

print('\n=== Regime / Gate 联合状态分布 ===')
combo = sd.groupby(['Gate', 'Regime_csi']).size().reset_index(name='周数')
combo['占比'] = (combo['周数'] / len(sd) * 100).round(1)
print(combo.to_string(index=False))

print('\n=== 主导板块占比（按周）===')
grp_dist = sd['主导板块'].value_counts(normalize=True) * 100
print(grp_dist.round(1).to_string())

print('\n=== 文件 ===')
print(f'  {OUT/"trading_log_v25_holdings.csv"}: {len(hd)} 行')
print(f'  {OUT/"trading_log_v25_actions.csv"}: {len(ad)} 行')
print(f'  {OUT/"trading_log_v25_summary.csv"}: {len(sd)} 行')
