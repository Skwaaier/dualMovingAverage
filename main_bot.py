# -*- coding: utf-8 -*-
"""
Created on Sun Apr 18 18:02:44 2021

Crypto trading bot using closing price and exponential moving average intersections

@author: tgdon
"""

#%% Import libraries

import os
import pandas as pd
import numpy as np
import re
import time
import ccxt

from urllib.error import HTTPError


#%% Functions

def my_floor(a, precision=0):
    return np.true_divide(np.floor(a * 10**precision), 10**precision)


#%% Input parameters

symbol_dict = {'NEO/BUSD' : '1d', 'ETH/USDT' : '1d'} # {'volatile/stable' : 'timeframe'}

# credentials = yaml.load(open('./credentials.yml'), Loader=yaml.SafeLoader)
import credentials

# Connect to Binance

# api currently only works for Lenovo laptop: add other IPs to Binance API later
exchange = ccxt.binance({
    'apiKey' : credentials.api_key,
    'secret' : credentials.secret, 
    'options' : {
        'adjustForTimeDifference': True,
        },
    'enableRateLimit': True
    })
# exchange.set_sandbox_mode(True) # enabled sandbox


#%% Initialisation

for symbol in symbol_dict.keys():
    
    timeframe = symbol_dict[symbol]
    
    # Create local order book
    if not os.path.isfile('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv'):
        order_book = pd.DataFrame(columns=['id', 'side', 'price', 'amount', 'filled', 'status'])
        order_book.to_csv('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv')
    
    # Create local history file
    if not os.path.isfile('historical_data_' + re.sub(r'[^\w]', '', symbol) + '.csv'):
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe)
        ohlcv = ohlcv[:-1] # remove last entity which is the partial (still moving) candle
        ohlcv_timestamps = pd.to_datetime([row[0] for row in ohlcv], unit = 'ms')
        ohlcv_data = [row[1:] for row in ohlcv]
    
        ohlcv_df = pd.DataFrame(ohlcv_data, index = ohlcv_timestamps, columns = ['open', 'high', 'low', 'close', 'volume'])
        ohlcv_df.to_csv('historical_data_' + re.sub(r'[^\w]', '', symbol) + '.csv')
    

#%% Read local historical data

    local_history_df = pd.read_csv('historical_data_' + re.sub(r'[^\w]', '', symbol) + '.csv', index_col=0)
    local_history_df.index = [pd.Timestamp(x) for x in local_history_df.index]


#%% Load remote data each minute

start_time = time.time()

