import sys
from colorama import init, Fore, Style
from src.market_data import MarketDataProvider
from src.backtester import Backtester
import pandas as pd

# Initialize Colorama
init(autoreset=True)

def print_header():
    print(Fore.MAGENTA + Style.BRIGHT + "="*60)
    print(Fore.MAGENTA + Style.BRIGHT + "       AI TRADING BOT - BACKTEST ENGINE       ")
    print(Fore.MAGENTA + Style.BRIGHT + "="*60)

def main():
    print_header()
    
    # Configuration
    symbol = "XRP/USDT"
    timeframe = "1h"
    limit = 1000 # Number of candles to fetch/simulate
    initial_capital = 10000
    
    print(Fore.YELLOW + f"Settings:")
    print(f"• Symbol: {symbol}")
    print(f"• Timeframe: {timeframe}")
    print(f"• Data Points: {limit}")
    print(f"• Initial Capital: ${initial_capital:,.2f}")
    
    # 1. Fetch Data
    print(Fore.CYAN + "\n[1] Fetching Historical Data...")
    market = MarketDataProvider()
    try:
        df = market.fetch_ohlcv(symbol, timeframe, limit=limit)
        print(Fore.GREEN + f"Successfully loaded {len(df)} candles.")
    except Exception as e:
        print(Fore.RED + f"Error fetching data: {e}")
        return

    # 2. Run Backtest
    print(Fore.CYAN + "\n[2] Running Backtest Simulation...")
    backtester = Backtester(df, initial_capital=initial_capital)
    
    try:
        results = backtester.run()
    except Exception as e:
        print(Fore.RED + f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Report Results
    print(Fore.WHITE + "\n" + "-"*60)
    print(Fore.GREEN + Style.BRIGHT + ">>> BACKTEST RESULTS REPORT <<<")
    
    print(Fore.CYAN + "\n[PERFORMANCE METRICS]")
    print(f"• Final Equity    : ${results['final_equity']:,.2f}")
    print(f"• ROI             : {results['roi']:+.2f}%")
    print(f"• Max Drawdown    : {results['max_drawdown']:.2f}%")
    print(f"• Sharpe Ratio    : {results['sharpe_ratio']:.2f}")
    
    print(Fore.CYAN + "\n[TRADE STATISTICS]")
    print(f"• Total Trades    : {results['total_trades']}")
    print(f"• Win Rate        : {results['win_rate']:.1f}%")
    print(f"• Profit Factor   : {results['profit_factor']:.2f}")
    
    # Benchmark Comparison
    benchmark_final = results['benchmark_curve'].iloc[-1]['equity']
    benchmark_roi = ((benchmark_final - initial_capital) / initial_capital) * 100
    print(Fore.MAGENTA + "\n[BENCHMARK COMPARISON (Buy & Hold)]")
    print(f"• Benchmark ROI   : {benchmark_roi:+.2f}%")
    if results['roi'] > benchmark_roi:
        print(Fore.GREEN + "• Result          : Strategy OUTPERFORMED Benchmark")
    else:
        print(Fore.RED + "• Result          : Strategy UNDERPERFORMED Benchmark")

    # 4. Visualization
    print(Fore.CYAN + "\n[VISUALIZATION]")
    backtester.plot_results(results)
    
    print(Fore.WHITE + "\n" + "="*60)

if __name__ == "__main__":
    main()
