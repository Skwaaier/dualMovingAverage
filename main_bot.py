# -*- coding: utf-8 -*-
"""
Created on Sun Apr 18 18:02:44 2021

Crypto trading bot using closing price and exponential moving average intersections.

Starting point is a portfolio with crypto assets. Use symbol_dict to set the trading pairs.

@author: tgdon
"""

#%% Import libraries

import os, sys
import pandas as pd
import numpy as np
import re
import time
import ccxt

import credentials

from urllib.error import HTTPError
import traceback
import logging

from lib.waveshare_epd import epd2in13b_V3
from PIL import Image, ImageDraw, ImageFont


#%% Functions

def my_floor(a, precision=0):
    return np.true_divide(np.floor(a * 10**precision), 10**precision)


def place_buy_order(exchange, order, portfolio, order_book, ohlcv_df, price_offset):

    # buy for stable amount equal to last sell
    if not order_book[(order_book['side'] == 'sell')].empty and (order_book[(order_book['side'] == 'sell')].iloc[-1]['status'] == 'closed'):
        last_sell_stable = order_book[(order_book['side'] == 'sell')].iloc[-1]
        amount_stable = last_sell_stable['price']*last_sell_stable['filled']
    # no previous sell in order_book
    else:
        raise ValueError('No previous sell order has been found for ' + symbol + '. Unable to determine buy amount.')
    
    price_volatile = ohlcv_df['close'][-1] - price_offset*(ohlcv_df['close'][-1] - ohlcv_df['open'][-1])
    amount_volatile_floor = my_floor(amount_stable/price_volatile, decimals)
    if (amount_volatile_floor >= 10**-decimals) and (amount_volatile_floor*price_volatile >= 10):
        order = exchange.create_order(symbol, 'limit', 'buy', amount_volatile_floor, price_volatile)
        print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : Placed ' + symbol + ' buy limit order for ' + str(round(amount_stable,2)) + ' ' + str_stable + 
              ' at ' + str(round(price_volatile,2)) + ' ' + str_stable + ' (' + str(round(amount_stable/price_volatile,decimals)) + ' ' + str_volatile + ')')
        
    return order

        
def place_sell_order(exchange, order, portfolio, order_book, ohlcv_df, price_offset):
    row_volatile = portfolio.where(portfolio==str_volatile).dropna(how='all').index
    amount_volatile = portfolio.loc[row_volatile]['free'].values[0]
    amount_volatile_floor = my_floor(amount_volatile, decimals)
    
    price_volatile = ohlcv_df['close'][-1] + price_offset*(ohlcv_df['open'][-1] - ohlcv_df['close'][-1])
    
    if (amount_volatile_floor >= 10**-decimals) and (amount_volatile_floor*price_volatile >= 10):
        order = exchange.create_order(symbol, 'limit', 'sell', amount_volatile_floor, price_volatile)
        print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : Placed ' + symbol + ' sell limit order for ' + str(amount_volatile_floor) + ' ' + str_volatile + 
              ' at ' + str(round(price_volatile,2)) + ' ' + str_stable + ' ($ ' + str(round(amount_volatile_floor*price_volatile,2)) + ')')
        
    return order


#%% Input parameters

# Define coin pairs and associated time frame
symbol_dict = {'ADA/EUR' : ['1d', 5], 'ETH/EUR' : ['1d', 7], 'BTC/EUR' : ['1d', 7]} # {'volatile/stable' : ['timeframe', decimals]}

# Relative offset for limit orders (price = close +/- price_offset*(close - open))
price_offset = 0.15

# Connect to Bitvavo
exchange = ccxt.bitvavo({
    'apiKey' : credentials.api_key,
    'secret' : credentials.secret, 
    'options' : {
        'adjustForTimeDifference': True,
        },
    'enableRateLimit': True
    })

logFile = 'log.out'

# Maximum number of retries if the connection to the exchange fails
numberOfRetries = 25
logging.basicConfig(filename=logFile, level=logging.ERROR)


#%% Initialisation

for symbol in symbol_dict.keys():
    
    timeframe = symbol_dict[symbol][0]
    
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
        
if not os.path.isfile('portfolio.csv'):
    portfolio_df = pd.DataFrame()
    portfolio_df.to_csv('portfolio.csv')
    
if not os.path.isfile('portfolio_eur.csv'):
    portfolio_eur_df = pd.DataFrame()
    portfolio_eur_df.to_csv('portfolio_eur.csv')
    
if not os.path.isfile('portfolio_eur_relative.csv'):
    portfolio_eur_relative_df = pd.DataFrame()
    portfolio_eur_relative_df.to_csv('portfolio_eur_relative.csv')
    

#%% Load remote data each minute

start_time = time.time()

