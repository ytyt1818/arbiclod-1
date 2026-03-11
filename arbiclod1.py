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
    return "Arbiclod-1 פועל! 🚀"

@app.route('/ping')
def ping():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)


# עמלות משוערות לכל בורסה (באחוזים)
EXCHANGE_FEES = {
    'binance': {'maker': 0.1, 'taker': 0.1, 'withdrawal': 0.0005},
    'kucoin': {'maker': 0.1, 'taker': 0.1, 'withdrawal': 0.0005},
    'bybit': {'maker': 0.1, 'taker': 0.1, 'withdrawal': 0.0005},
    'okx': {'maker': 0.08, 'taker': 0.1, 'withdrawal': 0.0004},
    'gate': {'maker': 0.2, 'taker': 0.2, 'withdrawal': 0.001},
    'mexc': {'maker': 0.0, 'taker': 0.1, 'withdrawal': 0.0005},
    'huobi': {'maker': 0.2, 'taker': 0.2, 'withdrawal': 0.0005},
    'kraken': {'maker': 0.16, 'taker': 0.26, 'withdrawal': 0.0005},
    'coinbase': {'maker': 0.4, 'taker': 0.6, 'withdrawal': 0.0001},
}


class Arbiclod1:
    def __init__(self):
        logger.info("=" * 60)
        logger.info("🚀 ARBICLOD-1 - מתחיל")
        logger.info("=" * 60)
        
        # קריאה מ-Environment Variables
        self.telegram_token = os.environ.get('TELEGRAM_TOKEN', '')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        self.sheet_url = os.environ.get('GOOGLE_SHEET_URL', '')
        
        # הגדרות ברירת מחדל
        self.scan_interval = 10
        self.min_profit = 0.5
        self.heartbeat_interval = 10
        self.last_heartbeat = None
        self.opportunities_found = 0
        self.total_scans = 0
        self.start_time = datetime.now()
        self.last_config_hash = None
        
        self.exchanges_config = ['binance', 'kucoin', 'bybit']
        self.symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        
        # אתחול בורסות
        self.exchanges = {}
        
        # טעינה מ-Google Sheets
        if self.sheet_url:
            self.load_from_google_sheets()
        
        # יצירת חיבורים לבורסות
        self.init_exchanges()
        
        logger.info("=" * 60)
        logger.info(f"📊 בורסות: {list(self.exchanges.keys())}")
        logger.info(f"💰 מטבעות: {self.symbols}")
        logger.info(f"📈 רווח מינימלי: {self.min_profit}%")
        logger.info("=" * 60)
        
        self.send_startup_message()

    def init_exchanges(self):
        """אתחול חיבורים לבורסות"""
        for exchange_id in self.exchanges_config:
            try:
                exchange_class = getattr(ccxt, exchange_id)
                self.exchanges[exchange_id] = exchange_class({
                    'enableRateLimit': True,
                    'timeout': 10000,
                })
                logger.info(f"✅ {exchange_id} מחובר")
            except Exception as e:
                logger.error(f"❌ שגיאה בחיבור ל-{exchange_id}: {e}")

    def get_config_hash(self):
        """יצירת hash של ההגדרות לזיהוי שינויים"""
        config_str = f"{self.exchanges_config}{self.symbols}{self.min_profit}{self.scan_interval}"
        return hash(config_str)

    def load_from_google_sheets(self):
        """טעינת הגדרות מ-Google Sheets"""
        try:
            logger.info("📊 טוען הגדרות מ-Google Sheets...")
            
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
                
                # זיהוי סקשנים
                if 'הגדרות בוט' in setting or 'BOT' in setting.upper():
                    current_section = 'settings'
                    continue
                elif 'הגדרות סריקה' in setting or 'SCAN' in setting.upper():
                    current_section = 'settings'
                    continue
                elif 'בורסות' in setting or 'EXCHANGE' in setting.upper():
                    current_section = 'exchanges'
                    continue
                elif 'מטבעות' in setting or 'SYMBOL' in setting.upper():
                    current_section = 'symbols'
                    continue
                elif 'הוראות' in setting:
                    break
                
                if current_section == 'settings':
                    if ('token' in setting.lower() or 'טוקן' in setting) and not self.telegram_token:
                        self.telegram_token = value
                    
                    if ('chat' in setting.lower() or 'צאט' in setting or 'מזהה' in setting) and not self.telegram_chat_id:
                        if '.' in value:
                            value = value.split('.')[0]
                        self.telegram_chat_id = value
                    
                    if 'שניות' in setting or 'interval' in setting.lower():
                        try:
                            self.scan_interval = int(float(value))
                        except:
                            pass
                    
                    if 'רווח' in setting or 'profit' in setting.lower():
                        try:
                            self.min_profit = float(value)
                        except:
                            pass
                    
                    if 'דקות' in setting or 'heartbeat' in setting.lower():
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
            
            # שמירת hash להשוואה
            self.last_config_hash = self.get_config_hash()
            
            logger.info("✅ הגדרות נטענו בהצלחה!")
            
        except Exception as e:
            logger.error(f"❌ שגיאה בטעינת Google Sheets: {e}")
