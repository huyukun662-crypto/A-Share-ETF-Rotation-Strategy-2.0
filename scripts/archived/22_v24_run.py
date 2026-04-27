# -*- coding: utf-8 -*-
"""V24 Phase 4: 池子重组 (49 / 15) + Regime 信号升级 (csi_all_acc) 回测
   对比矩阵：
     A. V22 baseline (V7 35 池 + hs300_acc + top_k=3)
     B. V24 池 + V22 因子 + hs300_acc + top_k=3 (孤立池子效应)
     C. V24 池 + V22 因子 + csi_all_acc + top_k=3 (孤立信号效应)
     D. V24 池 + V22 因子 + csi_all_acc + top_k=4 (主推方案)
   对每个组合输出 IS/Val/OOS/Full + 八维 vs V7_gold + WF 5 折
"""
import json, sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strategy_v15 import run_strategy, segment_stats, stats

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data_cache'
OUT = ROOT / 'results'
OUT.mkdir(exist_ok=True)

V24_UNI = CACHE / 'etf_universe_v24.csv'
V24_WK = CACHE / 'etf_weekly_v24.parquet'
CSI_PATH = CACHE / 'csi_all_weekly.parquet'

V7 = dict(full_sh=1.915, full_ann=0.2467, full_dd=-0.0818, full_cal=3.01,
          oos_sh=2.029, oos_ann=0.2907, oos_dd=-0.0609, oos_cal=4.77)

P_BASE = dict(mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12,
              per_group=1, risk_adj_nu=0.4, rev_w=0.05,
              accel_w=0.10, longmom_window=13,
              regime_accel_theta_on=0.05, regime_accel_theta_off=0.0,
              regime_accel_k_min=8)

VARIANTS = [
    dict(label='A V22 baseline (V7 池 + hs300_acc + topk=3)',
         top_k_groups=3, regime_accel_signal='hs300_acc'),
    dict(label='B V24 池 + hs300_acc + topk=3',
         top_k_groups=3, regime_accel_signal='hs300_acc',
         weekly_path=V24_WK, uni_path=V24_UNI),
    dict(label='C V24 池 + csi_all_acc + topk=3',
         top_k_groups=3, regime_accel_signal='csi_all_acc',
         weekly_path=V24_WK, uni_path=V24_UNI, csi_path=CSI_PATH),
    dict(label='D V24 池 + csi_all_acc + topk=4 (主推)',
         top_k_groups=4, regime_accel_signal='csi_all_acc',
         weekly_path=V24_WK, uni_path=V24_UNI, csi_path=CSI_PATH),
]

def beats_v7(r):
    return all([r['Full_Sh']>=V7['full_sh'], r['Full_ann']>=V7['full_ann'],
                  r['Full_dd']>=V7['full_dd'], r['Full_cal']>=V7['full_cal'],
                  r['OOS_Sh']>=V7['oos_sh'], r['OOS_ann']>=V7['oos_ann'],
                  r['OOS_dd']>=V7['oos_dd'], r['OOS_cal']>=V7['oos_cal']])

print('=' * 78)
print('V24 池子+信号双变量对比扫描')
print('=' * 78)
rows, regime_pcts = [], {}
for v in VARIANTS:
    label = v.pop('label')
    print(f'\n--- {label} ---')
    res = run_strategy(**P_BASE, **v, return_full=True)
    pnl = res['pnl_net']
    ss = segment_stats(pnl)
    reg = res.get('regime_accel_log')
    on_pct = float(reg.mean()) if reg is not None else 1.0
    n_switch = int((reg != reg.shift(1)).sum()) if reg is not None else 0
    regime_pcts[label] = (on_pct, n_switch)
    row = dict(label=label,
        IS_Sh=round(ss['IS']['sharpe'], 3), Val_Sh=round(ss['Val']['sharpe'], 3),
        OOS_Sh=round(ss['OOS']['sharpe'], 3), OOS_ann=round(ss['OOS']['ann'], 4),
        OOS_dd=round(ss['OOS']['mdd'], 4), OOS_cal=round(ss['OOS']['calmar'], 2),
        Full_Sh=round(ss['Full']['sharpe'], 3), Full_ann=round(ss['Full']['ann'], 4),
        Full_dd=round(ss['Full']['mdd'], 4), Full_cal=round(ss['Full']['calmar'], 2),
        regime_on_pct=round(on_pct, 3), n_switch=n_switch,
        beats_V7=beats_v7({'Full_Sh': ss['Full']['sharpe'], 'Full_ann': ss['Full']['ann'],
                              'Full_dd': ss['Full']['mdd'], 'Full_cal': ss['Full']['calmar'],
                              'OOS_Sh': ss['OOS']['sharpe'], 'OOS_ann': ss['OOS']['ann'],
                              'OOS_dd': ss['OOS']['mdd'], 'OOS_cal': ss['OOS']['calmar']}))
    rows.append(row)
    print(f'  IS Sh={row["IS_Sh"]} Val={row["Val_Sh"]} OOS={row["OOS_Sh"]} (ann={row["OOS_ann"]*100:+.2f}%, dd={row["OOS_dd"]*100:.2f}%, Cal={row["OOS_cal"]})')
    print(f'  Full Sh={row["Full_Sh"]} ann={row["Full_ann"]*100:+.2f}% dd={row["Full_dd"]*100:.2f}% Cal={row["Full_cal"]}')
    print(f'  Regime ON {on_pct*100:.1f}% / 切换 {n_switch} 次 / 八维全超 V7: {"✓" if row["beats_V7"] else "✗"}')

df = pd.DataFrame(rows)
df.to_csv(OUT / 'v24_variants.csv', index=False, encoding='utf-8-sig')

