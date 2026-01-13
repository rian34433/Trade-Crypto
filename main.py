import sys
import time
import argparse
import csv
import os
from datetime import datetime
from colorama import init, Fore, Style
from src.market_data import MarketDataProvider
from src.technical_analysis import TechnicalAnalyzer
from src.signal_engine import SignalEngine
from src.sentiment_analysis import SentimentAnalyzer
from src.execution import TradeExecutor, PaperTradeExecutor
from src.reporting import TradeReporter

# Initialize Colorama
init(autoreset=True)

# Global Paper Trader Instance (to persist state across loop iterations)
paper_trader = None

def print_header():
    print(Fore.CYAN + Style.BRIGHT + "="*60)
    print(Fore.CYAN + Style.BRIGHT + "       AI TRADE SIGNAL SYSTEM - TOKOCRYPTO INTEGRATION       ")
    print(Fore.CYAN + Style.BRIGHT + "="*60)

def format_currency(value):
    if value < 1:
        return f"{value:.8f}"
    return f"{value:.2f}"

def log_signal(symbol, timeframe, signal, price, reason):
    """Logs the signal to a CSV file"""
    file_path = 'trade_history.csv'
    file_exists = os.path.isfile(file_path)
    
    try:
        with open(file_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Timestamp', 'Symbol', 'Timeframe', 'Signal', 'Price', 'Reason'])
            writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), symbol, timeframe, signal, price, reason])
    except Exception as e:
        print(Fore.RED + f"Log Error: {e}")

