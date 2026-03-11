"""
Arbiclod-1 - Crypto Arbitrage Bot
With Google Sheets + Environment Variables support
"""
import asyncio
import random
import os
from datetime import datetime
import requests
import logging
from threading import Thread
from flask import Flask
import pandas as pd

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
        logger.info("=" * 60)
        logger.info("ARBICLOD-1 - STARTING UP")
        logger.info("=" * 60)
        
        # First try Environment Variables
        self.telegram_token = os.environ.get('TELEGRAM_TOKEN', '')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        self.sheet_url = os.environ.get('GOOGLE_SHEET_URL', '')
        
        logger.info(f"TELEGRAM_TOKEN from env: {'SET' if self.telegram_token else 'NOT SET'}")
        logger.info(f"TELEGRAM_CHAT_ID from env: {'SET' if self.telegram_chat_id else 'NOT SET'}")
        logger.info(f"GOOGLE_SHEET_URL from env: {'SET' if self.sheet_url else 'NOT SET'}")
        
        # Default settings
        self.scan_interval = 10
        self.min_profit = 0.5
        self.heartbeat_interval = 10
        self.last_heartbeat = None
        self.opportunities_found = 0
        self.total_scans = 0
        self.start_time = datetime.now()
        
        self.exchanges = ['binance', 'kucoin', 'bybit']
        self.symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT']
        
        # Load from Google Sheets if available
        if self.sheet_url:
            self.load_from_google_sheets()
        
        logger.info("=" * 60)
        logger.info(f"Token: {self.telegram_token[:20]}..." if self.telegram_token else "Token: NOT SET")
        logger.info(f"Chat ID: {self.telegram_chat_id}")
        logger.info(f"Exchanges: {self.exchanges}")
        logger.info(f"Symbols: {self.symbols}")
        logger.info("=" * 60)
        
        self.send_startup_message()

    def load_from_google_sheets(self):
        try:
            logger.info("Loading settings from Google Sheets...")
            
            if '/d/' in self.sheet_url:
                sheet_id = self.sheet_url.split('/d/')[1].split('/')[0]
            else:
                sheet_id = self.sheet_url
            
            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid=0"
            df = pd.read_csv(url, header=None)
            logger.info(f"Loaded {len(df)} rows from Google Sheets")
            
            current_section = None
            temp_exchanges = []
            temp_symbols = []
            
            for idx in range(len(df)):
                row = df.iloc[idx]
                
                if pd.isna(row[0]):
                    continue
                
                setting = str(row[0]).strip()
                value = str(row[1]).strip() if len(row) > 1 and not pd.isna(row[1]) else ""
                
                # Detect sections
                if 'הגדרות בוט' in setting or 'BOT' in setting.upper():
                    current_section = 'settings'
                    continue
                elif 'הגדרות סריקה' in setting or 'SCAN' in setting.upper():
                    current_section = 'settings'
                    continue
                elif 'בורסות' in setting or 'EXCHANGE' in setting.upper():
                    current_section = 'exchanges'
                    continue
                elif 'מטבעות' in setting or 'SYMBOL' in setting.upper() or 'COIN' in setting.upper():
                    current_section = 'symbols'
                    continue
                elif 'הוראות' in setting or 'INSTRUCTION' in setting.upper():
                    break
                
                if current_section == 'settings':
                    # Get telegram token if not set from env
                    if ('token' in setting.lower() or 'טוקן' in setting) and not self.telegram_token:
                        self.telegram_token = value
                        logger.info(f"Token loaded from sheet")
                    
                    # Get chat id if not set from env
                    if ('chat' in setting.lower() or 'צאט' in setting or 'מזהה' in setting) and not self.telegram_chat_id:
                        # Remove .0 if present
                        if '.' in value:
                            value = value.split('.')[0]
                        self.telegram_chat_id = value
                        logger.info(f"Chat ID loaded from sheet: {value}")
                    
                    # Get scan interval
                    if 'שניות' in setting or 'interval' in setting.lower():
                        try:
                            self.scan_interval = int(float(value))
                        except:
                            pass
                    
                    # Get min profit
                    if 'רווח' in setting or 'profit' in setting.lower():
                        try:
                            self.min_profit = float(value)
                        except:
                            pass
                    
                    # Get heartbeat
                    if 'דקות' in setting or 'heartbeat' in setting.lower():
                        try:
                            self.heartbeat_interval = int(float(value))
                        except:
                            pass
                
                elif current_section == 'exchanges':
                    if value.upper() == 'V':
                        temp_exchanges.append(setting.lower())
                        logger.info(f"Exchange enabled: {setting}")
                
                elif current_section == 'symbols':
                    if value.upper() == 'V':
                        temp_symbols.append(setting)
                        logger.info(f"Symbol enabled: {setting}")
            
            # Update if we found any
            if temp_exchanges:
                self.exchanges = temp_exchanges
            if temp_symbols:
                self.symbols = temp_symbols
                
            logger.info("Google Sheets loaded successfully!")
            
        except Exception as e:
            logger.error(f"Error loading Google Sheets: {e}")
            logger.info("Using default settings")

    def send_telegram(self, message):
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning(f"Telegram not configured!")
            logger.warning(f"Token: '{self.telegram_token[:10] if self.telegram_token else 'EMPTY'}...'")
            logger.warning(f"Chat ID: '{self.telegram_chat_id}'")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message
            }

            logger.info(f"Sending Telegram message to {self.telegram_chat_id}...")
            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200:
                logger.info("Telegram message sent!")
                return True
            else:
                logger.error(f"Telegram error {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Telegram error: {str(e)}")
            return False

    def send_startup_message(self):
        message = (
            "ARBICLOD-1 STARTED\n\n"
            f"Bot is now ONLINE\n"
            f"Monitoring {len(self.symbols)} symbols\n"
            f"Checking {len(self.exchanges)} exchanges\n"
            f"Min profit: {self.min_profit}%\n"
            f"Scan interval: {self.scan_interval}s\n"
            f"Heartbeat: {self.heartbeat_interval}min\n\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.send_telegram(message)

    def send_heartbeat(self):
        if self.heartbeat_interval <= 0:
            return

        now = datetime.now()
        if self.last_heartbeat is None or (now - self.last_heartbeat).total_seconds() >= (self.heartbeat_interval * 60):
            uptime = now - self.start_time
            hours = int(uptime.total_seconds()) // 3600
            minutes = (int(uptime.total_seconds()) % 3600) // 60

            message = (
                "HEARTBEAT\n\n"
                f"Bot is ALIVE\n"
                f"Uptime: {hours}h {minutes}m\n"
                f"Scans: {self.total_scans}\n"
                f"Opportunities: {self.opportunities_found}\n\n"
                f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.send_telegram(message)
            self.last_heartbeat = now
            logger.info("Heartbeat sent")

    def get_simulated_price(self, base_price):
        variation = random.uniform(-0.02, 0.02)
        return base_price * (1 + variation)

    async def check_arbitrage(self, symbol):
        base_prices = {
            'BTC/USDT': 95000,
            'ETH/USDT': 3400,
            'BNB/USDT': 620,
            'SOL/USDT': 180,
            'XRP/USDT': 2.5,
        }

        base_price = base_prices.get(symbol, 100)

        prices = []
        for exchange in self.exchanges:
            ask = self.get_simulated_price(base_price)
            bid = ask * 0.999
            prices.append({
                'exchange': exchange,
                'ask': ask,
                'bid': bid,
                'volume': random.uniform(100000, 5000000)
            })

        if len(prices) < 2:
            return None

        best_buy = min(prices, key=lambda x: x['ask'])
        best_sell = max(prices, key=lambda x: x['bid'])

        if best_buy['exchange'] == best_sell['exchange']:
            return None

        profit = ((best_sell['bid'] - best_buy['ask']) / best_buy['ask']) * 100

        if profit >= self.min_profit:
            return {
                'symbol': symbol,
                'buy_exchange': best_buy['exchange'],
                'buy_price': best_buy['ask'],
                'sell_exchange': best_sell['exchange'],
                'sell_price': best_sell['bid'],
                'profit': profit
            }

        return None

    def format_opportunity(self, opp):
        return (
            "ARBITRAGE OPPORTUNITY\n\n"
            f"Symbol: {opp['symbol']}\n"
            f"BUY: {opp['buy_exchange'].upper()} @ ${opp['buy_price']:.4f}\n"
            f"SELL: {opp['sell_exchange'].upper()} @ ${opp['sell_price']:.4f}\n"
            f"PROFIT: {opp['profit']:.2f}%\n\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    async def monitor_loop(self):
        logger.info("Bot started - monitoring markets")
        logger.info(f"Scanning every {self.scan_interval} seconds")

        while True:
            try:
                self.total_scans += 1
                logger.info(f"Scan #{self.total_scans}")

                self.send_heartbeat()

                for symbol in self.symbols:
                    opp = await self.check_arbitrage(symbol)
                    if opp:
                        self.opportunities_found += 1
                        logger.info(f"Found: {opp['symbol']} +{opp['profit']:.2f}%")
                        self.send_telegram(self.format_opportunity(opp))

                await asyncio.sleep(self.scan_interval)

            except Exception as e:
                logger.error(f"Error: {str(e)}")
                await asyncio.sleep(10)

    def run(self):
        logger.info("Starting Flask server...")
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()

        asyncio.run(self.monitor_loop())


if __name__ == "__main__":
    bot = Arbiclod1()
    bot.run()
