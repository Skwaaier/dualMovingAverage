# Dual moving averaging bot

# Import libraries

import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import mplfinance as mpf
import ccxt


# Input parameters

# symbol_container = ['BTCUSDT', 'ETHUSDT']
symbol = "BTC/USDT"
timeframe = '4h'

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

number_of_days = 481 # max: 500 - largest mav days

# simple moving average
close_mav5 = ohlcv_df['close'].rolling(5).mean().values[-number_of_days:]
close_mav10 = ohlcv_df['close'].rolling(10).mean().values[-number_of_days:]
close_mav20 = ohlcv_df['close'].rolling(20).mean().values[-number_of_days:]

# exponential moving average
close_ema1 = ohlcv_df['close'].ewm(span=1, adjust=False).mean().values[-number_of_days:]
close_ema3 = ohlcv_df['close'].ewm(span=3, adjust=False).mean().values[-number_of_days:]
close_ema5 = ohlcv_df['close'].ewm(span=5, adjust=False).mean().values[-number_of_days:]
open_ema1 = ohlcv_df['open'].ewm(span=1, adjust=False).mean().values[-number_of_days:]
open_ema5 = ohlcv_df['open'].ewm(span=5, adjust=False).mean().values[-number_of_days:]

mavdf = pd.DataFrame(dict(mav5 = close_mav5, mav10 = close_mav10), index = ohlcv_timestamps[-number_of_days:])
emadf = pd.DataFrame(dict(ema1 = close_ema1, ema3 = close_ema3, ema5 = close_ema5), index = ohlcv_timestamps[-number_of_days:])

ap = mpf.make_addplot(mavdf, type='line')


# Determine buy/sell action

intersect_mav_idx = np.argwhere(np.diff(np.sign(close_mav5 - close_mav10))).flatten()
intersect_mav_df = pd.DataFrame(dict(intersection = close_mav5[intersect_mav_idx]), index = ohlcv_timestamps[-number_of_days:][intersect_mav_idx])

intersect_ema3_mav10_idx = np.argwhere(np.diff(np.sign(close_ema3 - close_mav10))).flatten()
intersect_ema3_mav10_df = pd.DataFrame(dict(intersection = close_mav10[intersect_ema3_mav10_idx]), index = ohlcv_timestamps[-number_of_days:][intersect_ema3_mav10_idx])

intersect_ema3_mav20_idx = np.argwhere(np.diff(np.sign(close_ema3 - close_mav20))).flatten()
intersect_ema3_mav20_df = pd.DataFrame(dict(intersection = close_mav20[intersect_ema3_mav20_idx]), index = ohlcv_timestamps[-number_of_days:][intersect_ema3_mav20_idx])

intersect_ema1_mav10_idx = np.argwhere(np.diff(np.sign(close_ema1 - close_mav10))).flatten()
intersect_ema1_mav10_df = pd.DataFrame(dict(intersection = close_mav10[intersect_ema1_mav10_idx]), index = ohlcv_timestamps[-number_of_days:][intersect_ema1_mav10_idx])

intersect_ema1_mav5_idx = np.argwhere(np.diff(np.sign(close_ema1 - close_mav5))).flatten()
intersect_ema1_mav5_df = pd.DataFrame(dict(intersection = close_mav5[intersect_ema1_mav5_idx]), index = ohlcv_timestamps[-number_of_days:][intersect_ema1_mav5_idx])

intersect_ema1_ema5_idx = np.argwhere(np.diff(np.sign(close_ema1 - close_ema5))).flatten()
intersect_ema1_ema5_df = pd.DataFrame(dict(intersection = close_ema5[intersect_ema1_ema5_idx]), index = ohlcv_timestamps[-number_of_days:][intersect_ema1_ema5_idx])

intersect_ema1_ema5_open_idx = np.argwhere(np.diff(np.sign(open_ema1 - open_ema5))).flatten()
intersect_ema1_ema5_open_df = pd.DataFrame(dict(intersection = open_ema5[intersect_ema1_ema5_open_idx]), index = ohlcv_timestamps[-number_of_days:][intersect_ema1_ema5_open_idx])

# Calculate value evolution

