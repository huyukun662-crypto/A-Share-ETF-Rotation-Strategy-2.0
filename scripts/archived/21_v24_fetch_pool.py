# -*- coding: utf-8 -*-
"""V24 Phase 1+2: 标的池扩容数据抓取
   - 18 只新 ETF 日线 + adj → 周线（与 V7 trade_week 严格对齐）
   - CSI 000985 中证全指日线 → 周线（regime 信号源）
   - MRF 互认基金 fund_basic 全量扫 + 候选周净值
   - 流动性筛选：上市 ≥ 2 年 + 日均成交 ≥ 3000 万
   - 输出：etf_universe_v24.csv / etf_weekly_v24.parquet
           csi_all_weekly.parquet / mrf_screening_v24.csv
"""
import os, sys, time
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
V7_ROOT = Path(__file__).resolve().parents[2] / 'A-Share-ETF-Rotation-Strategy-2.0'
CACHE = ROOT / 'data_cache'
CACHE.mkdir(exist_ok=True)

os.environ['TUSHARE_TOKEN'] = 'ddd1b26b20ff085ac9b60c9bd902ae76bbff60910863e8cc0168da53'
import tushare as ts
ts.set_token(os.environ['TUSHARE_TOKEN'])
pro = ts.pro_api()

START_DATE = '20180101'
END_DATE = '20260430'
LIQ_AMT_MIN_WAN = 3000      # 日均成交 ≥ 3000 万元
LIQ_LISTED_DAYS = 504       # 上市 ≥ 2 年（约 504 交易日）

# === V24 完整池子（53 只 ETF / 15 板块）===
V24_POOL = [
    # 半导体（上游）
    ('512480.SH', '半导体ETF',     '半导体'),
    ('159516.SZ', '半导体设备ETF', '半导体'),
    ('562590.SH', '半导体材料ETF', '半导体'),
    # 芯片（下游 / 科创）
    ('159995.SZ', '芯片ETF',       '芯片'),
    ('589100.SH', '科创芯片ETF',   '芯片'),
    ('512760.SH', '芯片产业ETF',   '芯片'),
    # 通信光模块
    ('515880.SH', '通信ETF',       '通信光模块'),
    ('515050.SH', '5G通信ETF',     '通信光模块'),
    ('159583.SZ', '通信设备ETF',   '通信光模块'),
    # AI 软件
    ('515980.SH', 'AI_ETF',         'AI软件'),
    ('515230.SH', '软件ETF',       'AI软件'),
    ('159890.SZ', '云计算ETF',     'AI软件'),
    ('159819.SZ', '人工智能AI_ETF','AI软件'),
    # 数字消费
    ('159779.SZ', '消费电子ETF',   '数字消费'),
    ('159869.SZ', '游戏ETF',       '数字消费'),
    # 新能源
    ('159857.SZ', '光伏ETF',       '新能源'),
    ('159755.SZ', '电池ETF',       '新能源'),
    ('515030.SH', '新能源车ETF',   '新能源'),
    ('159326.SZ', '电网设备ETF',   '新能源'),
    # 高端制造
    ('562500.SH', '机器人ETF',     '高端制造'),
    ('159227.SZ', '航空航天ETF',   '高端制造'),
    ('512660.SH', '军工ETF',       '高端制造'),
    # 大金融
    ('512800.SH', '银行ETF',       '大金融'),
    ('512880.SH', '证券ETF',       '大金融'),
    ('159892.SZ', '非银ETF',       '大金融'),
    # 医疗
    ('512010.SH', '医药ETF',       '医疗'),
    ('159992.SZ', '创新药ETF',     '医疗'),
    ('159883.SZ', '医疗器械ETF',   '医疗'),
    ('512290.SH', '生物医药ETF',   '医疗'),
    # 家电
    ('561120.SH', '家电ETF',       '家电'),
    ('159996.SZ', '家用电器ETF',   '家电'),
    ('159663.SZ', '智能家居ETF',   '家电'),
    # 食品酒水
    ('515170.SH', '食品ETF',       '食品酒水'),
    ('159736.SZ', '食品饮料ETF',   '食品酒水'),
    ('512690.SH', '酒ETF',         '食品酒水'),
    ('159843.SZ', '国证酒ETF',     '食品酒水'),
    # 周期资源
    ('159980.SZ', '有色ETF',       '周期资源'),
    ('515220.SH', '煤炭ETF',       '周期资源'),
    ('515210.SH', '钢铁ETF',       '周期资源'),
    ('561360.SH', '石油ETF',       '周期资源'),
    ('159870.SZ', '化工ETF',       '周期资源'),
    ('159713.SZ', '稀土ETF',       '周期资源'),
    ('159934.SZ', '黄金ETF',       '周期资源'),
    # 地产链
    ('512200.SH', '房地产ETF',     '地产链'),
    ('516750.SH', '建材ETF',       '地产链'),
    ('159619.SZ', '基建ETF',       '地产链'),
    # 农业
    ('159867.SZ', '畜牧ETF',       '农业'),
    ('159825.SZ', '农业ETF',       '农业'),
    ('516670.SH', '化肥农药ETF',   '农业'),
    # 红利
    ('515080.SH', '红利ETF',       '红利'),
    ('512890.SH', '红利低波ETF',   '红利'),
    ('561580.SH', '央企红利ETF',   '红利'),
    ('510880.SH', '中证红利ETF',   '红利'),
]
print(f'V24 候选池: {len(V24_POOL)} 只 / {len(set(g for _,_,g in V24_POOL))} 板块')

