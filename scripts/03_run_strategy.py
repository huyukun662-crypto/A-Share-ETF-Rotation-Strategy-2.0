"""
03_run_strategy.py — Run V7_gold strategy end-to-end and save metrics.

Pipeline:
  1. Load weekly ETF panel
  2. Build Leg A (penalized momentum, top-4)
  3. Build Leg G (9-group rotator, top-3 groups × top-1 ETF)
  4. Ensemble 50/50
  5. Apply slow gate (MA50) with gold fallback (159934.SZ)
  6. Apply 15% vol target
  7. Backtest with delay=1, cost 5 bps/side
  8. Write metrics + per-year + drawdowns + holdings + pnl

Outputs (in ./results/):
  metrics.json
  peryear.csv
  drawdowns.csv
  holdings.csv
  pnl.csv
  equity_curve.csv
"""
import json, time
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent.parent
CACHE = HERE / "data_cache"
OUT   = HERE / "results"; OUT.mkdir(parents=True, exist_ok=True)

def say(s): print(f"[{time.strftime('%H:%M:%S')}] {s}", flush=True)

GOLD = "159934.SZ"
SAMPLE_START = "2019-01-01"
VOL_TARGET   = 0.15
VOL_LB       = 26
GATE_MA      = 50
DELAY        = 1
COST_BPS     = 5
MOM_W        = 4
TURN_W       = 4
LAMBDA       = 1.5
MU           = 0.3
TOP_N_A      = 4
TOP_K_GROUPS = 3
PER_GROUP    = 1
ELIG_WEEKS   = 12

# ---- load ----
W = pd.read_parquet(CACHE / "etf_weekly.parquet")
uni = pd.read_csv(CACHE / "etf_universe.csv")
code2name = dict(zip(uni["ts_code"], uni["name"]))
code2group = dict(zip(uni["ts_code"], uni["group"]))

W["trade_week"] = pd.to_datetime(W["trade_week"])
W = W[W["trade_week"] >= SAMPLE_START].sort_values(["trade_week","ts_code"]).reset_index(drop=True)

ret  = W.pivot(index="trade_week", columns="ts_code", values="ret_w").sort_index()
turn = W.pivot(index="trade_week", columns="ts_code", values="turnover_w").sort_index()
gross = 1 + ret.fillna(0); cum = gross.cumprod()
age = ret.notna().cumsum(); elig = age >= ELIG_WEEKS
cols = ret.columns
say(f"weekly panel: {len(ret)} weeks × {len(cols)} ETFs, sample {ret.index[0].date()} → {ret.index[-1].date()}")

# ---- signals ----
def zscore_cs(df):
    df = df.where(elig); m=df.mean(axis=1); s=df.std(axis=1)
    return df.sub(m, axis=0).div(s, axis=0)