def run_analysis(symbol, timeframe, market_provider, live_mode=False, trade_amount=10.0):
    print(Fore.WHITE + "\n" + "-"*60)
    print(Fore.YELLOW + f"Analyzing {symbol} on {timeframe} timeframe at {datetime.now().strftime('%H:%M:%S')}...")
    
    # 1. Fetch Data
    df = market_provider.fetch_ohlcv(symbol, timeframe, limit=300)
    
    # Fetch real-time price
    try:
        ticker_info = market_provider.get_ticker_info(symbol)
        current_price = ticker_info['price']
        if current_price <= 0: raise ValueError("Invalid Price")
    except:
        current_price = df.iloc[-1]['close'] if not df.empty else 0
    
    if df.empty:
        print(Fore.RED + "Error: No data received from exchange.")
        return None

    # 2. Analyze Data
    analyzer = TechnicalAnalyzer(df)
    df_analyzed = analyzer.add_all_indicators()
    metrics = analyzer.get_latest_metrics()
    
    # 3. Generate Signal
    engine = SignalEngine(metrics)
    analysis_result = engine.analyze()
    trade_setup = engine.calculate_entry_exit(
        analysis_result['signal'], 
        metrics['close'], 
        metrics['atr']
    )

    # 4. Output Results
    print(Fore.GREEN + Style.BRIGHT + f"\n>>> SIGNAL REPORT FOR [{symbol}] <<<")
    
    # Section: Trend Analysis
    print(Fore.CYAN + "\n[1] MARKET TREND ANALYSIS")
    print(f"• Trend Direction : {metrics['trend_direction']}")
    print(f"• Trend Strength  : {metrics['trend_strength']}")
    
    # Section: Key Levels
    print(Fore.CYAN + "\n[2] KEY LEVELS")
    print(f"• Support (Dynamic)    : {format_currency(metrics['support'])}")
    print(f"• Resistance (Dynamic) : {format_currency(metrics['resistance'])}")
    
    # Section: Signal
    sig_color = Fore.GREEN if analysis_result['signal'] == "BUY" else (Fore.RED if analysis_result['signal'] == "SELL" else Fore.YELLOW)
    print(Fore.CYAN + "\n[3] TRADING SIGNAL")
    print(f"• Recommendation : {sig_color + Style.BRIGHT + analysis_result['signal']}")
    print(f"• Reasoning      : {analysis_result['reason']}")
    
    # Section: Entry Details
    print(Fore.CYAN + "\n[4] ENTRY SETUP (Risk Management)")
    print(f"• Current Price : {format_currency(current_price)}")
    
    if analysis_result['signal'] != "HOLD":
        print(f"• Entry Price : {format_currency(trade_setup['entry'])}")
        print(f"• Stop Loss   : {Fore.RED}{format_currency(trade_setup['sl'])}")
        print(f"• Take Profit : {Fore.GREEN}{format_currency(trade_setup['tp'])}")
        
        # RR Ratio
        risk = abs(trade_setup['entry'] - trade_setup['sl'])
        reward = abs(trade_setup['tp'] - trade_setup['entry'])
        if risk > 0:
            rr_ratio = reward / risk
            print(f"• R:R Ratio   : 1:{rr_ratio:.2f}")

        # --- AUTO TRADING EXECUTION ---
        base_currency = symbol.split('/')[0]
        quote_currency = symbol.split('/')[1]
        
        if live_mode:
            print(Fore.MAGENTA + "\n[!] AUTO TRADING ENGAGED (REAL MONEY)")
            executor = TradeExecutor(market_provider)
            
            if analysis_result['signal'] == "BUY":
                # Check USDT Balance
                balance = executor.get_balance(quote_currency)
                print(f"• {quote_currency} Balance: {format_currency(balance)}")
                
                if balance >= trade_amount:
                    qty = trade_amount / current_price
                    qty = round(qty, 4) 
                    
                    print(Fore.YELLOW + f"[*] Attempting BUY {qty} {base_currency} (~${trade_amount})...")
                    executor.execute_order(symbol, 'buy', qty)
                else:
                    print(Fore.RED + f"[!] Insufficient {quote_currency} Balance for trade.")
            
            elif analysis_result['signal'] == "SELL":
                # Check Coin Balance
                balance = executor.get_balance(base_currency)
                print(f"• {base_currency} Balance: {format_currency(balance)}")
                
                # Sell everything if balance > minimal threshold (e.g. $1 value)
                value_usd = balance * current_price
                if value_usd > 1.0:
                    print(Fore.YELLOW + f"[*] Attempting SELL {balance} {base_currency}...")
                    executor.execute_order(symbol, 'sell', balance)
                else:
                    print(Fore.RED + f"[!] Insufficient {base_currency} Balance to sell.")

        else:
            # --- PAPER TRADING MODE ---
            print(Fore.BLUE + "\n[!] PAPER TRADING SIMULATION (VIRTUAL)")
            global paper_trader
            if paper_trader is None:
                paper_trader = PaperTradeExecutor(initial_balance_usdt=1000.0) # Default $1000 virtual
            
            executor = paper_trader
            
            if analysis_result['signal'] == "BUY":
                 # Check Virtual Balance
                balance = executor.get_balance(quote_currency)
                print(f"• Virtual {quote_currency} Balance: ${format_currency(balance)}")
                
                if balance >= trade_amount:
                    qty = trade_amount / current_price
                    qty = round(qty, 4)
                    print(Fore.YELLOW + f"[*] Simulating BUY {qty} {base_currency} (~${trade_amount})...")
                    executor.execute_order(symbol, 'buy', qty, current_price)
                else:
                    print(Fore.RED + f"[!] Insufficient Virtual {quote_currency} Balance.")

            elif analysis_result['signal'] == "SELL":
                # Check Virtual Coin Balance
                balance = executor.get_balance(base_currency)
                print(f"• Virtual {base_currency} Balance: {format_currency(balance)}")
                
                if balance > 0:
                    print(Fore.YELLOW + f"[*] Simulating SELL {balance} {base_currency}...")
                    executor.execute_order(symbol, 'sell', balance, current_price)
                else:
                    print(Fore.RED + f"[!] No Virtual {base_currency} to sell.")

        # Log valid signal
        log_signal(symbol, timeframe, analysis_result['signal'], current_price, analysis_result['reason'])
    else:
        print(Fore.YELLOW + "• Status: Waiting for clear signal to generate entry parameters.")
    
    # Section: AI Probability
    print(Fore.MAGENTA + "\n[5] AI PROBABILITY ANALYSIS")
    print(f"• Probability Score : {analysis_result['probability']:.1f}%")
    print(f"• Confidence Level  : {analysis_result['confidence']:.1f}%")
    print("• Influencing Factors:")
    for factor in analysis_result['factors']:
        print(f"  - {factor}")

    # Section: AI Market Sentiment
    sent_analyzer = SentimentAnalyzer()
    sentiment_results = sent_analyzer.analyze_market_sentiment(metrics)
    
    print(Fore.CYAN + "\n[6] AI MARKET SENTIMENT (Social/News Proxy)")
    print(f"• Global Sentiment  : {sentiment_results['global_sentiment']['classification']} ({sentiment_results['global_sentiment']['value']}/100)")
    print(f"• Local Sentiment   : {sentiment_results['local_sentiment']['label']} ({sentiment_results['local_sentiment']['score']}/100)")
    print(f"• Technical Score   : {sentiment_results['technical_sentiment']['score']}/100 ({sentiment_results['technical_sentiment']['label']})")
    print(f"• Composite Score   : {sentiment_results['composite_score']}/100 ({sentiment_results['composite_label']})")
    print(f"• Summary           : {sentiment_results['summary']}")
        
    print(Fore.WHITE + "\n" + "="*60)
    return analysis_result

