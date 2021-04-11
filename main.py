# Dual moving averaging bot

# Import libraries

import pandas as pd
import numpy as np
import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import mplfinance as mpf
import ccxt

# Input parameters

# symbol_container = ['BTCUSDT', 'ETHUSDT']
symbol = "BTC/USDT"
timeframe = '1d'

# Read historical data
  
exchange = ccxt.binance({
    'enableRateLimit': True
    })
markets = exchange.load_markets()


# each ohlcv candle is a list of [ timestamp, open, high, low, close, volume ]
ohlcv = exchange.fetch_ohlcv(symbol, timeframe)
ohlcv_timestamps = pd.to_datetime([row[0] for row in ohlcv], unit = 'ms')
ohlcv_data = [row[1:] for row in ohlcv]

ohlcv_df = pd.DataFrame(ohlcv_data, index = ohlcv_timestamps, columns = ['open', 'high', 'low', 'close', 'volume'])




# Determine moving averages

number_of_days = 100

close_mav5 = ohlcv_df['close'].rolling(5).mean().values[-number_of_days:]
close_mav10 = ohlcv_df['close'].rolling(10).mean().values[-number_of_days:]
mavdf = pd.DataFrame(dict(mav5 = close_mav5, mav10 = close_mav10), index = ohlcv_timestamps[-number_of_days:])

ap = mpf.make_addplot(mavdf, type='line')


# Determine buy/sell action

idx = np.argwhere(np.diff(np.sign(close_mav5 - close_mav10))).flatten()
intersectdf = pd.DataFrame(dict(intersection = close_mav5[idx]), index = ohlcv_timestamps[-number_of_days:][idx])


# Calculate value evolution

portfolio = pd.DataFrame(index = ohlcv_timestamps[-number_of_days:], columns = ['No trading', 'MAV5-MAV10'])
initial_amount = 100
purchase_date = min(portfolio.index)
purchase_price = ohlcv_df['open'][purchase_date]

# closest_to_purchase_date = min(ohlcv_df.index, key=lambda d: abs(d - purchase_date))

# No trading
for date in portfolio.index:
    day_price = ohlcv_df['open'][date]
    portfolio['No trading'][date] = day_price/purchase_price * initial_amount

# Trading on MAV5 AND MAV10 intersections



# Plotting

# Candle sticks with MAV
fig, ax = plt.subplots()
mpf.plot(ohlcv_df[-number_of_days:], type = 'candle', addplot = ap)

# MAV with intersections
fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], close_mav5)
plt.plot(ohlcv_timestamps[-number_of_days:], close_mav10)
plt.plot(ohlcv_timestamps[-number_of_days:][idx], intersectdf, 'ro')

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
ax.set_ylabel('Price')
plt.xticks(rotation=45)

