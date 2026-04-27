# -*- coding: utf-8 -*-
"""V24 补丁：将 159583 通信设备 ETF 加入池子（用户决策：豁免上市时长门槛）
   动态池 elig_weeks=12 会兜底处理 IS 段空数据。"""
import os, sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
V7_ROOT = Path(__file__).resolve().parents[2] / 'A-Share-ETF-Rotation-Strategy-2.0'
CACHE = ROOT / 'data_cache'

os.environ['TUSHARE_TOKEN'] = 'ddd1b26b20ff085ac9b60c9bd902ae76bbff60910863e8cc0168da53'
import tushare as ts
ts.set_token(os.environ['TUSHARE_TOKEN'])
pro = ts.pro_api()

CODE, NAME, GRP = '159583.SZ', '通信设备ETF', '通信光模块'

# 抓日线 + adj
df = pro.fund_daily(ts_code=CODE, start_date='20180101', end_date='20260430')
df['trade_date'] = pd.to_datetime(df['trade_date'])
df = df.sort_values('trade_date').reset_index(drop=True)
print(f'{CODE}: {len(df)} 行 / {df["trade_date"].iloc[0].date()} → {df["trade_date"].iloc[-1].date()}')

try:
    adj = pro.fund_adj(ts_code=CODE, start_date='20180101', end_date='20260430')
    adj['trade_date'] = pd.to_datetime(adj['trade_date'])
except Exception:
    adj = pd.DataFrame({'ts_code': df['ts_code'], 'trade_date': df['trade_date'], 'adj_factor': 1.0})

df = df.merge(adj[['ts_code', 'trade_date', 'adj_factor']], on=['ts_code', 'trade_date'], how='left')
df['adj_factor'] = df['adj_factor'].fillna(1.0)
df['close_adj'] = df['close'] * df['adj_factor']
df = df.dropna(subset=['close_adj']).sort_values('trade_date')

# 锚到 V7 weekly trade_week
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
agg['etf_name'] = NAME
agg = agg[['ts_code', 'etf_name', 'year_week', 'trade_week', 'cum_w', 'turnover_w', 'amount_w', 'ret_w']]
print(f'{CODE} 周线: {len(agg)} 行 / {agg["trade_week"].iloc[0].date()} → {agg["trade_week"].iloc[-1].date()}')

# 合并到 v24 weekly parquet
v24w = pd.read_parquet(CACHE / 'etf_weekly_v24.parquet')
if CODE in v24w['ts_code'].unique():
    v24w = v24w[v24w['ts_code'] != CODE]
v24w_new = pd.concat([v24w, agg], ignore_index=True).sort_values(['trade_week', 'ts_code']).reset_index(drop=True)
v24w_new.to_parquet(CACHE / 'etf_weekly_v24.parquet', index=False)
print(f'V24 weekly 更新: {len(v24w_new)} 行 / {v24w_new["ts_code"].nunique()} ETF')

# 加入 universe csv
v24u = pd.read_csv(CACHE / 'etf_universe_v24.csv', encoding='utf-8')
if CODE in v24u['ts_code'].values:
    print(f'{CODE} 已在 universe，跳过')
else:
    new_row = pd.DataFrame([{'ts_code': CODE, 'name': NAME, 'group': GRP}])
    # 插入到 515050.SH 后面（保持板块连续）
    insert_idx = v24u.index[v24u['ts_code'] == '515050.SH'].max() + 1
    v24u = pd.concat([v24u.iloc[:insert_idx], new_row, v24u.iloc[insert_idx:]], ignore_index=True)
    v24u.to_csv(CACHE / 'etf_universe_v24.csv', index=False, encoding='utf-8-sig')
    print(f'V24 universe 更新: {len(v24u)} 只')
print(v24u.groupby('group').size().to_string())