portfolio = pd.DataFrame(index = ohlcv_timestamps[-number_of_days:], columns = ['No trading', 'MAV5-MAV10', 'EMA3-MAV10', 'EMA3-MAV20', 'EMA1-MAV10', 'EMA1-MAV5', 'EMA1-EMA5', 'EMA1-EMA5 open'])
portfolio_initial_value = 1 # dollar
purchase_date = min(portfolio.index)
purchase_price = ohlcv_df['close'][purchase_date]
purchase_amount = portfolio_initial_value/purchase_price
transaction_fee = 0 # 0.1% on binance

# closest_to_purchase_date = min(ohlcv_df.index, key=lambda d: abs(d - purchase_date))


# No trading
for date in portfolio.index:
    day_price = ohlcv_df['close'][date]
    portfolio['No trading'][date] = day_price/purchase_price * portfolio_initial_value


# Trading on MAV5 AND MAV10 intersections
purchase_amount = portfolio_initial_value/purchase_price

for idx, date in enumerate(portfolio.index):
    
    # hold
    if np.sign(close_mav5 - close_mav10)[idx] == 1: 
        day_price = ohlcv_df['close'][date]
        
        # buy 
        if np.sign(close_mav5 - close_mav10)[idx-1] == -1 and idx != 0:
            purchase_amount = portfolio['MAV5-MAV10'].iloc[idx-1]/day_price*(1-transaction_fee)
        
        portfolio['MAV5-MAV10'][date] = day_price*purchase_amount
    
    # sell
    elif np.sign(close_mav5 - close_mav10)[idx] == -1:
        if idx == 0:
            portfolio['MAV5-MAV10'][date] = ohlcv_df['close'][purchase_date]*purchase_amount*(1-transaction_fee)
        else:
            portfolio['MAV5-MAV10'][date] = portfolio['MAV5-MAV10'].iloc[idx-1]*(1-transaction_fee)
        
    else:
        print('Unexpected change in moving average evaluation')
        
        
# Trading on EMA3 AND MAV10 intersections
purchase_amount = portfolio_initial_value/purchase_price

for idx, date in enumerate(portfolio.index):
    
    # hold
    if np.sign(close_ema3 - close_mav10)[idx] == 1: 
        day_price = ohlcv_df['close'][date]
        
        # buy 
        if np.sign(close_ema3 - close_mav10)[idx-1] == -1 and idx != 0:
            purchase_amount = portfolio['EMA3-MAV10'].iloc[idx-1]/day_price*(1-transaction_fee)
        
        portfolio['EMA3-MAV10'][date] = day_price*purchase_amount
    
    # sell
    elif np.sign(close_ema3 - close_mav10)[idx] == -1:
        if idx == 0:
            portfolio['EMA3-MAV10'][date] = ohlcv_df['close'][purchase_date]*purchase_amount*(1-transaction_fee)
        else:
            portfolio['EMA3-MAV10'][date] = portfolio['EMA3-MAV10'].iloc[idx-1]*(1-transaction_fee)
        
    else:
        print('Unexpected change in moving average evaluation')
        
        
# Trading on EMA3 AND MAV20 intersections
purchase_amount = portfolio_initial_value/purchase_price

for idx, date in enumerate(portfolio.index):
    
    # hold
    if np.sign(close_ema3 - close_mav20)[idx] == 1: 
        day_price = ohlcv_df['close'][date]
        
        # buy 
        if np.sign(close_ema3 - close_mav20)[idx-1] == -1 and idx != 0:
            purchase_amount = portfolio['EMA3-MAV20'].iloc[idx-1]/day_price*(1-transaction_fee)
        
        portfolio['EMA3-MAV20'][date] = day_price*purchase_amount
    
    # sell
    elif np.sign(close_ema3 - close_mav20)[idx] == -1:
        if idx == 0:
            portfolio['EMA3-MAV20'][date] = ohlcv_df['close'][purchase_date]*purchase_amount*(1-transaction_fee)
        else:
            portfolio['EMA3-MAV20'][date] = portfolio['EMA3-MAV20'].iloc[idx-1]*(1-transaction_fee)
        
    else:
        print('Unexpected change in moving average evaluation')
        
        
