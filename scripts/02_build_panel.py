"""
02_build_panel.py — Build weekly ETF panel from daily cache.

Inputs  (from scripts/01_fetch_data.py):
  data_cache/fund_daily_34.parquet
  data_cache/fund_adj_34.parquet
  data_cache/etf_universe.csv

Output:
  data_cache/etf_weekly.parquet  (columns: ts_code, etf_name, trade_week, ret_w, turnover_w, amount_w, cum_w)
"""
import time
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent.parent
CACHE = HERE / "data_cache"
def say(s): print(f"[{time.strftime('%H:%M:%S')}] {s}", flush=True)

fd = pd.read_parquet(CACHE / "fund_daily_34.parquet")
fa = pd.read_parquet(CACHE / "fund_adj_34.parquet")
df = fd.merge(fa, on=["ts_code","trade_date"], how="left")
df["close_adj"] = df["close"] * df["adj_factor"].fillna(1.0)
df = df.sort_values(["ts_code","trade_date"]).reset_index(drop=True)
df["ret"] = df.groupby("ts_code")["close_adj"].pct_change()
df["turnover_proxy"] = df["amount"]   # absolute amount, used as crowding z-score proxy

df[["trade_date","ts_code","etf_name","close","close_adj","ret","amount","vol","turnover_proxy"]].to_parquet(
    CACHE / "etf_daily.parquet"
)
say(f"daily panel written: {CACHE / 'etf_daily.parquet'}  ({len(df):,} rows)")

# Weekly (ISO-week Friday close)
df["year_week"] = df["trade_date"].dt.strftime("%G-%V")
df["gross"] = 1 + df["ret"].fillna(0)
df["cum"]   = df.groupby("ts_code")["gross"].cumprod()

weekly = (df.groupby(["ts_code","etf_name","year_week"], sort=False)
          .agg(trade_week=("trade_date","last"),
               cum_w=("cum","last"),
               turnover_w=("turnover_proxy","mean"),
               amount_w=("amount","sum"),
               vol_w=("vol","sum"))
          .reset_index()
          .sort_values(["ts_code","trade_week"]))
weekly["ret_w"] = weekly.groupby("ts_code")["cum_w"].pct_change()
weekly = weekly.dropna(subset=["ret_w"]).copy()
weekly.to_parquet(CACHE / "etf_weekly.parquet")
say(f"weekly panel written: {CACHE / 'etf_weekly.parquet'}  "
    f"({len(weekly):,} rows, {weekly['trade_week'].nunique()} weeks, {weekly['ts_code'].nunique()} ETFs)")
