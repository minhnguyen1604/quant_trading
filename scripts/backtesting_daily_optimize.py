#!/usr/bin/env python3
"""
Backtest EMA9 vs WMA45 crossover strategy with Daily mixed execution:
- Buy: Daily Close (crossover day Close)
- Sell: Daily Open (exit day Open)
Saves results to backtest_daily_optimize_ema9wma45.db.
"""
import argparse
import os
import sqlite3
import warnings
import sys
import numpy as np
import pandas as pd
from tqdm import tqdm
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.backtesting import _Broker

# Suppress Bokeh warnings and standard backtesting output clutter
import logging
logging.getLogger('bokeh').setLevel(logging.ERROR)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# Apply property-based monkey patch to _Broker to implement the mixed execution model
def get_trade_on_close(self):
    frame = sys._getframe()
    while frame:
        if frame.f_code.co_name == '_process_orders':
            order = frame.f_locals.get('order')
            if order is not None:
                # If it is a market buy order (long, not limit, not stop)
                if order.size > 0 and not order.limit and not order.stop:
                    return True
            break
        frame = frame.f_back
    return getattr(self, '_stored_trade_on_close', False)

def set_trade_on_close(self, value):
    self._stored_trade_on_close = value

_Broker._trade_on_close = property(get_trade_on_close, set_trade_on_close)

# Helper functions to calculate indicators
def calculate_ema(values, period):
    return pd.Series(values).ewm(span=period, adjust=False).mean().values

def calculate_wma(values, period):
    values_series = pd.Series(values)
    weights = np.arange(1, period + 1)
    return values_series.rolling(period).apply(lambda p: np.dot(p, weights) / weights.sum(), raw=True).values

class EmaWmaCrossover(Strategy):
    ema_period = 9
    wma_period = 45
    # Optional trailing stop: exit when Close falls this fraction below the highest close since entry (0 = off)
    trail_pct = 0.0
    peak = None

    def init(self):
        self.ema = self.I(calculate_ema, self.data.Close, self.ema_period)
        self.wma = self.I(calculate_wma, self.data.Close, self.wma_period)

    def next(self):
        if not self.position:
            self.peak = None
        # Buy: EMA9 crosses above WMA45
        if crossover(self.ema, self.wma):
            self.buy()
        # Exit: EMA9 crosses below WMA45, or the optional trailing stop is hit
        elif crossover(self.wma, self.ema) or self.trailing_stop_hit():
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

def run_daily_optimized_backtest(db_path, out_db_path, cash, commission, trail_pct=0.0):
    print(f"\n=== Running Daily Optimized EMA9-WMA45 Backtest (Buy on Close, Sell on Open) ===")
    if not os.path.exists(db_path):
        print(f"Error: Source database {db_path} does not exist.")
        return

    # Load daily data
    conn = sqlite3.connect(db_path)
    try:
        df_all = pd.read_sql_query(
            "SELECT Ticker, Date, Open, High, Low, Close, Volume FROM daily_prices ORDER BY Date ASC", 
            conn
        )
    except Exception as e:
        print(f"Error reading daily_prices: {e}")
        conn.close()
        return
    conn.close()

    if df_all.empty:
        print("daily_prices table is empty.")
        return

    tickers = df_all['Ticker'].unique()
    print(f"Found {len(tickers)} tickers to process.")

    results_list = []

    for ticker in tqdm(tickers, desc="Backtesting Daily Optimized"):
        df_ticker = df_all[df_all['Ticker'] == ticker].copy()
        
        if len(df_ticker) < 45:
            continue

        df_ticker['Date'] = pd.to_datetime(df_ticker['Date'])
        df_ticker.set_index('Date', inplace=True)
        df_ticker.sort_index(inplace=True)
        
        df_ticker = df_ticker[['Open', 'High', 'Low', 'Close', 'Volume']]
        for col in df_ticker.columns:
            df_ticker[col] = pd.to_numeric(df_ticker[col], errors='coerce')
        
        df_ticker.dropna(inplace=True)

        if len(df_ticker) < 45:
            continue

        try:
            bt = Backtest(df_ticker, EmaWmaCrossover, cash=cash, commission=commission)
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
        print("No successful backtests.")
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
    parser = argparse.ArgumentParser(description="Backtest EMA9 vs WMA45 Daily Optimized")
    parser.add_argument("--db", default="data_prices.db", help="Source SQLite database path")
    parser.add_argument("--daily-out", default="backtest_daily_optimize_ema9wma45.db", help="Output database for daily optimized results")
    parser.add_argument("--cash", type=float, default=100000000.0, help="Initial cash/equity per ticker")
    parser.add_argument("--commission", type=float, default=0.0015, help="Commission per trade")
    parser.add_argument("--trailing-stop", type=float, default=0.0, help="Trailing stop in percent below the highest close since entry, e.g. 25 (0 = off). Output DB names get a _trail<N> suffix")
    args = parser.parse_args()

    run_daily_optimized_backtest(
        db_path=args.db,
        out_db_path=with_trailing_suffix(args.daily_out, args.trailing_stop),
        cash=args.cash,
        commission=args.commission,
        trail_pct=args.trailing_stop / 100
    )

if __name__ == "__main__":
    main()
