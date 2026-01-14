
import csv
import os
from colorama import Fore, Style
from datetime import datetime
from src.market_data import MarketDataProvider

class TradeReporter:
    def __init__(self, history_file='paper_trade_history.csv'):
        self.history_file = history_file

    def generate_report(self):
        if not os.path.exists(self.history_file):
            print(Fore.RED + f"[!] History file '{self.history_file}' not found.")
            return

        print(Fore.CYAN + "\n==========================================================================================")
        print(Fore.CYAN + "                                PAPER TRADE HISTORY ANALYSIS                               ")
        print(Fore.CYAN + "==========================================================================================")
        
        # Header
        print(f"{'TIMESTAMP':<20} | {'SIDE':<4} | {'PRICE':<12} | {'AMOUNT':<10} | {'VALUE':<10} | {'PnL (USDT)':<12} | {'PnL (%)':<8}")
        print("-" * 90)

        rows = []
        try:
            with open(self.history_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as e:
            print(Fore.RED + f"Error reading history: {e}")
            return

        portfolio = {} # { 'BTC/USDT': {'qty': 0.0, 'cost_basis': 0.0} }
        
        total_pnl = 0.0
        win_count = 0
        loss_count = 0
        trade_count = 0

        for row in rows:
            try:
                ts = row['Timestamp']
                symbol = row['Symbol']
                side = row['Type'].upper()
                amount = float(row['Amount'])
                price = float(row['Price'])
                
                # Handle potential float conversion issues or missing keys
                
                if symbol not in portfolio:
                    portfolio[symbol] = {'qty': 0.0, 'cost_basis': 0.0}
                
                pos = portfolio[symbol]
                
                pnl_str = "-"
                pnl_pct_str = "-"
                
                if side == 'BUY':
                    # Weighted Average Cost Basis
                    current_val = pos['qty'] * pos['cost_basis']
                    new_val = amount * price
                    total_qty = pos['qty'] + amount
                    
                    if total_qty > 0:
                        pos['cost_basis'] = (current_val + new_val) / total_qty
                    
                    pos['qty'] = total_qty
                    
                    side_color = Fore.GREEN
                    
                elif side == 'SELL':
                    trade_count += 1
                    avg_cost = pos['cost_basis']
                    
                    # PnL Calculation
                    realized_pnl = (price - avg_cost) * amount
                    pnl_pct = ((price - avg_cost) / avg_cost) * 100 if avg_cost > 0 else 0.0
                    
                    total_pnl += realized_pnl
                    if realized_pnl > 0: win_count += 1
                    else: loss_count += 1
                    
                    pos['qty'] -= amount
                    if pos['qty'] < 0: pos['qty'] = 0
                    
                    # Formatting
                    color = Fore.GREEN if realized_pnl >= 0 else Fore.RED
                    pnl_str = f"{color}{realized_pnl:+,.2f}{Style.RESET_ALL}"
                    pnl_pct_str = f"{color}{pnl_pct:+,.2f}%{Style.RESET_ALL}"
                    side_color = Fore.RED

                print(f"{ts:<20} | {side_color}{side:<4}{Style.RESET_ALL} | {price:<12,.2f} | {amount:<10.5f} | {amount*price:<10,.2f} | {pnl_str:<12} | {pnl_pct_str:<8}")

            except KeyError as e:
                continue # Skip malformed rows
            except ValueError:
                continue

        print("-" * 90)
        
        # --- Floating PnL Calculation ---
        print(Fore.YELLOW + "\n[OPEN POSITIONS & FLOATING PnL]")
        
        market = None
        has_open_positions = False
        
        for symbol, pos in portfolio.items():
            if pos['qty'] > 0.00000001: # Filter tiny dust
                has_open_positions = True
                
                # Lazy Init Market Data
                if market is None:
                    print(Fore.WHITE + "[*] Fetching live market prices...")
                    market = MarketDataProvider()
                
                try:
                    ticker = market.get_ticker_info(symbol)
                    current_price = ticker['price']
                    
                    avg_cost = pos['cost_basis']
                    qty = pos['qty']
                    value_now = qty * current_price
                    cost_basis_total = qty * avg_cost
                    
                    unrealized_pnl = value_now - cost_basis_total
                    unrealized_pnl_pct = ((current_price - avg_cost) / avg_cost) * 100 if avg_cost > 0 else 0
                    
                    color = Fore.GREEN if unrealized_pnl >= 0 else Fore.RED
                    
                    print(f"• {symbol:<10} | Qty: {qty:.5f} | Avg Cost: {avg_cost:,.2f} | Current: {current_price:,.2f}")
                    print(f"  Floating PnL: {color}${unrealized_pnl:+,.2f} ({unrealized_pnl_pct:+,.2f}%){Style.RESET_ALL}")
                    
                except Exception as e:
                    print(Fore.RED + f"• {symbol}: Failed to fetch price ({e})")
        
        if not has_open_positions:
            print("No open positions.")
        
        # Summary
        print(Fore.YELLOW + "\n[SUMMARY STATISTICS (REALIZED)]")
        print(f"• Total Trades (Sell): {trade_count}")
        print(f"• Win/Loss           : {win_count}W - {loss_count}L")
        print(f"• Realized PnL       : {Fore.GREEN if total_pnl >= 0 else Fore.RED}${total_pnl:,.2f}{Style.RESET_ALL}")
        print("==========================================================================================\n")


if __name__ == "__main__":
    reporter = TradeReporter()
    reporter.generate_report()