# Trading on EMA1 AND MAV10 intersections
purchase_amount = portfolio_initial_value/purchase_price

for idx, date in enumerate(portfolio.index):
    
    # hold
    if np.sign(close_ema1 - close_mav10)[idx] == 1: 
        day_price = ohlcv_df['close'][date]
        
        # buy 
        if np.sign(close_ema1 - close_mav10)[idx-1] == -1 and idx != 0:
            purchase_amount = portfolio['EMA1-MAV10'].iloc[idx-1]/day_price*(1-transaction_fee)
        
        portfolio['EMA1-MAV10'][date] = day_price*purchase_amount
    
    # sell
    elif np.sign(close_ema1 - close_mav10)[idx] == -1:
        if idx == 0:
            portfolio['EMA1-MAV10'][date] = ohlcv_df['close'][purchase_date]*purchase_amount*(1-transaction_fee)
        else:
            portfolio['EMA1-MAV10'][date] = portfolio['EMA1-MAV10'].iloc[idx-1]*(1-transaction_fee)
        
    else:
        print('Unexpected change in moving average evaluation')
        

# Trading on EMA1 AND MAV5 intersections
purchase_amount = portfolio_initial_value/purchase_price

for idx, date in enumerate(portfolio.index):
    
    # hold
    if np.sign(close_ema1 - close_mav5)[idx] == 1: 
        day_price = ohlcv_df['close'][date]
        
        # buy 
        if np.sign(close_ema1 - close_mav5)[idx-1] == -1 and idx != 0:
            purchase_amount = portfolio['EMA1-MAV5'].iloc[idx-1]/day_price*(1-transaction_fee)
        
        portfolio['EMA1-MAV5'][date] = day_price*purchase_amount
    
    # sell
    elif np.sign(close_ema1 - close_mav5)[idx] == -1:
        if idx == 0:
            portfolio['EMA1-MAV5'][date] = ohlcv_df['close'][purchase_date]*purchase_amount*(1-transaction_fee)
        else:
            portfolio['EMA1-MAV5'][date] = portfolio['EMA1-MAV5'].iloc[idx-1]*(1-transaction_fee)
        
    else:
        print('Unexpected change in moving average evaluation')
        
        
# Trading on EMA1 AND EMA5 intersections
purchase_amount = portfolio_initial_value/purchase_price

for idx, date in enumerate(portfolio.index):
    
    # hold
    if np.sign(close_ema1 - close_ema5)[idx] == 1: 
        day_price = ohlcv_df['close'][date]
        
        # buy 
        if np.sign(close_ema1 - close_ema5)[idx-1] == -1 and idx != 0:
            purchase_amount = portfolio['EMA1-EMA5'].iloc[idx-1]/day_price*(1-transaction_fee)
        
        portfolio['EMA1-EMA5'][date] = day_price*purchase_amount
    
    # sell
    elif np.sign(close_ema1 - close_ema5)[idx] == -1:
        if idx == 0:
            portfolio['EMA1-EMA5'][date] = ohlcv_df['close'][purchase_date]*purchase_amount*(1-transaction_fee)
        else:
            portfolio['EMA1-EMA5'][date] = portfolio['EMA1-EMA5'].iloc[idx-1]*(1-transaction_fee)
        
    else:
        print('Unexpected change in moving average evaluation')
        
        
# Trading on open EMA1 AND EMA5 intersections
purchase_amount = portfolio_initial_value/purchase_price

for idx, date in enumerate(portfolio.index):
    
    # hold
    if np.sign(open_ema1 - open_ema5)[idx] == 1: 
        day_price = ohlcv_df['open'][date]
        
        # buy 
        if np.sign(open_ema1 - open_ema5)[idx-1] == -1 and idx != 0:
            purchase_amount = portfolio['EMA1-EMA5 open'].iloc[idx-1]/day_price*(1-transaction_fee)
        
        portfolio['EMA1-EMA5 open'][date] = day_price*purchase_amount
    
    # sell
    elif np.sign(open_ema1 - open_ema5)[idx] == -1:
        if idx == 0:
            portfolio['EMA1-EMA5 open'][date] = ohlcv_df['open'][purchase_date]*purchase_amount*(1-transaction_fee)
        else:
            portfolio['EMA1-EMA5 open'][date] = portfolio['EMA1-EMA5 open'].iloc[idx-1]*(1-transaction_fee)
        
    else:
        print('Unexpected change in moving average evaluation')