print('\n' + '=' * 78)
print('八维严格非劣 V7_gold 检查')
print('=' * 78)
print(df[['label', 'Full_Sh', 'Full_ann', 'Full_dd', 'Full_cal',
          'OOS_Sh', 'OOS_ann', 'OOS_dd', 'OOS_cal', 'beats_V7']].to_string(index=False))

# === WF 5 折：仅对主推 D ===
print('\n' + '=' * 78)
print('WF 5 折：D = V24 + csi_all_acc + topk=4')
print('=' * 78)

D_PARAMS = dict(top_k_groups=4, regime_accel_signal='csi_all_acc',
                  weekly_path=V24_WK, uni_path=V24_UNI, csi_path=CSI_PATH)
folds = [
    ('2021-12-31', '2022'),
    ('2022-12-31', '2023'),
    ('2023-12-31', '2024'),
    ('2024-12-31', '2025'),
    ('2025-12-31', '2026'),
]
TOPK_GRID = [3, 4, 5]
pnl_by_topk = {}
for k in TOPK_GRID:
    print(f'  跑 top_k={k}...', flush=True)
    pp = {**P_BASE, **D_PARAMS, 'top_k_groups': k}
    pnl_by_topk[k] = run_strategy(**pp)

wf_rows = []
for tr_end, te_year in folds:
    te_s = pd.Timestamp(f'{te_year}-01-01')
    te_e = pd.Timestamp(f'{te_year}-12-31')
    best_k, best_sh = None, -1e9
    for k in TOPK_GRID:
        tr = pnl_by_topk[k].loc[:tr_end]
        if len(tr) < 50: continue
        sh = stats(tr)['sharpe']
        if sh > best_sh: best_sh = sh; best_k = k
    test = pnl_by_topk[best_k].loc[te_s:te_e]
    s = stats(test)
    wf_rows.append(dict(year=te_year, picked_topk=best_k,
                          train_Sh=round(best_sh, 2), test_Sh=round(s['sharpe'], 2),
                          test_ann=f'{s["ann"]*100:+.2f}%', test_dd=f'{s["mdd"]*100:.2f}%'))
wf = pd.DataFrame(wf_rows)
wf.to_csv(OUT / 'v24_walk_forward.csv', index=False, encoding='utf-8-sig')
print(wf.to_string(index=False))
n_pass = (wf['test_Sh'] >= 1.0).sum()
n_top4 = (wf['picked_topk'] == 4).sum()
print(f'\nWF: {n_pass}/{len(wf)} 折 test_Sh ≥ 1.0 / top_k=4 在 {n_top4}/{len(wf)} 折胜出')

# === 最终 metrics ===
final_idx = df['label'].str.startswith('D ').idxmax()
final = df.iloc[final_idx].to_dict()
final['wf_pass'] = int(n_pass)
final['wf_total'] = len(wf)
final['regime_on_pct'] = regime_pcts.get(df.iloc[final_idx]['label'], (None, None))[0]
with open(OUT / 'v24_metrics.json', 'w', encoding='utf-8') as f:
    json.dump(final, f, indent=2, ensure_ascii=False, default=str)

print('\n' + '=' * 78)
print('=== V24 主推 D vs V22 baseline vs V7_gold ===')
print('=' * 78)
print(f"{'指标':<20} {'V7_gold':>10} {'V22 (A)':>10} {'V24 (D)':>10} {'Δ vs V22':>10}")
print('-' * 70)
A = df.iloc[0]; D = df.iloc[final_idx]
for k_v7, k_a, label in [
    ('full_sh', 'Full_Sh', 'Full Sharpe'),
    ('full_ann', 'Full_ann', 'Full 年化 (%)'),
    ('full_dd', 'Full_dd', 'Full 回撤 (%)'),
    ('full_cal', 'Full_cal', 'Full Calmar'),
    ('oos_sh', 'OOS_Sh', 'OOS Sharpe'),
    ('oos_ann', 'OOS_ann', 'OOS 年化 (%)'),
    ('oos_dd', 'OOS_dd', 'OOS 回撤 (%)'),
    ('oos_cal', 'OOS_cal', 'OOS Calmar'),
]:
    v7v = V7[k_v7]
    av = A[k_a]; dv = D[k_a]
    delta = dv - av
    if 'ann' in k_a or 'dd' in k_a:
        print(f"{label:<20} {v7v*100:>9.2f}% {av*100:>9.2f}% {dv*100:>9.2f}% {delta*100:>+9.2f}pp")
    else:
        print(f"{label:<20} {v7v:>10.3f} {av:>10.3f} {dv:>10.3f} {delta:>+10.3f}")

print(f"\n{'WF 通过':<20} {'—':>10} {'4/5':>10} {f'{n_pass}/{len(wf)}':>10}")
print(f"{'Regime ON %':<20} {'—':>10} {f'{regime_pcts[A.label][0]*100:.1f}%':>10} {f'{regime_pcts[D.label][0]*100:.1f}%':>10}")

if D['beats_V7']:
    print('\n✓ V24 八维全超 V7_gold')
else:
    print('\n✗ V24 未八维全超 V7')

if all([D['Full_Sh'] >= A['Full_Sh'], D['Full_ann'] >= A['Full_ann'],
         D['Full_dd'] >= A['Full_dd'], D['Full_cal'] >= A['Full_cal'],
         D['OOS_Sh'] >= A['OOS_Sh'], D['OOS_ann'] >= A['OOS_ann'],
         D['OOS_dd'] >= A['OOS_dd'], D['OOS_cal'] >= A['OOS_cal']]):
    print('✓ V24 八维严格非劣 V22 → 可升级主版本')
else:
    print('✗ V24 未八维严格非劣 V22 → 保留 V22 主版本')
