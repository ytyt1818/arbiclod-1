"""
Arbiclod-1 - Enhanced Crypto Arbitrage Bot
Memory Optimized Version
"""
import asyncio
import hashlib
import logging
import os
import sys
import gc
from datetime import datetime, timedelta
from threading import Thread

# ✅ שעון ישראל
os.environ['TZ'] = 'Asia/Jerusalem'
try:
    import time
    time.tzset()
except AttributeError:
    pass

import requests
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
    os.environ['FLASK_ENV'] = 'production'
    app.run(host='0.0.0.0', port=8080, debug=False,
            use_reloader=False, threaded=True)


EXCHANGE_FEES = {
    'binance': {
        'taker': 0.001,
        'withdrawal': {
            'BTC': 0.0005, 'ETH': 0.005, 'BNB': 0.0005,
            'SOL': 0.01, 'XRP': 0.25, 'USDT': 1.0,
            'DEFAULT_PCT': 0.001
        }
    },
    'kucoin': {
        'taker': 0.001,
        'withdrawal': {
            'BTC': 0.0004, 'ETH': 0.004, 'BNB': 0.001,
            'SOL': 0.01, 'XRP': 0.2, 'USDT': 1.0,
            'DEFAULT_PCT': 0.001
        }
    },
    'bybit': {
        'taker': 0.001,
        'withdrawal': {
            'BTC': 0.0005, 'ETH': 0.005, 'BNB': 0.0008,
            'SOL': 0.01, 'XRP': 0.25, 'USDT': 1.0,
            'DEFAULT_PCT': 0.001
        }
    },
    'okx': {
        'taker': 0.0008,
        'withdrawal': {
            'BTC': 0.0004, 'ETH': 0.004, 'SOL': 0.01,
            'XRP': 0.2, 'USDT': 1.0, 'DEFAULT_PCT': 0.001
        }
    },
    'gate': {
        'taker': 0.002,
        'withdrawal': {
            'BTC': 0.001, 'ETH': 0.01, 'SOL': 0.02,
            'XRP': 0.3, 'USDT': 2.0, 'DEFAULT_PCT': 0.002
        }
    },
    'mexc': {
        'taker': 0.002,
        'withdrawal': {
            'BTC': 0.0005, 'ETH': 0.006, 'SOL': 0.01,
            'XRP': 0.25, 'USDT': 1.0, 'DEFAULT_PCT': 0.001
        }
    },
    'kraken': {
        'taker': 0.0026,
        'withdrawal': {
            'BTC': 0.00015, 'ETH': 0.0035, 'SOL': 0.01,
            'XRP': 0.02, 'USDT': 2.5, 'DEFAULT_PCT': 0.002
        }
    },
    'coinbase': {
        'taker': 0.006,
        'withdrawal': {
            'BTC': 0.0, 'ETH': 0.0, 'SOL': 0.0,
            'DEFAULT_PCT': 0.001
        }
    },
    'huobi': {
        'taker': 0.002,
        'withdrawal': {
            'BTC': 0.0004, 'ETH': 0.004, 'BNB': 0.001,
            'SOL': 0.01, 'XRP': 0.2, 'USDT': 1.0,
            'DEFAULT_PCT': 0.002
        }
    },
    'bitfinex': {
        'taker': 0.002,
        'withdrawal': {
            'BTC': 0.0004, 'ETH': 0.004, 'BNB': 0.001,
            'SOL': 0.01, 'XRP': 0.2, 'USDT': 1.0,
            'DEFAULT_PCT': 0.002
        }
    }
}


def calculate_real_fees(buy_exchange, sell_exchange,
                        coin_symbol, trade_usd, buy_price):
    buy_cfg = EXCHANGE_FEES.get(buy_exchange, EXCHANGE_FEES['binance'])
    sell_cfg = EXCHANGE_FEES.get(sell_exchange, EXCHANGE_FEES['binance'])
    buy_fee = trade_usd * buy_cfg['taker']
    sell_fee = trade_usd * sell_cfg['taker']
    wd = buy_cfg['withdrawal']
    if coin_symbol in wd:
        withdrawal_fee = wd[coin_symbol] * buy_price
    else:
        withdrawal_fee = trade_usd * wd.get('DEFAULT_PCT', 0.001)
    total = buy_fee + sell_fee + withdrawal_fee
    return {
        'buy_fee': buy_fee,
        'buy_fee_pct': buy_cfg['taker'] * 100,
        'sell_fee': sell_fee,
        'sell_fee_pct': sell_cfg['taker'] * 100,
        'withdrawal_fee': withdrawal_fee,
        'total': total,
        'total_pct': (total / trade_usd) * 100
    }


