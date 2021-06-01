# -*- coding: utf-8 -*-
"""
Created on Tue Jun  1 08:55:27 2021

Forced refresh display

@author: tgdon
"""

import pandas as pd
import time
import os
import logging

from lib.waveshare_epd import epd2in13b_V3
from PIL import Image, ImageDraw, ImageFont


#%% Import data

portfolio_usdt_df = pd.read_csv('portfolio_usdt.csv', index_col=0)
portfolio_usdt_relative_df = pd.read_csv('portfolio_usdt_relative.csv', index_col=0)


#%% Refresh display

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
    drawblack.text((10, 0),  'BTC: $' + str(round(portfolio_usdt_df.iloc[-1]['BTC'],2)) + ' ' + '(' + str(round(portfolio_usdt_relative_df.iloc[-1]['BTC'],2)) + '%)', font = font14, fill = 0)
    drawblack.text((10, 20), 'ETH: $' + str(round(portfolio_usdt_df.iloc[-1]['ETH'],2)) + ' ' + '(' + str(round(portfolio_usdt_relative_df.iloc[-1]['ETH'],2)) + '%)', font = font14, fill = 0)
    drawblack.text((10, 40), 'ADA: $' + str(round(portfolio_usdt_df.iloc[-1]['ADA'],2)) + ' ' + '(' + str(round(portfolio_usdt_relative_df.iloc[-1]['ADA'],2)) + '%)', font = font14, fill = 0)
    drawblack.text((10, 60), 'USDT: $' + str(round(portfolio_usdt_df.iloc[-1]['USDT'],2)), font = font14, fill = 0)
    drawblack.text((10, 80), 'Total: $' + str(round(portfolio_usdt_df.iloc[-1]['Total'],2)) + ' ' + '(' + str(round(portfolio_usdt_relative_df.iloc[-1]['Total'],2)) + '%)', font = font14, fill = 0)
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
    