# -*- coding: utf-8 -*-
"""
V15 strategy core — 精确复刻 V7_gold notebook cell 10 + V12-V14 增量改进。

关键设计:
  1. 主回测 (Leg A + Leg G + Gate + vol target) **完全照搬** V7 cell 10 → 引擎
     与 V7 notebook 1:1 一致，不引入任何 mask/cum 修改。
  2. 国债 ETF 511090 单独从 V12 weekly 读，仅在防御态触发时使用，
     **不进 ret/cum/momX/Leg A/Leg G** 横截面。
  3. 增量机制（ν 风险调整 / trailing stop / cat_cap / B 篮子）在主流程
     的特定位置插入，不污染 V7 baseline。
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

# Self-contained: 所有数据在仓内 data_cache/
REPO_ROOT = Path(__file__).resolve().parents[1]
V15_ROOT = REPO_ROOT  # 兼容 V18 OHLC 路径

WEEKLY_V7 = REPO_ROOT / 'data_cache' / 'etf_weekly.parquet'
WEEKLY_V12 = REPO_ROOT / 'data_cache' / 'etf_weekly_v12.parquet'
UNI_V7 = REPO_ROOT / 'data_cache' / 'etf_universe.csv'

GOLD = '159934.SZ'
BOND_30Y = '511090.SH'
SAMPLE_START = '2019-01-01'

_DATA_CACHE = {}  # key = (weekly_path, uni_path, csi_path) → dict


def _load_data(weekly_path=None, uni_path=None, csi_path=None):
    """加载周线/池子/CSI数据。默认 V7 池子，可传 V24 池子路径切换。
    csi_path 仅在 regime_*_signal=='csi_all_acc' 时需要。"""
    global _DATA_CACHE
    wp = str(weekly_path or WEEKLY_V7)
    up = str(uni_path or UNI_V7)
    cp = str(csi_path) if csi_path else None
    key = (wp, up, cp)
    if key in _DATA_CACHE:
        return _DATA_CACHE[key]
    weekly = pd.read_parquet(wp)
    uni = pd.read_csv(up, encoding='utf-8')
    W = weekly.copy()
    W['trade_week'] = pd.to_datetime(W['trade_week'])
    W = W[W['trade_week'] >= SAMPLE_START].sort_values(['trade_week', 'ts_code']).reset_index(drop=True)
    ret = W.pivot(index='trade_week', columns='ts_code', values='ret_w').sort_index()
    turn = W.pivot(index='trade_week', columns='ts_code', values='turnover_w').sort_index()
    cum = (1 + ret.fillna(0)).cumprod()
    bond_w = pd.read_parquet(WEEKLY_V12)
    bond_w = bond_w[bond_w['ts_code'] == BOND_30Y].copy()
    bond_w['trade_week'] = pd.to_datetime(bond_w['trade_week'])
    bond_w = bond_w[bond_w['trade_week'] >= SAMPLE_START].sort_values('trade_week')
    bond_ret = bond_w.set_index('trade_week')['ret_w']

    # === OHLC 周线（V18 日内因子）===
    ohlc_path = V15_ROOT / 'data_cache' / 'etf_weekly_ohlc.parquet'
    intraday_sum = overnight_sum = amplitude = close_pos = None
    if ohlc_path.exists():
        oh = pd.read_parquet(ohlc_path)
        oh['trade_week'] = pd.to_datetime(oh['trade_week'])
        oh = oh[oh['trade_week'] >= SAMPLE_START].sort_values(['trade_week', 'ts_code'])
        intraday_sum = oh.pivot(index='trade_week', columns='ts_code', values='intraday_sum_w').sort_index()
        overnight_sum = oh.pivot(index='trade_week', columns='ts_code', values='overnight_sum_w').sort_index()
        amplitude = oh.pivot(index='trade_week', columns='ts_code', values='amplitude_w_total').sort_index()
        close_pos = oh.pivot(index='trade_week', columns='ts_code', values='close_pos_w_total').sort_index()
        # 对齐 ret 的 columns/index
        for f in [intraday_sum, overnight_sum, amplitude, close_pos]:
            f.reindex_like(ret)

    # === CSI 000985 中证全指（V24 regime 信号源）===
    csi_ret = None
    if csi_path is not None and Path(csi_path).exists():
        cw = pd.read_parquet(csi_path)
        cw['trade_week'] = pd.to_datetime(cw['trade_week'])
        cw = cw[cw['trade_week'] >= SAMPLE_START].sort_values('trade_week')
        csi_ret = cw.set_index('trade_week')['ret_w']

    out = dict(weekly=W, uni=uni, ret=ret, turn=turn, cum=cum, bond_ret=bond_ret,
                intraday_sum=intraday_sum, overnight_sum=overnight_sum,
                amplitude=amplitude, close_pos=close_pos, csi_ret=csi_ret)
    _DATA_CACHE[key] = out
    return out


def run_strategy(
    # 沿用 V7 三段式冠军（不变）
    mom_w=4, lam=1.5, top_n_a=4, vol_target=0.12,
    top_k_groups=3, per_group=1,
    turn_w=4, mu=0.3, vol_lb=26, gate_ma=50,
    delay=1, cost_bps=5, elig_weeks=12,
    # V15 增量机制
    defense_basket=None,         # dict {ts_code: weight}; None = 单仓黄金
    basket_min_active=2,
    risk_adj_nu=0.0,             # myinvestpilot 风险调整动量系数
    cat_cap=None,                # 单板块上限
    scale_lower=0.0,             # vol target scale 下限
    trailing_dd=None,            # peak-to-now 触发阈值
    trailing_recover=0.03,
    trailing_max_cooldown=20,
    trailing_min_cooldown=5,
    # === 非动量因子（V16+）===
    rev_w=0.0,                   # F1 短期反转: -ω·z(ret_1w)
    lowvol_w=0.0,                # F2 低波动: -ω·z(vol_26w)
    trend_w=0.0,                 # F3 OLS 趋势 β·R² (20w 窗口)
    lowcorr_w=0.0,               # F4 低相关 -ω·z(mean_corr_52w)
    longmom_w=0.0,               # F5 长动量 z(cum/cum.shift(LONG_MOM)-1)
    longmom_window=13,           # 长动量窗口 (默认 13w 即 ~3M)
    accel_w=0.0,                 # F6 动量加速度 z(mom_4w - mom_13w)
    volchange_w=0.0,             # F7 波动突变 z(vol_4w/vol_26w)
    nearhigh_w=0.0,              # F8 接近 52w-high z(-(max-cur)/cur)
    pricepos_w=0.0,              # F9 52w 区间位置 z((cur-min)/(max-min))
    # 日内/隔夜因子族 (V18+)
    intraday_rev_w=0.0,          # F10 日内反转 -ω·z(intraday_sum_w) 4w 累计
    intraday_window=4,           # 日内/隔夜因子 rolling 窗口
    overnight_rev_w=0.0,         # F11 隔夜跳空反转 -ω·z(overnight_sum_w)
    amplitude_w_factor=0.0,      # F12 周振幅 ω·z(amplitude) 方向待测
    closepos_w=0.0,              # F13 周收盘位置 ω·z(close_pos_w)
    # === V22 Regime-Conditional accel_w ===
    regime_accel_signal=None,         # None / 'breadth_acc' / 'hs300_acc'
    regime_accel_theta_on=0.0, regime_accel_theta_off=-0.05,
    regime_accel_k_min=4, regime_accel_k_max=999,
    regime_accel_short_w=4, regime_accel_long_w=13,
    # === V23 Regime-Conditional nu (risk_adj) ===
    regime_nu_signal=None,            # None / 'low_vol' / 'high_vol' / 'hs300_acc'
    regime_nu_theta_on=0.0, regime_nu_theta_off=-0.05,
    regime_nu_k_min=4,
    # === V23 Regime-Conditional rev ===
    regime_rev_signal=None,           # None / 'high_vol' / 'low_vol'
    regime_rev_theta_on=0.0, regime_rev_theta_off=-0.05,
    regime_rev_k_min=4,
    return_full=False,
    # === V24: 数据路径覆盖 ===
    weekly_path=None, uni_path=None, csi_path=None,
):
    d = _load_data(weekly_path=weekly_path, uni_path=uni_path, csi_path=csi_path)
    uni = d['uni']
    ret, turn, cum = d['ret'], d['turn'], d['cum']
    bond_ret = d['bond_ret']

    age = ret.notna().cumsum()
    elig = age >= elig_weeks
    cols = ret.columns

    def zscore_cs(frame):
        df2 = frame.where(elig)
        m = df2.mean(axis=1); s = df2.std(axis=1)
        return df2.sub(m, axis=0).div(s, axis=0)

    momX = cum / cum.shift(mom_w) - 1
    turnX = turn.rolling(turn_w, min_periods=max(2, turn_w // 2)).mean()
    br_s = ((cum > cum.rolling(20, min_periods=8).mean()).where(elig).sum(axis=1)
            / elig.sum(axis=1).replace(0, np.nan))
    br_z = (br_s - br_s.rolling(52, min_periods=20).mean()) / br_s.rolling(52, min_periods=20).std()
    bread_df = pd.DataFrame({c: br_z for c in cols})
    z_m, z_t = zscore_cs(momX), zscore_cs(turnX)

    # === Leg A (V7 原版) ===
    score_A = (z_m - lam * z_t + mu * bread_df).reindex(columns=cols).astype(float)

    # ============ Regime 信号 helper (V22/V23 共用) ============
    def _build_regime_signal(signal_type, short_w=4, long_w=13):
        """计算 regime 信号 series, shift(1) 严格不含未来"""
        if signal_type == 'breadth_acc':
            br_legs = cum.where(elig)
            br_t = ((br_legs > br_legs.rolling(20, min_periods=8).mean()).sum(axis=1)
                    / elig.sum(axis=1).replace(0, np.nan))
            br_short = br_t.rolling(short_w, min_periods=2).mean()
            br_long = br_t.rolling(long_w, min_periods=4).mean()
            return (br_short - br_long).shift(1)
        elif signal_type == 'hs300_acc':
            mc_t = cum.where(elig).mean(axis=1)
            mom_short = mc_t / mc_t.shift(short_w) - 1
            mom_long = mc_t / mc_t.shift(long_w) - 1
            return (mom_short - mom_long).shift(1)
        elif signal_type == 'csi_all_acc':
            # V24: 真·中证全指 000985 加速度 = 4w 收益 - 13w 收益
            csi_r = d.get('csi_ret')
            if csi_r is None:
                # 回退到 hs300_acc 行为
                mc_t = cum.where(elig).mean(axis=1)
                mom_short = mc_t / mc_t.shift(short_w) - 1
                mom_long = mc_t / mc_t.shift(long_w) - 1
                return (mom_short - mom_long).shift(1)
            csi_cum = (1 + csi_r.fillna(0)).cumprod().reindex(cum.index, method='ffill')
            mom_short = csi_cum / csi_cum.shift(short_w) - 1
            mom_long = csi_cum / csi_cum.shift(long_w) - 1
            return (mom_short - mom_long).shift(1)
        elif signal_type == 'low_vol':
            # 大盘 vol z-score 取反: 低波动 = signal 高
            mc_t = cum.where(elig).mean(axis=1)
            mc_ret = mc_t.pct_change()
            rv_market = mc_ret.rolling(26, min_periods=8).std() * np.sqrt(52)
            rv_z = -((rv_market - rv_market.rolling(52, min_periods=20).mean())
                       / rv_market.rolling(52, min_periods=20).std())
            return rv_z.shift(1)
        elif signal_type == 'high_vol':
            mc_t = cum.where(elig).mean(axis=1)
            mc_ret = mc_t.pct_change()
            rv_market = mc_ret.rolling(26, min_periods=8).std() * np.sqrt(52)
            rv_z = ((rv_market - rv_market.rolling(52, min_periods=20).mean())
                       / rv_market.rolling(52, min_periods=20).std())
            return rv_z.shift(1)
        else:
            return pd.Series(1.0, index=cum.index)

    def _regime_state_machine(signal, theta_on, theta_off, k_min, k_max=999):
        """状态机: 滞回 + min/max persistence"""
        in_r = pd.Series(False, index=cum.index)
        cur, weeks = False, 0
        for i, t in enumerate(cum.index):
            sig = signal.iloc[i] if i < len(signal) else None
            if pd.isna(sig):
                in_r.iloc[i] = cur; weeks += 1; continue
            if not cur:
                if sig > theta_on and weeks >= k_min:
                    cur = True; weeks = 0
            else:
                timed_out = weeks >= k_max
                if (sig < theta_off or timed_out) and weeks >= k_min:
                    cur = False; weeks = 0
            in_r.iloc[i] = cur; weeks += 1
        return in_r

    # 增量 ν 风险调整动量项 (可选 regime-conditional)
    _regime_nu_log = None
    if risk_adj_nu and risk_adj_nu != 0.0:
        rv_etf = ret.rolling(vol_lb, min_periods=8).std() * np.sqrt(52)
        risk_adj_mom = (momX / rv_etf.replace(0, np.nan))
        z_ra = zscore_cs(risk_adj_mom)
        if regime_nu_signal is not None:
            sig = _build_regime_signal(regime_nu_signal)
            in_r = _regime_state_machine(sig, regime_nu_theta_on, regime_nu_theta_off, regime_nu_k_min)
            mask = in_r.astype(float).reindex(z_ra.index)
            score_A = score_A + risk_adj_nu * z_ra.mul(mask, axis=0).reindex(columns=cols).astype(float)
            _regime_nu_log = in_r
        else:
            score_A = score_A + risk_adj_nu * z_ra.reindex(columns=cols).astype(float)

    # === V16+ 非动量因子（每个独立 z-score，严格右对齐窗口）===
    # F1 短期反转: 1 周收益 z-score 取反 (可选 regime-conditional)
    _regime_rev_log = None
    if rev_w and rev_w != 0.0:
        z_rev = zscore_cs(ret)
        if regime_rev_signal is not None:
            sig = _build_regime_signal(regime_rev_signal)
            in_r = _regime_state_machine(sig, regime_rev_theta_on, regime_rev_theta_off, regime_rev_k_min)
            mask = in_r.astype(float).reindex(z_rev.index)
            score_A = score_A - rev_w * z_rev.mul(mask, axis=0).reindex(columns=cols).astype(float)
            _regime_rev_log = in_r
        else:
            score_A = score_A - rev_w * z_rev.reindex(columns=cols).astype(float)
    # F2 低波动: 26 周年化 vol z-score 取反
    if lowvol_w and lowvol_w != 0.0:
        vol_etf = ret.rolling(vol_lb, min_periods=8).std() * np.sqrt(52)
        z_lv = zscore_cs(vol_etf)
        score_A = score_A - lowvol_w * z_lv.reindex(columns=cols).astype(float)
    # F3 OLS 趋势 β·R² (20w 滚动)
    if trend_w and trend_w != 0.0:
        # log price OLS 趋势：β=斜率, R²=拟合度
        log_cum = np.log(cum.replace(0, np.nan))
        win = 20
        # 用 polyfit 太慢；用矩阵计算: β = cov(t, logP) / var(t)
        t_arr = np.arange(win)
        t_mean = t_arr.mean()
        t_centered = t_arr - t_mean
        t_var = (t_centered ** 2).sum()
        z_trend_dict = {}
        for c in cols:
            lp = log_cum[c].values
            beta = np.full(len(lp), np.nan)
            r2 = np.full(len(lp), np.nan)
            for i in range(win - 1, len(lp)):
                window = lp[i - win + 1:i + 1]
                if np.isnan(window).any():
                    continue
                y_mean = window.mean()
                y_centered = window - y_mean
                cov = (t_centered * y_centered).sum()
                b = cov / t_var
                ss_tot = (y_centered ** 2).sum()
                if ss_tot < 1e-12:
                    continue
                ss_res = ((y_centered - b * t_centered) ** 2).sum()
                rsq = max(0, 1 - ss_res / ss_tot)
                beta[i] = b
                r2[i] = rsq
            beta_ann = np.exp(beta * 252) - 1  # 年化趋势
            score = beta_ann * r2
            z_trend_dict[c] = pd.Series(score, index=log_cum.index)
        z_trend_raw = pd.DataFrame(z_trend_dict)
        z_trend = zscore_cs(z_trend_raw)
        score_A = score_A + trend_w * z_trend.reindex(columns=cols).astype(float)
    # F5 长动量
    if longmom_w and longmom_w != 0.0:
        long_mom = cum / cum.shift(longmom_window) - 1
        z_lm = zscore_cs(long_mom)
        score_A = score_A + longmom_w * z_lm.reindex(columns=cols).astype(float)
    # F6 动量加速度 (短动量 - 长动量) — 可选 regime-conditional 启用
    if accel_w and accel_w != 0.0:
        long_mom2 = cum / cum.shift(longmom_window) - 1
        accel = momX - long_mom2
        z_ac = zscore_cs(accel)

        # === V22: Regime-Conditional accel_w ===
        if regime_accel_signal is not None:
            # 计算 regime 信号
            if regime_accel_signal == 'breadth_acc':
                # 市场宽度加速度: breadth_short - breadth_long
                br_legs = cum.where(elig)
                br_t = ((br_legs > br_legs.rolling(20, min_periods=8).mean()).sum(axis=1)
                        / elig.sum(axis=1).replace(0, np.nan))
                br_short = br_t.rolling(regime_accel_short_w, min_periods=2).mean()
                br_long = br_t.rolling(regime_accel_long_w, min_periods=4).mean()
                regime_signal = (br_short - br_long).shift(1)  # 严格不含未来
            elif regime_accel_signal == 'hs300_acc':
                # HS300 动量加速 (用 cum 整体均值代替 HS300)
                mc_t = cum.where(elig).mean(axis=1)
                mom_short = mc_t / mc_t.shift(regime_accel_short_w) - 1
                mom_long = mc_t / mc_t.shift(regime_accel_long_w) - 1
                regime_signal = (mom_short - mom_long).shift(1)
            elif regime_accel_signal == 'csi_all_acc':
                # V24: 真·中证全指 000985 动量加速度
                csi_r = d.get('csi_ret')
                if csi_r is None:
                    mc_t = cum.where(elig).mean(axis=1)
                else:
                    mc_t = (1 + csi_r.fillna(0)).cumprod().reindex(cum.index, method='ffill')
                mom_short = mc_t / mc_t.shift(regime_accel_short_w) - 1
                mom_long = mc_t / mc_t.shift(regime_accel_long_w) - 1
                regime_signal = (mom_short - mom_long).shift(1)
            else:
                regime_signal = pd.Series(1.0, index=cum.index)  # 默认始终 ON

            # 状态机：滞回 + min_persistence
            in_regime = pd.Series(False, index=cum.index)
            cur_state = False
            weeks_held = 0
            for i, t in enumerate(cum.index):
                sig = regime_signal.iloc[i] if i < len(regime_signal) else None
                if pd.isna(sig):
                    in_regime.iloc[i] = cur_state
                    weeks_held += 1
                    continue
                if not cur_state:
                    if sig > regime_accel_theta_on and weeks_held >= regime_accel_k_min:
                        cur_state = True
                        weeks_held = 0
                else:
                    timed_out = weeks_held >= regime_accel_k_max
                    if (sig < regime_accel_theta_off or timed_out) and weeks_held >= regime_accel_k_min:
                        cur_state = False
                        weeks_held = 0
                in_regime.iloc[i] = cur_state
                weeks_held += 1

            # 按 regime 缩放 accel 贡献
            accel_mask = in_regime.astype(float).reindex(z_ac.index)
            z_ac_scaled = z_ac.mul(accel_mask, axis=0)
            score_A = score_A + accel_w * z_ac_scaled.reindex(columns=cols).astype(float)
            # 暴露 regime 序列给 return_full
            _regime_log = in_regime.copy()
        else:
            score_A = score_A + accel_w * z_ac.reindex(columns=cols).astype(float)
            _regime_log = pd.Series(True, index=cum.index)
    else:
        _regime_log = pd.Series(False, index=cum.index)
    # F7 波动突变
    if volchange_w and volchange_w != 0.0:
        vol_short = ret.rolling(4, min_periods=2).std() * np.sqrt(52)
        vol_long = ret.rolling(vol_lb, min_periods=8).std() * np.sqrt(52)
        vol_chg = vol_short / vol_long.replace(0, np.nan)
        z_vc = zscore_cs(vol_chg)
        score_A = score_A + volchange_w * z_vc.reindex(columns=cols).astype(float)
    # F8 接近 52w-high
    if nearhigh_w and nearhigh_w != 0.0:
        win_h = 52
        roll_max = cum.rolling(win_h, min_periods=12).max()
        # 距离 = (max - cur)/cur，越小越好；取反
        dist = (roll_max - cum) / cum.replace(0, np.nan)
        z_nh = zscore_cs(dist)
        score_A = score_A - nearhigh_w * z_nh.reindex(columns=cols).astype(float)
    # F9 52w 区间位置
    if pricepos_w and pricepos_w != 0.0:
        win_p = 52
        roll_max = cum.rolling(win_p, min_periods=12).max()
        roll_min = cum.rolling(win_p, min_periods=12).min()
        pos = (cum - roll_min) / (roll_max - roll_min).replace(0, np.nan)
        z_pp = zscore_cs(pos)
        score_A = score_A + pricepos_w * z_pp.reindex(columns=cols).astype(float)
    # === V18 日内/隔夜因子族（来自 BigQuant 昼夜分离 + heth.ink）===
    intra = d.get('intraday_sum')
    overn = d.get('overnight_sum')
    ampl = d.get('amplitude')
    cpos = d.get('close_pos')

    # F10 日内反转: 4w 累计 ln(close/open) 作为反转因子（A 股 IC ~ -7%）
    if intraday_rev_w and intraday_rev_w != 0.0 and intra is not None:
        intra_cum = intra.rolling(intraday_window, min_periods=2).sum()
        z_ir = zscore_cs(intra_cum)
        score_A = score_A - intraday_rev_w * z_ir.reindex(columns=cols).reindex(index=ret.index).astype(float)
    # F11 隔夜跳空反转: 绝对值越大反转越强（heth.ink）
    if overnight_rev_w and overnight_rev_w != 0.0 and overn is not None:
        # 用绝对值版本: 跳空越大越反转
        overn_cum = overn.abs().rolling(intraday_window, min_periods=2).sum()
        z_or = zscore_cs(overn_cum)
        score_A = score_A - overnight_rev_w * z_or.reindex(columns=cols).reindex(index=ret.index).astype(float)
    # F12 周振幅: 4w 平均振幅
    if amplitude_w_factor and amplitude_w_factor != 0.0 and ampl is not None:
        amp_avg = ampl.rolling(intraday_window, min_periods=2).mean()
        z_ap = zscore_cs(amp_avg)
        score_A = score_A + amplitude_w_factor * z_ap.reindex(columns=cols).reindex(index=ret.index).astype(float)
    # F13 周收盘位置: 4w 平均位置 (close-low)/(high-low)
    if closepos_w and closepos_w != 0.0 and cpos is not None:
        cp_avg = cpos.rolling(intraday_window, min_periods=2).mean()
        z_cp = zscore_cs(cp_avg)
        score_A = score_A + closepos_w * z_cp.reindex(columns=cols).reindex(index=ret.index).astype(float)

    # F4 低相关筛选（计算 52 周滚动相关，平均 |corr|，z-score 取反）
    if lowcorr_w and lowcorr_w != 0.0:
        # 简化：用 26 周窗口
        win = 26
        ret_cm = ret.fillna(0)
        z_lc_dict = {c: pd.Series(np.nan, index=ret.index) for c in cols}
        for i in range(win - 1, len(ret_cm)):
            window = ret_cm.iloc[i - win + 1:i + 1]
            corr_vals = window.corr().abs().values.copy()  # writeable copy
            np.fill_diagonal(corr_vals, np.nan)
            corr = pd.DataFrame(corr_vals, index=ret_cm.columns, columns=ret_cm.columns)
            mean_corr = corr.mean()
            for c in cols:
                z_lc_dict[c].iloc[i] = mean_corr.get(c, np.nan)
        z_lc_raw = pd.DataFrame(z_lc_dict)
        z_lc = zscore_cs(z_lc_raw)
        score_A = score_A - lowcorr_w * z_lc.reindex(columns=cols).astype(float)

    wA = np.zeros(score_A.shape)
    sv = score_A.values; rv = ret.values; em = elig.values.astype(bool)
    for ti in range(sv.shape[0]):
        s = sv[ti]; v = np.isfinite(s) & np.isfinite(rv[ti]) & em[ti]
        if v.sum() < top_n_a: continue
        sv_v = np.where(v, s, -np.inf)
        ix = np.argpartition(-sv_v, top_n_a)[:top_n_a]
        wA[ti, ix] = 1.0 / top_n_a
    w_A = pd.DataFrame(wA, index=ret.index, columns=cols)

    # === Leg G (V7 原版) ===
    group_names = sorted(set(uni['group'].dropna()))
    gret = pd.DataFrame(0.0, index=ret.index, columns=group_names)
    for g in group_names:
        codes_g = [c for c in uni[uni['group'] == g]['ts_code'] if c in cols]
        gret[g] = ret[codes_g].where(elig[codes_g]).mean(axis=1)
    gcum = (1 + gret.fillna(0)).cumprod()
    gmom4 = gcum / gcum.shift(mom_w) - 1
    wG = np.zeros((len(ret), len(cols)))
    for ti in range(len(ret)):
        gs = gmom4.iloc[ti].dropna()
        if len(gs) < top_k_groups: continue
        tops = gs.nlargest(top_k_groups).index.tolist()
        picks = []
        for g in tops:
            codes_g = [c for c in uni[uni['group'] == g]['ts_code'] if c in cols]
            s = momX.iloc[ti][codes_g].dropna()
            s = s[[c for c in s.index if elig.iloc[ti][c]]]
            if len(s) < per_group: continue
            picks += s.nlargest(per_group).index.tolist()
        if not picks: continue
        nw = 1.0 / len(picks)
        for c in picks: wG[ti, cols.get_loc(c)] = nw
    w_G = pd.DataFrame(wG, index=ret.index, columns=cols)

    # === Ensemble + Gate (V7 原版) ===
    w_ens = 0.5 * w_A + 0.5 * w_G

    # 增量：cat_cap 类别上限
    if cat_cap is not None and 0 < cat_cap < 1.0:
        code2grp = dict(zip(uni['ts_code'], uni['group']))
        for ti in range(len(w_ens)):
            row = w_ens.iloc[ti].copy()
            if row.sum() < 1e-6: continue
            grp_sum = {}
            for c, w_c in row.items():
                if w_c > 1e-6:
                    g = code2grp.get(c, '?')
                    grp_sum[g] = grp_sum.get(g, 0) + w_c
            for g, gw in grp_sum.items():
                if gw > cat_cap:
                    sc = cat_cap / gw
                    members = [c for c in row.index if code2grp.get(c) == g and row[c] > 1e-6]
                    for c in members:
                        row[c] *= sc
            new_sum = row.sum()
            orig_sum = w_ens.iloc[ti].sum()
            if new_sum > 1e-6:
                row *= (orig_sum / new_sum)
            w_ens.iloc[ti] = row

    # Gate (V7 原版)
    mc = cum.mean(axis=1)
    mcma = mc.rolling(gate_ma, min_periods=gate_ma // 2).mean()
    gate_on = (mc > mcma).reindex(ret.index).fillna(False)
    w = w_ens.copy()
    off = ~gate_on
    w.loc[off] = 0.0

    # 防御篮子（B2_gold_30Y）应用：在 RISK-OFF 周
    # 默认: 单仓黄金 (V7 原版)。若 defense_basket 给定，按 dict 分配。
    if defense_basket is None:
        # V7 原版逻辑：单仓黄金
        gold_ok = elig[GOLD].fillna(False)
        for t in w.index[off & gold_ok]:
            w.at[t, GOLD] = 1.0
    else:
        # V15 改进：B 篮子（含国债则需特殊处理）
        gold_ok = elig[GOLD].fillna(False)
        # 黄金 + 35 池其他 ETF 部分直接放进 w（在 cols 里）
        # 国债 511090 不在 cols 里，权重在 PnL 阶段单独 += bond_ret
        basket_in_cols = {c: w_ for c, w_ in defense_basket.items() if c in cols}
        bond_w_in_basket = sum(w_ for c, w_ in defense_basket.items() if c == BOND_30Y)
        for t in w.index[off]:
            # 动态可用性：国债 ETF 在该周必须有数据
            bond_avail = (t in bond_ret.index) and pd.notna(bond_ret.get(t))
            active = {}
            for c, w_c in basket_in_cols.items():
                if c == GOLD and gold_ok.get(t, False):
                    active[c] = w_c
                elif c != GOLD and elig.at[t, c]:
                    active[c] = w_c
            extra_bond = bond_w_in_basket if bond_avail else 0.0
            n_active_total = len(active) + (1 if bond_avail and bond_w_in_basket > 0 else 0)
            if n_active_total >= basket_min_active:
                tot = sum(active.values()) + extra_bond
                for c, w_c in active.items():
                    w.at[t, c] = w_c / tot
                # 国债权重存入额外的 series（在 PnL 阶段加进去）
            else:
                if gold_ok.get(t, False):
                    w.at[t, GOLD] = 1.0

    # === Vol target (V7 原版) ===
    pnl_raw = (w.shift(delay) * ret).sum(axis=1)
    rv_w = pnl_raw.rolling(vol_lb, min_periods=8).std() * np.sqrt(52)
    scale = (vol_target / rv_w).clip(lower=scale_lower, upper=1.0).fillna(scale_lower)
    w_final = w.mul(scale.reindex(w.index), axis=0)

    # === Trailing stop (V14 风格) ===
    trail_state = pd.Series(False, index=w_final.index)
    if trailing_dd is not None and trailing_dd < 0:
        # 用临时 NAV 算 peak-to-now
        w_exec_tmp = w_final.shift(delay)
        pnl_tmp = (w_exec_tmp * ret).sum(axis=1).fillna(0)
        nav_tmp = (1 + pnl_tmp).cumprod()

        in_trail = False
        weeks_in_trail = 0
        peak_at_entry = 1.0
        for i, t in enumerate(w_final.index):
            peak = nav_tmp.iloc[:i+1].max() if i >= 0 else 1.0
            cur_dd = nav_tmp.iloc[i] / peak - 1 if peak > 0 else 0.0
            if not in_trail:
                if cur_dd <= trailing_dd:
                    in_trail = True
                    weeks_in_trail = 0
                    peak_at_entry = nav_tmp.iloc[i]
            else:
                weeks_in_trail += 1
                recovered = (nav_tmp.iloc[i] / peak_at_entry - 1) >= trailing_recover
                timed_out = weeks_in_trail >= trailing_max_cooldown
                min_held = weeks_in_trail >= trailing_min_cooldown
                if min_held and (recovered or timed_out):
                    in_trail = False
            trail_state.iloc[i] = in_trail

        # 触发周覆盖为防御篮子（同 RISK-OFF 处理）
        for t in w_final.index[trail_state]:
            row = pd.Series(0.0, index=w_final.columns)
            if defense_basket is None:
                if elig[GOLD].get(t, False):
                    row[GOLD] = 1.0
            else:
                bond_avail = (t in bond_ret.index) and pd.notna(bond_ret.get(t))
                basket_in_cols = {c: w_ for c, w_ in defense_basket.items() if c in cols}
                bond_w_in_basket = sum(w_ for c, w_ in defense_basket.items() if c == BOND_30Y)
                active = {}
                for c, w_c in basket_in_cols.items():
                    if c == GOLD and elig[GOLD].get(t, False):
                        active[c] = w_c
                    elif c != GOLD and elig.at[t, c]:
                        active[c] = w_c
                extra = bond_w_in_basket if bond_avail else 0.0
                tot = sum(active.values()) + extra
                if tot > 1e-6:
                    for c, w_c in active.items():
                        row[c] = w_c / tot
                else:
                    if elig[GOLD].get(t, False):
                        row[GOLD] = 1.0
            w_final.loc[t] = row

    # === PnL 计算 (V7 原版) ===
    w_exec = w_final.shift(delay)
    pnl_g = (w_exec * ret).sum(axis=1)

    # 30Y 国债 PnL：在 RISK-OFF/trailing 周加进去（按 defense_basket 中的 bond 权重 × scale）
    if defense_basket and BOND_30Y in defense_basket:
        bond_w_target = defense_basket[BOND_30Y]
        # 防御态周且国债可用时，bond_pnl = bond_w_target × scale × bond_ret
        # 但实际 bond_w 取决于动态归一化（active 集合），这里近似用初始权重 × scale
        defense_weeks = (~gate_on) | trail_state
        bond_indicator = pd.Series(0.0, index=w_final.index)
        for t in w_final.index[defense_weeks]:
            bond_avail = (t in bond_ret.index) and pd.notna(bond_ret.get(t))
            if not bond_avail: continue
            # 重算 active 总权重做归一化
            basket_in_cols = {c: w_ for c, w_ in defense_basket.items() if c in cols}
            active = {}
            for c, w_c in basket_in_cols.items():
                if c == GOLD and elig[GOLD].get(t, False):
                    active[c] = w_c
                elif c != GOLD and elig.at[t, c]:
                    active[c] = w_c
            tot = sum(active.values()) + bond_w_target
            if tot > 1e-6:
                bond_indicator.loc[t] = bond_w_target / tot
        # bond_indicator * scale * bond_ret (shift delay 对齐)
        bond_w_series = bond_indicator * scale.reindex(w_final.index).fillna(0)
        bond_pnl = bond_w_series.shift(delay) * bond_ret.reindex(w_final.index).fillna(0)
        pnl_g = pnl_g + bond_pnl.fillna(0)
        # 加入换手成本（粗略：bond 权重变化也算换手）
        bond_tov = bond_w_series.diff().abs().fillna(0)
    else:
        bond_tov = pd.Series(0.0, index=w_final.index)

    tov = (w_exec.fillna(0).diff().abs().sum(axis=1) / 2).fillna(0) + bond_tov / 2
    cost = tov * (cost_bps / 1e4)
    pnl_net = pnl_g - cost

    if return_full:
        return dict(
            pnl_net=pnl_net, pnl_g=pnl_g, w_final=w_final, scale=scale,
            gate_on=gate_on, trail_state=trail_state,
            ret=ret, gmom=gmom4, group_names=group_names,
            uni=uni, cost=cost, cum=cum,
            regime_accel_log=locals().get('_regime_log', None),
            regime_nu_log=locals().get('_regime_nu_log', None),
            regime_rev_log=locals().get('_regime_rev_log', None),
        )
    return pnl_net


def stats(pnl, freq=52):
    """V7 风格统计：几何年化 (NAV^(freq/N)-1) + 算术波动 (sd*sqrt(freq))。
    Sharpe = 几何年化 / 算术年化波动。Calmar = 几何年化 / |MaxDD|.
    """
    r = pnl.dropna()
    if len(r) < 4:
        return dict(n=0, ann=np.nan, vol=np.nan, sharpe=np.nan,
                    sortino=np.nan, mdd=np.nan, calmar=np.nan, win=np.nan)
    nav = (1 + r).cumprod()
    n = len(r)
    ann = nav.iloc[-1] ** (freq / n) - 1   # 几何年化（V7 风格）
    sd = r.std() * np.sqrt(freq)
    sh = ann / sd if sd > 0 else np.nan
    dn = r[r < 0].std() * np.sqrt(freq)
    so = ann / dn if dn > 0 else np.nan
    mdd = (nav / nav.cummax() - 1).min()
    cal = ann / abs(mdd) if mdd < 0 else np.nan
    win = (r > 0).mean()
    return dict(n=n, ann=ann, vol=sd, sharpe=sh, sortino=so,
                mdd=mdd, calmar=cal, win=win)


def split_segments():
    return dict(
        IS=('2019-01-01', '2022-12-31'),
        Val=('2023-01-01', '2023-12-31'),
        OOS=('2024-01-01', '2099-12-31'),
        Full=('2019-01-01', '2099-12-31'),
    )


def segment_stats(pnl):
    out = {}
    for seg, (s, e) in split_segments().items():
        out[seg] = stats(pnl.loc[s:e])
    return out
