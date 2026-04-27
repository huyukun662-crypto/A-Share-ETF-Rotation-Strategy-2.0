# -*- coding: utf-8 -*-
"""V24m (R1 路线): 池子保留 50 只 ETF，但合并细分子板块到 12 板块。
   半导体+芯片 → 半导体芯片 (6)
   AI软件+数字消费 → AI数字 (6)
   食品酒水+家电 → 大消费 (5)
   其余不变 → 12 板块
   测试 top_k_groups = 3/4/5 + csi_all_acc。"""
import json, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strategy_v15 import run_strategy, segment_stats, stats

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data_cache'
OUT = ROOT / 'results'
OUT.mkdir(exist_ok=True)

V24M_UNI = CACHE / 'etf_universe_v24m.csv'
V24_WK = CACHE / 'etf_weekly_v24.parquet'
CSI_PATH = CACHE / 'csi_all_weekly.parquet'

V7 = dict(full_sh=1.915, full_ann=0.2467, full_dd=-0.0818, full_cal=3.01,
          oos_sh=2.029, oos_ann=0.2907, oos_dd=-0.0609, oos_cal=4.77)
V22 = dict(full_sh=1.955, full_ann=0.2512, full_dd=-0.0816, full_cal=3.08,
            oos_sh=2.097, oos_ann=0.2979, oos_dd=-0.0600, oos_cal=4.97)

P_BASE = dict(mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12,
              per_group=1, risk_adj_nu=0.4, rev_w=0.05,
              accel_w=0.10, longmom_window=13,
              regime_accel_theta_on=0.05, regime_accel_theta_off=0.0,
              regime_accel_k_min=8)

VARIANTS = [
    dict(label='M1 V24m + hs300_acc + topk=3', top_k_groups=3,
         regime_accel_signal='hs300_acc', weekly_path=V24_WK, uni_path=V24M_UNI),
    dict(label='M2 V24m + hs300_acc + topk=4', top_k_groups=4,
         regime_accel_signal='hs300_acc', weekly_path=V24_WK, uni_path=V24M_UNI),
    dict(label='M3 V24m + csi_all_acc + topk=3', top_k_groups=3,
         regime_accel_signal='csi_all_acc', weekly_path=V24_WK, uni_path=V24M_UNI, csi_path=CSI_PATH),
    dict(label='M4 V24m + csi_all_acc + topk=4', top_k_groups=4,
         regime_accel_signal='csi_all_acc', weekly_path=V24_WK, uni_path=V24M_UNI, csi_path=CSI_PATH),
    dict(label='M5 V24m + csi_all_acc + topk=5', top_k_groups=5,
         regime_accel_signal='csi_all_acc', weekly_path=V24_WK, uni_path=V24M_UNI, csi_path=CSI_PATH),
]

def beats(r, ref):
    return all([r['Full_Sh']>=ref['full_sh'], r['Full_ann']>=ref['full_ann'],
                  r['Full_dd']>=ref['full_dd'], r['Full_cal']>=ref['full_cal'],
                  r['OOS_Sh']>=ref['oos_sh'], r['OOS_ann']>=ref['oos_ann'],
                  r['OOS_dd']>=ref['oos_dd'], r['OOS_cal']>=ref['oos_cal']])

print('=' * 80)
print('V24m (R1 合并细分子板块) — 50 ETF / 12 板块 — 信号 × top_k 扫描')
print('=' * 80)
rows, regimes = [], {}
for v in VARIANTS:
    label = v.pop('label')
    print(f'\n--- {label} ---')
    res = run_strategy(**P_BASE, **v, return_full=True)
    pnl = res['pnl_net']
    ss = segment_stats(pnl)
    reg = res.get('regime_accel_log')
    on_pct = float(reg.mean()) if reg is not None else 1.0
    n_switch = int((reg != reg.shift(1)).sum()) if reg is not None else 0
    regimes[label] = (on_pct, n_switch, pnl)
    row = dict(label=label,
        IS_Sh=round(ss['IS']['sharpe'], 3), Val_Sh=round(ss['Val']['sharpe'], 3),
        OOS_Sh=round(ss['OOS']['sharpe'], 3), OOS_ann=round(ss['OOS']['ann'], 4),
        OOS_dd=round(ss['OOS']['mdd'], 4), OOS_cal=round(ss['OOS']['calmar'], 2),
        Full_Sh=round(ss['Full']['sharpe'], 3), Full_ann=round(ss['Full']['ann'], 4),
        Full_dd=round(ss['Full']['mdd'], 4), Full_cal=round(ss['Full']['calmar'], 2),
        regime_on_pct=round(on_pct, 3), n_switch=n_switch)
    eight_pack = {'Full_Sh': ss['Full']['sharpe'], 'Full_ann': ss['Full']['ann'],
                    'Full_dd': ss['Full']['mdd'], 'Full_cal': ss['Full']['calmar'],
                    'OOS_Sh': ss['OOS']['sharpe'], 'OOS_ann': ss['OOS']['ann'],
                    'OOS_dd': ss['OOS']['mdd'], 'OOS_cal': ss['OOS']['calmar']}
    row['beats_V7'] = beats(eight_pack, V7)
    row['beats_V22'] = beats(eight_pack, V22)
    rows.append(row)
    print(f'  IS Sh={row["IS_Sh"]} Val={row["Val_Sh"]} OOS={row["OOS_Sh"]} (ann={row["OOS_ann"]*100:+.2f}%, dd={row["OOS_dd"]*100:.2f}%, Cal={row["OOS_cal"]})')
    print(f'  Full Sh={row["Full_Sh"]} ann={row["Full_ann"]*100:+.2f}% dd={row["Full_dd"]*100:.2f}% Cal={row["Full_cal"]}')
    print(f'  Regime ON {on_pct*100:.1f}% / 切换 {n_switch} 次 / 全超 V7: {"✓" if row["beats_V7"] else "✗"} / 非劣 V22: {"✓" if row["beats_V22"] else "✗"}')

