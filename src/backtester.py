import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.technical_analysis import TechnicalAnalyzer
from src.signal_engine import SignalEngine
import matplotlib.dates as mdates

class Backtester:
    def __init__(self, df, initial_capital=10000, fee_pct=0.001, slippage_pct=0.0005):
        self.df = df.copy()
        self.initial_capital = initial_capital
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        
        # State
        self.balance = initial_capital
        self.position = None # None or {'type': 'BUY'/'SELL', 'entry_price': x, 'size': x, 'sl': x, 'tp': x}
        self.trades = []
        self.equity_curve = []
        self.benchmark_curve = []

    def run(self):
        """
        Runs the backtest simulation.
        """
        # 1. Pre-calculate indicators
        analyzer = TechnicalAnalyzer(self.df)
        self.df = analyzer.add_all_indicators()
        
        # Initialize benchmark (Buy & Hold)
        initial_price = self.df.iloc[0]['close']
        benchmark_shares = self.initial_capital / initial_price
        
        print("Running Backtest Simulation...")
        
        # 2. Iterate through candles
        # Start from index 200 to allow for EMA200 calculation
        start_index = 200
        if len(self.df) < start_index + 10:
            raise Exception("Not enough data points for backtesting (min 250)")

        for i in range(start_index, len(self.df)):
            current_candle = self.df.iloc[i]
            prev_candle = self.df.iloc[i-1]
            
            # Record Equity
            current_equity = self.balance
            if self.position:
                if self.position['type'] == 'BUY':
                    # Long: Equity = Cash + Asset Value
                    current_value = self.position['size'] * current_candle['close']
                    current_equity = self.balance + current_value
                elif self.position['type'] == 'SELL':
                    # Short: Equity = Cash + Margin + PnL
                    # Cash (Balance) has Margin deducted.
                    # Equity = Balance + 2*EntryVal - CurrentVal
                    entry_val = self.position['size'] * self.position['entry_price']
                    current_val = self.position['size'] * current_candle['close']
                    current_equity = self.balance + (2 * entry_val) - current_val
            
            self.equity_curve.append({
                'timestamp': current_candle['timestamp'],
                'equity': current_equity
            })
            
            # Record Benchmark
            self.benchmark_curve.append({
                'timestamp': current_candle['timestamp'],
                'equity': benchmark_shares * current_candle['close']
            })

            # Check for Exit (SL/TP)
            if self.position:
                self._check_exit(current_candle)
            
            # Check for Entry (if no position)
            if not self.position:
                self._check_entry(i)
                
        return self._calculate_metrics()

    def _check_exit(self, candle):
        # Logic for BUY positions
        if self.position['type'] == 'BUY':
            sl = self.position['sl']
            tp = self.position['tp']
            entry = self.position['entry_price']
            
            # --- TRAILING STOP LOGIC ---
            # Calculate Risk (R)
            risk = entry - self.position['initial_sl'] 
            if risk > 0:
                # 1. Break Even Trigger (at 2.5R Profit)
                # We give it plenty of room to breathe.
                if candle['high'] >= entry + (2.5 * risk):
                    new_sl = entry + (0.5 * risk) # Secure 0.5R profit
                    if new_sl > sl:
                        self.position['sl'] = new_sl
                        sl = new_sl
            
            # Note: No EMA50 Exit (Whipsaw prone)

            hit_sl = candle['low'] <= sl
            hit_tp = candle['high'] >= tp
            
            exit_price = None
            exit_reason = None
            
            if hit_sl and hit_tp:
                 if abs(candle['open'] - sl) < abs(candle['open'] - tp):
                    exit_price = sl
                    exit_reason = "SL"
                 else:
                    exit_price = tp
                    exit_reason = "TP"
            elif hit_sl:
                exit_price = sl
                exit_reason = "SL"
            elif hit_tp:
                exit_price = tp
                exit_reason = "TP"
                
            if exit_price:
                self._execute_sell(exit_price, candle['timestamp'], exit_reason)

        # Logic for SELL positions
        elif self.position['type'] == 'SELL':
            sl = self.position['sl']
            tp = self.position['tp']
            entry = self.position['entry_price']

            # --- TRAILING STOP LOGIC ---
            # Calculate Risk (R)
            risk = self.position['initial_sl'] - entry
            if risk > 0:
                # 1. Break Even Trigger (at 2.5R Profit)
                if candle['low'] <= entry - (2.5 * risk):
                    new_sl = entry - (0.5 * risk)
                    if new_sl < sl:
                        self.position['sl'] = new_sl
                        sl = new_sl

            # For Short: SL is higher (hit by High), TP is lower (hit by Low)
            hit_sl = candle['high'] >= sl
            hit_tp = candle['low'] <= tp
            
            exit_price = None
            exit_reason = None
            
            if hit_sl and hit_tp:
                if abs(candle['open'] - sl) < abs(candle['open'] - tp):
                    exit_price = sl
                    exit_reason = "SL"
                else:
                    exit_price = tp
                    exit_reason = "TP"
            elif hit_sl:
                exit_price = sl
                exit_reason = "SL"
            elif hit_tp:
                exit_price = tp
                exit_reason = "TP"
                
            if exit_price:
                self._execute_cover(exit_price, candle['timestamp'], exit_reason)

    def _check_entry(self, index):
        # Prepare metrics for SignalEngine
        # We need to construct the dictionary that SignalEngine expects
        row = self.df.iloc[index]
        
        # Reconstruct trend direction logic (simplified from TechnicalAnalyzer.get_latest_metrics)
        trend_direction = "Sideways"
        if row['EMA_50'] > row['EMA_200']: trend_direction = "Bullish"
        else: trend_direction = "Bearish"
            
        trend_strength = "Weak"
        if row['ADX_14'] > 25: trend_strength = "Strong"
        
        metrics = {
            'close': row['close'],
            'rsi': row['RSI'],
            'macd': row['MACD_12_26_9'],
            'macd_signal': row['MACDs_12_26_9'],
            'macd_hist': row['MACDh_12_26_9'],
            'ema_50': row['EMA_50'],
            'ema_200': row['EMA_200'],
            'atr': row['ATR'],
            'trend_direction': trend_direction,
            'trend_strength': trend_strength,
            'support': row['Support_Dynamic'],
            'resistance': row['Resistance_Dynamic'],
            'volume': row['volume'],
            'vol_sma': row['VOL_SMA_20']
        }
        
        engine = SignalEngine(metrics)
        analysis = engine.analyze()
        
        if analysis['signal'] == "BUY":
            trade_setup = engine.calculate_entry_exit("BUY", row['close'], row['ATR'])
            self._position_size_and_execute(trade_setup, row, "BUY")
            
        elif analysis['signal'] == "SELL":
            trade_setup = engine.calculate_entry_exit("SELL", row['close'], row['ATR'])
            self._position_size_and_execute(trade_setup, row, "SELL")

    def _position_size_and_execute(self, trade_setup, row, direction):
        if self.balance <= 0:
            return

        # Risk Management: Risk 2% of capital
        risk_amount = self.balance * 0.02
        price_risk = abs(trade_setup['entry'] - trade_setup['sl'])
        
        if price_risk == 0: return

        position_size = risk_amount / price_risk
        
        # Ensure we can afford it (assuming 1x leverage for simplicity, though shorts usually need margin)
        # For simulation, we assume we can short with cash balance as collateral
        max_cost = self.balance / (1 + self.fee_pct)
        cost = position_size * row['close']
        
        if cost > max_cost:
            position_size = max_cost / row['close']
            
        # Safety check for invalid size
        if position_size <= 0:
            return
        
        if direction == "BUY":
            self._execute_buy(row['close'], position_size, trade_setup['sl'], trade_setup['tp'], row['timestamp'])
        else:
            self._execute_short(row['close'], position_size, trade_setup['sl'], trade_setup['tp'], row['timestamp'])

    def _execute_buy(self, price, size, sl, tp, timestamp):
        # Apply slippage
        price = price * (1 + self.slippage_pct)
        
        # Apply fees
        cost = price * size
        fee = cost * self.fee_pct
        total_cost = cost + fee
        
        if total_cost > self.balance:
            return # Cannot afford
            
        self.balance -= total_cost
        self.position = {
            'type': 'BUY',
            'entry_price': price,
            'size': size,
            'sl': sl,
            'initial_sl': sl, # Added for Trailing Stop
            'tp': tp,
            'entry_time': timestamp
        }
        # print(f"[BUY] Price: {price:.2f}, Size: {size:.4f}, Bal: {self.balance:.2f}")

    def _execute_short(self, price, size, sl, tp, timestamp):
        # Apply slippage (sell lower)
        price = price * (1 - self.slippage_pct)
        
        # Initial Margin Requirement (100% for simplicity)
        # We "sell" so we get cash, but we lock it as collateral + margin
        # Simplified model: We deduct the full value from balance as "locked margin"
        
        cost = price * size
        fee = cost * self.fee_pct
        
        required_margin = cost + fee
        
        if required_margin > self.balance:
            return
            
        self.balance -= required_margin
        self.position = {
            'type': 'SELL',
            'entry_price': price,
            'size': size,
            'sl': sl,
            'initial_sl': sl, # Added for Trailing Stop
            'tp': tp,
            'entry_time': timestamp
        }
        # print(f"[SHORT] Price: {price:.2f}, Size: {size:.4f}, Bal: {self.balance:.2f}")

    def _execute_sell(self, price, timestamp, reason):
        # Apply slippage (sell lower)
        price = price * (1 - self.slippage_pct)
        
        size = self.position['size']
        revenue = price * size
        fee = revenue * self.fee_pct
        net_revenue = revenue - fee
        
        self.balance += net_revenue
        
        # Profit Calculation
        entry_price = self.position['entry_price']
        gross_pnl = (price - entry_price) * size
        total_fees = (entry_price * size * self.fee_pct) + (price * size * self.fee_pct)
        net_pnl = gross_pnl - total_fees
        
        pnl_pct = (net_pnl / (entry_price * size)) * 100
        
        self.trades.append({
            'entry_time': self.position['entry_time'],
            'exit_time': timestamp,
            'entry_price': entry_price,
            'exit_price': price,
            'type': 'BUY',
            'size': size,
            'pnl': net_pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        })
        
        self.position = None
        # print(f"[SELL] Price: {price:.2f}, PnL: {net_pnl:.2f}, Bal: {self.balance:.2f}")

    def _execute_cover(self, price, timestamp, reason):
        # Closing a SHORT position (Buying back)
        # Apply slippage (buy higher)
        price = price * (1 + self.slippage_pct)
        
        size = self.position['size']
        cost = price * size
        fee = cost * self.fee_pct
        
        # Return collateral + PnL
        entry_val = self.position['entry_price'] * size
        
        # Formula: Balance += EntryVal (Margin Release) + (EntryVal - Cost - Fee) (PnL)
        # Simplified: Balance += 2*EntryVal - Cost - Fee
        self.balance += (2 * entry_val) - cost - fee
        
        # Trade Stats
        entry_price = self.position['entry_price']
        gross_pnl = (entry_price - price) * size
        total_fees = (entry_price * size * self.fee_pct) + (price * size * self.fee_pct)
        net_pnl = gross_pnl - total_fees
        
        pnl_pct = (net_pnl / (entry_price * size)) * 100
        
        self.trades.append({
            'entry_time': self.position['entry_time'],
            'exit_time': timestamp,
            'entry_price': entry_price,
            'exit_price': price,
            'type': 'SELL',
            'size': size,
            'pnl': net_pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        })
        
        self.position = None
        # print(f"[COVER] Price: {price:.2f}, PnL: {net_pnl:.2f}, Bal: {self.balance:.2f}")

    def _calculate_metrics(self):
        df_equity = pd.DataFrame(self.equity_curve)
        df_benchmark = pd.DataFrame(self.benchmark_curve)
        
        if df_equity.empty:
            return {}

        final_equity = df_equity.iloc[-1]['equity']
        roi = ((final_equity - self.initial_capital) / self.initial_capital) * 100
        
        # Max Drawdown
        df_equity['peak'] = df_equity['equity'].cummax()
        df_equity['drawdown'] = (df_equity['equity'] - df_equity['peak']) / df_equity['peak']
        max_drawdown = df_equity['drawdown'].min() * 100
        
        # Trade Stats
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]
        
        win_rate = (len(wins) / len(self.trades)) * 100 if self.trades else 0
        
        total_profit = sum(t['pnl'] for t in wins)
        total_loss = abs(sum(t['pnl'] for t in losses))
        profit_factor = total_profit / total_loss if total_loss > 0 else 999
        
        # Sharpe Ratio (Simplified assuming daily returns)
        # Need to resample equity curve to daily if it's hourly
        # For simplicity, calculate based on period returns
        df_equity['returns'] = df_equity['equity'].pct_change()
        sharpe = 0
        if df_equity['returns'].std() > 0:
            sharpe = (df_equity['returns'].mean() / df_equity['returns'].std()) * np.sqrt(252*24) # Assuming hourly data
            
        return {
            'initial_capital': self.initial_capital,
            'final_equity': final_equity,
            'roi': roi,
            'max_drawdown': max_drawdown,
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'trades': self.trades,
            'equity_curve': df_equity,
            'benchmark_curve': df_benchmark
        }

    def plot_results(self, results):
        df_equity = results['equity_curve']
        df_benchmark = results['benchmark_curve']
        trades = results['trades']
        
        plt.style.use('dark_background')
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot 1: Equity Curve vs Benchmark
        ax1.plot(df_equity['timestamp'], df_equity['equity'], label='Strategy Equity', color='cyan', linewidth=1.5)
        ax1.plot(df_benchmark['timestamp'], df_benchmark['equity'], label='Benchmark (Buy & Hold)', color='gray', linestyle='--', alpha=0.6)
        
        # Mark Buy/Sell points on equity curve is hard, let's just show equity
        ax1.set_title(f"Backtest Performance: ROI {results['roi']:.2f}% | DD {results['max_drawdown']:.2f}%")
        ax1.set_ylabel("Portfolio Value ($)")
        ax1.legend()
        ax1.grid(True, alpha=0.2)
        
        # Plot 2: Drawdown
        ax2.fill_between(df_equity['timestamp'], df_equity['drawdown'] * 100, 0, color='red', alpha=0.3)
        ax2.set_title("Drawdown (%)")
        ax2.set_ylabel("Drawdown %")
        ax2.grid(True, alpha=0.2)
        
        plt.tight_layout()
        
        # Format dates
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gcf().autofmt_xdate()
        
        filename = f"backtest_result_{int(pd.Timestamp.now().timestamp())}.png"
        plt.savefig(filename)
        print(f"Chart saved to {filename}")
        # plt.show() # Can't show in headless env usually
