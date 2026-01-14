import requests
import pandas as pd
from colorama import Fore, Style
from datetime import datetime

class SentimentAnalyzer:
    def __init__(self):
        self.fng_api_url = "https://api.alternative.me/fng/"
        
    def get_fear_and_greed_index(self):
        """
        Fetches the Crypto Fear & Greed Index from alternative.me
        Returns a dictionary with value and classification.
        """
        try:
            # Short timeout to avoid blocking execution for too long
            response = requests.get(self.fng_api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    item = data['data'][0]
                    return {
                        'value': int(item['value']),
                        'classification': item['value_classification'],
                        'timestamp': int(item['timestamp'])
                    }
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.RequestException):
            # Suppress noisy stack trace for common connection errors (DNS block/Timeout)
            print(Fore.YELLOW + f"[!] Warning: Cannot reach Sentiment API (DNS Block/Offline). Using Neutral default.")
        except Exception as e:
            # Catch other unexpected errors
            print(Fore.YELLOW + f"[!] Sentiment API Error: {str(e)[:50]}... Using default.")
            
        # Fallback
        return {
            'value': 50,
            'classification': "Neutral (Fallback)",
            'timestamp': int(datetime.now().timestamp())
        }

    def analyze_market_sentiment(self, technical_metrics=None):
        """
        Combines Fear & Greed Index with Technical Metrics to give a 
        comprehensive AI Sentiment Score.
        """
        # 1. Global Market Sentiment (Social/News Proxy)
        fng = self.get_fear_and_greed_index()
        
        # 2. Technical Sentiment (Asset Specific)
        tech_score = 50 # Default Neutral
        tech_sentiment = "Neutral"
        
        # 3. Local Sentiment (Volume/Volatility Specific)
        local_score = 50
        local_sentiment = "Normal Activity"
        
        if technical_metrics:
            # --- Technical Trend ---
            direction = technical_metrics.get('trend_direction', 'Sideways')
            strength = technical_metrics.get('trend_strength', 'Weak')
            tech_sentiment = f"{strength} {direction}"
            
            base_score = 50
            if direction == "Bullish":
                if strength == "Very Strong": base_score = 90
                elif strength == "Strong": base_score = 80
                elif strength == "Medium": base_score = 70
                else: base_score = 60
            elif direction == "Bearish":
                if strength == "Very Strong": base_score = 10
                elif strength == "Strong": base_score = 20
                elif strength == "Medium": base_score = 30
                else: base_score = 40
            
            tech_score = base_score
            
            # Adjust based on RSI
            rsi = technical_metrics.get('rsi', 50)
            if rsi > 70: tech_score -= 10 # Overbought -> Less Bullish
            elif rsi < 30: tech_score += 10 # Oversold -> Less Bearish/Bounce likely
            
            # --- Local Volume Sentiment ---
            volume = technical_metrics.get('volume', 0)
            vol_sma = technical_metrics.get('vol_sma', 0)
            
            if vol_sma > 0:
                vol_ratio = volume / vol_sma
                if vol_ratio > 2.5:
                    local_score = 80 # Very High Interest
                    local_sentiment = "Very High Interest (Volume Spike)"
                elif vol_ratio > 1.5:
                    local_score = 65 # High Interest
                    local_sentiment = "High Interest"
                elif vol_ratio < 0.5:
                    local_score = 40 # Low Interest
                    local_sentiment = "Low Interest"
                
                # If price is dropping on high volume -> Bearish Sentiment
                if direction == "Bearish" and vol_ratio > 1.5:
                    local_score = 20 # Panic Selling?
                    local_sentiment = "High Selling Pressure"
                # If price is rising on high volume -> Bullish Sentiment
                elif direction == "Bullish" and vol_ratio > 1.5:
                    local_score = 80 # Strong Buying
                    local_sentiment = "Strong Buying Pressure"

        # 4. Composite AI Score
        # Weighting: 20% Global (F&G), 60% Technical, 20% Local (Volume)
        composite_score = (fng['value'] * 0.2) + (tech_score * 0.6) + (local_score * 0.2)
        
        sentiment_label = "NEUTRAL"
        if composite_score >= 75: sentiment_label = "EXTREME BULLISH"
        elif composite_score >= 60: sentiment_label = "BULLISH"
        elif composite_score <= 25: sentiment_label = "EXTREME BEARISH"
        elif composite_score <= 40: sentiment_label = "BEARISH"
        
        return {
            'global_sentiment': {
                'value': fng['value'],
                'classification': f"{fng['classification']} (Market-Wide)",
                'timestamp': fng['timestamp']
            },
            'technical_sentiment': {
                'score': tech_score,
                'label': tech_sentiment
            },
            'local_sentiment': {
                'score': local_score,
                'label': local_sentiment
            },
            'composite_score': round(composite_score, 1),
            'composite_label': sentiment_label,
            'summary': f"Global: {fng['classification']}, Local: {local_sentiment}, Tech: {tech_sentiment}."
        }

if __name__ == "__main__":
    analyzer = SentimentAnalyzer()
    print(analyzer.analyze_market_sentiment())
