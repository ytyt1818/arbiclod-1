"""
Arbiclod-1 - Crypto Arbitrage Bot
"""
import asyncio
import random
import os
from datetime import datetime
import requests
import logging
from threading import Thread
from flask import Flask

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "Arbiclod-1 is running!"

@app.route('/ping')
def ping():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)


class Arbiclod1:
    def __init__(self):
        # Read from Environment Variables
        self.telegram_token = os.environ.get('TELEGRAM_TOKEN', '')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        
        self.scan_interval = 10
        self.min_profit = 0.5
        self.heartbeat_interval = 10
        self.last_heartbeat = None
        self.opportunities_found = 0
        self.total_scans = 0
        self.start_time = datetime.now()
        
        self.exchanges = ['binance', 'kucoin', 'bybit']
        
