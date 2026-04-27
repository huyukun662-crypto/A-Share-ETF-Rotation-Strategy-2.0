# -*- coding: utf-8 -*-
"""V25 标的替换: 515980 AI_ETF (515980.SH) → 588790 科创人工智能 ETF (588790.SH)
   1. TuShare 抓 588790 日线 + adj → 周线（锚 V7 trade_week）
   2. 拼接 V7 weekly (剔除 515980) + 588790 周线 → etf_weekly_v25swap.parquet
   3. 写 etf_universe_v25swap.csv (35 只, 12 板块, 588790 落 AI数字)
   4. 跑 V25 回测对比 baseline
"""
import os, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V7_ROOT = Path(__file__).resolve().parents[2] / 'A-Share-ETF-Rotation-Strategy-2.0'
CACHE = ROOT / 'data_cache'
OUT = ROOT / 'results'

os.environ['TUSHARE_TOKEN'] = 'ddd1b26b20ff085ac9b60c9bd902ae76bbff60910863e8cc0168da53'
import tushare as ts
ts.set_token(os.environ['TUSHARE_TOKEN'])
pro = ts.pro_api()

OLD_CODE = '515980.SH'
NEW_CODE = '588790.SH'
NEW_NAME = '科创人工智能ETF'
NEW_GROUP = 'AI数字'

START_DATE = '20180101'
END_DATE = '20260430'

print(f'=== Phase 1: 抓 {NEW_CODE} {NEW_NAME} 日线 ===')
df = pro.fund_daily(ts_code=NEW_CODE, start_date=START_DATE, end_date=END_DATE)
if df is None or len(df) == 0:
    print('无日线数据，退出')
    sys.exit(1)
df['trade_date'] = pd.to_datetime(df['trade_date'])
df = df.sort_values('trade_date').reset_index(drop=True)
print(f'  日线 {len(df)} 行 / {df["trade_date"].min().date()} → {df["trade_date"].max().date()}')
last60 = df.tail(60)
avg_amt_wan = last60['amount'].mean() / 10
print(f'  近60d 日均成交: {avg_amt_wan:.0f} 万元')

try:
    adj = pro.fund_adj(ts_code=NEW_CODE, start_date=START_DATE, end_date=END_DATE)
    if adj is None or len(adj) == 0:
        adj = pd.DataFrame({'ts_code': df['ts_code'], 'trade_date': df['trade_date'], 'adj_factor': 1.0})
    else:
        adj['trade_date'] = pd.to_datetime(adj['trade_date'])
except Exception:
    adj = pd.DataFrame({'ts_code': df['ts_code'], 'trade_date': df['trade_date'], 'adj_factor': 1.0})

df = df.merge(adj[['ts_code', 'trade_date', 'adj_factor']], on=['ts_code', 'trade_date'], how='left')
df['adj_factor'] = df['adj_factor'].fillna(1.0)
df['close_adj'] = df['close'] * df['adj_factor']
df = df.dropna(subset=['close_adj']).sort_values('trade_date')
df['etf_name'] = NEW_NAME

# === Phase 2: 锚 V7 trade_week 聚合周线 ===
print('=== Phase 2: 锚 V7 trade_week 聚合周线 ===')
v7w = pd.read_parquet(V7_ROOT / 'data_cache' / 'etf_weekly.parquet')
v7w['trade_week'] = pd.to_datetime(v7w['trade_week'])
anchors = sorted(v7w['trade_week'].unique())
anchor_idx = pd.DatetimeIndex(anchors)

def assign_week(d):
    pos = anchor_idx.searchsorted(d, side='right') - 1
    return anchor_idx[pos] if pos >= 0 else pd.NaT

df['trade_week'] = df['trade_date'].apply(assign_week)
df = df.dropna(subset=['trade_week'])

agg = df.groupby(['ts_code', 'trade_week']).agg(
    cum_w=('close_adj', 'last'),
    amount_w=('amount', 'sum'),
    turnover_w=('pct_chg', lambda s: s.abs().mean()),
).reset_index()
agg['ret_w'] = agg.groupby('ts_code')['cum_w'].pct_change()
yw = v7w.drop_duplicates('trade_week').set_index('trade_week')['year_week']
agg['year_week'] = agg['trade_week'].map(yw)
agg['etf_name'] = NEW_NAME
agg = agg[['ts_code', 'etf_name', 'year_week', 'trade_week', 'cum_w', 'turnover_w', 'amount_w', 'ret_w']]
print(f'  588790 周线 {len(agg)} 行 / {agg["trade_week"].min().date()} → {agg["trade_week"].max().date()}')

# === Phase 3: 拼新 weekly parquet ===
print('=== Phase 3: 拼接 weekly parquet (剔除 515980 + 加 588790) ===')
v7w_keep = v7w[v7w['ts_code'] != OLD_CODE].copy()
new_w = pd.concat([v7w_keep, agg], ignore_index=True)
new_w = new_w.sort_values(['trade_week', 'ts_code']).reset_index(drop=True)
WK_OUT = CACHE / 'etf_weekly_v25swap.parquet'
new_w.to_parquet(WK_OUT, index=False)
print(f'  → {WK_OUT.name}: {len(new_w)} 行 / {new_w["ts_code"].nunique()} ETF')

# === Phase 4: 新 universe CSV ===
old_uni = pd.read_csv(CACHE / 'etf_universe_v24diag.csv', encoding='utf-8')
new_uni = old_uni[old_uni['ts_code'] != OLD_CODE].copy()
new_uni = pd.concat([new_uni, pd.DataFrame([dict(ts_code=NEW_CODE, name=NEW_NAME, group=NEW_GROUP)])],
                     ignore_index=True)
UNI_OUT = CACHE / 'etf_universe_v25swap.csv'
new_uni.to_csv(UNI_OUT, index=False, encoding='utf-8-sig')
print(f'  → {UNI_OUT.name}: {len(new_uni)} 只 / {new_uni["group"].nunique()} 板块')

# === Phase 5: V25 回测对比 ===
print('\n=== Phase 5: V25 回测对比 (515980 vs 588790) ===')
sys.path.insert(0, str(Path(__file__).resolve().parent))
# 清掉缓存
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

print('\n[A] V25 baseline (515980)')
ssA = segment_stats(run_strategy(**COMMON,
    uni_path=CACHE / 'etf_universe_v24diag.csv'))

print('[B] V25 swap (588790)')
eng._DATA_CACHE.clear()
ssB = segment_stats(run_strategy(**COMMON,
    weekly_path=WK_OUT, uni_path=UNI_OUT))

print(f'\n{"指标":<14} {"baseline 515980":>17} {"swap 588790":>14} {"Δ":>10}')
print('-' * 60)
for seg in ['Full', 'IS', 'OOS']:
    for k, lab in [('sharpe', 'Sh'), ('ann', '年化'), ('mdd', 'DD'), ('calmar', 'Cal')]:
        a = ssA[seg][k]; b = ssB[seg][k]; d = b - a
        if k in ('ann', 'mdd'):
            print(f'{seg+" "+lab:<14} {a*100:>16.2f}% {b*100:>13.2f}% {d*100:>+9.2f}pp')
        else:
            print(f'{seg+" "+lab:<14} {a:>17.3f} {b:>14.3f} {d:>+10.3f}')

print('\n[saved]')
print(f'  {WK_OUT}')
print(f'  {UNI_OUT}')
