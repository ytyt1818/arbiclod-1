"""
Arbiclod-1 - Enhanced Crypto Arbitrage Bot
Features:
- Unified single-sheet configuration
- Config change notifications
- Heartbeat (alive) messages
- Telegram group support
- Google Sheets integration
- Flask web server for Render Keep-Alive
"""
import asyncio
import random
import hashlib
from datetime import datetime, timedelta
import requests
import logging
from pathlib import Path
from threading import Thread
from flask import Flask

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('arbiclod1.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask app for keep-alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Arbiclod-1 is running! 🚀"

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
    """Run Flask in a separate thread"""
    import os
    # Disable Flask development mode warnings
    os.environ['FLASK_ENV'] = 'production'
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False, threaded=True)

class Arbiclod1:
    def __init__(self, use_google_sheets=False, sheet_url=None):
        self.use_google_sheets = use_google_sheets
        self.sheet_url = sheet_url
        self.config = {}
        self.config_hash = None
        self.last_heartbeat = None
        self.opportunities_found = 0
        self.total_scans = 0
        self.start_time = datetime.now()
        
        logger.info("="*60)
        logger.info("🤖 ARBICLOD-1 - STARTING UP")
        logger.info("="*60)
        
        self.load_config()
        self.send_startup_message()
        
    def calculate_config_hash(self):
        """Calculate hash of config to detect changes"""
        import json
        config_str = json.dumps(self.config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def load_config_from_excel(self):
        """Load from local Excel file"""
        import pandas as pd
        
        config_file = 'arbiclod1_config.xlsx'
        if not Path(config_file).exists():
            # Fallback to old config
            config_file = 'config.xlsx'
            if not Path(config_file).exists():
                raise FileNotFoundError(f"Config file not found")
        
        logger.info(f"📊 Loading config from: {config_file}")
        
        # Read the unified control panel
        df = pd.read_excel(config_file, sheet_name=0)  # First sheet
        
        # Detect column names (support both Hebrew and English)
        col_mapping = {}
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if 'הגדרה' in col_lower or 'setting' in col_lower:
                col_mapping['setting'] = col
            elif 'ערך' in col_lower or 'value' in col_lower:
                col_mapping['value'] = col
        
        # Check if we found the columns
        if 'setting' not in col_mapping or 'value' not in col_mapping:
            logger.error(f"Could not find required columns. Available columns: {df.columns.tolist()}")
            raise ValueError("Missing required columns in Excel file")
        
        setting_col = col_mapping['setting']
        value_col = col_mapping['value']
        
        # Parse settings
        self.config = {
            'settings': {},
            'exchanges': {},
            'symbols': {}
        }
        
        current_section = None
        for _, row in df.iterrows():
            if pd.isna(row[setting_col]):
                continue
                
            setting = str(row[setting_col]).strip()
            
            # Detect sections (support both English and Hebrew)
            if '🤖' in setting or 'BOT CONFIGURATION' in setting or 'הגדרות בוט' in setting:
                current_section = 'settings'
                continue
            elif '⚙️' in setting or 'SCANNING' in setting or 'הגדרות סריקה' in setting:
                current_section = 'settings'
                continue
            elif '🏦' in setting or 'EXCHANGES' in setting or 'בורסות למעקב' in setting:
                current_section = 'exchanges'
                continue
            elif '💰' in setting or 'SYMBOLS' in setting or 'מטבעות למעקב' in setting:
                current_section = 'symbols'
                continue
            elif '📖' in setting or 'HOW TO USE' in setting or 'הוראות שימוש' in setting:
                break
            
            # Parse values
            if current_section == 'settings':
                value = row[value_col]
                self.config['settings'][setting] = value
            elif current_section == 'exchanges':
                enabled = str(row[value_col]).strip().upper() == 'V'
                if enabled:
                    self.config['exchanges'][setting] = True
            elif current_section == 'symbols':
                enabled = str(row[value_col]).strip().upper() == 'V'
                if enabled:
                    self.config['symbols'][setting] = True
    
    def load_config_from_google_sheets(self):
        """Load from Google Sheets"""
        import pandas as pd
        
        logger.info("📊 Loading config from Google Sheets...")
        
        # Extract sheet ID
        if '/d/' in self.sheet_url:
            sheet_id = self.sheet_url.split('/d/')[1].split('/')[0]
        else:
            sheet_id = self.sheet_url
        
        # Load the unified sheet (gid=0 for first sheet)
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid=0"
        
        try:
            # Read without header, we'll use fixed positions
            df = pd.read_csv(url, header=None)
            
            logger.info(f"Loaded {len(df)} rows from Google Sheets")
            
            self.config = {
                'settings': {},
                'exchanges': {},
                'symbols': {}
            }
            
            current_section = None
            
            # Start from row 4 (index 3) - skip title and header rows
            for idx in range(3, len(df)):
                row = df.iloc[idx]
                
                # Column A (index 0) = Setting name
                if pd.isna(row[0]):
                    continue
                
                setting = str(row[0]).strip()
                
                # Column B (index 1) = Value
                value = row[1] if not pd.isna(row[1]) else ""
                
                # Detect sections
                if '🤖' in setting or 'הגדרות בוט' in setting:
                    current_section = 'settings'
                    logger.info("📍 Found settings section")
                    continue
                elif '⚙️' in setting or 'הגדרות סריקה' in setting:
                    current_section = 'settings'
                    logger.info("📍 Found scanning settings section")
                    continue
                elif '🏦' in setting or 'בורסות למעקב' in setting:
                    current_section = 'exchanges'
                    logger.info("📍 Found exchanges section")
                    continue
                elif '💰' in setting or 'מטבעות למעקב' in setting:
                    current_section = 'symbols'
                    logger.info("📍 Found symbols section")
                    continue
                elif '📖' in setting or 'הוראות שימוש' in setting:
                    logger.info("📍 Reached instructions - stopping")
                    break
                
                # Skip if no section yet
                if current_section is None:
                    continue
                
                # Parse values based on section
                if current_section == 'settings':
                    self.config['settings'][setting] = value
                    logger.info(f"  Setting: {setting} = {value}")
                elif current_section == 'exchanges':
                    enabled = str(value).strip().upper() == 'V'
                    if enabled:
                        self.config['exchanges'][setting] = True
                        logger.info(f"  Exchange enabled: {setting}")
                elif current_section == 'symbols':
                    enabled = str(value).strip().upper() == 'V'
                    if enabled:
                        self.config['symbols'][setting] = True
                        logger.info(f"  Symbol enabled: {setting}")
                        
        except Exception as e:
            logger.error(f"Failed to load from Google Sheets: {e}")
            raise
    
    def load_config(self):
        """Load configuration"""
        try:
            if self.use_google_sheets:
                self.load_config_from_google_sheets()
            else:
                self.load_config_from_excel()
            
            # Calculate initial hash
            self.config_hash = self.calculate_config_hash()
            
            # Extract key settings with Hebrew mapping
            settings = self.config['settings']
            
            # Hebrew to English mapping
            hebrew_to_english = {
                'טוקן_טלגרם': 'telegram_token',
                'מזהה_צאט': 'telegram_chat_id',
                'מצב_קבוצה': 'telegram_group_mode',
                'דקות_בין_הודעות_חיים': 'heartbeat_interval_minutes',
                'התרעה_על_שינויים': 'notify_on_config_change',
                'שניות_בין_סריקות': 'scan_interval_seconds',
                'אחוז_רווח_מינימלי': 'min_profit_percent',
                'מחזור_מינימלי_דולר': 'min_volume_usd'
            }
            
            # Support both Hebrew and English keys
            def get_setting(key_en, key_he, default=''):
                if key_he in settings:
                    return settings[key_he]
                elif key_en in settings:
                    return settings[key_en]
                return default
            
            self.telegram_token = get_setting('telegram_token', 'טוקן_טלגרם', '')
            self.telegram_chat_id = get_setting('telegram_chat_id', 'מזהה_צאט', '')
            self.group_mode = str(get_setting('telegram_group_mode', 'מצב_קבוצה', 'X')).upper() == 'V'
            self.heartbeat_interval = int(get_setting('heartbeat_interval_minutes', 'דקות_בין_הודעות_חיים', 30))
            self.notify_changes = str(get_setting('notify_on_config_change', 'התרעה_על_שינויים', 'V')).upper() == 'V'
            self.scan_interval = int(get_setting('scan_interval_seconds', 'שניות_בין_סריקות', 10))
            self.min_profit = float(get_setting('min_profit_percent', 'אחוז_רווח_מינימלי', 1.0))
            
            logger.info("\n" + "="*60)
            logger.info("✅ Configuration loaded successfully!")
            logger.info(f"   📊 Monitoring: {len(self.config['symbols'])} symbols")
            logger.info(f"   🏦 Exchanges: {len(self.config['exchanges'])}")
            logger.info(f"   💰 Min profit: {self.min_profit}%")
            logger.info(f"   ⏱️  Scan interval: {self.scan_interval}s")
            logger.info(f"   💬 Chat mode: {'Group' if self.group_mode else 'Personal'}")
            logger.info(f"   💓 Heartbeat: {self.heartbeat_interval}min")
            logger.info("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"❌ Fatal error loading config: {str(e)}")
            raise
    
    def check_config_changes(self):
        """Check if config changed and reload if needed"""
        try:
            # Reload config
            if self.use_google_sheets:
                self.load_config_from_google_sheets()
            else:
                self.load_config_from_excel()
            
            # Calculate new hash
            new_hash = self.calculate_config_hash()
            
            if new_hash != self.config_hash:
                logger.info("⚠️  Configuration changed! Reloading...")
                
                # Update hash
                old_hash = self.config_hash
                self.config_hash = new_hash
                
                # Update settings with Hebrew support
                settings = self.config['settings']
                
                # Support both Hebrew and English keys
                def get_setting(key_en, key_he, default=''):
                    if key_he in settings:
                        return settings[key_he]
                    elif key_en in settings:
                        return settings[key_en]
                    return default
                
                self.telegram_token = get_setting('telegram_token', 'טוקן_טלגרם', '')
                self.telegram_chat_id = get_setting('telegram_chat_id', 'מזהה_צאט', '')
                self.group_mode = str(get_setting('telegram_group_mode', 'מצב_קבוצה', 'X')).upper() == 'V'
                self.heartbeat_interval = int(get_setting('heartbeat_interval_minutes', 'דקות_בין_הודעות_חיים', 30))
                self.notify_changes = str(get_setting('notify_on_config_change', 'התרעה_על_שינויים', 'V')).upper() == 'V'
                self.scan_interval = int(get_setting('scan_interval_seconds', 'שניות_בין_סריקות', 10))
                self.min_profit = float(get_setting('min_profit_percent', 'אחוז_רווח_מינימלי', 1.0))
                
                # Send notification
                if self.notify_changes:
                    message = f"""
⚙️ <b>CONFIG CHANGED</b>

📊 Symbols: {len(self.config['symbols'])}
🏦 Exchanges: {len(self.config['exchanges'])}
💰 Min profit: {self.min_profit}%
⏱️  Scan interval: {self.scan_interval}s

✅ Settings reloaded successfully!

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
                    self.send_telegram(message.strip())
                
                logger.info("✅ Config reloaded!")
                return True
                
        except Exception as e:
            logger.error(f"Error checking config changes: {e}")
        
        return False
    
    def send_telegram(self, message):
        """Send message to Telegram"""
        if not self.telegram_token or self.telegram_token == 'YOUR_TELEGRAM_BOT_TOKEN':
            logger.debug("Telegram not configured")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                logger.warning(f"Telegram error: {response.text}")
                return False
                
        except Exception as e:
            logger.warning(f"Telegram send error: {str(e)}")
            return False
    
    def send_startup_message(self):
        """Send bot startup notification"""
        mode = "GROUP" if self.group_mode else "PERSONAL"
        message = f"""
🚀 <b>ARBICLOD-1 STARTED</b>

✅ Bot is now <b>ONLINE</b>
📊 Monitoring {len(self.config['symbols'])} symbols
🏦 Checking {len(self.config['exchanges'])} exchanges
💰 Min profit threshold: {self.min_profit}%
⏱️  Scan interval: {self.scan_interval} seconds
💬 Mode: {mode}
💓 Heartbeat: Every {self.heartbeat_interval} minutes

Ready to find arbitrage opportunities! 🎯

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        self.send_telegram(message.strip())
    
    def send_heartbeat(self):
        """Send heartbeat message"""
        if self.heartbeat_interval <= 0:
            return
        
        now = datetime.now()
        if self.last_heartbeat is None or (now - self.last_heartbeat).seconds >= (self.heartbeat_interval * 60):
            uptime = now - self.start_time
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            message = f"""
💓 <b>HEARTBEAT</b>

✅ Bot is <b>ALIVE</b> and running

📊 Stats:
• Uptime: {hours}h {minutes}m
• Total scans: {self.total_scans}
• Opportunities: {self.opportunities_found}
• Last scan: Just now

🕐 {now.strftime('%Y-%m-%d %H:%M:%S')}
            """
            self.send_telegram(message.strip())
            self.last_heartbeat = now
            logger.info("💓 Heartbeat sent")
    
    async def check_arbitrage(self, symbol):
        """Check for arbitrage opportunity using REAL prices"""
        import ccxt.async_support as ccxt
        
        prices = []
        
        # Fetch real prices from each exchange
        for exchange_name in self.config['exchanges'].keys():
            try:
                # Initialize exchange
                if exchange_name == 'binance':
                    exchange = ccxt.binance()
                elif exchange_name == 'kucoin':
                    exchange = ccxt.kucoin()
                elif exchange_name == 'bybit':
                    exchange = ccxt.bybit()
                elif exchange_name == 'coinbase':
                    exchange = ccxt.coinbase()
                elif exchange_name == 'kraken':
                    exchange = ccxt.kraken()
                elif exchange_name == 'gate':
                    exchange = ccxt.gate()
                elif exchange_name == 'mexc':
                    exchange = ccxt.mexc()
                elif exchange_name == 'okx':
                    exchange = ccxt.okx()
                else:
                    continue
                
                # Fetch ticker
                ticker = await exchange.fetch_ticker(symbol)
                await exchange.close()
                
                # Get prices and volume
                ask = ticker['ask']  # Buy price
                bid = ticker['bid']  # Sell price
                volume_24h = ticker['quoteVolume'] if ticker['quoteVolume'] else 0
                
                prices.append({
                    'exchange': exchange_name,
                    'ask': ask,
                    'bid': bid,
                    'volume': volume_24h
                })
                
            except Exception as e:
                logger.warning(f"Could not fetch {symbol} from {exchange_name}: {e}")
                continue
        
        # Need at least 2 exchanges to compare
        if len(prices) < 2:
            return None
        
        # Find best buy and sell opportunities
        best_buy = min(prices, key=lambda x: x['ask'])
        best_sell = max(prices, key=lambda x: x['bid'])
        
        # Skip if same exchange
        if best_buy['exchange'] == best_sell['exchange']:
            return None
        
        buy_price = best_buy['ask']
        sell_price = best_sell['bid']
        profit = ((sell_price - buy_price) / buy_price) * 100
        
        # Check if profit meets threshold
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
        """Format opportunity message in Hebrew with tradeable amounts and fees"""
        # Format prices
        buy_price_str = f"${opp['buy_price']:,.2f}"
        sell_price_str = f"${opp['sell_price']:,.2f}"
        
        # Calculate tradeable amounts (based on 24h volume)
        # Assume we can trade ~0.1% of 24h volume safely
        buy_volume_usd = opp['buy_volume'] * 0.001  # 0.1% of daily volume
        sell_volume_usd = opp['sell_volume'] * 0.001
        
        # Calculate coin amounts
        buy_amount_coins = buy_volume_usd / opp['buy_price']
        sell_amount_coins = sell_volume_usd / opp['sell_price']
        
        # Use the smaller amount (bottleneck)
        max_tradeable_coins = min(buy_amount_coins, sell_amount_coins)
        max_tradeable_usd = max_tradeable_coins * opp['buy_price']
        
        # Get coin symbol (e.g., BTC from BTC/USDT)
        coin_symbol = opp['symbol'].split('/')[0]
        
        # Calculate fees (typical exchange fees)
        # Buy fee: 0.1% (maker/taker on most exchanges)
        # Sell fee: 0.1%
        # Withdrawal fee: ~0.05% (varies, but conservative estimate)
        buy_fee = max_tradeable_usd * 0.001  # 0.1%
        sell_fee = max_tradeable_usd * 0.001  # 0.1%
        withdrawal_fee = max_tradeable_usd * 0.0005  # 0.05%
        total_fees = buy_fee + sell_fee + withdrawal_fee
        
        # Gross profit
        gross_profit = max_tradeable_usd * (opp['profit'] / 100)
        
        # Net profit after fees
        net_profit = gross_profit - total_fees
        net_profit_percent = (net_profit / max_tradeable_usd) * 100
        
        # Format amounts
        max_coins_str = f"{max_tradeable_coins:,.4f}"
        max_usd_str = f"${max_tradeable_usd:,.2f}"
        gross_profit_str = f"${gross_profit:,.2f}"
        net_profit_str = f"${net_profit:,.2f}"
        total_fees_str = f"${total_fees:,.2f}"
        
        # Choose emoji based on net profit
        profit_emoji = "✅" if net_profit > 0 else "⚠️"
        
        return f"""
🚨 <b>הזדמנות ארביטראז'!</b> 🚨

💰 <b>מטבע: {opp['symbol']}</b>

📉 <b>קנייה ב-{opp['buy_exchange'].upper()}</b>
   💵 מחיר: {buy_price_str}
   📊 נפח 24 שעות: ${opp['buy_volume']:,.0f}
   🔢 ניתן לקנות: {max_coins_str} {coin_symbol}

📈 <b>מכירה ב-{opp['sell_exchange'].upper()}</b>
   💵 מחיר: {sell_price_str}
   📊 נפח 24 שעות: ${opp['sell_volume']:,.0f}
   🔢 ניתן למכור: {max_coins_str} {coin_symbol}

💸 <b>סכום מומלץ למסחר: {max_usd_str}</b>

📊 <b>חישוב רווחיות:</b>
   • רווח גולמי: {gross_profit_str} ({opp['profit']:.2f}%)
   • עמלות (קנייה+מכירה+משיכה): {total_fees_str}
   • {profit_emoji} <b>רווח נטו: {net_profit_str} ({net_profit_percent:.2f}%)</b>

⚠️ <b>שים לב:</b>
   • בדוק עמלות בפועל בבורסות
   • מחירים משתנים במהירות
   • זמן העברה בין בורסות: 10-30 דקות

🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        """
    
    async def monitor_loop(self):
        """Main monitoring loop with synchronized timing"""
        logger.info("🤖 הבוט התחיל - מנטר שווקים")
        logger.info(f"⏱️  בודק כל {self.scan_interval} שניות")
        logger.info("💡 לחץ Ctrl+C לעצירה\n")
        
        config_check_counter = 0
        
        # Wait until next round time
        now = datetime.now()
        seconds_to_wait = self.scan_interval - (now.second % self.scan_interval)
        if seconds_to_wait > 0:
            logger.info(f"⏰ ממתין {seconds_to_wait} שניות עד לזמן עגול הבא...")
            await asyncio.sleep(seconds_to_wait)
        
        while True:
            try:
                self.total_scans += 1
                timestamp = datetime.now().strftime('%H:%M:%S')
                logger.info(f"[{timestamp}] 🔍 סריקה #{self.total_scans}")
                
                # Check for config changes every 5 scans
                config_check_counter += 1
                if config_check_counter >= 5:
                    self.check_config_changes()
                    config_check_counter = 0
                
                # Send heartbeat if needed
                self.send_heartbeat()
                
                # Scan for opportunities
                opportunities = []
                for symbol in self.config['symbols'].keys():
                    opp = await self.check_arbitrage(symbol)
                    if opp:
                        opportunities.append(opp)
                
                if opportunities:
                    self.opportunities_found += len(opportunities)
                    logger.info(f"🎯 נמצאו {len(opportunities)} הזדמנות!")
                    
                    for opp in opportunities:
                        message = self.format_opportunity(opp)
                        print("\n" + message + "\n")
                        self.send_telegram(message)
                else:
                    logger.info("   אין הזדמנויות")
                
                # Wait until next round time
                now = datetime.now()
                seconds_until_next = self.scan_interval - (now.second % self.scan_interval)
                await asyncio.sleep(seconds_until_next)
                
            except KeyboardInterrupt:
                logger.info("\n⛔ הבוט נעצר על ידי המשתמש")
                self.send_telegram("⛔ <b>ARBICLOD-1 נעצר</b>\n\nהבוט כובה.")
                break
            except Exception as e:
                logger.error(f"❌ שגיאה: {str(e)}")
                await asyncio.sleep(10)
    
    def run(self):
        """Start the bot with Flask server"""
        # Start Flask server in background thread
        logger.info("🌐 Starting Flask web server on port 8080...")
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Start bot
        try:
            asyncio.run(self.monitor_loop())
        except KeyboardInterrupt:
            logger.info("\n👋 Goodbye!")

if __name__ == "__main__":
    import sys
    
    use_sheets = '--sheets' in sys.argv
    
    if use_sheets:
        sheet_url = None
        for arg in sys.argv:
            if 'docs.google.com' in arg or (len(arg) == 44 and '-' in arg):
                sheet_url = arg
                break
        
        if not sheet_url:
            print("❌ Please provide Google Sheets URL")
            print("Usage: python arbiclod1.py --sheets YOUR_SHEET_URL")
            sys.exit(1)
        
        bot = Arbiclod1(use_google_sheets=True, sheet_url=sheet_url)
    else:
        bot = Arbiclod1(use_google_sheets=False)
    
    bot.run()