# === V7 已有的 35 只（直接复用其周线）===
v7_uni = pd.read_csv(V7_ROOT / 'data_cache' / 'etf_universe.csv', encoding='utf-8')
v7_codes = set(v7_uni['ts_code'])
new_codes = [(c, n, g) for c, n, g in V24_POOL if c not in v7_codes]
print(f'V7 已有: {len(v7_codes)} 只 / V24 新增: {len(new_codes)} 只')
for c, n, g in new_codes:
    print(f'  + {c} {n} ({g})')

# === Phase 1: 抓新 ETF 日线 + adj + 流动性筛选 ===
print(f'\n=== Phase 1: 抓 {len(new_codes)} 只新 ETF 日线 ===')
all_d, all_a, screening = [], [], []
for code, name, grp in new_codes:
    print(f'  {code} {name} ...', end=' ', flush=True)
    try:
        df = pro.fund_daily(ts_code=code, start_date=START_DATE, end_date=END_DATE)
        if df is None or len(df) == 0:
            print('无数据')
            screening.append(dict(ts_code=code, name=name, group=grp,
                                    listed_days=0, avg_amt_wan=0, pass_=False, reason='无日线数据'))
            continue
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)
        df['etf_name'] = name
        # 流动性指标
        listed_days = len(df)
        last60 = df.tail(60)
        avg_amt_wan = last60['amount'].mean() / 10  # tushare amount 单位 = 千元 → 转万元
        passed = (listed_days >= LIQ_LISTED_DAYS) and (avg_amt_wan >= LIQ_AMT_MIN_WAN)
        reason = ''
        if listed_days < LIQ_LISTED_DAYS:
            reason = f'上市{listed_days}d<{LIQ_LISTED_DAYS}d'
        elif avg_amt_wan < LIQ_AMT_MIN_WAN:
            reason = f'近60d均量{avg_amt_wan:.0f}万<{LIQ_AMT_MIN_WAN}万'
        screening.append(dict(ts_code=code, name=name, group=grp,
                                listed_days=listed_days, avg_amt_wan=round(avg_amt_wan, 1),
                                pass_=passed, reason=reason or 'OK'))
        all_d.append(df)
        # adj
        try:
            adj = pro.fund_adj(ts_code=code, start_date=START_DATE, end_date=END_DATE)
            if adj is not None and len(adj) > 0:
                adj['trade_date'] = pd.to_datetime(adj['trade_date'])
            else:
                adj = pd.DataFrame({'ts_code': df['ts_code'], 'trade_date': df['trade_date'], 'adj_factor': 1.0})
        except Exception:
            adj = pd.DataFrame({'ts_code': df['ts_code'], 'trade_date': df['trade_date'], 'adj_factor': 1.0})
        all_a.append(adj[['ts_code', 'trade_date', 'adj_factor']])
        flag = '✓' if passed else '✗'
        print(f'{flag} {listed_days}d / 量{avg_amt_wan:.0f}万')
        time.sleep(0.15)
    except Exception as e:
        print(f'失败: {e}')
        screening.append(dict(ts_code=code, name=name, group=grp,
                                listed_days=0, avg_amt_wan=0, pass_=False, reason=f'API错误:{e}'))

scr = pd.DataFrame(screening)
scr.to_csv(CACHE / 'etf_v24_screening.csv', index=False, encoding='utf-8-sig')
n_pass = scr['pass_'].sum() if len(scr) > 0 else 0
print(f'\nPhase 1 筛选结果：{n_pass}/{len(scr)} 新 ETF 通过流动性')
print(scr[['ts_code', 'name', 'group', 'listed_days', 'avg_amt_wan', 'pass_', 'reason']].to_string(index=False))

