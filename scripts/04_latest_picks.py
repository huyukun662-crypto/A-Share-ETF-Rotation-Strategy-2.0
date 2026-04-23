"""
04_latest_picks.py — Generate V7_gold picks for the most-recent trade week.

Trace through the full decision pipeline:
  1. Market gate state (MA50)
  2. Leg A score top-4 selection
  3. Leg G 9-group ranking + per-group leader
  4. Ensemble raw weights
  5. Vol target scale from rolling 26w strategy vol
  6. Final target weights
  7. Trade list vs previous week

Assumes strategy already ran at least once so we have pnl.csv for vol target.
If not, re-runs the backtest inline.
"""
import json, time
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent.parent
CACHE = HERE / "data_cache"
OUT   = HERE / "results"
def say(s): print(f"[{time.strftime('%H:%M:%S')}] {s}", flush=True)

GOLD = "159934.SZ"
SAMPLE_START = "2019-01-01"
VOL_TARGET = 0.15
MOM_W = 4; TURN_W = 4; LAMBDA = 1.5; MU = 0.3
TOP_N_A = 4; TOP_K_GROUPS = 3; PER_GROUP = 1
GATE_MA = 50; VOL_LB = 26; ELIG_WEEKS = 12

W = pd.read_parquet(CACHE / "etf_weekly.parquet")
uni = pd.read_csv(CACHE / "etf_universe.csv")
code2name = dict(zip(uni["ts_code"], uni["name"]))
code2group = dict(zip(uni["ts_code"], uni["group"]))

W["trade_week"] = pd.to_datetime(W["trade_week"])
W = W[W["trade_week"] >= SAMPLE_START].sort_values(["trade_week","ts_code"]).reset_index(drop=True)
ret = W.pivot(index="trade_week", columns="ts_code", values="ret_w").sort_index()
turn = W.pivot(index="trade_week", columns="ts_code", values="turnover_w").sort_index()
gross = 1 + ret.fillna(0); cum = gross.cumprod()
age = ret.notna().cumsum(); elig = age >= ELIG_WEEKS
cols = ret.columns
t_last = ret.index[-1]

say(f"Latest trade week:  {t_last.date()}")
say(f"Eligible ETFs:      {int(elig.iloc[-1].sum())} / {len(cols)}")