class ExchangePool:
    def __init__(self, exchange_names):
        self.exchange_names = exchange_names
        self.exchanges = {}
        self.semaphore = None

    async def initialize(self):
        import ccxt.async_support as ccxt

        # ✅ סמפור להגבלת בקשות מקביליות
        self.semaphore = asyncio.Semaphore(15)

        classes = {
            'binance': ccxt.binance,
            'kucoin': ccxt.kucoin,
            'bybit': ccxt.bybit,
            'coinbase': ccxt.coinbase,
            'kraken': ccxt.kraken,
            'gate': ccxt.gate,
            'mexc': ccxt.mexc,
            'okx': ccxt.okx,
            'huobi': ccxt.huobi,
            'bitfinex': ccxt.bitfinex,
        }

        for name in self.exchange_names:
            if name in classes:
                try:
                    self.exchanges[name] = classes[name]({
                        'enableRateLimit': True,
                        'timeout': 10000,
                        'options': {'defaultType': 'spot'}
                    })
                    logger.info(f"✅ Connected: {name}")
                except Exception as e:
                    logger.error(f"❌ Failed {name}: {e}")
            else:
                logger.warning(f"⚠️ Unknown exchange: {name}")

        logger.info(f"🏦 Pool ready: {list(self.exchanges.keys())}")

    async def close_all(self):
        for ex in self.exchanges.values():
            try:
                await ex.close()
            except Exception:
                pass
        self.exchanges.clear()


