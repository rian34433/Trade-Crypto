import numpy as np

class SignalEngine:
    def __init__(self, metrics):
        self.metrics = metrics

    def analyze(self):
        """
        Analyzes metrics to produce a signal, confidence, and probability.
        """
        score = 0
        factors = []
        
        # 1. Trend Analysis (Weight: 40%)
        # Refined: Price vs EMA50 is faster than EMA crossover
        ema_50 = self.metrics.get('ema_50')
        close = self.metrics['close']
        
        if self.metrics['trend_direction'] == 'Bullish':
            score += 15
            factors.append("Bullish Trend (EMA50 > EMA200)")
            # Stronger confirmation if price is above EMA50
            if ema_50 and close > ema_50:
                score += 10
                factors.append("Price above EMA50 (Strong Momentum)")
        elif self.metrics['trend_direction'] == 'Bearish':
            score -= 15
            factors.append("Bearish Trend (EMA50 < EMA200)")
            # Stronger confirmation if price is below EMA50
            if ema_50 and close < ema_50:
                score -= 10
                factors.append("Price below EMA50 (Strong Momentum)")
        
        # Trend Strength Filter (ADX)
        trend_strength = self.metrics.get('trend_strength', 'Weak')
        ema_200 = self.metrics.get('ema_200')
        close = self.metrics['close']
        
        # MARKET REGIME FILTER (Higher Timeframe Bias)
        is_bull_regime = False
        is_bear_regime = False
        if ema_200:
            if close > ema_200: is_bull_regime = True
            else: is_bear_regime = True
        
        # STRATEGY SWITCHING LOGIC
        # If Trend is Weak/Sideways (ADX < 25), HOLD (Cash is a position)
        # If Trend is Strong (ADX > 25), use Trend Following Strategy
        
        if trend_strength == "Weak": # ADX < 25
            # --- NO TRADE ZONE (Sideways Market) ---
            factors.append("Strategy: HOLD (Sideways/Weak Trend)")
            score = 0 # Force Neutral Score
            # We skip all Mean Reversion logic to protect capital in choppy markets
            factors.append("Action: Waiting for clearer trend (ADX > 25)")

        else:
            # --- TREND FOLLOWING STRATEGY ---
            factors.append(f"Strategy: Trend Following ({trend_strength} Trend)")
            
            # EMA200 Filter: Only take trades in direction of major trend
            if is_bull_regime:
                if score > 0: score += 15 # Boost Buy Signal
                elif score < 0: score = 0 # Kill sell signals
                factors.append("Bullish Regime (Price > EMA200)")
            elif is_bear_regime:
                if score < 0: score -= 15 # Boost Sell Signal
                elif score > 0: score = 0 # Kill buy signals
                factors.append("Bearish Regime (Price < EMA200)")

            if trend_strength in ["Strong", "Very Strong"]:
                if score > 0: score += 10
                elif score < 0: score -= 10
                factors.append(f"{trend_strength} Trend Bonus")

            # 2. Momentum Analysis - RSI (Trend Following Mode)
            rsi = self.metrics['rsi']
            
            # RSI Logic Adjusted for Trend Strength
            if is_bull_regime:
                if rsi < 40: # Dip Buy opportunity
                    score += 20
                    factors.append(f"RSI Dip in Bull Trend ({rsi:.2f})")
                elif rsi > 70:
                    if trend_strength == "Very Strong":
                        score += 5 # Super Bullish Momentum
                        factors.append("RSI Overbought (Ignored - Super Trend)")
                    else:
                        score -= 10 # Normal Overbought Caution
                        factors.append(f"RSI Overbought ({rsi:.2f})")
                elif rsi > 50:
                    score += 10 # Bullish Momentum
            
            elif is_bear_regime:
                if rsi > 60: # Rip Sell opportunity
                    score -= 20
                    factors.append(f"RSI Spike in Bear Trend ({rsi:.2f})")
                elif rsi < 30:
                    if trend_strength == "Very Strong":
                        score -= 5 # Super Bearish Momentum
                        factors.append("RSI Oversold (Ignored - Super Trend)")
                    else:
                        score += 10 # Normal Oversold Caution
                        factors.append(f"RSI Oversold ({rsi:.2f})")
                elif rsi < 50:
                    score -= 10 # Bearish Momentum

        # 3. MACD Analysis (Weight: 20%)

        # 3. MACD Analysis (Weight: 20%)
        # Check histogram direction
        if self.metrics['macd_hist'] > 0:
            score += 10
            factors.append("MACD Histogram Positive")
        else:
            score -= 10
            factors.append("MACD Histogram Negative")

        # 4. Price Action vs Support/Resistance (Weight: 20%)
        close = self.metrics['close']
        support = self.metrics['support']
        resistance = self.metrics['resistance']
        
        # If close to support (within 1% range), potential bounce (Bullish)
        if support and close <= support * 1.01:
            score += 15
            factors.append("Price near Support Level")
        # If close to resistance (within 1% range), potential rejection (Bearish)
        if resistance and close >= resistance * 0.99:
            score -= 15
            factors.append("Price near Resistance Level")

        # 5. Volume/Sentiment Analysis (Weight: 20%)
        # Enhanced with Local Sentiment Logic (Volume Anomalies)
        if self.metrics.get('volume') and self.metrics.get('vol_sma'):
            vol_sma = self.metrics['vol_sma']
            if vol_sma > 0:
                vol_ratio = self.metrics['volume'] / vol_sma
                
                # Volume Spike Logic
                if vol_ratio > 2.0:
                    # Extreme Volume -> Strong Confirmation
                    if score > 0:
                        score += 20
                        factors.append(f"Extreme Volume Spike ({vol_ratio:.1f}x) - Bullish")
                    elif score < 0:
                        score -= 20
                        factors.append(f"Extreme Volume Spike ({vol_ratio:.1f}x) - Bearish")
                elif vol_ratio > 1.2:
                    # High Volume -> Moderate Confirmation
                    if score > 0:
                        score += 10
                        factors.append(f"High Volume ({vol_ratio:.1f}x) - Bullish")
                    elif score < 0:
                        score -= 10
                        factors.append(f"High Volume ({vol_ratio:.1f}x) - Bearish")
                elif vol_ratio < 0.6:
                    # Low Volume -> Weakens the signal
                    if score > 0:
                        score -= 5
                        factors.append("Low Volume (Weakens Bullish Signal)")
                    elif score < 0:
                        score += 5
                        factors.append("Low Volume (Weakens Bearish Signal)")

        # Normalize Score to Probability (0-100)
        # Base score is 50 (Neutral). Range approx -75 to +75 added to 50.
        # We clamp it between 0 and 100.
        
        base_probability = 50 + score
        final_probability = max(0, min(100, base_probability))
        
        # Determine Signal
        signal = "HOLD"
        reason = "Market Indecisive"
        
        # Increased threshold for more confidence (75% instead of 70%)
        if final_probability >= 75:
            signal = "BUY"
            reason = "Strong Bullish Confluence"
        elif final_probability <= 25:
            signal = "SELL"
            reason = "Strong Bearish Confluence"
        
        # Calculate Confidence (Distance from 50%)
        confidence = abs(final_probability - 50) * 2 # 50->0%, 100->100%, 0->100%
        
        return {
            'signal': signal,
            'reason': reason,
            'probability': final_probability,
            'confidence': confidence,
            'factors': factors
        }

    def calculate_entry_exit(self, signal, price, atr):
        """
        Calculates SL and TP based on ATR and Trend Strength.
        """
        trend_strength = self.metrics.get('trend_strength', 'Weak')
        
        # Base Multipliers
        sl_mult = 1.8
        tp_mult = 3.0 
        
        # Dynamic Adjustment
        if trend_strength in ["Strong", "Very Strong"]:
            # Let winners run, but not too far
            tp_mult = 4.0
            sl_mult = 2.0 
        elif trend_strength == "Weak":
            # Wider stop for noise (Though we don't trade weak trends now)
            tp_mult = 2.0
            sl_mult = 1.5

        if signal == "BUY":
            sl = price - (sl_mult * atr)
            tp = price + (tp_mult * atr)
            return {'entry': price, 'sl': sl, 'tp': tp}
        elif signal == "SELL":
            sl = price + (sl_mult * atr)
            tp = price - (tp_mult * atr)
            return {'entry': price, 'sl': sl, 'tp': tp}
        else:
            return {'entry': price, 'sl': 0, 'tp': 0}
