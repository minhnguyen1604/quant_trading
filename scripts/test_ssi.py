import sys
import pandas as pd
import sqlite3
from backtesting import Backtest
from backtesting.backtesting import _Broker
import backtesting_ema9wma45_strategy as s

conn = sqlite3.connect('data_prices.db')
df = pd.read_sql_query('SELECT Date, Open, High, Low, Close, Volume FROM weekly_prices WHERE Ticker=\'SSI.VN\' ORDER BY Date ASC', conn)
conn.close()

df['Date'] = pd.to_datetime(df['Date'])
df.set_index('Date', inplace=True)
df = df.apply(pd.to_numeric)

# Run standard backtest
bt_std = Backtest(df, s.EmaWmaCrossover, cash=100000000.0, commission=0.0015)
stats_std = bt_std.run()
trades_std = stats_std['_trades'].copy()

# Apply property-based monkey patch for optimized execution
original_open_trade = _Broker._open_trade
def get_trade_on_close(self):
    frame = sys._getframe()
    while frame:
        if frame.f_code.co_name == '_process_orders':
            order = frame.f_locals.get('order')
            if order is not None:
                if order.size > 0 and not order.limit and not order.stop:
                    return True
            break
        frame = frame.f_back
    return getattr(self, '_stored_trade_on_close', False)

def set_trade_on_close(self, value):
    self._stored_trade_on_close = value

_Broker._trade_on_close = property(get_trade_on_close, set_trade_on_close)

bt_opt = Backtest(df, s.EmaWmaCrossover, cash=100000000.0, commission=0.0015)
stats_opt = bt_opt.run()
trades_opt = stats_opt['_trades'].copy()

# Revert patch
_Broker._trade_on_close = False

# Function to map Monday date label to Friday Calendar Date
def to_friday_date(dt):
    return (dt + pd.Timedelta(days=4)).strftime('%Y-%m-%d (Friday Close)')

def format_trades(trades, is_opt=False):
    res = []
    for idx, row in enumerate(trades.itertuples(), 1):
        buy_date = to_friday_date(row.EntryTime) if is_opt else row.EntryTime.strftime('%Y-%m-%d (Monday Open)')
        sell_date = row.ExitTime.strftime('%Y-%m-%d (Monday Open)')
        
        invested = row.Size * row.EntryPrice
        pnl = row.PnL
        ret_pct = row.ReturnPct * 100
        
        res.append({
            'Trade': idx,
            'Buy_Date': buy_date,
            'Buy_Price': f'{row.EntryPrice:,.2f}',
            'Sell_Date': sell_date,
            'Sell_Price': f'{row.ExitPrice:,.2f}',
            'Size': f'{row.Size:,}',
            'Invested': f'{invested:,.0f}',
            'PnL_VND': f'{pnl:+,.0f}',
            'Return': f'{ret_pct:+.2f}%'
        })
    return pd.DataFrame(res)

print('=== SSI.VN STANDARD TRADES (MON OPEN) ===')
print(format_trades(trades_std, is_opt=False).to_string(index=False))

print('\n=== SSI.VN OPTIMIZED TRADES (FRI CLOSE BUY) ===')
print(format_trades(trades_opt, is_opt=True).to_string(index=False))