while True:
    
    symbol_count = 0
    
    for symbol in symbol_dict.keys():
        
        str_volatile = symbol.split('/')[0]
        str_stable = symbol.split('/')[1]
        timeframe = symbol_dict[symbol][0]
        decimals = symbol_dict[symbol][1]

        for _ in range(numberOfRetries):       
            try:
                # each ohlcv candle is a list of [ timestamp, open, high, low, close, volume ]
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe)
                tickers = exchange.fetchTickers()
                break
            except (ccxt.NetworkError, HTTPError):
                typ, val, tb = sys.exc_info()
                logging.error(traceback.format_exception(typ, val, tb))
                print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : encountered error')
                time.sleep(60)
        else:
            raise
            
        ohlcv = ohlcv[:-1] # remove last entity which is the partial (still moving) candle
        ohlcv_timestamps = pd.to_datetime([row[0] for row in ohlcv], unit = 'ms')
        ohlcv_data = [row[1:] for row in ohlcv]
        
        ohlcv_df = pd.DataFrame(ohlcv_data, index = ohlcv_timestamps, columns = ['open', 'high', 'low', 'close', 'volume'])
        
        # calculate exponential moving average using the last five data points
        close_ema5 = ohlcv_df['close'].ewm(span=5, adjust=False).mean().values[-2:]
        
        
        #%% Read local historical data

        local_history_df = pd.read_csv('historical_data_' + re.sub(r'[^\w]', '', symbol) + '.csv', index_col=0)
        local_history_df.index = [pd.Timestamp(x) for x in local_history_df.index]
    
        
        #%% Actions if last remote date is more recent than last date of local version
        if ohlcv_df.index[-1] > pd.Timestamp(local_history_df.index[-1]):
            
            time.sleep(10)
            
            # Append historical data 
            try:
                lag_hours = np.count_nonzero(ohlcv_df.index > pd.Timestamp(local_history_df.index[-1]))
                local_history_df = local_history_df.append(ohlcv_df.tail(lag_hours))
                local_history_df.to_csv('historical_data_' + re.sub(r'[^\w]', '', symbol) + '.csv')
            except:
                raise ValueError('Lag has become to big. Consider reinitiating historical data file with the most recent data.')
            
                       
            #%% Load local order book
            order_book = pd.read_csv('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv', index_col=0)
            
            # Load and cancel open orders
            open_order_ids = [open_order['id'] for open_order in exchange.fetchOpenOrders(symbol)]
            
            for order_id in open_order_ids:
                if order_id in order_book['id'].values:
                    
                    # open order was not filled
                    exchange.cancelOrder(order_id, symbol)
                    order_book_index = order_book.loc[order_book.isin([open_order_ids[-1]]).any(axis=1)].index
                    
                    if (order_book.loc[order_book_index, 'status'] == 'open').values[0]:
                        order_book.loc[order_book_index, 'status'] = 'cancelled'
                        order_book.to_csv('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv')
                        
                        if order_book.loc[order_book_index, 'side'].values[0] == 'buy':
                            print('Buy order ' + str(order_book.loc[order_book_index, 'id'].values[0]) + ' (' + symbol + ') for ' + 
                                  str(round(order_book.loc[order_book_index, 'price'].values[0]*order_book.loc[order_book_index, 'amount'], 2)) + ' ' + str_stable + ' was cancelled.')
                        else:
                            print('Sell order ' + str(order_book.loc[order_book_index, 'id'].values[0]) + ' (' + symbol + ') for ' + 
                                  str(round(order_book.loc[order_book_index, 'amount'].values[0], 5)) + ' ' + str_volatile + ' was cancelled.')
                            
            # Load closed orders
            closed_order_ids = [closed_order['id'] for closed_order in exchange.fetchOrders(symbol) if closed_order['status'] == 'closed']
            
            for order_id in closed_order_ids:
                if order_id in order_book['id'].values:
                    order_book_index = order_book.loc[order_book.isin([closed_order_ids[-1]]).any(axis=1)].index
                    
                    # open order was filled
                    if (order_book.loc[order_book_index, 'status'] == 'open').values[0]:
                        order_book.loc[order_book_index, 'filled'] = exchange.fetchClosedOrders(symbol)[-1]['filled']
                        order_book.loc[order_book_index, 'status'] = 'closed'
                        order_book.to_csv('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv')
                    
                        if order_book.loc[order_book_index, 'side'].values[0] == 'buy':
                            print('Buy order ' + str(order_book.loc[order_book_index, 'id'].values[0]) + ' (' + symbol + ') for ' + 
                                  str(round(order_book.loc[order_book_index, 'price'].values[0]*order_book.loc[order_book_index, 'amount'].values[0], 2)) + ' ' + str_stable + ' was closed successfully.')
                        else:
                            print('Sell order ' + str(order_book.loc[order_book_index, 'id'].values[0]) + ' (' + symbol + ') for ' + 
                                  str(round(order_book.loc[order_book_index, 'amount'].values[0], 5)) + ' ' + str_volatile + ' was closed successfully.')
            
            
            #%% Load portfolio
            
            portfolio = pd.DataFrame(exchange.fetch_balance()['info'])
            portfolio['free'] = [float(price) for price in portfolio['available']]
            portfolio['locked'] = [float(price) for price in portfolio['inOrder']]
            portfolio['total'] = portfolio['free'] + portfolio['locked']
            
            
            #%% Place orders if criterium is met
            
            order_book = pd.read_csv('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv', index_col=0)
            
            order = dict()
            
            # buy
            if (ohlcv_df['close'][-1] >= close_ema5[-1]) & (ohlcv_df['close'][-2] < close_ema5[-2]):
                row_volatile = portfolio.where(portfolio==str_volatile).dropna(how='all').index
                amount_volatile = portfolio.loc[row_volatile]['free'].values[0]
                if amount_volatile <= 10**-decimals: # not holding the current asset
                    order = place_buy_order(exchange, order, portfolio, order_book, ohlcv_df, price_offset)
                else:
                    print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : Hold ' + symbol)
            
            # sell
            elif (ohlcv_df['close'][-1] < close_ema5[-1]) & (ohlcv_df['close'][-2] >= close_ema5[-2]):
                order = place_sell_order(exchange, order, portfolio, order_book, ohlcv_df, price_offset)
            
            # retry buy or hold
            elif (ohlcv_df['close'][-1] >= close_ema5[-1]) & (ohlcv_df['close'][-2] >= close_ema5[-2]):
                if (order_book.iloc[-1]['side'] == 'buy') and (order_book.iloc[-1]['status'] == 'cancelled'):
                    order =  place_buy_order(exchange, order, portfolio, order_book, ohlcv_df, price_offset)
                else:
                    print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : Hold ' + symbol)
            
            # retry sell or no assets available
            elif (ohlcv_df['close'][-1] < close_ema5[-1]) & (ohlcv_df['close'][-2] < close_ema5[-2]):
                if (order_book.iloc[-1]['side'] == 'sell') and (order_book.iloc[-1]['status'] == 'cancelled'):
                    order = place_sell_order(exchange, order, portfolio, order_book, ohlcv_df, price_offset)
                else:
                    print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' : No assets available for ' + symbol)
                    
            # encountered unknown situation
            else:
                raise ValueError('Encountered unknown situation.')
            
            # save order to order_book dataframe
            if order:
                order_data = {'id': order['id'], 'side' : order['side'], 'price' : order['price'], 'amount' : order['amount'], 'filled' : order['filled'], 'status' : 'open'}
                order_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                save_order = pd.DataFrame(order_data, index = [order_time])
                order_book = pd.concat([order_book, save_order])
                order_book.to_csv('order_book_' + re.sub(r'[^\w]', '', symbol) + '.csv')
          
            
            #%% Update portfolio files
            
            symbol_count += 1
            
            if symbol_count == len(symbol_dict):
            
                # Update local portfolio
                portfolio_df = pd.read_csv('portfolio.csv', index_col=0)
                as_list = portfolio_df.index.to_list()
                portfolio_df.index = [pd.Timestamp(x) for x in as_list]
                
                new_portfolio_values = portfolio[(portfolio.select_dtypes(include=['number']) != 0).any(1)]
                portfolio_df.loc[ohlcv_df.index[-1], new_portfolio_values['symbol']] = new_portfolio_values['total'].values
                
                zero_indexes = portfolio_df.columns.difference(new_portfolio_values['symbol'])
                portfolio_df.loc[ohlcv_df.index[-1], zero_indexes] = 0.0
                portfolio_df.to_csv('portfolio.csv')
                
                # Update EUR based portfolio
                portfolio_eur_df = pd.read_csv('portfolio_eur.csv', index_col=0)
                as_list = portfolio_eur_df.index.to_list()
                portfolio_eur_df.index = [pd.Timestamp(x) for x in as_list]
                
                portfolio_asset_list = portfolio_df.columns.to_list()
                exclude_asset_list = ['EUR', 'EON', 'ADD', 'MEETONE', 'ATD', 'EOP']
                portfolio_asset_list = [x for x in portfolio_asset_list if x not in exclude_asset_list]
                tickers_string = [x + '/EUR' for x in portfolio_asset_list]
                
                tickers_bid = {}
                for ticker in tickers_string:
                    tickers_bid[ticker[:-4]] = tickers[ticker]['bid']
                
                for ticker in tickers_bid.keys():
                    portfolio_eur_df.loc[ohlcv_df.index[-1], ticker] = tickers_bid[ticker]*portfolio_df.loc[ohlcv_df.index[-1], ticker]
                portfolio_eur_df.loc[ohlcv_df.index[-1], 'EUR'] = portfolio_df.loc[ohlcv_df.index[-1], 'EUR']
                portfolio_eur_df.loc[ohlcv_df.index[-1], 'Total'] = portfolio_eur_df.loc[ohlcv_df.index[-1], tickers_bid.keys()].sum() + portfolio_df.loc[ohlcv_df.index[-1], 'EUR']
                portfolio_eur_df.to_csv('portfolio_eur.csv')
                
                # Calculate relative change
                portfolio_eur_relative_df = pd.read_csv('portfolio_eur_relative.csv', index_col=0)
                as_list = portfolio_eur_relative_df.index.to_list()
                portfolio_eur_relative_df.index = [pd.Timestamp(x) for x in as_list]
                         
                if len(portfolio_eur_df) > 1:
                    for ticker in portfolio_eur_df.columns.to_list(): 
                        new_value = portfolio_eur_df.loc[ohlcv_df.index[-1], ticker]
                        
                        if (new_value <= 0.1) or (len(portfolio_eur_df[ticker]) - portfolio_eur_df[ticker].isnull().sum() <= 1): # smaller than ??? 0.01 or only one entry
                            portfolio_eur_relative_df.loc[ohlcv_df.index[-1], ticker] = 0.0
                        else:
                            old_non_zero_index = portfolio_eur_df[ticker][portfolio_eur_df[ticker] >= 0.01].index[-2]
                            old_non_zero_value = portfolio_eur_df.loc[old_non_zero_index, ticker]
                            portfolio_eur_relative_df.loc[ohlcv_df.index[-1], ticker] = round((new_value - old_non_zero_value)/new_value * 100,2)
                    
                    portfolio_eur_relative_df.to_csv('portfolio_eur_relative.csv')
                    
            
                #%% Plot portfolio on display
            
                # Points to pic directory
                figDir = 'fig'
                fontDir = 'fonts'
                
                try:
                    # Display init, clear
                    epd = epd2in13b_V3.EPD()
                    epd.init()
                    epd.Clear()
                    time.sleep(5)
                
                    w = epd.height
                    h = epd.width
                    
                    font14 = ImageFont.truetype(os.path.join(fontDir, 'OpenSans-Regular.ttf'), 14)
                    
                    # Drawing on the Horizontal image
                    HBlackimage = Image.new('1', (epd.height, epd.width), 255)               
                    HRYimage = Image.new('1', (epd.height, epd.width), 255)               
                    drawblack = ImageDraw.Draw(HBlackimage)
                    drawry = ImageDraw.Draw(HRYimage)
                    drawblack.text((10, 0),  'BTC: ???' + str(round(portfolio_eur_df.loc[ohlcv_df.index[-1], 'BTC'],2)) + ' ' + '(' + str(round(portfolio_eur_relative_df.loc[ohlcv_df.index[-1], 'BTC'],2)) + '%)', font = font14, fill = 0)
                    drawblack.text((10, 20), 'ETH: ???' + str(round(portfolio_eur_df.loc[ohlcv_df.index[-1], 'ETH'],2)) + ' ' + '(' + str(round(portfolio_eur_relative_df.loc[ohlcv_df.index[-1], 'ETH'],2)) + '%)', font = font14, fill = 0)
                    drawblack.text((10, 40), 'ADA: ???' + str(round(portfolio_eur_df.loc[ohlcv_df.index[-1], 'ADA'],2)) + ' ' + '(' + str(round(portfolio_eur_relative_df.loc[ohlcv_df.index[-1], 'ADA'],2)) + '%)', font = font14, fill = 0)
                    drawblack.text((10, 60), 'EUR: ???' + str(round(portfolio_eur_df.loc[ohlcv_df.index[-1], 'EUR'],2)), font = font14, fill = 0)
                    drawblack.text((10, 80), 'Total: ???' + str(round(portfolio_eur_df.loc[ohlcv_df.index[-1], 'Total'],2)) + ' ' + '(' + str(round(portfolio_eur_relative_df.loc[ohlcv_df.index[-1], 'Total'],2)) + '%)', font = font14, fill = 0)
                    HBlackimage = HBlackimage.transpose(Image.ROTATE_180)
                    HRYimage = HRYimage.transpose(Image.ROTATE_180)
                    epd.display(epd.getbuffer(HBlackimage), epd.getbuffer(HRYimage))
    
                    logging.info("Goto Sleep...")
                    epd.sleep()
                    
                    print_count = 0
                    
                except IOError as e:
                    print(e)
                    
                except KeyboardInterrupt:    
                    logging.info("ctrl + c:")
                    epd.init()
                    epd.Clear()
                    epd2in13b_V3.epdconfig.module_exit()   
                    exit()
            
            
    #%% Wait for one minute before checking for changes
    
    time.sleep(60.0 - ((time.time() - start_time) % 60.0))
