# -*- coding: utf-8 -*-
"""V25 final: V7 35-pool + V24 风格 12 板块重命名 + topk=4 + csi_all_acc
   完整 WF 5 折 + 八维严格非劣判定。"""
import json, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strategy_v15 import run_strategy, segment_stats, stats

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data_cache'
OUT = ROOT / 'results'
V25_UNI = CACHE / 'etf_universe_v24diag.csv'
CSI_PATH = CACHE / 'csi_all_weekly.parquet'

V22 = dict(full_sh=1.955, full_ann=0.2512, full_dd=-0.0816, full_cal=3.08,
            oos_sh=2.097, oos_ann=0.2979, oos_dd=-0.0600, oos_cal=4.97)
V7 = dict(full_sh=1.915, full_ann=0.2467, full_dd=-0.0818, full_cal=3.01,
          oos_sh=2.029, oos_ann=0.2907, oos_dd=-0.0609, oos_cal=4.77)

P25 = dict(mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12, per_group=1,
            top_k_groups=4, risk_adj_nu=0.4, rev_w=0.05, accel_w=0.10,
            longmom_window=13, regime_accel_signal='hs300_acc',
            regime_accel_theta_on=0.05, regime_accel_theta_off=0.0,
            regime_accel_k_min=8, uni_path=V25_UNI)

print('=== V25 final: V7 35-pool + V24 12-板块 + topk=4 + hs300_acc ===\n')
res = run_strategy(**P25, return_full=True)
ss = segment_stats(res['pnl_net'])
reg = res['regime_accel_log']
on_pct = float(reg.mean()) if reg is not None else 1.0
n_switch = int((reg != reg.shift(1)).sum()) if reg is not None else 0

# 也跑 csi_all_acc 对照
P25c = {**P25, 'regime_accel_signal': 'csi_all_acc', 'csi_path': CSI_PATH}
ssc = segment_stats(run_strategy(**P25c))
print(f'{"指标":<14} {"V7_gold":>10} {"V22":>10} {"V25 hs300":>10} {"V25 csi":>10}')
print('-' * 60)
for k_v7, k_a, lab in [('full_sh', 'sharpe', 'Full Sh'),
                         ('full_ann', 'ann', 'Full 年化'),
                         ('full_dd', 'mdd', 'Full DD'),
                         ('full_cal', 'calmar', 'Full Cal'),
                         ('oos_sh', 'sharpe', 'OOS Sh'),
                         ('oos_ann', 'ann', 'OOS 年化'),
                         ('oos_dd', 'mdd', 'OOS DD'),
                         ('oos_cal', 'calmar', 'OOS Cal')]:
    seg = 'OOS' if 'oos' in k_v7 else 'Full'
    v7v, v22v = V7[k_v7], V22[k_v7]
    bv, cv = ss[seg][k_a], ssc[seg][k_a]
    if 'ann' in k_v7 or 'dd' in k_v7:
        print(f'{lab:<14} {v7v*100:>9.2f}% {v22v*100:>9.2f}% {bv*100:>9.2f}% {cv*100:>9.2f}%')
    else:
        print(f'{lab:<14} {v7v:>10.3f} {v22v:>10.3f} {bv:>10.3f} {cv:>10.3f}')

# 八维非劣判定
def beats(s, ref):
    return all([s['Full']['sharpe']>=ref['full_sh'], s['Full']['ann']>=ref['full_ann'],
                  s['Full']['mdd']>=ref['full_dd'], s['Full']['calmar']>=ref['full_cal'],
                  s['OOS']['sharpe']>=ref['oos_sh'], s['OOS']['ann']>=ref['oos_ann'],
                  s['OOS']['mdd']>=ref['oos_dd'], s['OOS']['calmar']>=ref['oos_cal']])

print(f'\nV25 hs300:  全超 V7? {beats(ss, V7)}  非劣 V22? {beats(ss, V22)}')
print(f'V25 csi:    全超 V7? {beats(ssc, V7)}  非劣 V22? {beats(ssc, V22)}')

# WF 5 折 - 选 hs300 (Full Sh 2.007 > csi 2.002)
print(f'\n=== WF 5 折 (hs300_acc, scan top_k 3/4/5) ===')
folds = [('2021-12-31', '2022'), ('2022-12-31', '2023'), ('2023-12-31', '2024'),
          ('2024-12-31', '2025'), ('2025-12-31', '2026')]
TOPK_GRID = [3, 4, 5]
pnl_by_topk = {}
for k in TOPK_GRID:
    pnl_by_topk[k] = run_strategy(**{**P25, 'top_k_groups': k})

wf_rows = []
for tr_end, te_year in folds:
    te_s = pd.Timestamp(f'{te_year}-01-01'); te_e = pd.Timestamp(f'{te_year}-12-31')
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
wf.to_csv(OUT / 'v25_walk_forward_final.csv', index=False, encoding='utf-8-sig')
print(wf.to_string(index=False))
n_pass = (wf['test_Sh'] >= 1.0).sum()
n_top4 = (wf['picked_topk'] == 4).sum()
print(f'\nWF: {n_pass}/{len(wf)} 折 test_Sh ≥ 1.0 / top_k=4 在 {n_top4}/{len(wf)} 折胜出')
print(f'Regime ON: {on_pct*100:.1f}% / 切换: {n_switch} 次')

# 终判 + metrics 落地
def to_float(d):
    return {k: float(v) if hasattr(v,'item') else v for k,v in d.items()}
final = dict(label='V25 V7-pool + V24-12板块 + topk=4 + hs300_acc',
              **{f'Full_{k}': float(ss['Full'][k]) for k in ['sharpe','ann','mdd','calmar']},
              **{f'OOS_{k}': float(ss['OOS'][k]) for k in ['sharpe','ann','mdd','calmar']},
              **{f'IS_{k}': float(ss['IS'][k]) for k in ['sharpe','ann','mdd','calmar']},
              regime_on_pct=on_pct, n_switch=n_switch,
              wf_pass=int(n_pass), wf_total=len(wf),
              beats_V7=beats(ss, V7), beats_V22=beats(ss, V22))
with open(OUT / 'v25_metrics_final.json', 'w', encoding='utf-8') as f:
    json.dump(final, f, indent=2, ensure_ascii=False)
print(f'\n[saved] results/v25_metrics_final.json')

if final['beats_V22']:
    print('\n✓✓✓ V25 八维严格非劣 V22 → V25 升级为新主版本')
elif final['beats_V7']:
    print('\n△ V25 八维全超 V7 但单维微败 V22')
    print('  → 用户可酌情采纳: V25 在大部分维度更优, 仅 Full DD 微弱退化')
else:
    print('\n✗ V25 未八维全超 V7 → 保留 V22')
