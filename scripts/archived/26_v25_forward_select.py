# -*- coding: utf-8 -*-
"""V25 + 前向选择: 从 V7 35 + 12 板块出发，贪心加入新 ETF 直到 Full Sh 停止改善。
   目标: 找到 35 + k 的最优组合，避免一次性加 15 只造成的横截面 z-score 污染。
"""
import sys, os
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strategy_v15 import run_strategy, segment_stats

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data_cache'
OUT = ROOT / 'results'
V25_UNI = CACHE / 'etf_universe_v24diag.csv'   # V7 35 + 12 板块标签
V24_UNI = CACHE / 'etf_universe_v24.csv'         # 完整 50 / 15
V24_WK = CACHE / 'etf_weekly_v24.parquet'
CSI_PATH = CACHE / 'csi_all_weekly.parquet'

P = dict(mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12, per_group=1,
          top_k_groups=4, risk_adj_nu=0.4, rev_w=0.05, accel_w=0.10,
          longmom_window=13, regime_accel_signal='csi_all_acc',
          regime_accel_theta_on=0.05, regime_accel_theta_off=0.0,
          regime_accel_k_min=8, csi_path=CSI_PATH, weekly_path=V24_WK)

# 候选新 ETF（含 V24 board 标签，使用 V24 group 不变）
v25_uni = pd.read_csv(V25_UNI)   # 35 ETFs / 12 boards
v24_uni = pd.read_csv(V24_UNI)
v25_codes = set(v25_uni['ts_code'])
new_codes = sorted(set(v24_uni['ts_code']) - v25_codes)

def run_with_uni(uni_df):
    """关键: 必须把 weekly parquet 过滤到 uni_df 的 ts_code 子集，
       否则 Leg A 会从全部 50 只里选股，破坏隔离性"""
    tmp_uni = CACHE / '_tmp_fwd_uni.csv'
    tmp_wk = CACHE / '_tmp_fwd_wk.parquet'
    uni_df.to_csv(tmp_uni, index=False, encoding='utf-8-sig')
    wk = pd.read_parquet(V24_WK)
    wk_filt = wk[wk['ts_code'].isin(uni_df['ts_code'])].copy()
    wk_filt.to_parquet(tmp_wk, index=False)
    try:
        P_local = {k: v for k, v in P.items() if k != 'weekly_path'}
        ss = segment_stats(run_strategy(**P_local, weekly_path=tmp_wk, uni_path=tmp_uni))
        return ss['Full']['sharpe'], ss['OOS']['sharpe'], ss['Full']['calmar'], ss['OOS']['calmar']
    finally:
        os.unlink(tmp_uni); os.unlink(tmp_wk)

print('=== Step 0: V25 baseline (35 ETF / 12 板块) ===')
b_full, b_oos, b_fcal, b_ocal = run_with_uni(v25_uni)
print(f'  Full Sh={b_full:.3f} OOS Sh={b_oos:.3f} Full Cal={b_fcal:.2f} OOS Cal={b_ocal:.2f}')

current_uni = v25_uni.copy()
current_codes = set(current_uni['ts_code'])
remaining = list(new_codes)
history = [dict(step=0, n=len(current_codes), added='—',
                 Full_Sh=round(b_full, 3), OOS_Sh=round(b_oos, 3),
                 Full_Cal=round(b_fcal, 2), OOS_Cal=round(b_ocal, 2))]

step = 0
while remaining:
    step += 1
    print(f'\n--- Step {step}: 测试加入剩余 {len(remaining)} 只 ---')
    best_code, best_full, best_oos, best_fcal, best_ocal = None, b_full, b_oos, b_fcal, b_ocal
    trial_results = []
    for code in remaining:
        row = v24_uni[v24_uni['ts_code'] == code].iloc[0]
        new_uni = pd.concat([current_uni, pd.DataFrame([row])], ignore_index=True)
        try:
            f, o, fc, oc = run_with_uni(new_uni)
            trial_results.append((code, f, o, fc, oc))
            if f > best_full + 1e-4:
                best_full, best_oos, best_fcal, best_ocal, best_code = f, o, fc, oc, code
        except Exception as e:
            print(f'  + {code} 失败: {e}')

    # 输出本轮 top 3
    trial_results.sort(key=lambda x: -x[1])
    for c, f, o, fc, oc in trial_results[:3]:
        n = v24_uni[v24_uni['ts_code']==c].iloc[0]['name']
        d = f - b_full
        print(f'  + {c} {n:<10}  ΔFull={d:+.3f}  Full={f:.3f} OOS={o:.3f} OOS_Cal={oc:.2f}')

    if best_code is None:
        print(f'\n→ 无任何加入能提升 Full Sh, 停止')
        break

    name = v24_uni[v24_uni['ts_code']==best_code].iloc[0]['name']
    print(f'\n  ★ 选中: + {best_code} {name}  Full Sh: {b_full:.3f} → {best_full:.3f} (+{best_full-b_full:.3f})')
    new_row = v24_uni[v24_uni['ts_code']==best_code]
    current_uni = pd.concat([current_uni, new_row], ignore_index=True)
    current_codes.add(best_code)
    remaining.remove(best_code)
    b_full, b_oos, b_fcal, b_ocal = best_full, best_oos, best_fcal, best_ocal
    history.append(dict(step=step, n=len(current_codes), added=best_code,
                         Full_Sh=round(b_full, 3), OOS_Sh=round(b_oos, 3),
                         Full_Cal=round(b_fcal, 2), OOS_Cal=round(b_ocal, 2)))

hist_df = pd.DataFrame(history)
hist_df.to_csv(OUT / 'v25_forward_select.csv', index=False, encoding='utf-8-sig')
print('\n=== 前向选择历史 ===')
print(hist_df.to_string(index=False))

# 最终池子
final_uni = current_uni
final_uni.to_csv(CACHE / 'etf_universe_v26.csv', index=False, encoding='utf-8-sig')
print(f'\n=== V26 最终池子 ({len(final_uni)} 只 / {final_uni["group"].nunique()} 板块) ===')
print(f'V7 35 + 加入 {len(final_uni) - 35} 只: {sorted(set(final_uni["ts_code"]) - v25_codes)}')
print(f'\nFull Sh: {history[0]["Full_Sh"]:.3f} → {history[-1]["Full_Sh"]:.3f}')
print(f'OOS Sh:  {history[0]["OOS_Sh"]:.3f} → {history[-1]["OOS_Sh"]:.3f}')
print(f'OOS Cal: {history[0]["OOS_Cal"]:.2f} → {history[-1]["OOS_Cal"]:.2f}')
print(f'\n输出: {CACHE/"etf_universe_v26.csv"}')
