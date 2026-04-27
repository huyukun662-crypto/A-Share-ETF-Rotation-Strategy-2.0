# -*- coding: utf-8 -*-
"""V22_regime_accel final: hs300_acc + θ_on=0.05 + k_min=8"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strategy_v15 import run_strategy, segment_stats, V7_ROOT

rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
rcParams['axes.unicode_minus'] = False

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results'

PARAMS = dict(
    mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12,
    top_k_groups=3, per_group=1,
    risk_adj_nu=0.4,        # V15 (myinvestpilot)
    rev_w=0.05,              # V16 (Jegadeesh 1990)
    accel_w=0.10, longmom_window=13,    # V17 (Da et al 2014)
    # V22 增量: regime-conditional accel
    regime_accel_signal='hs300_acc',
    regime_accel_theta_on=0.05,
    regime_accel_theta_off=0.0,
    regime_accel_k_min=8,
    regime_accel_short_w=4,
    regime_accel_long_w=13,
)

print('=== V22_regime_accel final ===\n')
result = run_strategy(**PARAMS, return_full=True)
pnl_net = result['pnl_net']; w_final = result['w_final']
scale = result['scale']; gate_on = result['gate_on']
uni = result['uni']; regime_log = result['regime_accel_log']
ss = segment_stats(pnl_net)

# 八维对比 V7
v7m = json.loads((V7_ROOT / 'results' / 'metrics.json').read_text(encoding='utf-8'))
v17m = json.loads((OUT / 'v17_alt_metrics.json').read_text(encoding='utf-8'))
v19m = json.loads((OUT / 'v19_metrics.json').read_text(encoding='utf-8'))
v16m = json.loads((OUT / 'v16_metrics.json').read_text(encoding='utf-8'))

print(f"{'维度':<12} {'V7':>8} {'V16':>8} {'V17_alt':>8} {'V19':>8} {'V22':>8}")
print('-' * 60)
checks = []
for seg, key, label in [
    ('full', 'sharpe', 'Full Sh'), ('full', 'ann_ret', 'Full Ann'),
    ('full', 'max_dd', 'Full DD'), ('full', 'calmar', 'Full Cal'),
    ('oos', 'sharpe', 'OOS Sh'), ('oos', 'ann_ret', 'OOS Ann'),
    ('oos', 'max_dd', 'OOS DD'), ('oos', 'calmar', 'OOS Cal'),
]:
    v7v = v7m[seg][key]; v16v = v16m[seg][key]
    v17v = v17m[seg][key]; v19v = v19m[seg][key]
    seg_full = seg.upper() if seg == 'oos' else seg.title()
    fld = 'sharpe' if key=='sharpe' else 'ann' if key=='ann_ret' else 'mdd' if key=='max_dd' else 'calmar'
    v22v = ss[seg_full][fld]
    checks.append(v22v >= v7v)
    if key in ('ann_ret', 'max_dd'):
        print(f'{label:<12} {v7v*100:>7.2f}% {v16v*100:>7.2f}% {v17v*100:>7.2f}% '
              f'{v19v*100:>7.2f}% {v22v*100:>7.2f}%')
    else:
        print(f'{label:<12} {v7v:>8.3f} {v16v:>8.3f} {v17v:>8.3f} {v19v:>8.3f} {v22v:>8.3f}')

print(f'\n八维全超 V7: {"是 ✓" if all(checks) else "否 ✗"}')
on_pct = float(regime_log.mean()) if regime_log is not None else 0.0
n_switches = int((regime_log != regime_log.shift(1)).sum()) if regime_log is not None else 0
print(f'Regime ON 占比: {on_pct*100:.1f}% / 切换次数: {n_switches}')

# WF 5 折校验
print('\n=== WF 5 折稳定性 ===')
from _strategy_v15 import stats
folds = [('2021-12-31','2022'),('2022-12-31','2023'),('2023-12-31','2024'),
          ('2024-12-31','2025'),('2025-12-31','2026')]
COMBOS = [
    {'spec': 'V16', 'p': dict(mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12, top_k_groups=3, per_group=1, risk_adj_nu=0.4, rev_w=0.05)},
    {'spec': 'V17_alt', 'p': dict(mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12, top_k_groups=3, per_group=1, risk_adj_nu=0.4, rev_w=0.05, accel_w=0.10, longmom_window=13)},
    {'spec': 'V22', 'p': PARAMS},
]
pnl_by = {c['spec']: run_strategy(**c['p']) for c in COMBOS}
print(f'{"year":<6} {"picked":>10} {"train_Sh":>10} {"test_Sh":>9} {"test_ann":>10}')
v22_wins = 0
for tr_end, te_year in folds:
    te_s = pd.Timestamp(f'{te_year}-01-01'); te_e = pd.Timestamp(f'{te_year}-12-31')
    best, best_sh = None, -1e9
    for c in COMBOS:
        tr = pnl_by[c['spec']].loc[:tr_end]
        if len(tr) < 50: continue
        sh = stats(tr)['sharpe']
        if sh > best_sh: best_sh, best = sh, c['spec']
    test = pnl_by[best].loc[te_s:te_e]
    s = stats(test)
    if best == 'V22': v22_wins += 1
    print(f'{te_year:<6} {best:>10} {best_sh:>10.2f} {s["sharpe"]:>9.2f} {s["ann"]*100:>+9.2f}%')
print(f'V22 在 {v22_wins}/{len(folds)} 折被选中')

# 写 metrics
metrics = {
    'spec': 'V22_regime_accel',
    'sample': {'start': str(pnl_net.index[0].date()), 'end': str(pnl_net.index[-1].date()), 'n_weeks': len(pnl_net)},
    'params': dict(PARAMS),
    'design_intent': 'V17_alt + Regime-Conditional accel: 仅在 HS300 加速行情时启用动量加速度因子',
    'public_credit': {
        'engine': 'V7_gold cell 10', 'risk_adj_mom': 'myinvestpilot',
        'short_term_reversal': 'Jegadeesh 1990', 'momentum_acceleration': 'Da-Gurun-Warachka 2014',
        'regime_filter': '类比 Quantpedia trend filter 思路',
    },
    'regime_on_rate': on_pct,
    'regime_switch_count': n_switches,
    'wf_v22_win_rate': f'{v22_wins}/{len(folds)}',
    'full': dict(n_weeks=ss['Full']['n'], ann_ret=ss['Full']['ann'], vol=ss['Full']['vol'],
                  sharpe=ss['Full']['sharpe'], sortino=ss['Full']['sortino'],
                  max_dd=ss['Full']['mdd'], calmar=ss['Full']['calmar'], win_rate=ss['Full']['win']),
    'is': dict(n_weeks=ss['IS']['n'], ann_ret=ss['IS']['ann'], vol=ss['IS']['vol'],
                sharpe=ss['IS']['sharpe'], sortino=ss['IS']['sortino'],
                max_dd=ss['IS']['mdd'], calmar=ss['IS']['calmar'], win_rate=ss['IS']['win']),
    'val': dict(n_weeks=ss['Val']['n'], ann_ret=ss['Val']['ann'], vol=ss['Val']['vol'],
                 sharpe=ss['Val']['sharpe'], sortino=ss['Val']['sortino'],
                 max_dd=ss['Val']['mdd'], calmar=ss['Val']['calmar'], win_rate=ss['Val']['win']),
    'oos': dict(n_weeks=ss['OOS']['n'], ann_ret=ss['OOS']['ann'], vol=ss['OOS']['vol'],
                 sharpe=ss['OOS']['sharpe'], sortino=ss['OOS']['sortino'],
                 max_dd=ss['OOS']['mdd'], calmar=ss['OOS']['calmar'], win_rate=ss['OOS']['win']),
    'gate_on_rate': float(gate_on.mean()),
    'mode_now': 'RISK-ON' if bool(gate_on.iloc[-1]) else 'RISK-OFF',
    'regime_accel_now': bool(regime_log.iloc[-1]) if regime_log is not None else False,
    'scale_now': float(scale.iloc[-1]),
    'v22_8d_pass_v7': bool(all(checks)),
}
(OUT / 'v22_metrics.json').write_text(
    json.dumps(metrics, indent=2, ensure_ascii=False, default=float), encoding='utf-8')

# regime log
if regime_log is not None:
    pd.DataFrame({'trade_week': regime_log.index, 'regime_accel_on': regime_log.values}).to_csv(
        OUT / 'v22_regime_log.csv', index=False, encoding='utf-8-sig')

# NAV
nav = (1 + pnl_net.fillna(0)).cumprod()
nav.to_frame('equity').to_csv(OUT / 'v22_equity_curve.csv', encoding='utf-8-sig')
hs = pd.read_csv(V7_ROOT / 'results' / 'nav_vs_benchmark.csv')
hs['trade_week'] = pd.to_datetime(hs['trade_week'])
bench = hs.set_index('trade_week')['nav_csi300'].reindex(nav.index, method='ffill')
bench = bench / bench.iloc[0]
v7_nav = hs.set_index('trade_week')['nav_v7_gold'].reindex(nav.index, method='ffill')

fig, ax = plt.subplots(figsize=(12, 5.5))
ax.plot(nav.index, nav.values, color='#16A085', lw=2.0,
         label=f'V22_regime_accel (Sh {ss["Full"]["sharpe"]:.2f}, OOS Sh {ss["OOS"]["sharpe"]:.2f})')
ax.plot(v7_nav.index, v7_nav.values, color='#27AE60', lw=1.4, alpha=0.7, label='V7_gold')
ax.plot(bench.index, bench.values, color='#999', lw=1.2, label='CSI 300')
# regime ON 区间标黄
if regime_log is not None:
    for t in regime_log.index[regime_log]:
        ax.axvline(t, color='gold', alpha=0.05, lw=1.0)
ax.set_yscale('log'); ax.set_title(f'V22_regime_accel · accel ON {on_pct*100:.0f}% (黄线)')
ax.legend(loc='upper left'); ax.grid(True, ls=':', alpha=0.5)
dd = nav / nav.cummax() - 1
ax2 = ax.twinx()
ax2.fill_between(dd.index, dd.values * 100, 0, color='#C0392B', alpha=0.18)
ax2.set_ylabel('回撤 (%)', color='#C0392B')
ax2.set_ylim(min(dd.min() * 100 * 1.5, -15), 1)
plt.tight_layout()
plt.savefig(OUT / 'v22_nav_vs_benchmark.png', dpi=140); plt.close()

print(f'\n[saved] v22_metrics.json + v22_regime_log.csv + v22_nav.png')
