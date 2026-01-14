import ccxt
from colorama import Fore, Style
import time
import csv
import os
from datetime import datetime

class TradeExecutor:
    def __init__(self, market_provider):
        self.provider = market_provider
        self.exchange = market_provider.exchange

    def execute_order(self, symbol, side, amount, price=None, order_type='market'):
        """
        Executes an order on the exchange.
        :param symbol: e.g., 'BTC/USDT'
        :param side: 'buy' or 'sell'
        :param amount: Quantity to trade
        :param price: Price for limit orders (optional)
        :param order_type: 'market' or 'limit'
        """
        if not self.exchange:
            print(Fore.RED + "[!] Exchange not initialized. Cannot trade.")
            return None

        # Check if we are on Fallback (Read-Only)
        if self.provider.using_fallback:
            print(Fore.RED + "[!] Using Public Data Node (Read-Only). Cannot execute trades.")
            print(Fore.RED + "[!] Please check your Tokocrypto API Keys and Internet Connection.")
            return None

        # Check API Keys (Double Check)
        if not self.exchange.apiKey or not self.exchange.secret:
            print(Fore.RED + "[!] API Keys missing. Cannot execute trades.")
            return None

        try:
            print(Fore.YELLOW + f"[*] Submitting {side.upper()} order for {amount} {symbol}...")
            
            if order_type == 'market':
                order = self.exchange.create_market_order(symbol, side, amount)
            elif order_type == 'limit':
                if price is None:
                    raise ValueError("Price is required for limit orders")
                order = self.exchange.create_limit_order(symbol, side, amount, price)
            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            print(Fore.GREEN + f"[✓] Order Executed! ID: {order['id']}")
            return order

        except ccxt.InsufficientFunds as e:
            print(Fore.RED + f"[!] Insufficient Funds: {e}")
        except ccxt.NetworkError as e:
            print(Fore.RED + f"[!] Network Error: {e}")
        except Exception as e:
            print(Fore.RED + f"[!] Order Failed: {e}")
        
        return None

    def get_balance(self, currency):
        """Fetch free balance for a specific currency (e.g., 'USDT')"""
        if self.provider.using_fallback:
            return 0.0

        try:
            balance = self.exchange.fetch_balance()
            return balance.get(currency, {}).get('free', 0.0)
        except Exception as e:
            print(Fore.RED + f"[!] Failed to fetch balance: {e}")
            return 0.0

class PaperTradeExecutor:
    """
    Simulates trade execution for forward testing / paper trading.
    Tracks virtual portfolio and logs orders to CSV.
    """
    def __init__(self, initial_balance_usdt=1000.0):
        self.balance_usdt = initial_balance_usdt
        self.positions = {} # { 'BTC': 0.5, 'ETH': 2.0 }
        self.history_file = 'paper_trade_history.csv'
        self._init_history_file()

    def _init_history_file(self):
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Symbol', 'Type', 'Amount', 'Price', 'Value (USDT)', 'Balance (USDT)'])

    def get_balance(self, currency):
        """Returns virtual balance"""
        if currency == 'USDT':
            return self.balance_usdt
        return self.positions.get(currency, 0.0)

    def execute_order(self, symbol, side, amount, price):
        """
        Simulates order execution.
        :param symbol: e.g. 'BTC/USDT'
        :param side: 'buy' or 'sell'
        :param amount: quantity
        :param price: current market price
        """
        base_currency = symbol.split('/')[0] # BTC
        quote_currency = symbol.split('/')[1] # USDT
        
        value = amount * price
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if side == 'buy':
            # Check if we already have a position in this asset
            current_qty = self.positions.get(base_currency, 0.0)
            
            # Simple Logic: Don't buy if we already have a significant position (e.g. > $1 value)
            # This prevents "spam buying" on every loop iteration for the same signal
            if current_qty * price > 1.0:
                 print(Fore.YELLOW + f"[PAPER TRADE] Position exists ({current_qty:.4f} {base_currency}). Skipping BUY to avoid duplicates.")
                 return None

            if self.balance_usdt >= value:
                self.balance_usdt -= value
                self.positions[base_currency] = current_qty + amount
                print(Fore.GREEN + f"[PAPER TRADE] BUY {amount} {base_currency} @ {price} | Cost: ${value:.2f}")
                self._log_trade(timestamp, symbol, 'BUY', amount, price, value)
                return {'id': f'paper_{int(time.time())}', 'status': 'closed'}
            else:
                print(Fore.RED + f"[PAPER TRADE] Insufficient Virtual USDT. Balance: ${self.balance_usdt:.2f}, Required: ${value:.2f}")
                return None
                
        elif side == 'sell':
            current_qty = self.positions.get(base_currency, 0.0)
            if current_qty >= amount:
                self.positions[base_currency] = current_qty - amount
                self.balance_usdt += value
                print(Fore.GREEN + f"[PAPER TRADE] SELL {amount} {base_currency} @ {price} | Value: ${value:.2f}")
                self._log_trade(timestamp, symbol, 'SELL', amount, price, value)
                return {'id': f'paper_{int(time.time())}', 'status': 'closed'}
            else:
                print(Fore.RED + f"[PAPER TRADE] Insufficient Virtual {base_currency}. Owned: {current_qty}")
                return None

    def _log_trade(self, timestamp, symbol, side, amount, price, value):
        try:
            with open(self.history_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, symbol, side, amount, price, value, self.balance_usdt])
            print(Fore.CYAN + f"[PAPER TRADE] Logged to {self.history_file}")
        except Exception as e:
            print(Fore.RED + f"[!] Error logging paper trade: {e}")

