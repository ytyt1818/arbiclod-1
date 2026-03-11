"""
Arbiclod-1 - Enhanced Crypto Arbitrage Bot
Fixed version - Telegram sending + Google Sheets support
"""
import asyncio
import random
import hashlib
import os
from datetime import datetime
import requests
import logging
from threading import Thread
from flask import Flask

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "Arbiclod-1 is running!"

@app.route('/ping')
def ping():
    return "OK", 200

@app.route('/status')
def status():
    return {
        "status": "alive",
        "bot": "Arbiclod-1",
        "timestamp": datetime.now().isoformat()
    }

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)


class Arbiclod1:
    def __init__(self, sheet_url=None):
        self.sheet_url = sheet_url
        self.config = {}
        self.config_hash = None
        self.last_heartbeat = None
        self.opportunities_found = 0
        self.total_scans = 0
        self.start_time = datetime.now()

        self.telegram_token = ''
        self.telegram_chat_id = ''
        self.group_mode = False
        self.heartbeat_interval = 30
        self.notify_changes = True
        self.scan_interval = 10
        self.min_profit = 1.0

        logger.info("=" * 60)
        logger.info("ARBICLOD-1 - STARTING UP")
        logger.info("=" * 60)

        self.load_config()
        self.send_startup_message()

    def calculate_config_hash(self):
        import json
        config_str = json.dumps(self.config, sort_keys=True, default=str)
        return hashlib.md5(config_str.encode()).hexdigest()

    def load_config_from_google_sheets(self):
        import pandas as pd

        logger.info("Loading config from Google Sheets...")

        if '/d/' in self.sheet_url:
            sheet_id = self.sheet_url.split('/d/')[1].split('/')[0]
        else:
            sheet_id = self.sheet_url

        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid=0"

        try:
            df = pd.read_csv(url, header=None)
            logger.info(f"Loaded {len(df)} rows from Google Sheets")

            self.config = {
                'settings': {},
                'exchanges': {},
                'symbols': {}
            }

            current_section = None

            for idx in range(len(df)):
                row = df.iloc[idx]

                if pd.isna(row[0]):
                    continue

                setting = str(row[0]).strip()
                value = str(row[1]).strip() if len(row) > 1 and not pd.isna(row[1]) else ""

                if 'הגדרות בוט' in setting or 'BOT' in setting.upper():
                    current_section = 'settings'
                    logger.info("Found settings section")
                    continue
                elif 'הגדרות סריקה' in setting or 'SCAN' in setting.upper():
                    current_section = 'settings'
                    logger.info("Found scanning settings section")
                    continue
                elif 'בורסות' in setting or 'EXCHANGE' in setting.upper():
                    current_section = 'exchanges'
                    logger.info("Found exchanges section")
                    continue
                elif 'מטבעות' in setting or 'SYMBOL' in setting.upper() or 'COIN' in setting.upper():
                    current_section = 'symbols'
                    logger.info("Found symbols section")
                    continue
                elif 'הוראות' in setting or 'INSTRUCTION' in setting.upper():
                    logger.info("Reached instructions - stopping")
                    break

                if current_section is None:
                    continue

                if current_section == 'settings':
                    self.config['settings'][setting] = value
                    logger.info(f"  Setting: {setting} = {value}")
                elif current_section == 'exchanges':
                    enabled = value.upper() == 'V'
                    if enabled:
                        self.config['exchanges'][setting] = True
                        logger.info(f"  Exchange enabled: {setting}")
                elif current_section == 'symbols':
                    enabled = value.upper() == 'V'
                    if enabled:
                        self.config['symbols'][setting] = True
                        logger.info(f"  Symbol enabled: {setting}")

        except Exception as e:
            logger.error(f"Failed to load from Google Sheets: {e}")
            raise

    def load_config(self):
        try:
            self.load_config_from_google_sheets()

            self.config_hash = self.calculate_config_hash()

            settings = self.config['settings']

            def get_setting(key_he, default=''):
                for k, v in settings.items():
                    if key_he in k:
                        return str(v).strip()
                return default

            self.telegram_token = get_setting('טוקן_טלגרם', '')
            
            chat_id_raw = get_setting('מזהה_צאט', '')
            if '.' in chat_id_raw:
                chat_id_raw = chat_id_raw.split('.')[0]
            self.telegram_chat_id = chat_id_raw

            self.group_mode = get_setting('מצב_קבוצה', 'X').upper() == 'V'
            
            try:
                self.heartbeat_interval = int(float(get_setting('��קות_בין_הודעות_חיים', '30')))
            except:
                self.heartbeat_interval = 30
                
            self.notify_changes = get_setting('התרעה_על_שינויים', 'V').upper() == 'V'
            
            try:
                self.scan_interval = int(float(get_setting('שניות_בין_סריקות', '10')))
            except:
                self.scan_interval = 10
                
            try:
                self.min_profit = float(get_setting('אחוז_רווח_מינימלי', '1.0'))
            except:
                self.min_profit = 1.0

            logger.info("=" * 60)
            logger.info("Configuration loaded successfully!")
            logger.info(f"   Token: {self.telegram_token[:20]}..." if len(self.telegram_token) > 20 else f"   Token: {self.telegram_token}")
            logger.info(f"   Chat ID: {self.telegram_chat_id}")
            logger.info(f"   Symbols: {len(self.config['symbols'])}")
            logger.info(f"   Exchanges: {len(self.config['exchanges'])}")
            logger.info(f"   Min profit: {self.min_profit}%")
            logger.info(f"   Scan interval: {self.scan_interval}s")
            logger.info(f"   Group mode: {self.group_mode}")
            logger.info(f"   Heartbeat: {self.heartbeat_interval}min")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Fatal error loading config: {str(e)}")
            raise

    def check_config_changes(self):
        try:
            old_hash = self.config_hash

            self.load_config_from_google_sheets()
            new_hash = self.calculate_config_hash()

            if new_hash != old_hash:
                logger.info("Configuration changed! Reloading...")
                self.config_hash = new_hash

                settings = self.config['settings']

                def get_setting(key_he, default=''):
                    for k, v in settings.items():
                        if key_he in k:
                            return str(v).strip()
                    return default

                self.telegram_token = get_setting('טוקן_טלגרם', '')
                
                chat_id_raw = get_setting('מזהה_צאט', '')
                if '.' in chat_id_raw:
                    chat_id_raw = chat_id_raw.split('.')[0]
                self.telegram_chat_id = chat_id_raw

                self.group_mode = get_setting('מצב_קבוצה', 'X').upper() == 'V'
                
                try:
                    self.heartbeat_interval = int(float(get_setting('דקות_בין_הודעות_חיים', '30')))
                except:
                    self.heartbeat_interval = 30
                    
                self.notify_changes = get_setting('התרעה_על_שינויים', 'V').upper() == 'V'
                
                try:
                    self.scan_interval = int(float(get_setting('שניות_בין_סריקות', '10')))
                except:
                    self.scan_interval = 10
                    
                try:
                    self.min_profit = float(get_setting('אחוז_רווח_מינימלי', '1.0'))
                except:
                    self.min_profit = 1.0

                if self.notify_changes:
                    message = (
                        "CONFIG CHANGED\n\n"
                        f"Symbols: {len(self.config['symbols'])}\n"
                        f"Exchanges: {len(self.config['exchanges'])}\n"
                        f"Min profit: {self.min_profit}%\n"
                        f"Scan interval: {self.scan_interval}s\n"
                        f"Chat ID: {self.telegram_chat_id}\n\n"
                        "Settings reloaded!\n\n"
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    self.send_telegram(message)

                logger.info("Config reloaded!")
                return True

        except Exception as e:
            logger.error(f"Error checking config changes: {e}")

        return False

    def send_telegram(self, message):
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("Telegram not configured - token or chat_id missing")
            logger.warning(f"Token: '{self.telegram_token[:10]}...' Chat ID: '{self.telegram_chat_id}'")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message
            }

            logger.info(f"Sending Telegram message to chat_id: {self.telegram_chat_id}")
            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200:
                logger.info("Telegram message sent successfully!")
                return True
            else:
                logger.error(f"Telegram error {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Telegram send error: {str(e)}")
            return False

    def send_startup_message(self):
        mode = "GROUP" if self.group_mode else "PERSONAL"
        message = (
            "ARBICLOD-1 STARTED\n\n"
            f"Bot is now ONLINE\n"
            f"Monitoring {len(self.config['symbols'])} symbols\n"
            f"Checking {len(self.config['exchanges'])} exchanges\n"
            f"Min profit: {self.min_profit}%\n"
            f"Scan interval: {self.scan_interval}s\n"
            f"Mode: {mode}\n"
            f"Heartbeat: Every {self.heartbeat_interval}min\n\n"
            "Ready to find opportunities!\n\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        result = self.send_telegram(message)
        if result:
            logger.info("Startup message sent to Telegram!")
        else:
            logger.error("Failed to send startup message!")

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
                f"Bot is ALIVE\n\n"
                f"Uptime: {hours}h {minutes}m\n"
                f"Total scans: {self.total_scans}\n"
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
            'ADA/USDT': 0.8,
            'DOGE/USDT': 0.15,
            'AVAX/USDT': 40,
            'MATIC/USDT': 0.9,
            'DOT/USDT': 7.5,
        }

        base_price = base_prices.get(symbol, 100)

        prices = []
        for exchange in self.config['exchanges'].keys():
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

        buy_price = best_buy['ask']
        sell_price = best_sell['bid']
        profit = ((sell_price - buy_price) / buy_price) * 100

        if profit >= self.min_profit:
            return {
                'symbol': symbol,
                'buy_exchange': best_buy['exchange'],
                'buy_price': buy_price,
                'sell_exchange': best_sell['exchange'],
                'sell_price': sell_price,
                'profit': profit,
                'buy_volume': best_buy['volume'],
                'sell_volume': best_sell['volume']
            }

        return None

    def format_opportunity(self, opp):
        return (
            "ARBITRAGE OPPORTUNITY\n\n"
            f"Symbol: {opp['symbol']}\n\n"
            f"BUY: {opp['buy_exchange'].upper()}\n"
            f"Price: ${opp['buy_price']:.4f}\n"
            f"Volume: ${opp['buy_volume']:,.0f}\n\n"
            f"SELL: {opp['sell_exchange'].upper()}\n"
            f"Price: ${opp['sell_price']:.4f}\n"
            f"Volume: ${opp['sell_volume']:,.0f}\n\n"
            f"PROFIT: {opp['profit']:.2f}%\n\n"
            "Check fees before trading!\n\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    async def monitor_loop(self):
        logger.info("Bot started - monitoring markets")
        logger.info(f"Checking every {self.scan_interval} seconds")

        config_check_counter = 0

        while True:
            try:
                self.total_scans += 1
                timestamp = datetime.now().strftime('%H:%M:%S')
                logger.info(f"[{timestamp}] Scan #{self.total_scans}")

                config_check_counter += 1
                if config_check_counter >= 5:
                    self.check_config_changes()
                    config_check_counter = 0

                self.send_heartbeat()

                opportunities = []
                for symbol in self.config['symbols'].keys():
                    opp = await self.check_arbitrage(symbol)
                    if opp:
                        opportunities.append(opp)

                if opportunities:
                    self.opportunities_found += len(opportunities)
                    logger.info(f"Found {len(opportunities)} opportunity(ies)!")

                    for opp in opportunities:
                        message = self.format_opportunity(opp)
                        self.send_telegram(message)
                else:
                    logger.info("   No opportunities above threshold")

                await asyncio.sleep(self.scan_interval)

            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                self.send_telegram("ARBICLOD-1 STOPPED\n\nBot has been shut down.")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                await asyncio.sleep(10)

    def run(self):
        logger.info("Starting Flask web server...")
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()

        try:
            asyncio.run(self.monitor_loop())
        except KeyboardInterrupt:
            logger.info("Goodbye!")


if __name__ == "__main__":
    sheet_url = os.environ.get('GOOGLE_SHEET_URL', '')

    if not sheet_url:
        print("ERROR: GOOGLE_SHEET_URL environment variable not set!")
        print("Set it in Render.com Environment Variables")
        import sys
        sys.exit(1)

    logger.info(f"Using Google Sheet URL: {sheet_url[:50]}...")
    bot = Arbiclod1(sheet_url=sheet_url)
    bot.run()
