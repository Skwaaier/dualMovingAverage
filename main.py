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

number_of_days = 50

close_mav5 = ohlcv_df['open'].rolling(5).mean().values[-number_of_days:]
close_mav10 = ohlcv_df['open'].rolling(10).mean().values[-number_of_days:]
mavdf = pd.DataFrame(dict(mav5 = close_mav5, mav10 = close_mav10), index = ohlcv_timestamps[-number_of_days:])

ap = mpf.make_addplot(mavdf, type='line')


# Determine buy/sell action

intersect_idx = np.argwhere(np.diff(np.sign(close_mav5 - close_mav10))).flatten()
intersectdf = pd.DataFrame(dict(intersection = close_mav5[intersect_idx]), index = ohlcv_timestamps[-number_of_days:][intersect_idx])


# Calculate value evolution

portfolio = pd.DataFrame(index = ohlcv_timestamps[-number_of_days:], columns = ['No trading', 'MAV5-MAV10'])
portfolio_initial_value = 1 # dollar
purchase_date = min(portfolio.index)
purchase_price = ohlcv_df['open'][purchase_date]
purchase_amount = portfolio_initial_value/purchase_price

# closest_to_purchase_date = min(ohlcv_df.index, key=lambda d: abs(d - purchase_date))

# No trading
for date in portfolio.index:
    day_price = ohlcv_df['open'][date]
    portfolio['No trading'][date] = day_price/purchase_price * portfolio_initial_value

# Trading on MAV5 AND MAV10 intersections
portfolio_value = portfolio_initial_value

for idx, date in enumerate(portfolio.index):
    
    # hold
    if np.sign(close_mav5 - close_mav10)[idx] == 1: 
        day_price = ohlcv_df['open'][date]  
        
        # buy 
        if np.sign(close_mav5 - close_mav10)[idx-1] == -1 and idx != 0:
            purchase_amount = portfolio['MAV5-MAV10'].iloc[idx-1]/day_price
        
        portfolio['MAV5-MAV10'][date] = day_price*purchase_amount
    
    # sell
    elif np.sign(close_mav5 - close_mav10)[idx] == -1:
        if idx == 0:
            portfolio['MAV5-MAV10'][date] = ohlcv_df['open'][purchase_date]*purchase_amount
        else:
            portfolio['MAV5-MAV10'][date] = portfolio['MAV5-MAV10'].iloc[idx-1]
        
    else:
        print('Unexpected change in moving average evaluation')



# Plotting

# Candle sticks with MAV
plt.figure()
mpf.plot(ohlcv_df[-number_of_days:], type = 'candle', addplot = ap)

# MAV with intersections
fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], close_mav5)
plt.plot(ohlcv_timestamps[-number_of_days:], close_mav10)
plt.plot(ohlcv_timestamps[-number_of_days:][intersect_idx], intersectdf, 'ro')

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
ax.set_ylabel('Price')
plt.xticks(rotation=45)