df = pd.DataFrame(rows)
df.to_csv(OUT / 'v24m_variants.csv', index=False, encoding='utf-8-sig')
print('\n=== 汇总 ===')
print(df[['label', 'IS_Sh', 'OOS_Sh', 'Full_Sh', 'OOS_ann', 'OOS_dd', 'OOS_cal',
          'Full_dd', 'Full_cal', 'beats_V7', 'beats_V22']].to_string(index=False))

# WF 5 折 - 选 IS Sh 最高的 V24m 变体
best_idx = df['IS_Sh'].idxmax()
best_label = df.iloc[best_idx]['label']
print(f'\n=== WF 5 折：IS Sh 冠军 = {best_label} ===')
folds = [('2021-12-31', '2022'), ('2022-12-31', '2023'), ('2023-12-31', '2024'),
          ('2024-12-31', '2025'), ('2025-12-31', '2026')]
TOPK_GRID = [3, 4, 5]
pnl_by_topk = {}
for k in TOPK_GRID:
    pnl_by_topk[k] = run_strategy(**P_BASE, top_k_groups=k,
                                       regime_accel_signal='csi_all_acc',
                                       weekly_path=V24_WK, uni_path=V24M_UNI, csi_path=CSI_PATH)
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
wf.to_csv(OUT / 'v24m_walk_forward.csv', index=False, encoding='utf-8-sig')
print(wf.to_string(index=False))
n_pass = (wf['test_Sh'] >= 1.0).sum()
print(f'\nWF: {n_pass}/{len(wf)} 折 test_Sh ≥ 1.0')

# 终判
print('\n' + '=' * 80)
print(f"{'指标':<14} {'V7_gold':>10} {'V22':>10} {'V24m best':>10} {'Δ vs V22':>10}")
print('-' * 60)
B = df.iloc[best_idx]
for k_v7, k_a, lab in [
    ('full_sh', 'Full_Sh', 'Full Sh'),
    ('full_ann', 'Full_ann', 'Full 年化'),
    ('full_dd', 'Full_dd', 'Full DD'),
    ('full_cal', 'Full_cal', 'Full Cal'),
    ('oos_sh', 'OOS_Sh', 'OOS Sh'),
    ('oos_ann', 'OOS_ann', 'OOS 年化'),
    ('oos_dd', 'OOS_dd', 'OOS DD'),
    ('oos_cal', 'OOS_cal', 'OOS Cal'),
]:
    v7v, v22v, bv = V7[k_v7], V22[k_v7], B[k_a]
    delta = bv - v22v
    if 'ann' in k_a or 'dd' in k_a:
        print(f"{lab:<14} {v7v*100:>9.2f}% {v22v*100:>9.2f}% {bv*100:>9.2f}% {delta*100:>+9.2f}pp")
    else:
        print(f"{lab:<14} {v7v:>10.3f} {v22v:>10.3f} {bv:>10.3f} {delta:>+10.3f}")
print(f"\n{'WF 通过':<14} {'—':>10} {'4/5':>10} {f'{n_pass}/{len(wf)}':>10}")

if B['beats_V22']:
    print('\n✓✓✓ V24m best 八维严格非劣 V22 → V24m 升级为新主版本')
elif B['beats_V7']:
    print('\n△ V24m best 八维全超 V7 但未非劣 V22 → V22 保留主版本，V24m 作研究存档')
else:
    print('\n✗ V24m best 未八维全超 V7 → 保留 V22 主版本')

with open(OUT / 'v24m_metrics.json', 'w', encoding='utf-8') as f:
    json.dump(B.to_dict(), f, indent=2, ensure_ascii=False, default=str)
