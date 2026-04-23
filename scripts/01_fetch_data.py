"""
01_fetch_data.py — Fetch all ETFs needed for V7_gold strategy.

Universe: 34 A-share thematic ETFs + 黄金ETF (159934.SZ) as fallback.

Outputs (in ./data_cache/):
  - fund_daily_34.parquet       main universe daily
  - fund_adj_34.parquet         adjustment factors
  - fund_daily_gold.parquet     (folded into main via 159934.SZ)

Requires: TUSHARE_TOKEN environment variable.
"""
import os, sys, time
from pathlib import Path
import pandas as pd
import tushare as ts

HERE = Path(__file__).resolve().parent.parent
CACHE = HERE / "data_cache"
CACHE.mkdir(parents=True, exist_ok=True)

TOKEN = os.environ.get("TUSHARE_TOKEN")
if not TOKEN:
    sys.exit("TUSHARE_TOKEN environment variable required.\n"
             "Get your token at https://tushare.pro/ and export it:\n"
             "  export TUSHARE_TOKEN='your_token'")
pro = ts.pro_api(TOKEN)

# 34-ETF universe + groups
ETFS = {
    # 科技成长
    "半导体ETF": "512480.SH", "消费电子ETF": "159779.SZ", "软件ETF": "515230.SH",
    "通信ETF": "515880.SH", "云计算ETF": "159890.SZ", "AI_ETF": "515980.SH",
    "游戏ETF": "159869.SZ",
    # 新能源
    "光伏ETF": "159857.SZ", "电池ETF": "159755.SZ", "新能源车ETF": "515030.SH",
    "电网设备ETF": "159326.SZ",
    # 高端制造
    "机器人ETF": "562500.SH", "航空航天ETF": "159227.SZ", "军工ETF": "512660.SH",
    # 大金融
    "银行ETF": "512800.SH", "证券ETF": "512880.SH", "非银ETF": "159892.SZ",
    # 大消费
    "酒ETF": "512690.SH", "家电ETF": "561120.SH", "食品ETF": "515170.SH",
    "医药ETF": "512010.SH", "创新药ETF": "159992.SZ", "医疗器械ETF": "159883.SZ",
    # 周期 / 上游
    "有色ETF": "159980.SZ", "煤炭ETF": "515220.SH", "钢铁ETF": "515210.SH",
    "石油ETF": "561360.SH", "化工ETF": "159870.SZ", "稀土ETF": "159713.SZ",
    "黄金ETF": "159934.SZ",
    # 地产链
    "房地产ETF": "512200.SH", "建材ETF": "516750.SH",
    # 农业
    "畜牧ETF": "159867.SZ",
    # 红利
    "红利ETF": "515080.SH",
}
GROUPS = {
    "科技成长": ["半导体ETF","消费电子ETF","软件ETF","通信ETF","云计算ETF","AI_ETF","游戏ETF"],
    "新能源":   ["光伏ETF","电池ETF","新能源车ETF","电网设备ETF"],
    "高端制造": ["机器人ETF","航空航天ETF","军工ETF"],
    "大金融":   ["银行ETF","证券ETF","非银ETF"],
    "大消费":   ["酒ETF","家电ETF","食品ETF","医药ETF","创新药ETF","医疗器械ETF"],
    "周期资源": ["有色ETF","煤炭ETF","钢铁ETF","石油ETF","化工ETF","稀土ETF","黄金ETF"],
    "地产链":   ["房地产ETF","建材ETF"],
    "农业":     ["畜牧ETF"],
    "红利":     ["红利ETF"],
}

def say(s): print(f"[{time.strftime('%H:%M:%S')}] {s}", flush=True)

# Save mapping
uni_df = pd.DataFrame(
    [{"name": n, "ts_code": c,
      "group": next((g for g,m in GROUPS.items() if n in m), None)}
     for n, c in ETFS.items()]
)
uni_df.to_csv(CACHE / "etf_universe.csv", index=False)
say(f"Saved ETF universe mapping: {CACHE / 'etf_universe.csv'}")

# Fetch fund_daily
FD = CACHE / "fund_daily_34.parquet"
if FD.exists():
    say(f"Already cached: {FD}")
else:
    rows = []
    for name, code in ETFS.items():
        for tries in range(3):
            try:
                df = pro.fund_daily(ts_code=code, start_date="20150101",
                                     end_date=time.strftime("%Y%m%d"))
                break
            except Exception as e:
                time.sleep(2 + tries)
        else:
            df = pd.DataFrame()
        if len(df) == 0:
            say(f"  NO DATA {name} ({code})"); continue
        df["etf_name"] = name
        rows.append(df)
        say(f"  {name} ({code}): {len(df)} rows")
    fd = pd.concat(rows, ignore_index=True)
    fd["trade_date"] = pd.to_datetime(fd["trade_date"])
    fd.to_parquet(FD)
    say(f"Saved: {FD}")

# Fetch fund_adj
FAJ = CACHE / "fund_adj_34.parquet"
if FAJ.exists():
    say(f"Already cached: {FAJ}")
else:
    rows = []
    for name, code in ETFS.items():
        for tries in range(3):
            try:
                df = pro.fund_adj(ts_code=code, start_date="20150101",
                                  end_date=time.strftime("%Y%m%d"))
                break
            except Exception as e:
                time.sleep(2 + tries)
        else:
            df = pd.DataFrame()
        if len(df) == 0: continue
        rows.append(df)
    fa = pd.concat(rows, ignore_index=True)
    fa["trade_date"] = pd.to_datetime(fa["trade_date"])
    fa.to_parquet(FAJ)
    say(f"Saved: {FAJ}")

say("[done] all data fetched.")