class Arbiclod1:
    def __init__(self, use_google_sheets=False, sheet_url=None):
        self.use_google_sheets = use_google_sheets
        self.sheet_url = sheet_url
        self.config = {}
        self.config_hash = None
        self.last_heartbeat = None
        self.last_pool_refresh = datetime.now()
        self.opportunities_found = 0
        self.total_scans = 0
        self.start_time = datetime.now()
        self.exchange_pool = None

        logger.info("=" * 60)
        logger.info("🤖 ARBICLOD-1 - STARTING UP")
        logger.info("=" * 60)

        self.load_config()
        self.send_startup_message()

    def calculate_config_hash(self):
        import json
        return hashlib.md5(
            json.dumps(self.config, sort_keys=True).encode()
        ).hexdigest()

    def load_config_from_google_sheets(self):
        import pandas as pd
        import io

        logger.info("📊 Loading from Google Sheets...")

        if self.sheet_url and '/d/' in self.sheet_url:
            sheet_id = self.sheet_url.split('/d/')[1].split('/')[0]
        else:
            sheet_id = self.sheet_url

        url = (f"https://docs.google.com/spreadsheets/d/"
               f"{sheet_id}/gviz/tq?tqx=out:csv&gid=0")

        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            raise Exception(f"Failed to load sheet: {resp.status_code}")

        df = pd.read_csv(io.StringIO(resp.text), header=None)
        logger.info(f"Loaded {len(df)} rows")

        self.config = {'settings': {}, 'exchanges': {}, 'symbols': {}}
        current_section = 'settings'

        for idx in range(len(df)):
            row = df.iloc[idx]
            if pd.isna(row[0]):
                continue

            col_a = str(row[0]).strip()
            col_b = str(row[1]).strip() if not pd.isna(row[1]) else ""

            if idx == 0:
                if col_b and 'ערך' in col_b:
                    token_val = col_b.replace('ערך', '').strip()
                    if token_val:
                        self.config['settings']['token'] = token_val
                continue

            if '⚙️' in col_a or 'הגדרות סריקה' in col_a:
                current_section = 'settings'
                continue
            elif '🏦' in col_a or 'בורסות למעקב' in col_a:
                current_section = 'exchanges'
                continue
            elif '💰' in col_a or 'מטבעות למעקב' in col_a:
                current_section = 'symbols'
                continue
            elif '📖' in col_a or 'הוראות שימוש' in col_a:
                break

            if not col_a or col_a == 'ריק':
                continue

            if current_section == 'settings':
                self.config['settings'][col_a] = col_b
            elif current_section == 'exchanges':
                if col_b.upper() == 'V':
                    self.config['exchanges'][col_a] = True
                    logger.info(f"  Exchange ON: {col_a}")
            elif current_section == 'symbols':
                if col_b.upper() == 'V':
                    self.config['symbols'][col_a] = True
                    logger.info(f"  Symbol ON: {col_a}")

        logger.info(
            f"✅ Loaded: {len(self.config['settings'])} settings, "
            f"{len(self.config['exchanges'])} exchanges, "
            f"{len(self.config['symbols'])} symbols"
        )

    def load_config_from_excel(self):
        import pandas as pd
        from pathlib import Path

        config_file = 'arbiclod1_config.xlsx'
        if not Path(config_file).exists():
            config_file = 'config.xlsx'

        df = pd.read_excel(config_file, sheet_name=0)
        col_mapping = {}
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if 'הגדרה' in col_lower or 'setting' in col_lower:
                col_mapping['setting'] = col
            elif 'ערך' in col_lower or 'value' in col_lower:
                col_mapping['value'] = col

        sc = col_mapping['setting']
        vc = col_mapping['value']
        self.config = {'settings': {}, 'exchanges': {}, 'symbols': {}}
        current_section = None

        for _, row in df.iterrows():
            if pd.isna(row[sc]):
                continue
            setting = str(row[sc]).strip()

            if '🤖' in setting:
                current_section = 'settings'
                continue
            elif '⚙️' in setting:
                current_section = 'settings'
                continue
            elif '🏦' in setting:
                current_section = 'exchanges'
                continue
            elif '💰' in setting:
                current_section = 'symbols'
                continue
            elif '📖' in setting:
                break

            if current_section == 'settings':
                self.config['settings'][setting] = row[vc]
            elif current_section in ('exchanges', 'symbols'):
                if str(row[vc]).strip().upper() == 'V':
                    self.config[current_section][setting] = True

    def load_config(self):
        try:
            if self.use_google_sheets:
                self.load_config_from_google_sheets()
            else:
                self.load_config_from_excel()

            self.config_hash = self.calculate_config_hash()
            s = self.config['settings']

            def get(key1, key2='', default=''):
                return s.get(key1, s.get(key2, default))

            self.telegram_token = get('token', 'טוקן_טלגרם', '')
            self.telegram_chat_id = get('chatid', 'מזהה_צאט', '')
            self.group_mode = (
                str(get('מצב_קבוצה', 'group_mode', 'X')).upper() == 'V'
            )
            self.heartbeat_interval = int(float(
                get('דקות_בין_הודעות_חיים', 'heartbeat_minutes', 20)
            ))
            self.notify_changes = (
                str(get('התרעה_על_שינויים', 'notify_changes', 'V'))
                .upper() == 'V'
            )
            self.scan_interval = int(float(
                get('שניות_בין_סריקות', 'scan_seconds', 15)
            ))
            self.min_profit = float(
                get('אחוז_רווח_מינימלי', 'min_profit', 0.1)
            )
            self.min_volume_usd = float(
                get('מחזור_מינימלי_דולר', 'min_volume', 10000)
            )

            logger.info(
                f"\n{'=' * 50}\n"
                f"✅ Config loaded!\n"
                f"   Token: {self.telegram_token[:20]}...\n"
                f"   Chat ID: {self.telegram_chat_id}\n"
                f"   Symbols: {len(self.config['symbols'])}\n"
                f"   Exchanges: {len(self.config['exchanges'])}\n"
                f"   Min profit: {self.min_profit}%\n"
                f"   Min volume: ${self.min_volume_usd:,.0f}\n"
                f"   Scan every: {self.scan_interval}s\n"
                f"   Heartbeat: {self.heartbeat_interval}min\n"
                f"{'=' * 50}\n"
            )

        except Exception as e:
            logger.error(f"❌ Config error: {e}", exc_info=True)
            raise

    def check_config_changes(self):
        try:
            if self.use_google_sheets:
                self.load_config_from_google_sheets()
            else:
                self.load_config_from_excel()

            new_hash = self.calculate_config_hash()
            if new_hash != self.config_hash:
                logger.info("⚙️  Config changed!")
                self.config_hash = new_hash
                self.load_config()

                if self.notify_changes:
                    self.send_telegram(
                        f"⚙️ <b>הגדרות עודכנו!</b>\n\n"
                        f"📊 מטבעות: {len(self.config['symbols'])}\n"
                        f"🏦 בורסות: {len(self.config['exchanges'])}\n"
                        f"💰 רווח מינימלי: {self.min_profit}%\n"
                        f"✅ הבוט עודכן בהצלחה\n"
                        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                    )
                return True
        except Exception as e:
            logger.error(f"Config check error: {e}")
        return False

    def send_telegram(self, message):
        if not self.telegram_token:
            return False
        try:
            url = (f"https://api.telegram.org/"
                   f"bot{self.telegram_token}/sendMessage")
            resp = requests.post(url, data={
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Telegram error: {e}")
            return False

    def send_startup_message(self):
        mode = "קבוצה 👥" if self.group_mode else "אישי 👤"
        exchanges = ", ".join(self.config['exchanges'].keys()).upper()
        symbols = "\n".join(
            f"   • {s}" for s in self.config['symbols'].keys()
        )
        self.send_telegram(
            f"🚀 <b>ARBICLOD-1 הופעל!</b>\n\n"
            f"✅ הבוט פעיל ועובד\n\n"
            f"⚙️ <b>הגדרות:</b>\n"
            f"   💬 מצב: {mode}\n"
            f"   ⏱️ סריקה כל: {self.scan_interval} שניות\n"
            f"   💰 רווח מינימלי: {self.min_profit}%\n"
            f"   📊 מחזור מינימלי: ${self.min_volume_usd:,.0f}\n"
            f"   💓 דופק: כל {self.heartbeat_interval} דקות\n\n"
            f"🏦 <b>בורסות:</b> {exchanges}\n\n"
            f"💰 <b>מטבעות:</b>\n{symbols}\n\n"
            f"🎯 מחפש הזדמנויות ארביטראז'...\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        logger.info("✅ Startup message sent")

    def send_heartbeat(self, top_opportunities=None):
        if self.heartbeat_interval <= 0:
            return

        now = datetime.now()
        should_send = (
            self.last_heartbeat is None or
            (now - self.last_heartbeat).total_seconds() >=
            self.heartbeat_interval * 60
        )

        if not should_send:
            return

        uptime = now - self.start_time
        total_secs = int(uptime.total_seconds())
        h = total_secs // 3600
        m = (total_secs % 3600) // 60

        exchanges = ", ".join(
            self.exchange_pool.exchanges.keys()
        ).upper() if self.exchange_pool else ""

        top_text = ""
        if top_opportunities:
            top_text = "\n\n🏆 <b>הזדמנויות אחרונות:</b>\n"
            for i, opp in enumerate(top_opportunities[:5], 1):
                top_text += (
                    f"   {i}. <b>{opp['symbol']}</b>\n"
                    f"      📉 {opp['buy_exchange'].upper()} "
                    f"→ 📈 {opp['sell_exchange'].upper()}\n"
                    f"      💵 סכום: ${opp['trade_usd']:,.0f}\n"
                    f"      ✅ רווח נטו: ${opp['net_usd']:,.2f} "
                    f"({opp['net_pct']:.3f}%)\n\n"
                )
        else:
            top_text = "\n\n📊 אין הזדמנויות בסריקה האחרונה\n"

        self.send_telegram(
            f"💓 <b>הבוט חי!</b>\n\n"
            f"✅ פעיל ורץ\n\n"
            f"📊 <b>סטטיסטיקה:</b>\n"
            f"   ⏱️ זמן פעילות: {h}h {m}m\n"
            f"   🔍 סריקות: {self.total_scans:,}\n"
            f"   🎯 הזדמנויות: {self.opportunities_found:,}\n"
            f"   ⚡ סריקה כל: {self.scan_interval}s\n"
            f"   💰 רווח מינימלי: {self.min_profit}%\n\n"
            f"🏦 בורסות: {exchanges}"
            f"{top_text}\n"
            f"🕐 {now.strftime('%d/%m/%Y %H:%M:%S')}"
        )
        self.last_heartbeat = now
        logger.info(f"💓 Heartbeat sent ({h}h {m}m uptime)")

    async def fetch_price(self, exchange_name, symbol):
        # ✅ סמפור - מגביל עומס זיכרון
        async with self.exchange_pool.semaphore:
            exchange = self.exchange_pool.exchanges.get(exchange_name)
            if not exchange:
                return None
            try:
                ticker = await asyncio.wait_for(
                    exchange.fetch_ticker(symbol),
                    timeout=6.0
                )
                if not ticker:
                    return None
                ask = ticker.get('ask')
                bid = ticker.get('bid')
                if not ask or not bid or ask <= 0 or bid <= 0:
                    return None
                return {
                    'exchange': exchange_name,
                    'ask': float(ask),
                    'bid': float(bid),
                    'volume': float(ticker.get('quoteVolume') or 0)
                }
            except Exception:
                return None

    async def check_arbitrage(self, symbol):
        tasks = [
            self.fetch_price(name, symbol)
            for name in self.exchange_pool.exchanges.keys()
        ]
        results = await asyncio.gather(*tasks)
        prices = [
            r for r in results
            if r is not None and r['volume'] >= self.min_volume_usd
        ]

        if len(prices) < 2:
            return None

        best_buy = min(prices, key=lambda x: x['ask'])
        best_sell = max(prices, key=lambda x: x['bid'])

        if best_buy['exchange'] == best_sell['exchange']:
            return None

        buy_price = best_buy['ask']
        sell_price = best_sell['bid']
        gross_pct = ((sell_price - buy_price) / buy_price) * 100

        if gross_pct < self.min_profit * 0.5:
            return None

        coin = symbol.split('/')[0]
        buy_tradeable = best_buy['volume'] * 0.0005
        sell_tradeable = best_sell['volume'] * 0.0005
        trade_usd = max(1000, min(buy_tradeable, sell_tradeable, 50000))

        fees = calculate_real_fees(
            best_buy['exchange'], best_sell['exchange'],
            coin, trade_usd, buy_price
        )

        gross_usd = trade_usd * (gross_pct / 100)
        net_usd = gross_usd - fees['total']
        net_pct = (net_usd / trade_usd) * 100

        if net_pct < self.min_profit:
            return None

        return {
            'symbol': symbol,
            'coin': coin,
            'buy_exchange': best_buy['exchange'],
            'buy_price': buy_price,
            'buy_volume': best_buy['volume'],
            'buy_tradeable_usd': buy_tradeable,
            'sell_exchange': best_sell['exchange'],
            'sell_price': sell_price,
            'sell_volume': best_sell['volume'],
            'sell_tradeable_usd': sell_tradeable,
            'gross_pct': gross_pct,
            'gross_usd': gross_usd,
            'net_pct': net_pct,
            'net_usd': net_usd,
            'trade_usd': trade_usd,
            'fees': fees,
            'all_prices': prices
        }

    def format_opportunity(self, opp):
        fees = opp['fees']
        coin = opp['coin']

        prices_text = ""
        for p in sorted(opp['all_prices'], key=lambda x: x['ask']):
            tag = ""
            if p['exchange'] == opp['buy_exchange']:
                tag = " ← קנייה"
            elif p['exchange'] == opp['sell_exchange']:
                tag = " ← מכירה"
            prices_text += (
                f"   • {p['exchange'].upper()}: "
                f"${p['ask']:,.4f}{tag}\n"
            )

        emoji = "✅" if opp['net_usd'] > 0 else "⚠️"
        buy_coins = opp['buy_tradeable_usd'] / opp['buy_price']
        sell_coins = opp['sell_tradeable_usd'] / opp['sell_price']
        trade_coins = opp['trade_usd'] / opp['buy_price']

        return (
            f"🚨 <b>ארביטראז': {opp['symbol']}</b> 🚨\n\n"
            f"📊 <b>מחירים עכשיו:</b>\n"
            f"{prices_text}\n"
            f"📉 <b>קנייה: {opp['buy_exchange'].upper()}</b> "
            f"@ ${opp['buy_price']:,.4f}\n"
            f"   💵 ניתן לקנות: ${opp['buy_tradeable_usd']:,.0f} "
            f"({buy_coins:,.2f} {coin})\n\n"
            f"📈 <b>מכירה: {opp['sell_exchange'].upper()}</b> "
            f"@ ${opp['sell_price']:,.4f}\n"
            f"   💵 ניתן למכור: ${opp['sell_tradeable_usd']:,.0f} "
            f"({sell_coins:,.2f} {coin})\n\n"
            f"💸 <b>סכום עסקה מומלץ: ${opp['trade_usd']:,.0f}</b>\n"
            f"   🔢 כמות: {trade_coins:,.4f} {coin}\n\n"
            f"📊 <b>חישוב רווח על ${opp['trade_usd']:,.0f}:</b>\n"
            f"   • רווח גולמי: ${opp['gross_usd']:,.2f} "
            f"({opp['gross_pct']:.3f}%)\n"
            f"   • עמלת קנייה ({fees['buy_fee_pct']:.2f}%): "
            f"-${fees['buy_fee']:,.2f}\n"
            f"   • עמלת מכירה ({fees['sell_fee_pct']:.2f}%): "
            f"-${fees['sell_fee']:,.2f}\n"
            f"   • עמלת משיכת {coin}: "
            f"-${fees['withdrawal_fee']:,.2f}\n"
            f"   ─────────────────\n"
            f"   {emoji} <b>רווח נטו: ${opp['net_usd']:,.2f} "
            f"({opp['net_pct']:.3f}%)</b>\n\n"
            f"⚠️ פעל מהר - מחירים משתנים!\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )

    async def monitor_loop(self):
        logger.info("🔍 Monitor loop started")
        config_counter = 0
        last_opportunities = []

        now = datetime.now()
        wait = self.scan_interval - (now.second % self.scan_interval)
        if 0 < wait < self.scan_interval:
            await asyncio.sleep(wait)

        while True:
            try:
                t_start = datetime.now()
                self.total_scans += 1
                ts = t_start.strftime('%H:%M:%S')

                # ✅ רענון pool כל שעה למניעת דליפת זיכרון
                if datetime.now() - self.last_pool_refresh > timedelta(hours=1):
                    logger.info("♻️ Refreshing Exchange Pool...")
                    await self.exchange_pool.close_all()
                    await self.exchange_pool.initialize()
                    self.last_pool_refresh = datetime.now()

                # בדוק שינויי קונפיג כל 5 סריקות
                config_counter += 1
                if config_counter >= 5:
                    self.check_config_changes()
                    config_counter = 0

                # שלח דופק
                self.send_heartbeat(top_opportunities=last_opportunities)

                # סרוק כל המטבעות
                tasks = [
                    self.check_arbitrage(s)
                    for s in self.config['symbols'].keys()
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                opportunities = []
                for r in results:
                    if r is None:
                        continue
                    if isinstance(r, (Exception, BaseException)):
                        continue
                    if not isinstance(r, dict):
                        continue
                    if 'fees' not in r or 'net_pct' not in r:
                        continue
                    opportunities.append(r)

                opportunities.sort(
                    key=lambda x: x['net_pct'], reverse=True
                )
                last_opportunities = opportunities

                duration = (datetime.now() - t_start).total_seconds()

                if opportunities:
                    self.opportunities_found += len(opportunities)
                    logger.info(
                        f"[{ts}] 🎯 #{self.total_scans}: "
                        f"{len(opportunities)} opportunities! "
                        f"({duration:.1f}s)"
                    )
                    for opp in opportunities[:3]:
                        msg = self.format_opportunity(opp)
                        self.send_telegram(msg)
                else:
                    logger.info(
                        f"[{ts}] 🔍 #{self.total_scans}: "
                        f"No opportunities ({duration:.1f}s)"
                    )

                # ✅ ניקוי זיכרון
                gc.collect()

                elapsed = (datetime.now() - t_start).total_seconds()
                sleep_time = max(1, self.scan_interval - elapsed)
                await asyncio.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("⛔ Stopped")
                self.send_telegram("⛔ <b>הבוט נעצר</b>")
                break
            except Exception as e:
                logger.error(f"Loop error: {e}", exc_info=True)
                await asyncio.sleep(10)

    async def run_async(self):
        self.exchange_pool = ExchangePool(
            list(self.config['exchanges'].keys())
        )
        try:
            await self.exchange_pool.initialize()
            await self.monitor_loop()
        finally:
            await self.exchange_pool.close_all()

    def run(self):
        logger.info("🌐 Starting Flask on port 8080...")
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("👋 Goodbye!")


if __name__ == "__main__":
    use_sheets = '--sheets' in sys.argv
    sheet_url = None

    if use_sheets:
        for arg in sys.argv[1:]:
            if 'docs.google.com' in arg:
                sheet_url = arg
                break
            if len(arg) > 20 and '/' not in arg:
                sheet_url = arg
                break

        if not sheet_url:
            print("❌ Usage: python arbiclod1.py --sheets YOUR_SHEET_URL")
            sys.exit(1)

    bot = Arbiclod1(use_google_sheets=use_sheets, sheet_url=sheet_url)
    bot.run()