# --- STEP 1: Gate
mkt_cum = cum.mean(axis=1)
mkt_ma = mkt_cum.rolling(GATE_MA, min_periods=GATE_MA//2).mean()
gate_on = mkt_cum.loc[t_last] > mkt_ma.loc[t_last]
say(f"\n=== STEP 1 · MARKET GATE ===")
say(f"  mkt_cum @ {t_last.date()} = {mkt_cum.loc[t_last]:.4f}")
say(f"  mkt_cum 50w MA           = {mkt_ma.loc[t_last]:.4f}")
say(f"  Gate = {'ON (risk-on)' if gate_on else 'OFF (risk-off → 黄金 fallback)'}")

if not gate_on:
    say(f"\n=== FALLBACK: 100% 黄金ETF (159934.SZ) ===")
    say(f"(scale down by vol target; compute scale below)")

# --- Signals
def zscore_cs(df):
    df = df.where(elig); m=df.mean(axis=1); s=df.std(axis=1)
    return df.sub(m, axis=0).div(s, axis=0)

momX = cum / cum.shift(MOM_W) - 1
turnX = turn.rolling(TURN_W, min_periods=max(2, TURN_W//2)).mean()
br_s = ((cum > cum.rolling(20, min_periods=8).mean()).where(elig).sum(axis=1) /
        elig.sum(axis=1).replace(0, np.nan))
br_z = (br_s - br_s.rolling(52, min_periods=20).mean()) / br_s.rolling(52, min_periods=20).std()

z_m = zscore_cs(momX); z_t = zscore_cs(turnX)
row_score = z_m.loc[t_last] - LAMBDA*z_t.loc[t_last] + MU*br_z.loc[t_last]
row_mom = momX.loc[t_last]; row_turn = turnX.loc[t_last]

# --- STEP 2: Leg A
say(f"\n=== STEP 2 · LEG A (penalized momentum) ===")
say(f"  score = z(mom_4w) - {LAMBDA}*z(turn_4w) + {MU}*breadth_z")
say(f"  breadth_z = {br_z.loc[t_last]:+.3f}")
A_tab = pd.DataFrame({
    "etf": [code2name.get(c,"?") for c in cols],
    "group":[code2group.get(c,"?") for c in cols],
    "mom_4w":row_mom.values, "turn_4w":row_turn.values,
    "z_mom":z_m.loc[t_last].values, "z_turn":z_t.loc[t_last].values,
    "score_A":row_score.values,
    "eligible":elig.loc[t_last].values,
}, index=cols)
A_valid = A_tab[A_tab["eligible"]].sort_values("score_A", ascending=False)
top_A = A_valid.head(TOP_N_A).index.tolist()
say(f"\n  top-{TOP_N_A} picks:")
print(A_valid.head(TOP_N_A)[["etf","group","mom_4w","z_mom","z_turn","score_A"]].to_string())

w_A = pd.Series(0.0, index=cols)
for c in top_A: w_A[c] = 1.0/TOP_N_A

# --- STEP 3: Leg G
say(f"\n=== STEP 3 · LEG G (9-group rotator) ===")
group_names = sorted(set(uni["group"].dropna()))
gmom = {}
for g in group_names:
    codes_g = [c for c in uni[uni["group"]==g]["ts_code"] if c in cols]
    sub = row_mom[codes_g][elig.loc[t_last][codes_g]]
    gmom[g] = sub.mean() if len(sub)>0 else np.nan
gm = pd.Series(gmom).sort_values(ascending=False)
say(f"  组别 4w momentum (组内等权):")
for g, v in gm.items():
    mark = " ← PICK" if g in gm.head(TOP_K_GROUPS).index.tolist() else ""
    say(f"    {g:10s}  {v*100:+6.2f}%{mark}")

top_groups = gm.head(TOP_K_GROUPS).index.tolist()
picks_G = []
say(f"\n  每组领头:")
for g in top_groups:
    codes_g = [c for c in uni[uni["group"]==g]["ts_code"] if c in cols]
    sub = row_mom[codes_g].dropna()
    sub = sub[[c for c in sub.index if elig.loc[t_last][c]]]
    if len(sub)<PER_GROUP: continue
    leader = sub.nlargest(PER_GROUP).index[0]
    picks_G.append(leader)
    say(f"    [{g:6s}] {code2name[leader]:10s} ({leader})  mom_4w = {sub[leader]*100:+6.2f}%")

w_G = pd.Series(0.0, index=cols)
nw = 1.0/len(picks_G) if picks_G else 0
for c in picks_G: w_G[c] = nw

# --- STEP 4: Ensemble
say(f"\n=== STEP 4 · ENSEMBLE (0.5*A + 0.5*G) ===")
if gate_on:
    w_raw = 0.5*w_A + 0.5*w_G
else:
    w_raw = pd.Series(0.0, index=cols)
    if elig.loc[t_last][GOLD]:
        w_raw[GOLD] = 1.0

nz = w_raw[w_raw > 0].sort_values(ascending=False)
combo = pd.DataFrame({
    "etf": [code2name.get(c,"?") for c in nz.index],
    "group":[code2group.get(c,"?") for c in nz.index],
    "w_A": [w_A.get(c,0) for c in nz.index],
    "w_G": [w_G.get(c,0) for c in nz.index],
    "w_raw": nz.values,
}, index=nz.index)
print(combo.to_string())
say(f"  Raw total: {w_raw.sum()*100:.1f}%")

# --- STEP 5: Vol target
say(f"\n=== STEP 5 · VOL TARGET (15% annual, scale-down only) ===")
# Need rolling 26w strategy vol. Reconstruct quickly.
def build_full_weights():
    # Leg A full
    wm_A = np.zeros((len(ret), len(cols)))
    sv = (z_m - LAMBDA*z_t).values.astype(float)   # ignore breadth broadcast? Actually:
    # Use score = z_m - 1.5*z_t + 0.3*br_z (broadcast br_z)
    br_mat = pd.DataFrame({c: br_z for c in cols}).values.astype(float)
    score_full = sv + MU*br_mat
    rv = ret.values.astype(float); em = elig.values.astype(bool)
    for ti in range(len(ret)):
        s = score_full[ti]; v = np.isfinite(s) & np.isfinite(rv[ti]) & em[ti]
        if v.sum() < TOP_N_A: continue
        s_v = np.where(v, s, -np.inf); ix = np.argpartition(-s_v, TOP_N_A)[:TOP_N_A]
        wm_A[ti, ix] = 1.0/TOP_N_A
    # Leg G full
    gret = pd.DataFrame(0.0, index=ret.index, columns=group_names)
    for g in group_names:
        codes_g = [c for c in uni[uni["group"]==g]["ts_code"] if c in cols]
        v = elig[codes_g]
        gret[g] = ret[codes_g].where(v).mean(axis=1)
    gcum = (1+gret.fillna(0)).cumprod(); gmom4 = gcum/gcum.shift(MOM_W) - 1
    wm_G = np.zeros((len(ret), len(cols)))
    for ti in range(len(ret)):
        gs = gmom4.iloc[ti].dropna()
        if len(gs) < TOP_K_GROUPS: continue
        tops = gs.nlargest(TOP_K_GROUPS).index.tolist()
        picks = []
        for g in tops:
            codes_g = [c for c in uni[uni["group"]==g]["ts_code"] if c in cols]
            s = momX.iloc[ti][codes_g].dropna()
            s = s[[c for c in s.index if elig.iloc[ti][c]]]
            if len(s)<PER_GROUP: continue
            picks += s.nlargest(PER_GROUP).index.tolist()
        if not picks: continue
        nwt = 1.0/len(picks)
        for c in picks: wm_G[ti, cols.get_loc(c)] = nwt
    w_A_full = pd.DataFrame(wm_A, index=ret.index, columns=cols)
    w_G_full = pd.DataFrame(wm_G, index=ret.index, columns=cols)
    return w_A_full, w_G_full

w_Af, w_Gf = build_full_weights()
w_ens_full = 0.5*w_Af + 0.5*w_Gf
gate_series = (mkt_cum > mkt_ma).reindex(ret.index).fillna(False)
w_gated = w_ens_full.copy()
off_mask = ~gate_series
w_gated.loc[off_mask] = 0.0
gold_ok = elig[GOLD].fillna(False)
for t in w_gated.index[off_mask & gold_ok]:
    w_gated.at[t, GOLD] = 1.0
pnl_raw = (w_gated.shift(1) * ret).sum(axis=1)
rv26 = pnl_raw.rolling(VOL_LB, min_periods=8).std()*np.sqrt(52)
scale_series = (VOL_TARGET / rv26).clip(upper=1.0).fillna(0)
scale_now = scale_series.loc[t_last]
rv_now = rv26.loc[t_last]

say(f"  rolling 26w vol @ {t_last.date()}:  {rv_now*100:.2f}%")
say(f"  target vol:                       {VOL_TARGET*100:.2f}%")
say(f"  scale = min(1, {VOL_TARGET:.3f}/{rv_now:.4f}) = {scale_now:.3f}")

# --- STEP 6: Final weights
say(f"\n=== STEP 6 · FINAL TARGET WEIGHTS (for next trading day open) ===")
w_final = w_raw * scale_now
nz2 = w_final[w_final > 0].sort_values(ascending=False)
final_tab = pd.DataFrame({
    "etf": [code2name.get(c,"?") for c in nz2.index],
    "group":[code2group.get(c,"?") for c in nz2.index],
    "w_raw": [w_raw[c] for c in nz2.index],
    "scale": scale_now,
    "w_final": nz2.values,
}, index=nz2.index)
print(final_tab.to_string())
invested = w_final.sum()
say(f"\n  Invested total: {invested*100:.1f}%")
say(f"  Residual cash:  {(1-invested)*100:.1f}%")

# --- STEP 7: Trade list
say(f"\n=== STEP 7 · TRADES vs previous week ({ret.index[-2].date()}) ===")
scale_prev = scale_series.iloc[-2]
w_prev = w_gated.iloc[-2] * scale_prev
trades = w_final - w_prev
active = trades[abs(trades) > 1e-4].sort_values()
for code, delta in active.items():
    side = "BUY " if delta > 0 else "SELL"
    say(f"    {side}  {code2name.get(code,'?'):12s} ({code})  Δw = {delta*100:+6.2f}%")
tov_this = abs(trades).sum() / 2
say(f"\n  One-way turnover: {tov_this*100:.1f}%")

# Save pick
final_tab.to_csv(OUT / f"picks_{t_last.date()}.csv")
say(f"\n[done] Saved picks for {t_last.date()} to {OUT / f'picks_{t_last.date()}.csv'}")