momX = cum / cum.shift(MOM_W) - 1
turnX = turn.rolling(TURN_W, min_periods=max(2, TURN_W//2)).mean()
br_s = ((cum > cum.rolling(20, min_periods=8).mean()).where(elig).sum(axis=1) /
        elig.sum(axis=1).replace(0, np.nan))
br_z = (br_s - br_s.rolling(52, min_periods=20).mean()) / br_s.rolling(52, min_periods=20).std()
bread_df = pd.DataFrame({c: br_z for c in cols})

# ---- Leg A ----
score_A = (zscore_cs(momX) - LAMBDA*zscore_cs(turnX) + MU*bread_df).reindex(columns=cols).astype(float)
w_A = np.zeros(score_A.shape)
sv = score_A.values.astype(float); rv = ret.values.astype(float); em = elig.values.astype(bool)
for ti in range(sv.shape[0]):
    s = sv[ti]; v = np.isfinite(s) & np.isfinite(rv[ti]) & em[ti]
    if v.sum() < TOP_N_A: continue
    s_v = np.where(v, s, -np.inf); ix = np.argpartition(-s_v, TOP_N_A)[:TOP_N_A]
    w_A[ti, ix] = 1.0/TOP_N_A
w_A = pd.DataFrame(w_A, index=ret.index, columns=cols)

# ---- Leg G ----
group_names = sorted(set(uni["group"].dropna()))
gret = pd.DataFrame(0.0, index=ret.index, columns=group_names)
for g in group_names:
    codes_g = [c for c in uni[uni["group"]==g]["ts_code"] if c in cols]
    v = elig[codes_g]
    gret[g] = ret[codes_g].where(v).mean(axis=1)
gcum = (1+gret.fillna(0)).cumprod()
gmom4 = gcum/gcum.shift(MOM_W) - 1

w_G = np.zeros((len(ret), len(cols)))
for ti in range(len(ret)):
    gs = gmom4.iloc[ti].dropna()
    if len(gs) < TOP_K_GROUPS: continue
    tops = gs.nlargest(TOP_K_GROUPS).index.tolist()
    picks = []
    for g in tops:
        codes_g = [c for c in uni[uni["group"]==g]["ts_code"] if c in cols]
        s = momX.iloc[ti][codes_g].dropna()
        s = s[[c for c in s.index if elig.iloc[ti][c]]]
        if len(s) < PER_GROUP: continue
        picks += s.nlargest(PER_GROUP).index.tolist()
    if not picks: continue
    nw = 1.0/len(picks)
    for c in picks: w_G[ti, cols.get_loc(c)] = nw
w_G = pd.DataFrame(w_G, index=ret.index, columns=cols)

# ---- Ensemble ----
w_ens = 0.5*w_A + 0.5*w_G

# ---- Gate (MA50) + gold fallback ----
mc = cum.mean(axis=1)
gate_on = (mc > mc.rolling(GATE_MA, min_periods=GATE_MA//2).mean()).reindex(ret.index).fillna(False)
w = w_ens.copy()
off = ~gate_on
w.loc[off] = 0.0
# 100% gold when off (if eligible)
gold_ok = elig[GOLD].fillna(False)
for t in w.index[off & gold_ok]:
    w.at[t, GOLD] = 1.0

# ---- Vol target ----
pnl_raw = (w.shift(DELAY) * ret).sum(axis=1)
rv = pnl_raw.rolling(VOL_LB, min_periods=8).std()*np.sqrt(52)
scale = (VOL_TARGET / rv).clip(upper=1.0).fillna(0)
w_final = w.mul(scale.reindex(w.index), axis=0)

# ---- Backtest ----
w_exec = w_final.shift(DELAY)
pnl_g  = (w_exec * ret).sum(axis=1)
tov    = (w_exec.fillna(0).diff().abs().sum(axis=1) / 2).fillna(0)
cost   = tov * (COST_BPS / 1e4)
pnl_net = pnl_g - cost

# ---- Metrics ----
def full_stats(pnl):
    r = pnl.dropna()
    yrs = len(r)/52.0
    ann = (1+r).prod()**(1/yrs)-1
    vol = r.std()*np.sqrt(52)
    sh  = ann/vol if vol>0 else np.nan
    eq  = (1+r).cumprod(); peak = eq.cummax()
    dd_s = eq/peak - 1; dd = dd_s.min()
    cal = ann/abs(dd) if dd<0 else np.nan
    down = r[r<0]; dv = down.std()*np.sqrt(52) if len(down)>0 else np.nan
    sortino = ann/dv if dv and dv>0 else np.nan
    return {
        "n_weeks": int(len(r)), "years": float(yrs),
        "ann_ret": float(ann), "vol": float(vol),
        "sharpe": float(sh), "sortino": float(sortino) if np.isfinite(sortino) else None,
        "max_dd": float(dd), "calmar": float(cal) if np.isfinite(cal) else None,
        "win_rate_weekly": float((r>0).mean()),
        "worst_week": float(r.min()), "best_week": float(r.max()),
        "skew": float(r.skew()), "kurt_excess": float(r.kurt()),
    }

def per_year(pnl):
    r = pnl.dropna(); r.index = pd.to_datetime(r.index); rows = []
    for yr, grp in r.groupby(r.index.year):
        if len(grp)<10: continue
        ann = (1+grp).prod()**(52/len(grp))-1
        vol_y = grp.std()*np.sqrt(52)
        sh = ann/vol_y if vol_y>0 else np.nan
        eq=(1+grp).cumprod(); dd=(eq/eq.cummax()-1).min()
        cal = ann/abs(dd) if dd<0 else np.nan
        down = grp[grp<0]; dv = down.std()*np.sqrt(52) if len(down)>0 else np.nan
        sortino = ann/dv if dv and dv>0 else np.nan
        rows.append({
            "year": int(yr),
            "ann_ret": float(ann), "vol": float(vol_y), "sharpe": float(sh),
            "sortino": float(sortino) if np.isfinite(sortino) else None,
            "max_dd": float(dd), "calmar": float(cal) if np.isfinite(cal) else None,
            "win_rate": float((grp>0).mean()), "n_weeks": int(len(grp)),
        })
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)

def top_drawdowns(pnl, k=10):
    r = pnl.dropna(); r.index = pd.to_datetime(r.index)
    eq = (1+r).cumprod(); peak = eq.cummax()
    dd = eq/peak - 1
    episodes = []
    start = None; mn = 0; mn_idx = None; last = None
    for t, v in dd.items():
        if v < -0.001:
            if start is None:
                start = t; mn = v; mn_idx = t
            else:
                if v < mn: mn = v; mn_idx = t
            last = t
        else:
            if start is not None:
                episodes.append({
                    "peak_date": str(dd.index[dd.index.get_loc(start)-1].date()) if dd.index.get_loc(start) > 0 else str(start.date()),
                    "trough_date": str(mn_idx.date()),
                    "recovery_date": str(t.date()),
                    "depth_pct": float(mn*100),
                    "duration_weeks": int((t - start).days/7 + 1),
                })
                start = None; mn = 0; mn_idx = None
    if start is not None:
        episodes.append({
            "peak_date": str(dd.index[dd.index.get_loc(start)-1].date()) if dd.index.get_loc(start) > 0 else str(start.date()),
            "trough_date": str(mn_idx.date()),
            "recovery_date": "not yet",
            "depth_pct": float(mn*100),
            "duration_weeks": int((last - start).days/7 + 1),
        })
    return pd.DataFrame(episodes).sort_values("depth_pct").head(k).reset_index(drop=True)

def time_weighted_holdings(w_exec, top=25):
    total = w_exec.fillna(0).sum(axis=0)
    avg = total / len(w_exec)
    rows = []
    for code in total.index:
        if total[code] == 0: continue
        rows.append({
            "ts_code": code,
            "etf_name": code2name.get(code, "?"),
            "group": code2group.get(code, "?"),
            "avg_weight": float(avg[code]),
            "weeks_held": int((w_exec[code] > 0).sum()),
            "pct_weeks_held": float((w_exec[code] > 0).mean()),
        })
    return pd.DataFrame(rows).sort_values("avg_weight", ascending=False).head(top).reset_index(drop=True)

# Compute
full = full_stats(pnl_net)
is_mask  = pnl_net.index < pd.Timestamp("2024-01-01")
oos_mask = pnl_net.index >= pd.Timestamp("2024-01-01")
is_stats  = full_stats(pnl_net[is_mask])
oos_stats = full_stats(pnl_net[oos_mask])

py = per_year(pnl_net)
dd_df = top_drawdowns(pnl_net, 10)
hold_df = time_weighted_holdings(w_exec, 25)

# Gate / fallback stats
gate_on_pct = gate_on.mean()
gold_dominant = (w_exec.get(GOLD, pd.Series(0,index=w_exec.index)).fillna(0) > 0.5).sum()

metrics = {
    "spec": "V7_gold",
    "description": "Ensemble (Leg A penalized mom + Leg G 9-group rotator) + MA50 gate + 100% 黄金ETF fallback + 15% vol target",
    "config": {
        "mom_w":MOM_W, "turn_w":TURN_W, "lambda":LAMBDA, "mu":MU, "top_n_A":TOP_N_A,
        "group_top_k":TOP_K_GROUPS, "per_group":PER_GROUP,
        "gate":"mkt_cum > 50w MA", "fallback":"100% 黄金ETF (159934.SZ)",
        "vol_target_annual":VOL_TARGET, "vol_lookback_w":VOL_LB,
        "rebalance_w":1, "delay":DELAY, "cost_bps_per_side":COST_BPS,
    },
    "sample": {"start": str(ret.index[0].date()), "end": str(ret.index[-1].date()), "n_weeks": int(len(ret))},
    "full": full, "is": is_stats, "oos": oos_stats,
    "gate_on_rate": float(gate_on_pct),
    "gold_dominant_weeks": int(gold_dominant),
    "gold_dominant_pct": float(gold_dominant / len(w_exec)),
    "annual_turnover_oneway": float(tov.mean()*52),
}

with open(OUT / "metrics.json", "w") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False)
py.to_csv(OUT / "peryear.csv", index=False)
dd_df.to_csv(OUT / "drawdowns.csv", index=False)
hold_df.to_csv(OUT / "holdings.csv", index=False)
pnl_net.to_frame("pnl_net").to_csv(OUT / "pnl.csv")
(1+pnl_net.fillna(0)).cumprod().to_frame("equity").to_csv(OUT / "equity_curve.csv")

say("===== V7_gold — HEADLINE =====")
for k in ("ann_ret","vol","sharpe","sortino","max_dd","calmar","win_rate_weekly","n_weeks"):
    v = full[k]
    if k in ("ann_ret","vol","max_dd","win_rate_weekly"):
        say(f"  {k:18s} {v*100:+.2f}%")
    else:
        say(f"  {k:18s} {v:.3f}" if isinstance(v,float) else f"  {k:18s} {v}")

say("\n===== Per-year =====")
print(py[["year","ann_ret","sharpe","sortino","max_dd","calmar","n_weeks"]].to_string(index=False))

say("\n===== Top 5 drawdowns =====")
print(dd_df.head(5).to_string(index=False))

say(f"\n[done] results written to {OUT}")
