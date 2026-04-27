# -*- coding: utf-8 -*-
"""V25: V7 35-pool + V24 风格细化板块 (12 板块) + csi_all_acc + topk=4
   关键发现: V24 退化主因是新 ETF 加入 (z-score 噪声 + 防御稀释)；
              板块细化本身是微正向贡献。
   V25 = 严守 V7 池子 35 只 + 仅做板块标签精细化 + 信号源升级
"""
import json, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strategy_v15 import run_strategy, segment_stats, stats

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data_cache'
OUT = ROOT / 'results'
V25_UNI = CACHE / 'etf_universe_v24diag.csv'  # V7 35 + V24 12-板块标签
CSI_PATH = CACHE / 'csi_all_weekly.parquet'

V7 = dict(full_sh=1.915, full_ann=0.2467, full_dd=-0.0818, full_cal=3.01,
          oos_sh=2.029, oos_ann=0.2907, oos_dd=-0.0609, oos_cal=4.77)
V22 = dict(full_sh=1.955, full_ann=0.2512, full_dd=-0.0816, full_cal=3.08,
            oos_sh=2.097, oos_ann=0.2979, oos_dd=-0.0600, oos_cal=4.97)

P_BASE = dict(mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12, per_group=1,
              risk_adj_nu=0.4, rev_w=0.05, accel_w=0.10, longmom_window=13,
              regime_accel_theta_on=0.05, regime_accel_theta_off=0.0,
              regime_accel_k_min=8)

def beats(r, ref):
    return all([r['Full_Sh']>=ref['full_sh'], r['Full_ann']>=ref['full_ann'],
                  r['Full_dd']>=ref['full_dd'], r['Full_cal']>=ref['full_cal'],
                  r['OOS_Sh']>=ref['oos_sh'], r['OOS_ann']>=ref['oos_ann'],
                  r['OOS_dd']>=ref['oos_dd'], r['OOS_cal']>=ref['oos_cal']])

VARIANTS = [
    dict(label='V25.A 12板块 + hs300_acc + topk=3', top_k_groups=3,
          regime_accel_signal='hs300_acc', uni_path=V25_UNI),
    dict(label='V25.B 12板块 + hs300_acc + topk=4', top_k_groups=4,
          regime_accel_signal='hs300_acc', uni_path=V25_UNI),
    dict(label='V25.C 12板块 + csi_all_acc + topk=3', top_k_groups=3,
          regime_accel_signal='csi_all_acc', uni_path=V25_UNI, csi_path=CSI_PATH),
    dict(label='V25.D 12板块 + csi_all_acc + topk=4', top_k_groups=4,
          regime_accel_signal='csi_all_acc', uni_path=V25_UNI, csi_path=CSI_PATH),
    dict(label='V25.E 12板块 + csi_all_acc + topk=5', top_k_groups=5,
          regime_accel_signal='csi_all_acc', uni_path=V25_UNI, csi_path=CSI_PATH),
]

print('=' * 80)
print('V25: V7 35-池 + V24 风格 12 细板块 + 信号 × top_k 扫描')
print('=' * 80)
rows = []
for v in VARIANTS:
    label = v.pop('label')
    res = run_strategy(**P_BASE, **v, return_full=True)
    pnl = res['pnl_net']
    ss = segment_stats(pnl)
    reg = res.get('regime_accel_log')
    on_pct = float(reg.mean()) if reg is not None else 1.0
    eight = {'Full_Sh': ss['Full']['sharpe'], 'Full_ann': ss['Full']['ann'],
              'Full_dd': ss['Full']['mdd'], 'Full_cal': ss['Full']['calmar'],
              'OOS_Sh': ss['OOS']['sharpe'], 'OOS_ann': ss['OOS']['ann'],
              'OOS_dd': ss['OOS']['mdd'], 'OOS_cal': ss['OOS']['calmar']}
    row = dict(label=label, IS_Sh=round(ss['IS']['sharpe'], 3),
                Val_Sh=round(ss['Val']['sharpe'], 3),
                **{k: round(v_, 4) for k, v_ in eight.items()},
                regime_on=round(on_pct, 3),
                beats_V7=beats(eight, V7), beats_V22=beats(eight, V22))
    rows.append(row)
    print(f"\n{label}:")
    print(f"  Full Sh={row['Full_Sh']:.3f} ann={row['Full_ann']*100:+.2f}% DD={row['Full_dd']*100:.2f}% Cal={row['Full_cal']:.2f}")
    print(f"  OOS  Sh={row['OOS_Sh']:.3f} ann={row['OOS_ann']*100:+.2f}% DD={row['OOS_dd']*100:.2f}% Cal={row['OOS_cal']:.2f}")
    print(f"  Regime ON {on_pct*100:.1f}% | 全超 V7: {'✓' if row['beats_V7'] else '✗'} | 非劣 V22: {'✓' if row['beats_V22'] else '✗'}")

