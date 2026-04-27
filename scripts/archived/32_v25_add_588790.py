# -*- coding: utf-8 -*-
"""V25 标的扩容: 在 AI数字 板块新增 588790 科创人工智能 ETF (不替换 515980)
   AI数字 5只 → 6只: AI 515980 / 软件 515230 / 云计算 159890 /
                    消费电子 159779 / 游戏 159869 / 科创人工智能 588790
   总池子 35 → 36 只 / 12 板块不变
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V7_ROOT = Path(__file__).resolve().parents[2] / 'A-Share-ETF-Rotation-Strategy-2.0'
CACHE = ROOT / 'data_cache'

NEW_CODE = '588790.SH'
NEW_NAME = '科创人工智能ETF'
NEW_GROUP = 'AI数字'

# 复用 31 已抓的 588790 周线（在 etf_weekly_v25swap.parquet 中）
swap_w = pd.read_parquet(CACHE / 'etf_weekly_v25swap.parquet')
new_w_only = swap_w[swap_w['ts_code'] == NEW_CODE].copy()
print(f'588790 周线 {len(new_w_only)} 行 / {new_w_only["trade_week"].min().date()} → {new_w_only["trade_week"].max().date()}')

# V7 全量 35 + 588790 = 36 只
v7w = pd.read_parquet(V7_ROOT / 'data_cache' / 'etf_weekly.parquet')
v7w['trade_week'] = pd.to_datetime(v7w['trade_week'])
add_w = pd.concat([v7w, new_w_only], ignore_index=True)
add_w = add_w.sort_values(['trade_week', 'ts_code']).reset_index(drop=True)
WK_OUT = CACHE / 'etf_weekly_v25add.parquet'
add_w.to_parquet(WK_OUT, index=False)
print(f'→ {WK_OUT.name}: {len(add_w)} 行 / {add_w["ts_code"].nunique()} ETF')

# 新 universe = V25 baseline 35 + 588790
old_uni = pd.read_csv(CACHE / 'etf_universe_v24diag.csv', encoding='utf-8')
add_uni = pd.concat([old_uni,
                       pd.DataFrame([dict(ts_code=NEW_CODE, name=NEW_NAME, group=NEW_GROUP)])],
                      ignore_index=True)
UNI_OUT = CACHE / 'etf_universe_v25add.csv'
add_uni.to_csv(UNI_OUT, index=False, encoding='utf-8-sig')
ai_codes = add_uni[add_uni['group']=='AI数字']
print(f'→ {UNI_OUT.name}: {len(add_uni)} 只 / {add_uni["group"].nunique()} 板块 / AI数字 {len(ai_codes)} 只')
print(ai_codes.to_string(index=False))

# === 回测 ===
print('\n=== V25 回测对比 ===')
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _strategy_v15 as eng
eng._DATA_CACHE.clear()
from _strategy_v15 import run_strategy, segment_stats

CSI = CACHE / 'csi_all_weekly.parquet'
COMMON = dict(mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12,
                top_k_groups=4, per_group=1,
                risk_adj_nu=0.4, rev_w=0.05, accel_w=0.10, longmom_window=13,
                regime_accel_signal='csi_all_acc',
                regime_accel_theta_on=0.05, regime_accel_theta_off=0.0,
                regime_accel_k_min=8,
                csi_path=CSI)

V22 = dict(full_sh=1.955, full_ann=0.2512, full_dd=-0.0816, full_cal=3.08,
            oos_sh=2.097, oos_ann=0.2979, oos_dd=-0.0600, oos_cal=4.97)

print('[A] V25 baseline (35只, AI数字 5只)')
ssA = segment_stats(run_strategy(**COMMON, uni_path=CACHE / 'etf_universe_v24diag.csv'))

print('[B] V25 add 588790 (36只, AI数字 6只)')
eng._DATA_CACHE.clear()
ssB = segment_stats(run_strategy(**COMMON, weekly_path=WK_OUT, uni_path=UNI_OUT))

print(f'\n{"指标":<14} {"V22":>10} {"V25 base":>10} {"V25 +588790":>13} {"Δ vs base":>10}')
print('-' * 65)
for seg, k_v22 in [('Full','full_sh'),('Full','full_ann'),('Full','full_dd'),('Full','full_cal'),
                     ('OOS','oos_sh'),('OOS','oos_ann'),('OOS','oos_dd'),('OOS','oos_cal')]:
    k = {'sh':'sharpe','ann':'ann','dd':'mdd','cal':'calmar'}[k_v22.split('_')[1]]
    lab = f'{seg} {k_v22.split("_")[1]}'
    a = ssA[seg][k]; b = ssB[seg][k]; d = b - a
    v22v = V22[k_v22]
    if k in ('ann','mdd'):
        print(f'{lab:<14} {v22v*100:>9.2f}% {a*100:>9.2f}% {b*100:>12.2f}% {d*100:>+9.2f}pp')
    else:
        print(f'{lab:<14} {v22v:>10.3f} {a:>10.3f} {b:>13.3f} {d:>+10.3f}')

# 八维严格非劣判定
def beats(s, ref):
    return all([s['Full']['sharpe']>=ref['full_sh'], s['Full']['ann']>=ref['full_ann'],
                  s['Full']['mdd']>=ref['full_dd'], s['Full']['calmar']>=ref['full_cal'],
                  s['OOS']['sharpe']>=ref['oos_sh'], s['OOS']['ann']>=ref['oos_ann'],
                  s['OOS']['mdd']>=ref['oos_dd'], s['OOS']['calmar']>=ref['oos_cal']])

print(f'\nV25 base   八维非劣 V22? {beats(ssA, V22)}')
print(f'V25 +588790 八维非劣 V22? {beats(ssB, V22)}')

# 588790 是否被持仓？
print('\n=== 588790 持仓检查 ===')
eng._DATA_CACHE.clear()
res = run_strategy(**COMMON, weekly_path=WK_OUT, uni_path=UNI_OUT, return_full=True)
w = res['w_final']
if NEW_CODE in w.columns:
    w588 = w[NEW_CODE]
    held_weeks = (w588 > 1e-5).sum()
    avg_w = w588[w588 > 1e-5].mean() if held_weeks > 0 else 0
    max_w = w588.max()
    first_held = w588[w588 > 1e-5].index[0] if held_weeks > 0 else None
    print(f'  持有周数: {held_weeks} / {len(w)} ({held_weeks/len(w)*100:.1f}%)')
    print(f'  平均权重: {avg_w*100:.2f}% / 最大权重: {max_w*100:.2f}%')
    print(f'  首次入场: {first_held.date() if first_held is not None else "—"}')
else:
    print('  588790 不在持仓矩阵中')