def get_args():
    parser = argparse.ArgumentParser(description="AI Trade Signal Bot")
    parser.add_argument("symbol", nargs="?", help="Trading Pair (e.g. BTC/USDT)")
    parser.add_argument("timeframe", nargs="?", help="Timeframe (e.g. 1h, 4h)")
    parser.add_argument("--loop", action="store_true", help="Run in continuous monitoring mode")
    parser.add_argument("--interval", type=int, default=60, help="Refresh interval in seconds (default: 60)")
    parser.add_argument("--live", action="store_true", help="ENABLE REAL TRADING (Use with caution!)")
    parser.add_argument("--usdt", type=float, default=10.0, help="USDT Amount to Buy per trade (Default: 10 USDT)")
    parser.add_argument("--history", action="store_true", help="Show Paper Trade History Analysis")
    return parser.parse_args()

def main():
    print_header()
    args = get_args()

    if args.history:
        reporter = TradeReporter()
        reporter.generate_report()
        sys.exit(0)
    
    # Interactive Input if args missing
    symbol = args.symbol
    timeframe = args.timeframe
    
    if not symbol:
        print(Fore.YELLOW + "\n[INPUT CONFIGURATION]")
        symbol = input("Enter Coin/Asset (e.g., BTC/USDT): ").strip().upper()
        if not symbol: symbol = "BTC/USDT"
        
    if not timeframe:
        timeframe = input("Enter Timeframe (e.g., 1h, 4h, 1d): ").strip().lower()
        if not timeframe: timeframe = "1h"

    print(Fore.YELLOW + f"Connecting to Tokocrypto via CCXT...")
    market = MarketDataProvider()

    if args.loop:
        print(Fore.MAGENTA + f"\n[!] STARTING AUTOMATIC MONITORING LOOP ({timeframe})...")
        print(Fore.MAGENTA + f"[!] Live Trading: {'ENABLED' if args.live else 'DISABLED'}")
        if args.live:
             print(Fore.MAGENTA + f"[!] Trade Amount: ${args.usdt}")

        try:
            while True:
                run_analysis(symbol, timeframe, market, args.live, args.usdt)
                
                # Countdown
                for i in range(args.interval, 0, -1):
                    sys.stdout.write(f"\rWaiting {i}s for next check...")
                    sys.stdout.flush()
                    time.sleep(1)
                sys.stdout.write("\r" + " "*30 + "\r") # Clear line
                
        except KeyboardInterrupt:
            print(Fore.RED + "\nStopped by user.")
    else:
        run_analysis(symbol, timeframe, market, args.live, args.usdt)

if __name__ == "__main__":
    main()
