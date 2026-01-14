import ccxt
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from colorama import init, Fore, Style

load_dotenv()
init(autoreset=True)

class MarketDataProvider:
    def __init__(self, exchange_id='tokocrypto'):
        self.exchange_id = exchange_id
        self.exchange = None
        self.using_fallback = False
        
        # 1. Try Tokocrypto Direct
        try:
            print(Fore.YELLOW + f"Initializing connection to {exchange_id}...")
            self.exchange = getattr(ccxt, exchange_id)({
                'enableRateLimit': True,
                'apiKey': os.getenv('TOKOCRYPTO_API_KEY'),
                'secret': os.getenv('TOKOCRYPTO_SECRET_KEY'),
                'timeout': 5000,
            })
            # Test connection
            self.exchange.fetch_time()
            print(Fore.GREEN + f"Successfully connected to {exchange_id}.")
        except Exception as e:
            print(Fore.RED + f"[!] Connection Error to {exchange_id}: {str(e)}")
            self._switch_to_fallback()

    def _switch_to_fallback(self):
        """Switches to Binance Public Data Node"""
        if self.using_fallback:
            return

        print(Fore.YELLOW + f"[*] Attempting fallback to Binance Public Data Node (same liquidity source)...")
        try:
            self.exchange = ccxt.binance({
                'enableRateLimit': True,
                'timeout': 10000,
                'options': {'defaultType': 'spot'}, 
                'urls': {
                    'api': {
                        'public': 'https://data-api.binance.vision/api/v3',
                        'fapiPublic': 'https://data-api.binance.vision/api/v3', # Redirect to avoid blocked domains
                        'dapiPublic': 'https://data-api.binance.vision/api/v3',
                    }
                }
            })
            self.exchange.load_markets()
            self.using_fallback = True
            print(Fore.GREEN + f"[*] Successfully connected to Binance Public Data Node (Live Market Data).")
        except Exception as e2:
            print(Fore.RED + f"[!] Public Node connection failed: {e2}")
            self.exchange = None

    def _fetch_coingecko_price(self, symbol):
        """Fetches real price from CoinGecko as fallback for simulation"""
        try:
            # Map common symbols to CoinGecko IDs
            mapper = {
                'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin',
                'SOL': 'solana', 'XRP': 'ripple', 'ADA': 'cardano',
                'DOGE': 'dogecoin', 'AVAX': 'avalanche-2', 'DOT': 'polkadot',
                'MATIC': 'matic-network', 'TRX': 'tron', 'LTC': 'litecoin'
            }
            
            base_currency = symbol.split('/')[0].upper()
            coin_id = mapper.get(base_currency)
            
            if not coin_id:
                return None
                
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if coin_id in data:
                return float(data[coin_id]['usd'])
            return None
        except:
            return None

    def _fetch_tokocrypto_direct(self, endpoint, params):
        """
        Direct REST API call to Tokocrypto (bypassing CCXT if needed)
        Docs: https://www.tokocrypto.com/apidocs/
        """
        base_url = "https://www.tokocrypto.com"
        url = f"{base_url}{endpoint}"
        try:
            # Tokocrypto requires symbols without slash (e.g. BTCUSDT)
            if 'symbol' in params:
                params['symbol'] = params['symbol'].replace('/', '')
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, params=params, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Check for API error structure {code: 0, msg: "...", data: ...}
                if isinstance(data, dict) and 'code' in data and data['code'] == 0:
                    return data['data']
                return data # Some endpoints might return list directly
            return None
        except Exception as e:
            print(Fore.RED + f"[!] Tokocrypto Direct API Error: {e}")
            return None

    def fetch_ohlcv(self, symbol, timeframe, limit=100):
        """
        Fetches OHLCV data from the exchange.
        Priority:
        1. CCXT (Tokocrypto)
        2. Direct Tokocrypto API (/open/v1/market/klines)
        3. Binance Public Data Node (Fallback)
        4. Mock Data
        """
        # 1. Try CCXT first (if connected)
        try:
            if self.exchange and not self.using_fallback:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                cols = ['open', 'high', 'low', 'close', 'volume']
                df[cols] = df[cols].apply(pd.to_numeric)
                return df
        except Exception as e:
            print(Fore.YELLOW + f"[!] CCXT Error: {e}")

        # 2. Try Direct Tokocrypto API
        print(Fore.YELLOW + f"[*] Trying Direct Tokocrypto API...")
        try:
            # Map timeframe to Tokocrypto format if needed (usually same as Binance)
            toko_params = {
                'symbol': symbol,
                'interval': timeframe,
                'limit': limit
            }
            data = self._fetch_tokocrypto_direct('/open/v1/market/klines', toko_params)
            
            if data and isinstance(data, list):
                # Tokocrypto klines format is list of lists, similar to Binance
                # [Open Time, Open, High, Low, Close, Volume, Close Time, ...]
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'q_vol', 'trades', 't_base', 't_quote', 'ignore'])
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                cols = ['open', 'high', 'low', 'close', 'volume']
                df[cols] = df[cols].apply(pd.to_numeric)
                print(Fore.GREEN + f"[*] Success: Retrieved data from Tokocrypto Direct API.")
                return df
        except Exception as e:
            print(Fore.RED + f"[!] Tokocrypto Direct failed: {e}")

        # 3. Fallback to Binance Public Data
        try:
            if not self.using_fallback:
                self._switch_to_fallback()
            
            if self.exchange:
                 ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                 df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                 df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                 cols = ['open', 'high', 'low', 'close', 'volume']
                 df[cols] = df[cols].apply(pd.to_numeric)
                 return df
        except Exception as e:
            print(f"\n[!] All Connections Failed: {str(e)}")
            print(f"[!] Switching to SIMULATION MODE (Mock Data).")
            return self._generate_mock_data(symbol, timeframe, limit)

    def get_ticker_info(self, symbol):
        """
        Fetches detailed ticker information.
        """
        # 1. Try CCXT
        try:
            if self.exchange and not self.using_fallback:
                ticker = self.exchange.fetch_ticker(symbol)
                return self._format_ticker(ticker, symbol)
        except:
            pass

        # 2. Try Direct Tokocrypto API
        try:
            # Endpoint: /open/v1/market/ticker/24hr
            data = self._fetch_tokocrypto_direct('/open/v1/market/ticker/24hr', {'symbol': symbol})
            
            if data:
                if isinstance(data, list):
                    # Filter list for correct symbol
                    clean_symbol = symbol.replace('/', '')
                    ticker_data = next((item for item in data if item['symbol'] == clean_symbol), None)
                else:
                    ticker_data = data
                
                if ticker_data:
                    price = float(ticker_data.get('lastPrice') or 0)
                    if price > 0:
                        return {
                            'symbol': symbol,
                            'price': price,
                            'change_24h': float(ticker_data.get('priceChangePercent') or 0),
                            'high_24h': float(ticker_data.get('highPrice') or 0),
                            'low_24h': float(ticker_data.get('lowPrice') or 0),
                            'volume_24h': float(ticker_data.get('volume') or 0),
                            'is_mock': False
                        }
        except Exception as e:
            pass

        # 3. Fallback / Mock
        try:
             if not self.using_fallback:
                self._switch_to_fallback()
             if self.exchange:
                 ticker = self.exchange.fetch_ticker(symbol)
                 return self._format_ticker(ticker, symbol)
        except:
            pass
            
        return self._generate_mock_ticker(symbol)

    def _format_ticker(self, ticker, symbol):
        return {
            'symbol': symbol,
            'price': float(ticker['last']),
            'change_24h': float(ticker['percentage']) if ticker.get('percentage') is not None else 0.0,
            'high_24h': float(ticker['high']) if ticker.get('high') is not None else 0.0,
            'low_24h': float(ticker['low']) if ticker.get('low') is not None else 0.0,
            'volume_24h': float(ticker['baseVolume']) if ticker.get('baseVolume') is not None else 0.0,
            'is_mock': False
        }

    def _generate_mock_ticker(self, symbol):
        # Mock Data Fallback
        # Try to get real price from CoinGecko first
        real_price = self._fetch_coingecko_price(symbol)
        
        if real_price:
            base_price = real_price
        else:
            base_price = 95000 if 'BTC' in symbol else 2500 if 'ETH' in symbol else 100
        
        change = np.random.uniform(-5, 5)
        price = base_price * (1 + (change/100))
        
        return {
            'symbol': symbol,
            'price': price,
            'change_24h': change,
            'high_24h': price * 1.02,
            'low_24h': price * 0.98,
            'volume_24h': np.random.uniform(100, 1000),
            'is_mock': True
        }


    def _generate_mock_data(self, symbol, timeframe, limit):
        """Generates realistic-looking random market data with trends"""
        # Try to get real price from CoinGecko first for start point
        real_price = self._fetch_coingecko_price(symbol)
        
        if real_price:
            base_price = real_price
        else:
            base_price = 95000 if 'BTC' in symbol else 2500 if 'ETH' in symbol else 100
        
        # Generate random walk with trend regimes
        prices = [base_price]
        trend = 0
        trend_duration = 0
        
        for i in range(limit):
            # Change trend every 50-150 periods
            if trend_duration <= 0:
                trend = np.random.choice([-1, 0, 1], p=[0.4, 0.2, 0.4]) # Bullish, Sideways, Bearish
                trend_duration = np.random.randint(50, 150)
            
            # Trend component
            trend_move = base_price * 0.001 * trend
            
            # Random component
            noise = np.random.normal(0, base_price * 0.003) 
            
            change = trend_move + noise
            new_price = prices[-1] + change
            
            # Ensure price doesn't go negative
            if new_price < base_price * 0.1: new_price = base_price * 0.1
            
            prices.append(new_price)
            trend_duration -= 1
            
        data = []
        now = datetime.now()
        
        # Timeframe delta approximation
        delta = timedelta(hours=1)
        if 'm' in timeframe: delta = timedelta(minutes=int(timeframe.replace('m','')))
        elif 'd' in timeframe: delta = timedelta(days=1)
        elif '4h' in timeframe: delta = timedelta(hours=4)
        
        start_time = now - (delta * limit)
        
        for i in range(limit):
            close = prices[i+1]
            open_p = prices[i]
            high = max(open_p, close) + abs(np.random.normal(0, base_price * 0.002))
            low = min(open_p, close) - abs(np.random.normal(0, base_price * 0.002))
            vol = np.random.randint(100, 1000)
            
            data.append({
                'timestamp': start_time + (delta * i),
                'open': open_p,
                'high': high,
                'low': low,
                'close': close,
                'volume': vol
            })
            
        df = pd.DataFrame(data)
        return df

if __name__ == "__main__":
    # Test
    provider = MarketDataProvider()
    df = provider.fetch_ohlcv('BTC/USDT', '1h', limit=5)
    print(df)
