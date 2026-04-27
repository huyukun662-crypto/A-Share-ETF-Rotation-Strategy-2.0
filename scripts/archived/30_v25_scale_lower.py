# -*- coding: utf-8 -*-
"""V25 + scale_lower 测试: 提高 vol target 下限到 0.80（最低 80% 仓位）
   现状: scale 在 vol overshoot 时可下探到 0 (高波动期满仓退出)
   测试: scale ∈ [0.80, 1.00]，强制最低 80% 仓位"""
import json, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strategy_v15 import run_strategy, segment_stats, stats

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data_cache'
OUT = ROOT / 'results'

V25 = dict(mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12,
            top_k_groups=4, per_group=1,
            risk_adj_nu=0.4, rev_w=0.05, accel_w=0.10, longmom_window=13,
            regime_accel_signal='csi_all_acc',
            regime_accel_theta_on=0.05, regime_accel_theta_off=0.0,
            regime_accel_k_min=8,
            uni_path=CACHE / 'etf_universe_v24diag.csv',
            csi_path=CACHE / 'csi_all_weekly.parquet')

V22_REF = dict(full_sh=1.955, full_ann=0.2512, full_dd=-0.0816, full_cal=3.08,
                oos_sh=2.097, oos_ann=0.2979, oos_dd=-0.0600, oos_cal=4.97)

print('=' * 80)
print('V25 + scale_lower 扫描 (vol target 仓位下限)')
print('=' * 80)

GRID = [0.0, 0.30, 0.50, 0.70, 0.80, 0.90, 1.00]
rows = []
for sl in GRID:
    res = run_strategy(**V25, scale_lower=sl, return_full=True)
    pnl = res['pnl_net']
    ss = segment_stats(pnl)
    scale = res['scale']
    avg_scale = float(scale.mean())
    min_scale = float(scale.min())
    weeks_below_1 = int((scale < 0.99).sum())
    weeks_at_floor = int((scale <= sl + 1e-6).sum()) if sl > 0 else 0
    rows.append(dict(scale_lower=sl,
                       Full_Sh=round(ss['Full']['sharpe'], 3),
                       Full_ann=round(ss['Full']['ann'], 4),
                       Full_dd=round(ss['Full']['mdd'], 4),
                       Full_cal=round(ss['Full']['calmar'], 2),
                       OOS_Sh=round(ss['OOS']['sharpe'], 3),
                       OOS_ann=round(ss['OOS']['ann'], 4),
                       OOS_dd=round(ss['OOS']['mdd'], 4),
                       OOS_cal=round(ss['OOS']['calmar'], 2),
                       avg_scale=round(avg_scale, 3),
                       min_scale=round(min_scale, 3),
                       wks_below1=weeks_below_1,
                       wks_at_floor=weeks_at_floor))
    flag = '★' if abs(sl - 0.80) < 1e-6 else ' '
    print(f'{flag} scale_lower={sl:.2f} | Full Sh={ss["Full"]["sharpe"]:.3f} ann={ss["Full"]["ann"]*100:+.2f}% '
          f'DD={ss["Full"]["mdd"]*100:.2f}% Cal={ss["Full"]["calmar"]:.2f} | '
          f'OOS Sh={ss["OOS"]["sharpe"]:.3f} DD={ss["OOS"]["mdd"]*100:.2f}% '
          f'Cal={ss["OOS"]["calmar"]:.2f} | avg_scale={avg_scale:.3f}')

df = pd.DataFrame(rows)
df.to_csv(OUT / 'v25_scale_lower_grid.csv', index=False, encoding='utf-8-sig')

# 重点对比: scale_lower=0.80
print('\n' + '=' * 80)
print('重点对比: V25 baseline (sl=0) vs V25 + scale_lower=0.80 vs V22')
print('=' * 80)
b0 = df[df['scale_lower']==0.0].iloc[0]
b8 = df[df['scale_lower']==0.80].iloc[0]
print(f'{"指标":<14} {"V22":>10} {"V25 sl=0":>10} {"V25 sl=0.80":>12} {"Δ vs V25":>10}')
print('-' * 65)
for k_v22, k_a, lab in [('full_sh', 'Full_Sh', 'Full Sh'),
                          ('full_ann', 'Full_ann', 'Full 年化'),
                          ('full_dd', 'Full_dd', 'Full DD'),
                          ('full_cal', 'Full_cal', 'Full Cal'),
                          ('oos_sh', 'OOS_Sh', 'OOS Sh'),
                          ('oos_ann', 'OOS_ann', 'OOS 年化'),
                          ('oos_dd', 'OOS_dd', 'OOS DD'),
                          ('oos_cal', 'OOS_cal', 'OOS Cal')]:
    v22v = V22_REF[k_v22]
    v0 = b0[k_a]; v8 = b8[k_a]
    delta = v8 - v0
    if 'ann' in k_a or 'dd' in k_a:
        print(f'{lab:<14} {v22v*100:>9.2f}% {v0*100:>9.2f}% {v8*100:>11.2f}% {delta*100:>+9.2f}pp')
    else:
        print(f'{lab:<14} {v22v:>10.3f} {v0:>10.3f} {v8:>12.3f} {delta:>+10.3f}')
print(f'{"avg scale":<14} {"—":>10} {b0["avg_scale"]:>10.3f} {b8["avg_scale"]:>12.3f}')
print(f'{"周数 < 1":<14} {"—":>10} {int(b0["wks_below1"]):>10d} {int(b8["wks_below1"]):>12d}')
print(f'{"周数 = 下限":<14} {"—":>10} {"0":>10} {int(b8["wks_at_floor"]):>12d}')

# 八维判定
def beats(r, ref):
    return all([r['Full_Sh']>=ref['full_sh'], r['Full_ann']>=ref['full_ann'],
                  r['Full_dd']>=ref['full_dd'], r['Full_cal']>=ref['full_cal'],
                  r['OOS_Sh']>=ref['oos_sh'], r['OOS_ann']>=ref['oos_ann'],
                  r['OOS_dd']>=ref['oos_dd'], r['OOS_cal']>=ref['oos_cal']])

print(f'\nV25 sl=0:    八维非劣 V22? {beats(b0.to_dict(), V22_REF)}')
print(f'V25 sl=0.80: 八维非劣 V22? {beats(b8.to_dict(), V22_REF)}')
