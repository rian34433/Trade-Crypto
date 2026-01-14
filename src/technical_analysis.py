import pandas as pd
import pandas_ta as ta

class TechnicalAnalyzer:
    def __init__(self, df):
        self.df = df.copy()

    def add_all_indicators(self):
        """
        Calculates all necessary indicators for the strategy.
        """
        # Trend Indicators
        self.df['EMA_50'] = ta.ema(self.df['close'], length=50)
        self.df['EMA_200'] = ta.ema(self.df['close'], length=200)
        
        adx = ta.adx(self.df['high'], self.df['low'], self.df['close'])
        self.df = pd.concat([self.df, adx], axis=1) # ADX_14, DMP_14, DMN_14

        # Momentum Indicators
        self.df['RSI'] = ta.rsi(self.df['close'], length=14)
        macd = ta.macd(self.df['close'])
        self.df = pd.concat([self.df, macd], axis=1) # MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9

        # Volatility Indicators
        self.df['ATR'] = ta.atr(self.df['high'], self.df['low'], self.df['close'], length=14)
        bb = ta.bbands(self.df['close'], length=20, std=2)
        self.df = pd.concat([self.df, bb], axis=1)

        # Volume Indicators
        self.df['VOL_SMA_20'] = ta.sma(self.df['volume'], length=20)
        self.df['OBV'] = ta.obv(self.df['close'], self.df['volume'])

        # Support & Resistance (Dynamic - Local Min/Max over last 20 periods)
        # Using a rolling window to find local min/max which act as S/R
        self.df['Support_Dynamic'] = self.df['low'].rolling(window=20).min()
        self.df['Resistance_Dynamic'] = self.df['high'].rolling(window=20).max()

        return self.df

    def get_latest_metrics(self):
        """
        Returns the indicators for the latest candle.
        """
        latest = self.df.iloc[-1]
        
        # Check if EMA_200 exists (might be NaN if not enough data)
        trend_direction = "Sideways"
        if pd.notna(latest['EMA_50']) and pd.notna(latest['EMA_200']):
            if latest['EMA_50'] > latest['EMA_200']:
                trend_direction = "Bullish"
            else:
                trend_direction = "Bearish"

        # Determine Trend Strength based on ADX
        # ADX > 25 indicates a strong trend
        adx_col = 'ADX_14'
        trend_strength = "Weak"
        if pd.notna(latest.get(adx_col)):
            if latest[adx_col] > 50:
                trend_strength = "Very Strong"
            elif latest[adx_col] > 25:
                trend_strength = "Strong"
            elif latest[adx_col] > 20:
                trend_strength = "Medium"
        
        return {
            'close': latest['close'],
            'volume': latest['volume'],
            'vol_sma': latest['VOL_SMA_20'],
            'obv': latest['OBV'],
            'rsi': latest['RSI'],
            'macd': latest['MACD_12_26_9'],
            'macd_signal': latest['MACDs_12_26_9'],
            'macd_hist': latest['MACDh_12_26_9'],
            'ema_50': latest['EMA_50'],
            'ema_200': latest['EMA_200'],
            'atr': latest['ATR'],
            'trend_direction': trend_direction,
            'trend_strength': trend_strength,
            'support': latest['Support_Dynamic'],
            'resistance': latest['Resistance_Dynamic']
        }
