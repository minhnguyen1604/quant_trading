#!/usr/bin/env python3
"""
Backtest SMA5 vs SMA20 crossover strategy for all tickers in Daily and Weekly timeframes.
Saves results to SQLite databases: backtest_daily_ma5ma20.db and backtest_weekly_ma5ma20.db.
"""
import argparse
import os
import sqlite3
import warnings
import numpy as np
import pandas as pd
from tqdm import tqdm
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

# Suppress Bokeh warnings and standard backtesting output clutter
import logging
logging.getLogger('bokeh').setLevel(logging.ERROR)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# Helper function to calculate indicators inside backtesting.py self.I()
def calculate_sma(values, period):
    return pd.Series(values).rolling(period).mean().values

class SmaCrossover(Strategy):
    fast_period = 5
    slow_period = 20
    # Optional trailing stop: exit when Close falls this fraction below the highest close since entry (0 = off)
    trail_pct = 0.0
    peak = None

    def init(self):
        # Calculate SMA5 and SMA20
        self.fast_ma = self.I(calculate_sma, self.data.Close, self.fast_period)
        self.slow_ma = self.I(calculate_sma, self.data.Close, self.slow_period)

    def next(self):
        if not self.position:
            self.peak = None
        # Buy: SMA5 crosses above SMA20
        if crossover(self.fast_ma, self.slow_ma):
            self.buy()
        # Exit: SMA5 crosses below SMA20, or the optional trailing stop is hit
        elif crossover(self.slow_ma, self.fast_ma) or self.trailing_stop_hit():
            self.position.close()

    def trailing_stop_hit(self):
        if not self.position or not self.trail_pct:
            return False
        close = self.data.Close[-1]
        if self.peak is None:
            self.peak = self.trades[-1].entry_price
        self.peak = max(self.peak, close)
        return close <= self.peak * (1 - self.trail_pct)

def clean_val(val):
    if pd.isna(val) or val == np.inf or val == -np.inf:
        return None
    if hasattr(val, 'item'):
        return val.item()
    return val

