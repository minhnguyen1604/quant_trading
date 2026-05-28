#!/usr/bin/env python3
"""
Backtest EMA9 vs WMA45 crossover strategy for all tickers in Daily and Weekly timeframes.
Saves results to SQLite databases: backtest_daily.db and backtest_weekly.db.
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
def calculate_ema(values, period):
    return pd.Series(values).ewm(span=period, adjust=False).mean().values

def calculate_wma(values, period):
    values_series = pd.Series(values)
    weights = np.arange(1, period + 1)
    return values_series.rolling(period).apply(lambda p: np.dot(p, weights) / weights.sum(), raw=True).values

class EmaWmaCrossover(Strategy):
    ema_period = 9
    wma_period = 45

    def init(self):
        # Calculate EMA and WMA
        self.ema = self.I(calculate_ema, self.data.Close, self.ema_period)
        self.wma = self.I(calculate_wma, self.data.Close, self.wma_period)

    def next(self):
        # Long-only crossover strategy (VND market doesn't allow short selling)
        # Buy: EMA9 crosses above WMA45
        if crossover(self.ema, self.wma):
            self.buy()
        # Exit: EMA9 crosses below WMA45 (close position)
        elif crossover(self.wma, self.ema):
            self.position.close()

def clean_val(val):
    if pd.isna(val) or val == np.inf or val == -np.inf:
        return None
    # For numpy float/int types, convert to standard Python float/int
    if hasattr(val, 'item'):
        return val.item()
    return val

def run_backtest_for_table(db_path, table_name, out_db_path, cash, commission):
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
        
        # Check minimum data requirement (WMA45 requires at least 45 data points)
        if len(df_ticker) < 45:
            continue

        # Format DataFrame index and columns for backtesting.py
        df_ticker['Date'] = pd.to_datetime(df_ticker['Date'])
        df_ticker.set_index('Date', inplace=True)
        df_ticker.sort_index(inplace=True)
        
        # Keep only required columns
        df_ticker = df_ticker[['Open', 'High', 'Low', 'Close', 'Volume']]
        for col in df_ticker.columns:
            df_ticker[col] = pd.to_numeric(df_ticker[col], errors='coerce')
        
        df_ticker.dropna(inplace=True)

        if len(df_ticker) < 45:
            continue

        try:
            bt = Backtest(df_ticker, EmaWmaCrossover, cash=cash, commission=commission)
            stats = bt.run()
            
            # Map stats Series to clean dictionary structure
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

    # Write to target SQLite DB
    df_res = pd.DataFrame(results_list)
    
    # Sort by Ticker
    df_res.sort_values(by='Ticker', inplace=True)
    
    # Connect and save
    out_conn = sqlite3.connect(out_db_path)
    df_res.to_sql('results', out_conn, if_exists='replace', index=False)
    
    # Create indexes for quick query
    cur = out_conn.cursor()
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_results_ticker ON results(Ticker)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_results_return ON results(Return_Pct)")
    out_conn.commit()
    out_conn.close()

    print(f"Saved {len(df_res)} results to {out_db_path}")
    
    # Print summary top 10 performing tickers
    top_10 = df_res.sort_values(by='Return_Pct', ascending=False).head(10)
    print(f"\nTop 10 Tickers in {table_name} by Return [%]:")
    for idx, row in enumerate(top_10.itertuples(), 1):
        win_rate = f"{row.Win_Rate_Pct:.2f}%" if row.Win_Rate_Pct is not None else "N/A"
        print(f"{idx}. {row.Ticker}: Return: {row.Return_Pct:.2f}%, B&H Return: {row.Buy_Hold_Return_Pct:.2f}%, Trades: {row.Num_Trades}, Win Rate: {win_rate}")

def main():
    parser = argparse.ArgumentParser(description="Backtest EMA9 vs WMA45 strategy for all tickers")
    parser.add_argument("--db", default="data_prices.db", help="Source SQLite database path")
    parser.add_argument("--daily-out", default="backtest_daily_ema9wma45.db", help="Output database for daily results")
    parser.add_argument("--weekly-out", default="backtest_weekly_ema9wma45.db", help="Output database for weekly results")
    parser.add_argument("--cash", type=float, default=100000000.0, help="Initial cash/equity per ticker")
    parser.add_argument("--commission", type=float, default=0.0015, help="Commission per trade (0.0015 is 0.15%)")
    args = parser.parse_args()

    # Run Daily backtest
    run_backtest_for_table(
        db_path=args.db,
        table_name="daily_prices",
        out_db_path=args.daily_out,
        cash=args.cash,
        commission=args.commission
    )

    # Run Weekly backtest
    run_backtest_for_table(
        db_path=args.db,
        table_name="weekly_prices",
        out_db_path=args.weekly_out,
        cash=args.cash,
        commission=args.commission
    )

if __name__ == "__main__":
    main()