# Plotting

plt.close('all')

# Closing price evolution
fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], ohlcv_df['close'][-number_of_days:])
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %Y'))
ax.set_ylabel('Price')
plt.xticks(rotation=45)

# Candle sticks with MAV
plt.figure()
mpf.plot(ohlcv_df[-number_of_days:], type = 'candle', addplot = ap)

# MAV with intersections
fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], close_mav5)
plt.plot(ohlcv_timestamps[-number_of_days:], close_mav10)
plt.plot(ohlcv_timestamps[-number_of_days:][intersect_mav_idx], intersect_mav_df, 'ro')

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %Y'))
ax.set_ylabel('Price')
plt.xticks(rotation=45)

# EMA with intersections
fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], close_ema3)
plt.plot(ohlcv_timestamps[-number_of_days:], close_mav10)
plt.plot(ohlcv_timestamps[-number_of_days:][intersect_ema3_mav10_idx], intersect_ema3_mav10_df, 'ro')

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %Y'))
ax.set_ylabel('Price')
plt.xticks(rotation=45)

# EMA with intersections
fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], close_ema3)
plt.plot(ohlcv_timestamps[-number_of_days:], close_mav20)
plt.plot(ohlcv_timestamps[-number_of_days:][intersect_ema3_mav20_idx], intersect_ema3_mav20_df, 'ro')

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %Y'))
ax.set_ylabel('Price')
plt.xticks(rotation=45)

# EMA with intersections
fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], close_ema1)
plt.plot(ohlcv_timestamps[-number_of_days:], close_mav10)
plt.plot(ohlcv_timestamps[-number_of_days:][intersect_ema1_mav10_idx], intersect_ema1_mav10_df, 'ro')

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %Y'))
ax.set_ylabel('Price')
plt.xticks(rotation=45)

# EMA with intersections
fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], close_ema1)
plt.plot(ohlcv_timestamps[-number_of_days:], close_mav5)
plt.plot(ohlcv_timestamps[-number_of_days:][intersect_ema1_mav5_idx], intersect_ema1_mav5_df, 'ro')

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %Y'))
ax.set_ylabel('Price')
plt.xticks(rotation=45)

# EMA with intersections
fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], close_ema1)
plt.plot(ohlcv_timestamps[-number_of_days:], close_ema5)
plt.plot(ohlcv_timestamps[-number_of_days:][intersect_ema1_ema5_idx], intersect_ema1_ema5_df, 'ro')

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %Y'))
ax.set_ylabel('Price')
plt.xticks(rotation=45)

# EMA with intersections
fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], open_ema1)
plt.plot(ohlcv_timestamps[-number_of_days:], open_ema5)
plt.plot(ohlcv_timestamps[-number_of_days:][intersect_ema1_ema5_open_idx], intersect_ema1_ema5_open_df, 'ro')

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %Y'))
ax.set_ylabel('Price')
plt.xticks(rotation=45)

# Portofolio evolution

fig, ax = plt.subplots()
plt.plot(ohlcv_timestamps[-number_of_days:], portfolio['No trading'])
plt.plot(ohlcv_timestamps[-number_of_days:], portfolio['MAV5-MAV10'])
plt.plot(ohlcv_timestamps[-number_of_days:], portfolio['EMA3-MAV10'])
plt.plot(ohlcv_timestamps[-number_of_days:], portfolio['EMA3-MAV20'])
plt.plot(ohlcv_timestamps[-number_of_days:], portfolio['EMA1-MAV10'])
plt.plot(ohlcv_timestamps[-number_of_days:], portfolio['EMA1-MAV5'])
plt.plot(ohlcv_timestamps[-number_of_days:], portfolio['EMA1-EMA5'])
plt.plot(ohlcv_timestamps[-number_of_days:], portfolio['EMA1-EMA5 open'])

plt.legend(portfolio.columns)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %Y'))
ax.set_ylabel('Relative growth')
plt.xticks(rotation=45)