df = pd.DataFrame(rows)
df.to_csv(OUT / 'v25_variants.csv', index=False, encoding='utf-8-sig')

# 按 IS Sh 选冠军
best_idx = df['IS_Sh'].idxmax()
champ = df.iloc[best_idx]
print(f'\n=== IS Sh 冠军 = {champ["label"]} (IS={champ["IS_Sh"]}) ===')

# 冠军参数复跑 + WF 5 折
def get_champ_kwargs(label):
    if 'topk=3' in label: tk = 3
    elif 'topk=4' in label: tk = 4
    else: tk = 5
    if 'csi_all_acc' in label:
        return dict(top_k_groups=tk, regime_accel_signal='csi_all_acc',
                     uni_path=V25_UNI, csi_path=CSI_PATH)
    else:
        return dict(top_k_groups=tk, regime_accel_signal='hs300_acc', uni_path=V25_UNI)

ckw = get_champ_kwargs(champ['label'])
print('\n=== WF 5 折：IS Sh 冠军参数 ===')
folds = [('2021-12-31', '2022'), ('2022-12-31', '2023'), ('2023-12-31', '2024'),
          ('2024-12-31', '2025'), ('2025-12-31', '2026')]
TOPK_GRID = [3, 4, 5]
pnl_by_topk = {}
for k in TOPK_GRID:
    kw = {**ckw, 'top_k_groups': k}
    pnl_by_topk[k] = run_strategy(**P_BASE, **kw)

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
wf.to_csv(OUT / 'v25_walk_forward.csv', index=False, encoding='utf-8-sig')
print(wf.to_string(index=False))
n_pass = (wf['test_Sh'] >= 1.0).sum()
n_top4 = (wf['picked_topk'] == ckw['top_k_groups']).sum()
print(f'\nWF: {n_pass}/{len(wf)} 折 test_Sh ≥ 1.0 / 冠军 top_k 在 {n_top4}/{len(wf)} 折胜出')

# 终判
print('\n' + '=' * 80)
print(f"{'指标':<14} {'V7_gold':>10} {'V22':>10} {'V25 best':>10} {'Δ vs V22':>10}")
print('-' * 60)
for k_v7, k_a, lab in [('full_sh', 'Full_Sh', 'Full Sh'),
                         ('full_ann', 'Full_ann', 'Full 年化'),
                         ('full_dd', 'Full_dd', 'Full DD'),
                         ('full_cal', 'Full_cal', 'Full Cal'),
                         ('oos_sh', 'OOS_Sh', 'OOS Sh'),
                         ('oos_ann', 'OOS_ann', 'OOS 年化'),
                         ('oos_dd', 'OOS_dd', 'OOS DD'),
                         ('oos_cal', 'OOS_cal', 'OOS Cal')]:
    v7v, v22v, bv = V7[k_v7], V22[k_v7], champ[k_a]
    delta = bv - v22v
    if 'ann' in k_a or 'dd' in k_a:
        print(f"{lab:<14} {v7v*100:>9.2f}% {v22v*100:>9.2f}% {bv*100:>9.2f}% {delta*100:>+9.2f}pp")
    else:
        print(f"{lab:<14} {v7v:>10.3f} {v22v:>10.3f} {bv:>10.3f} {delta:>+10.3f}")
print(f"{'WF 通过':<14} {'—':>10} {'4/5':>10} {f'{n_pass}/{len(wf)}':>10}")
print(f"{'Regime ON':<14} {'—':>10} {'32.4%':>10} {f'{champ.regime_on*100:.1f}%':>10}")

if champ['beats_V22']:
    print('\n✓✓✓ V25 八维严格非劣 V22 → V25 升级为新主版本')
elif champ['beats_V7']:
    print('\n△ V25 八维全超 V7 但未非劣 V22')
else:
    print('\n✗ V25 未八维全超 V7')

with open(OUT / 'v25_metrics.json', 'w', encoding='utf-8') as f:
    json.dump(champ.to_dict(), f, indent=2, ensure_ascii=False, default=str)
print(f'\n[saved] results/v25_metrics.json')
