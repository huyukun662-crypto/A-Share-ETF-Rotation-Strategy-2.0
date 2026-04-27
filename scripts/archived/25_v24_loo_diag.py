# -*- coding: utf-8 -*-
"""V24 leave-one-out 诊断: 找出 15 只新 ETF 谁在拖累，谁有贡献。
   流程:
     baseline = V24 (50/15) + csi_all_acc + topk=4
     for each new ETF: 临时构造 universe 去掉它 → 跑回测 → ΔSharpe
     ΔSharpe > 0 = 该 ETF 有害（去掉变好）
     ΔSharpe < 0 = 该 ETF 有用（去掉变坏）
   产物: results/v24_loo.csv 排序后给出"应保留 / 应剔除"清单
"""
import sys, tempfile, os
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strategy_v15 import run_strategy, segment_stats

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data_cache'
OUT = ROOT / 'results'

V24_UNI = CACHE / 'etf_universe_v24.csv'
V24_WK = CACHE / 'etf_weekly_v24.parquet'
CSI_PATH = CACHE / 'csi_all_weekly.parquet'

P = dict(mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12, per_group=1,
          top_k_groups=4, risk_adj_nu=0.4, rev_w=0.05, accel_w=0.10,
          longmom_window=13, regime_accel_signal='csi_all_acc',
          regime_accel_theta_on=0.05, regime_accel_theta_off=0.0,
          regime_accel_k_min=8, csi_path=CSI_PATH, weekly_path=V24_WK)

uni24 = pd.read_csv(V24_UNI)
v7_codes = set(pd.read_csv(ROOT.parent / 'A-Share-ETF-Rotation-Strategy-2.0' / 'data_cache' / 'etf_universe.csv')['ts_code'])
new_codes = sorted(set(uni24['ts_code']) - v7_codes)
print(f'V24 新增 {len(new_codes)} 只 ETF, 跑 leave-one-out 诊断')

# baseline V24
print('\n跑 V24 baseline (50/15) ...')
ss_b = segment_stats(run_strategy(**P, uni_path=V24_UNI))
b = dict(Full_Sh=ss_b['Full']['sharpe'], OOS_Sh=ss_b['OOS']['sharpe'],
          Full_Cal=ss_b['Full']['calmar'], OOS_Cal=ss_b['OOS']['calmar'])
print(f'  baseline: Full Sh={b["Full_Sh"]:.3f} OOS Sh={b["OOS_Sh"]:.3f}')

rows = []
for code in new_codes:
    uni_loo = uni24[uni24['ts_code'] != code].copy()
    name = uni24[uni24['ts_code']==code].iloc[0]['name']
    grp = uni24[uni24['ts_code']==code].iloc[0]['group']
    # 写临时 csv
    tmp = CACHE / f'_tmp_loo_{code.replace(".","_")}.csv'
    uni_loo.to_csv(tmp, index=False, encoding='utf-8-sig')
    try:
        ss = segment_stats(run_strategy(**P, uni_path=tmp))
        full_sh = ss['Full']['sharpe']; oos_sh = ss['OOS']['sharpe']
        full_cal = ss['Full']['calmar']; oos_cal = ss['OOS']['calmar']
        d_full_sh = full_sh - b['Full_Sh']
        d_oos_sh = oos_sh - b['OOS_Sh']
        d_full_cal = full_cal - b['Full_Cal']
        d_oos_cal = oos_cal - b['OOS_Cal']
        rows.append(dict(removed=code, name=name, group=grp,
                          Full_Sh=round(full_sh, 3), d_Full_Sh=round(d_full_sh, 3),
                          OOS_Sh=round(oos_sh, 3), d_OOS_Sh=round(d_oos_sh, 3),
                          Full_Cal=round(full_cal, 2), d_Full_Cal=round(d_full_cal, 2),
                          OOS_Cal=round(oos_cal, 2), d_OOS_Cal=round(d_oos_cal, 2)))
        flag = '🟢 有害' if d_full_sh > 0.02 and d_oos_sh > 0.02 else (
                  '🔴 有用' if d_full_sh < -0.02 and d_oos_sh < -0.02 else '⚪ 中性')
        print(f'  去掉 {code} {name:<10} ({grp:<6}): ΔFull={d_full_sh:+.3f} ΔOOS={d_oos_sh:+.3f}  {flag}')
    except Exception as e:
        print(f'  去掉 {code} 失败: {e}')
    finally:
        os.unlink(tmp)

df = pd.DataFrame(rows).sort_values('d_Full_Sh', ascending=False)
df.to_csv(OUT / 'v24_loo.csv', index=False, encoding='utf-8-sig')

print('\n=== 排序: ΔFull_Sh 大→小 (越大越说明该 ETF 是包袱) ===')
print(df[['removed', 'name', 'group', 'd_Full_Sh', 'd_OOS_Sh', 'd_Full_Cal', 'd_OOS_Cal']].to_string(index=False))

# 推荐保留集合
keep_thresh = -0.02  # 去掉后退化 ≥ 0.02 才算"有用"
drop_thresh = 0.02   # 去掉后改善 ≥ 0.02 才算"有害"
useful = df[df['d_Full_Sh'] < keep_thresh]['removed'].tolist()
toxic = df[df['d_Full_Sh'] > drop_thresh]['removed'].tolist()
neutral = df[(df['d_Full_Sh'] >= keep_thresh) & (df['d_Full_Sh'] <= drop_thresh)]['removed'].tolist()

print(f'\n=== 决策建议 (阈值 ±0.02 Full Sh) ===')
print(f'🔴 应保留 ({len(useful)} 只): {useful}')
print(f'🟢 应剔除 ({len(toxic)} 只): {toxic}')
print(f'⚪ 中性可去 ({len(neutral)} 只): {neutral}')
