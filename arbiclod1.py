"""
Arbiclod-1 - בוט ארביטראז' קריפטו
גרסה עם מחירים אמיתיים + עברית
"""
import asyncio
import os
from datetime import datetime
import requests
import logging
from threading import Thread
from flask import Flask
import pandas as pd
import ccxt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "Arbiclod-1 פועל!"

@app.route('/ping')
def ping():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

# עמלות לכל בורסה (באחוזים)
EXCHANGE_FEES = {
    'binance': {'taker': 0.1, 'withdrawal_btc': 0.0005},
    'kucoin': {'taker': 0.1, 'withdrawal_btc': 0.0005},
    'bybit': {'taker': 0.1, 'withdrawal_btc': 0.0005},
    'okx': {'taker': 0.1, 'withdrawal_btc': 0.0004},
    'gate': {'taker': 0.2, 'withdrawal_btc': 0.001},
    'mexc': {'taker': 0.1, 'withdrawal_btc': 0.0005},
    'kraken': {'taker': 0.26, 'withdrawal_btc': 0.0005},
    'coinbase': {'taker': 0.6, 'withdrawal_btc': 0.0001},
}

class Arbiclod1:
    def __init__(self):
        logger.info("=" * 60)
        logger.info("ARBICLOD-1 - מתחיל")
        logger.info("=" * 60)
        
        self.telegram_token = os.environ.get('TELEGRAM_TOKEN', '')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        self.sheet_url = os.environ.get('GOOGLE_SHEET_URL', '')
        
        self.scan_interval = 10
        self.min_profit = 0.5
        self.heartbeat_interval = 10
        self.last_heartbeat = None
        self.opportunities_found = 0
        self.total_scans = 0
        self.start_time = datetime.now()
        self.last_config_hash = ""
        
        self.exchanges_config = ['binance', 'kucoin', 'bybit']
        self.symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        self.exchanges = {}
        
        if self.sheet_url:
            self.load_from_google_sheets()
        
        self.init_exchanges()
        self.send_startup_message()

    def init_exchanges(self):
        for exchange_id in self.exchanges_config:
            try:
                exchange_class = getattr(ccxt, exchange_id)
                self.exchanges[exchange_id] = exchange_class({'enableRateLimit': True})
                logger.info(f"מחובר: {exchange_id}")
            except Exception as e:
                logger.error(f"שגיאה {exchange_id}: {e}")

    def get_config_hash(self):
        return f"{self.exchanges_config}{self.symbols}{self.min_profit}"

    def load_from_google_sheets(self):
        try:
            logger.info("טוען מ-Google Sheets...")
            
            if '/d/' in self.sheet_url:
                sheet_id = self.sheet_url.split('/d/')[1].split('/')[0]
            else:
                sheet_id = self.sheet_url
            
            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid=0"
            df = pd.read_csv(url, header=None)
            
            current_section = None
            temp_exchanges = []
            temp_symbols = []
            
            for idx in range(len(df)):
                row = df.iloc[idx]
                if pd.isna(row[0]):
                    continue
                
                setting = str(row[0]).strip()
                value = str(row[1]).strip() if len(row) > 1 and not pd.isna(row[1]) else ""
                
                if 'הגדרות בוט' in setting:
                    current_section = 'settings'
                    continue
                elif 'הגדרות סריקה' in setting:
                    current_section = 'settings'
                    continue
                elif 'בורסות' in setting:
                    current_section = 'exchanges'
                    continue
                elif 'מטבעות' in setting:
                    current_section = 'symbols'
                    continue
                elif 'הוראות' in setting:
                    break
                
                if current_section == 'settings':
                    if 'טוקן' in setting and not self.telegram_token:
                        self.telegram_token = value
                    if 'מזהה' in setting and not self.telegram_chat_id:
                        if '.' in value:
                            value = value.split('.')[0]
                        self.telegram_chat_id = value
                    if 'שניות' in setting:
                        try:
                            self.scan_interval = int(float(value))
                        except:
                            pass
                    if 'רווח' in setting:
                        try:
                            self.min_profit = float(value)
                        except:
                            pass
                    if 'דקות' in setting:
                        try:
                            self.heartbeat_interval = int(float(value))
                        except:
                            pass
                
                elif current_section == 'exchanges':
                    if value.upper() == 'V':
                        temp_exchanges.append(setting.lower())
                
                elif current_section == 'symbols':
                    if value.upper() == 'V':
                        temp_symbols.append(setting)
            
            if temp_exchanges:
                self.exchanges_config = temp_exchanges
            if temp_symbols:
                self.symbols = temp_symbols
            
            self.last_config_hash = self.get_config_hash()
            logger.info("הגדרות נטענו!")
            
        except Exception as e:
            logger.error(f"שגיאה: {e}")

    def check_config_changes(self):
        old_hash = self.last_config_hash
        old_exchanges = self.exchanges_config.copy()
        old_symbols = self.symbols.copy()
        old_profit = self.min_profit
        
        self.load_from_google_sheets()
        new_hash = self.get_config_hash()
        
        if old_hash != new_hash:
            changes = []
            if old_exchanges != self.exchanges_config:
                changes.append(f"בורסות: {self.exchanges_config}")
            if old_symbols != self.symbols:
                changes.append(f"מטבעות: {self.symbols}")
            if old_profit != self.min_profit:
                changes.append(f"רווח מינימלי: {self.min_profit}%")
            
            self.init_exchanges()
            
            msg = (
                "⚙️ *עדכון הגדרות*\n\n"
                "🔄 זוהו שינויים בהגדרות:\n\n"
                + "\n".join([f"• {c}" for c in changes]) +
                f"\n\n📊 בורסות פעילות: {len(self.exchanges_config)}\n"
                f"💰 מטבעות פעילים: {len(self.symbols)}\n\n"
                f"🕐 {datetime.now().strftime('%H:%M:%S')}"
            )
            self.send_telegram(msg)
            return True
        return False

    def send_telegram(self, message):
        if not self.telegram_token or not self.telegram_chat_id:
            return False
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {'chat_id': self.telegram_chat_id, 'text': message, 'parse_mode': 'Markdown'}
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except:
            return False

    def send_startup_message(self):
        msg = (
            "🚀 *הבוט התחיל לפעול!*\n\n"
            f"📊 בורסות: {len(self.exchanges_config)}\n"
            f"💰 מטבעות: {len(self.symbols)}\n"
            f"📈 רווח מינימלי: {self.min_profit}%\n"
            f"⏱ סריקה כל: {self.scan_interval} שניות\n"
            f"💓 דופק כל: {self.heartbeat_interval} דקות\n\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.send_telegram(msg)

    def send_heartbeat(self):
        if self.heartbeat_interval <= 0:
            return
        now = datetime.now()
        if self.last_heartbeat is None or (now - self.last_heartbeat).total_seconds() >= (self.heartbeat_interval * 60):
            uptime = now - self.start_time
            hours = int(uptime.total_seconds()) // 3600
            minutes = (int(uptime.total_seconds()) % 3600) // 60
            
            msg = (
                "💓 *דופק - הבוט פעיל*\n\n"
                f"⏱ זמן פעילות: {hours} שעות {minutes} דקות\n"
                f"🔍 סריקות: {self.total_scans}\n"
                f"🎯 הזדמנויות: {self.opportunities_found}\n\n"
                f"🕐 {now.strftime('%H:%M:%S')}"
            )
            self.send_telegram(msg)
            self.last_heartbeat = now

    async def get_prices(self, symbol):
        prices = {}
        for name, exchange in self.exchanges.items():
            try:
                ticker = exchange.fetch_ticker(symbol)
                if ticker and ticker.get('ask') and ticker.get('bid'):
                    orderbook = exchange.fetch_order_book(symbol, limit=5)
                    ask_volume = sum([o[1] for o in orderbook['asks'][:3]]) if orderbook['asks'] else 0
                    bid_volume = sum([o[1] for o in orderbook['bids'][:3]]) if orderbook['bids'] else 0
                    
                    prices[name] = {
                        'ask': ticker['ask'],
                        'bid': ticker['bid'],
                        'ask_volume': ask_volume,
                        'bid_volume': bid_volume
                    }
            except Exception as e:
                logger.debug(f"שגיאה {name} {symbol}: {e}")
        return prices

    def calculate_profit(self, buy_exchange, buy_price, sell_exchange, sell_price, amount):
        buy_fee = EXCHANGE_FEES.get(buy_exchange, {}).get('taker', 0.1) / 100
        sell_fee = EXCHANGE_FEES.get(sell_exchange, {}).get('taker', 0.1) / 100
        withdrawal_fee = EXCHANGE_FEES.get(buy_exchange, {}).get('withdrawal_btc', 0.0005)
        
        buy_cost = buy_price * amount * (1 + buy_fee)
        sell_revenue = sell_price * amount * (1 - sell_fee)
        withdrawal_cost = withdrawal_fee * buy_price
        
        gross_profit = sell_revenue - buy_cost
        net_profit = gross_profit - withdrawal_cost
        
        gross_percent = (gross_profit / buy_cost) * 100
        net_percent = (net_profit / buy_cost) * 100
        
        return {
            'gross_profit': gross_profit,
            'net_profit': net_profit,
            'gross_percent': gross_percent,
            'net_percent': net_percent,
            'buy_fee': buy_fee * 100,
            'sell_fee': sell_fee * 100,
            'withdrawal_cost': withdrawal_cost
        }
            async def check_arbitrage(self, symbol):
        prices = await self.get_prices(symbol)
        
        if len(prices) < 2:
            return None
        
        best_buy = min(prices.items(), key=lambda x: x[1]['ask'])
        best_sell = max(prices.items(), key=lambda x: x[1]['bid'])
        
        buy_exchange = best_buy[0]
        sell_exchange = best_sell[0]
        buy_price = best_buy[1]['ask']
        sell_price = best_sell[1]['bid']
        buy_volume = best_buy[1]['ask_volume']
        sell_volume = best_sell[1]['bid_volume']
        
        if buy_exchange == sell_exchange:
            return None
        
        amount = min(buy_volume, sell_volume, 1.0)
        
        profit_data = self.calculate_profit(buy_exchange, buy_price, sell_exchange, sell_price, amount)
        
        if profit_data['net_percent'] >= self.min_profit:
            return {
                'symbol': symbol,
                'buy_exchange': buy_exchange,
                'buy_price': buy_price,
                'buy_volume': buy_volume,
                'sell_exchange': sell_exchange,
                'sell_price': sell_price,
                'sell_volume': sell_volume,
                'amount': amount,
                'gross_percent': profit_data['gross_percent'],
                'net_percent': profit_data['net_percent'],
                'gross_profit': profit_data['gross_profit'],
                'net_profit': profit_data['net_profit'],
                'buy_fee': profit_data['buy_fee'],
                'sell_fee': profit_data['sell_fee']
            }
        
        return None

    def format_opportunity(self, opp):
        symbol_name = opp['symbol'].replace('/USDT', '')
        
        msg = (
            "🚨 *הזדמנות ארביטראז'!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 *מטבע:* {opp['symbol']}\n\n"
            
            f"📥 *קנייה:*\n"
            f"   🏦 בורסה: *{opp['buy_exchange'].upper()}*\n"
            f"   💵 מחיר: ${opp['buy_price']:,.4f}\n"
            f"   📊 כמות זמינה: {opp['buy_volume']:.4f} {symbol_name}\n"
            f"   💸 עמלה: {opp['buy_fee']:.2f}%\n\n"
            
            f"📤 *מכירה:*\n"
            f"   🏦 בורסה: *{opp['sell_exchange'].upper()}*\n"
            f"   💵 מחיר: ${opp['sell_price']:,.4f}\n"
            f"   📊 כמות זמינה: {opp['sell_volume']:.4f} {symbol_name}\n"
            f"   💸 עמלה: {opp['sell_fee']:.2f}%\n\n"
            
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 *רווח לפני עלויות:* {opp['gross_percent']:.2f}%\n"
            f"✅ *רווח אחרי עלויות:* {opp['net_percent']:.2f}%\n"
            f"💎 *כמות מומלצת:* {opp['amount']:.4f} {symbol_name}\n"
            f"💰 *רווח נקי:* ${opp['net_profit']:.2f}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        return msg

    async def monitor_loop(self):
        logger.info("מתחיל סריקה...")
        
        check_config_counter = 0
        
        while True:
            try:
                self.total_scans += 1
                logger.info(f"סריקה #{self.total_scans}")
                
                check_config_counter += 1
                if check_config_counter >= 6:
                    self.check_config_changes()
                    check_config_counter = 0
                
                self.send_heartbeat()
                
                for symbol in self.symbols:
                    opp = await self.check_arbitrage(symbol)
                    if opp:
                        self.opportunities_found += 1
                        logger.info(f"נמצא: {opp['symbol']} +{opp['net_percent']:.2f}%")
                        self.send_telegram(self.format_opportunity(opp))
                
                await asyncio.sleep(self.scan_interval)
                
            except Exception as e:
                logger.error(f"שגיאה: {str(e)}")
                await asyncio.sleep(10)

    def run(self):
        logger.info("מפעיל שרת Flask...")
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        asyncio.run(self.monitor_loop())


if __name__ == "__main__":
    bot = Arbiclod1()
    bot.run()