# === Phase 2a: 新 ETF 周线聚合（V7 schema）===
if all_d:
    new_d = pd.concat(all_d, ignore_index=True)
    new_a = pd.concat(all_a, ignore_index=True)
    df = new_d.merge(new_a, on=['ts_code', 'trade_date'], how='left')
    df['adj_factor'] = df['adj_factor'].fillna(1.0)
    df['close_adj'] = df['close'] * df['adj_factor']
    df = df.dropna(subset=['close_adj']).sort_values(['ts_code', 'trade_date'])

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

    agg_new = df.groupby(['ts_code', 'trade_week']).agg(
        cum_w=('close_adj', 'last'),
        amount_w=('amount', 'sum'),
        turnover_w=('pct_chg', lambda s: s.abs().mean()),
    ).reset_index()
    agg_new['ret_w'] = agg_new.groupby('ts_code')['cum_w'].pct_change()
    yw = v7w.drop_duplicates('trade_week').set_index('trade_week')['year_week']
    agg_new['year_week'] = agg_new['trade_week'].map(yw)
    name_map = {c: n for c, n, _ in new_codes}
    agg_new['etf_name'] = agg_new['ts_code'].map(name_map)
    agg_new = agg_new[['ts_code', 'etf_name', 'year_week', 'trade_week', 'cum_w', 'turnover_w', 'amount_w', 'ret_w']]

    # 仅保留通过流动性筛选的
    pass_codes = set(scr[scr['pass_']]['ts_code'])
    agg_new_pass = agg_new[agg_new['ts_code'].isin(pass_codes)].copy()
    print(f'\n通过筛选的新 ETF 周线行数: {len(agg_new_pass)}')
else:
    agg_new_pass = pd.DataFrame(columns=['ts_code', 'etf_name', 'year_week', 'trade_week', 'cum_w', 'turnover_w', 'amount_w', 'ret_w'])

# === Phase 2b: 合并 V7 35 + 新通过 → V24 weekly ===
v7w = pd.read_parquet(V7_ROOT / 'data_cache' / 'etf_weekly.parquet')
v24w = pd.concat([v7w, agg_new_pass], ignore_index=True)
v24w = v24w.sort_values(['trade_week', 'ts_code']).reset_index(drop=True)
v24w.to_parquet(CACHE / 'etf_weekly_v24.parquet', index=False)
print(f'V24 weekly: {len(v24w)} 行 / {v24w["ts_code"].nunique()} ETF')

# === Phase 2c: 写 V24 universe（仅含通过流动性的 ETF）===
v24_uni_rows = []
for c, n, g in V24_POOL:
    if c in v7_codes:
        v24_uni_rows.append(dict(ts_code=c, name=n, group=g))   # V7 已有 → 直接纳入
    elif c in pass_codes:
        v24_uni_rows.append(dict(ts_code=c, name=n, group=g))
v24_uni = pd.DataFrame(v24_uni_rows)
v24_uni.to_csv(CACHE / 'etf_universe_v24.csv', index=False, encoding='utf-8-sig')
print(f'\nV24 universe: {len(v24_uni)} 只 / {v24_uni["group"].nunique()} 板块')
print(v24_uni.groupby('group').size().to_string())

# === Phase 2d: CSI 000985 中证全指日线 → 周线 ===
print('\n=== Phase 2d: 抓 CSI 000985 中证全指 ===')
csi = pro.index_daily(ts_code='000985.CSI', start_date=START_DATE, end_date=END_DATE)
csi['trade_date'] = pd.to_datetime(csi['trade_date'])
csi = csi.sort_values('trade_date').reset_index(drop=True)
csi['trade_week'] = csi['trade_date'].apply(assign_week)
csi = csi.dropna(subset=['trade_week'])
csi_w = csi.groupby('trade_week').agg(close_w=('close', 'last')).reset_index()
csi_w['ret_w'] = csi_w['close_w'].pct_change()
csi_w.to_parquet(CACHE / 'csi_all_weekly.parquet', index=False)
print(f'CSI 000985 周线: {len(csi_w)} 行 / {csi_w["trade_week"].iloc[0].date()} → {csi_w["trade_week"].iloc[-1].date()}')

# === Phase 2e: MRF 互认基金扫描 ===
print('\n=== Phase 2e: MRF 互认基金 fund_basic 扫描 ===')
try:
    fb = pro.fund_basic(market='O')
    if fb is None or len(fb) == 0:
        fb = pro.fund_basic(market='OF')
    print(f'fund_basic 返回 {len(fb)} 行' if fb is not None else 'fb=None')
    if fb is not None and len(fb) > 0:
        # 互认基金代码 968 开头 或 名称含"互认/香港/摩根/惠理/行健"
        kw = ['互认', '香港', '摩根', '惠理', '行健', '易方达（香港）']
        m1 = fb['ts_code'].astype(str).str.startswith('968')
        m2 = fb['name'].astype(str).str.contains('|'.join(kw), na=False)
        mrf = fb[m1 | m2].copy()
        mrf.to_csv(CACHE / 'mrf_screening_v24.csv', index=False, encoding='utf-8-sig')
        print(f'MRF 候选: {len(mrf)} 只')
        if len(mrf) > 0:
            print(mrf[['ts_code', 'name', 'fund_type', 'found_date']].head(20).to_string(index=False))
except Exception as e:
    print(f'MRF 扫描失败: {e}')

print('\n=== 输出 ===')
for f in ['etf_universe_v24.csv', 'etf_weekly_v24.parquet', 'csi_all_weekly.parquet',
          'etf_v24_screening.csv', 'mrf_screening_v24.csv']:
    fp = CACHE / f
    if fp.exists():
        print(f'  {fp}: {fp.stat().st_size // 1024} KB')