while True:
    
    for symbol in symbol_dict.keys():
        
        str_volatile = symbol.split('/')[0]
        str_stable = symbol.split('/')[1]
        timeframe = symbol_dict[symbol]

        time.sleep(3) # hold for three seconds before pulling new data after candle change
        
        # each ohlcv candle is a list of [ timestamp, open, high, low, close, volume ]
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe)
        except ccxt.NetworkError:
            time.sleep(60)
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe)
            
        ohlcv = ohlcv[:-1] # remove last entity which is the partial (still moving) candle
        ohlcv_timestamps = pd.to_datetime([row[0] for row in ohlcv], unit = 'ms')
        ohlcv_data = [row[1:] for row in ohlcv]
        
        ohlcv_df = pd.DataFrame(ohlcv_data, index = ohlcv_timestamps, columns = ['open', 'high', 'low', 'close', 'volume'])
        
        # calculate exponential moving average using the last five data points
        close_ema5 = ohlcv_df['close'].ewm(span=5, adjust=False).mean().values[-2:]
        
        
        #%% Actions if last remote date is more recent than last date of local version
        if ohlcv_df.index[-1] > pd.Timestamp(local_history_df.index[-1]):
            
            
            # Append historical data 
            try:
                lag_hours = np.count_nonzero(ohlcv_df.index > pd.Timestamp(local_history_df.index[-1]))
                local_history_df = local_history_df.append(ohlcv_df.tail(lag_hours))
                local_history_df.to_csv('historical_data_' + re.sub(r'[^\w]', '', symbol) + '.csv')
            except:
                raise ValueError('Lag has become to big. Consider reinitiating historical data file with the most recent data.') 
            
            
            # Load portfolio
            portfolio = pd.DataFrame(exchange.fetch_balance()['info']['balances'])
            portfolio['free'] = [float(price) for price in portfolio['free']]
            portfolio['locked'] = [float(price) for price in portfolio['locked']]
            portfolio['total'] = portfolio['free'] + portfolio['locked']
            portfolio = portfolio[(portfolio.select_dtypes(include=['number']) != 0).any(1)]
            
            
            # Load local order book
            order_book = pd.read_csv('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv', index_col=0)
            
            # Load and cancel open orders
            open_order_ids = [open_order['id'] for open_order in exchange.fetchOpenOrders(symbol)]
            
            for order_id in open_order_ids:
                if int(order_id) in order_book['id'].values:
                    exchange.cancelOrder(order_id, symbol)
                    order_book_index = order_book.loc[order_book.isin([int(open_order_ids[-1])]).any(axis=1)].index
                    order_book.loc[order_book_index, 'status'] = 'cancelled'
                    order_book.to_csv('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv')
                    
        
            # Load closed orders
            closed_order_ids = [closed_order['id'] for closed_order in exchange.fetchClosedOrders(symbol)]
            
            for order_id in closed_order_ids:
                if int(order_id) in order_book['id'].values:
                    order_book_index = order_book.loc[order_book.isin([int(closed_order_ids[-1])]).any(axis=1)].index
                    order_book.loc[order_book_index, 'filled'] = exchange.fetchClosedOrders(symbol)[-1]['filled']
                    order_book.loc[order_book_index, 'status'] = 'closed'
                    order_book.to_csv('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv')
            
            
            #%% Place orders if criterium is met
            
            order = dict()
            
            # buy
            if (ohlcv_df['close'][-1] >= close_ema5[-1]) & (ohlcv_df['close'][-2] < close_ema5[-2]):
                row_stable = portfolio.where(portfolio==str_stable).dropna(how='all').index
                amount_stable = portfolio.loc[row_stable]['free'].values[0]
                amount_volatile_floor = my_floor(amount_stable/ohlcv_df['close'][-1], 3)
                if (amount_volatile_floor >= 0.001) and (amount_volatile_floor*ohlcv_df['close'][-1] >= 10):
                    order = exchange.create_order(symbol, 'limit', 'buy', amount_volatile_floor, ohlcv_df['close'][-1])
                    print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : Placed ' + symbol + ' buy limit order for ' + str(round(amount_stable,2)) + ' ' + str_stable + 
                          ' at ' + str(round(ohlcv_df['close'][-1],2)) + ' ' + str_stable + ' (' + str(round(amount_stable/ohlcv_df['close'][-1],3)) + ' ' + str_volatile + ')')
            
            # sell
            elif (ohlcv_df['close'][-1] < close_ema5[-1]) & (ohlcv_df['close'][-2] >= close_ema5[-2]):
                row_volatile = portfolio.where(portfolio==str_volatile).dropna(how='all').index
                amount_volatile = portfolio.loc[row_volatile]['free'].values[0]
                amount_volatile_floor = my_floor(amount_volatile,3)
                if (amount_volatile_floor >= 0.001) and (amount_volatile_floor*ohlcv_df['close'][-1] >= 10):
                    order = exchange.create_order(symbol, 'limit', 'sell', amount_volatile_floor, ohlcv_df['close'][-1])
                    print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : Placed ' + symbol + ' sell limit order for ' + str(amount_volatile_floor) + ' ' + str_stable + 
                          ' at ' + str(round(ohlcv_df['close'][-1],2)) + ' ' + str_stable + ' ($' + str(round(amount_volatile_floor*ohlcv_df['close'][-1],2)) + ')')
            
            # hold
            elif (ohlcv_df['close'][-1] >= close_ema5[-1]) & (ohlcv_df['close'][-2] >= close_ema5[-2]):
                
                # initial purchase
                row_volatile = portfolio.where(portfolio==str_volatile).dropna(how='all').index
                amount_volatile = portfolio.loc[row_volatile]['free'].values[0]
                if amount_volatile <= 0.001: # initial purchase
                    row_stable = portfolio.where(portfolio==str_stable).dropna(how='all').index
                    amount_stable = portfolio.loc[row_stable]['free'].values[0]
                    amount_volatile_floor = my_floor(amount_stable/ohlcv_df['close'][-1], 3)
                    if (amount_volatile_floor >= 0.001) and (amount_volatile_floor*ohlcv_df['close'][-1] >= 10):
                        order = exchange.create_order(symbol, 'limit', 'buy', amount_volatile_floor, ohlcv_df['close'][-1])
                        print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : Placed ' + symbol + ' buy limit order for ' + str(round(amount_stable,2)) + ' ' + str_stable +
                              ' at ' + str(round(ohlcv_df['close'][-1],2)) + ' ' + str_stable + ' (' + str(round(amount_stable*ohlcv_df['close'][-1],2)) + ' ' + str_volatile + ')')
                
                else:
                    print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : Hodl ' + symbol)
            
            else:
                print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : No assets available for ' + symbol)
            
            # save order to order_book dataframe
            if order:
                order_data = {'id': int(order['id']), 'side' : order['side'], 'price' : order['price'], 'amount' : order['amount'], 'filled' : order['filled'], 'status' : 'open'}
                order_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                save_order = pd.DataFrame(order_data, index = [order_time])
                order_book = pd.concat([order_book, save_order])
                order_book.to_csv('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv')
          
            
    #%% Wait for one minute before checking for changes
    
    time.sleep(60.0 - ((time.time() - start_time) % 60.0))