def run_backtest_for_table(db_path, table_name, out_db_path, cash, commission, trail_pct=0.0):
    print(f"\n=== Running backtest on table: {table_name} ===")
    if not os.path.exists(db_path):
        print(f"Error: Source database {db_path} does not exist.")
        return

    # Load data
    conn = sqlite3.connect(db_path)
    try:
        df_all = pd.read_sql_query(
            f"SELECT Ticker, Date, Open, High, Low, Close, Volume FROM {table_name} ORDER BY Date ASC", 
            conn
        )
    except Exception as e:
        print(f"Error reading table {table_name}: {e}")
        conn.close()
        return
    conn.close()

    if df_all.empty:
        print(f"Table {table_name} is empty.")
        return

    tickers = df_all['Ticker'].unique()
    print(f"Found {len(tickers)} tickers to process.")

    results_list = []

    for ticker in tqdm(tickers, desc=f"Backtesting {table_name}"):
        df_ticker = df_all[df_all['Ticker'] == ticker].copy()
        
        # Check minimum data requirement (SMA20 requires at least 20 data points)
        if len(df_ticker) < 20:
            continue

        df_ticker['Date'] = pd.to_datetime(df_ticker['Date'])
        df_ticker.set_index('Date', inplace=True)
        df_ticker.sort_index(inplace=True)
        
        df_ticker = df_ticker[['Open', 'High', 'Low', 'Close', 'Volume']]
        for col in df_ticker.columns:
            df_ticker[col] = pd.to_numeric(df_ticker[col], errors='coerce')
        
        df_ticker.dropna(inplace=True)

        if len(df_ticker) < 20:
            continue

        try:
            bt = Backtest(df_ticker, SmaCrossover, cash=cash, commission=commission)
            stats = bt.run(trail_pct=trail_pct)
            
            res = {
                'Ticker': ticker,
                'Start_Date': stats['Start'].strftime('%Y-%m-%d') if pd.notna(stats['Start']) else None,
                'End_Date': stats['End'].strftime('%Y-%m-%d') if pd.notna(stats['End']) else None,
                'Duration_Days': clean_val(stats['Duration'].days) if pd.notna(stats['Duration']) else None,
                'Exposure_Time_Pct': clean_val(stats['Exposure Time [%]']),
                'Equity_Final': clean_val(stats['Equity Final [$]']),
                'Equity_Peak': clean_val(stats['Equity Peak [$]']),
                'Return_Pct': clean_val(stats['Return [%]']),
                'Buy_Hold_Return_Pct': clean_val(stats['Buy & Hold Return [%]']),
                'Return_Ann_Pct': clean_val(stats['Return (Ann.) [%]']),
                'Volatility_Ann_Pct': clean_val(stats['Volatility (Ann.) [%]']),
                'Sharpe_Ratio': clean_val(stats['Sharpe Ratio']),
                'Sortino_Ratio': clean_val(stats['Sortino Ratio']),
                'Calmar_Ratio': clean_val(stats['Calmar Ratio']),
                'Max_Drawdown_Pct': clean_val(stats['Max. Drawdown [%]']),
                'Avg_Drawdown_Pct': clean_val(stats['Avg. Drawdown [%]']),
                'Max_Drawdown_Duration_Days': clean_val(stats['Max. Drawdown Duration'].days) if pd.notna(stats['Max. Drawdown Duration']) else None,
                'Avg_Drawdown_Duration_Days': clean_val(stats['Avg. Drawdown Duration'].days) if pd.notna(stats['Avg. Drawdown Duration']) else None,
                'Num_Trades': int(stats['# Trades']) if pd.notna(stats['# Trades']) else 0,
                'Win_Rate_Pct': clean_val(stats['Win Rate [%]']),
                'Best_Trade_Pct': clean_val(stats['Best Trade [%]']),
                'Worst_Trade_Pct': clean_val(stats['Worst Trade [%]']),
                'Avg_Trade_Pct': clean_val(stats['Avg. Trade [%]']),
                'Max_Trade_Duration_Days': clean_val(stats['Max. Trade Duration'].days) if pd.notna(stats['Max. Trade Duration']) else None,
                'Avg_Trade_Duration_Days': clean_val(stats['Avg. Trade Duration'].days) if pd.notna(stats['Avg. Trade Duration']) else None,
                'Profit_Factor': clean_val(stats['Profit Factor']),
                'Expectancy_Pct': clean_val(stats['Expectancy [%]']),
                'SQN': clean_val(stats['SQN'])
            }
            results_list.append(res)
        except Exception:
            pass

    if not results_list:
        print(f"No successful backtests for {table_name}.")
        return

    df_res = pd.DataFrame(results_list)
    df_res.sort_values(by='Ticker', inplace=True)
    
    out_conn = sqlite3.connect(out_db_path)
    df_res.to_sql('results', out_conn, if_exists='replace', index=False)
    
    cur = out_conn.cursor()
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_results_ticker ON results(Ticker)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_results_return ON results(Return_Pct)")
    out_conn.commit()
    out_conn.close()

    print(f"Saved {len(df_res)} results to {out_db_path}")

def with_trailing_suffix(path, trailing_stop):
    """Keep trailing-stop results apart from the plain crossover results, e.g. x.db -> x_trail25.db."""
    if not trailing_stop:
        return path
    root, ext = os.path.splitext(path)
    return f"{root}_trail{trailing_stop:g}{ext}"

def main():
    parser = argparse.ArgumentParser(description="Backtest SMA5 vs SMA20 strategy")
    parser.add_argument("--db", default="data_prices.db", help="Source SQLite database path")
    parser.add_argument("--daily-out", default="backtest_daily_ma5ma20.db", help="Output database for daily results")
    parser.add_argument("--weekly-out", default="backtest_weekly_ma5ma20.db", help="Output database for weekly results")
    parser.add_argument("--cash", type=float, default=100000000.0, help="Initial cash/equity per ticker")
    parser.add_argument("--commission", type=float, default=0.0015, help="Commission per trade")
    parser.add_argument("--trailing-stop", type=float, default=0.0, help="Trailing stop in percent below the highest close since entry, e.g. 25 (0 = off). Output DB names get a _trail<N> suffix")
    args = parser.parse_args()

    # Run Daily backtest
    run_backtest_for_table(
        db_path=args.db,
        table_name="daily_prices",
        out_db_path=with_trailing_suffix(args.daily_out, args.trailing_stop),
        cash=args.cash,
        commission=args.commission,
        trail_pct=args.trailing_stop / 100
    )

    # Run Weekly backtest
    run_backtest_for_table(
        db_path=args.db,
        table_name="weekly_prices",
        out_db_path=with_trailing_suffix(args.weekly_out, args.trailing_stop),
        cash=args.cash,
        commission=args.commission,
        trail_pct=args.trailing_stop / 100
    )

if __name__ == "__main__":
    main()
