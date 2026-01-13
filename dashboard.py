import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime
from src.market_data import MarketDataProvider
from src.sentiment_analysis import SentimentAnalyzer
from src.technical_analysis import TechnicalAnalyzer

# Page Configuration
st.set_page_config(
    page_title="AI Trade Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
    }
    .stMetric {
        background-color: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Settings
st.sidebar.title("⚙️ Settings")

symbol = st.sidebar.selectbox(
    "Select Coin",
    ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "DOGE/USDT", "XRP/USDT"],
    index=0
)

timeframe = st.sidebar.selectbox(
    "Chart Timeframe",
    ["15m", "1h", "4h", "1d"],
    index=1
)

st.sidebar.divider()

show_in_idr = st.sidebar.toggle("Show in IDR (Rp)", value=False)
idr_rate = 16200 # Fixed approximate rate or fetch dynamic if needed

auto_refresh = st.sidebar.checkbox("Auto Refresh (Every 60s)", value=False)

st.sidebar.markdown("---")
st.sidebar.caption("Powered by CCXT & Tokocrypto")

# Initialize Data Provider
@st.cache_resource
def get_provider():
    return MarketDataProvider()

provider = get_provider()

# Main Logic
def main():
    # Container for dynamic content
    main_container = st.empty()
    
    # Refresh Loop
    while True:
        with main_container.container():
            # 1. Fetch Data
            with st.spinner('Fetching market data...'):
                ticker = provider.get_ticker_info(symbol)
                history_df = provider.fetch_ohlcv(symbol, timeframe, limit=100)
            
            # 2. Process Data
            current_price = ticker['price']
            high_24h = ticker['high_24h']
            low_24h = ticker['low_24h']
            volume = ticker['volume_24h']
            change_24h = ticker['change_24h']
            
            currency_symbol = "$"
            
            if show_in_idr:
                current_price *= idr_rate
                high_24h *= idr_rate
                low_24h *= idr_rate
                # Volume usually in Base asset (Coin), so no conversion needed, 
                # but if Quote volume (USDT), need conversion. 
                # Assuming Base Volume from market_data.py
                currency_symbol = "Rp "
            
            # 3. Header & Metrics
            st.title(f"{symbol} Live Market")
            
            if ticker.get('is_mock'):
                st.warning("⚠️ Connection to Exchange Failed. Showing Simulation Data.")
            else:
                st.success("🟢 Live Connection Active")
            
            # Metric Columns
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                fmt = f"{currency_symbol}{current_price:,.0f}" if show_in_idr else f"{currency_symbol}{current_price:,.2f}"
                st.metric("Current Price", fmt, f"{change_24h:+.2f}%")
                
            with col2:
                fmt = f"{currency_symbol}{high_24h:,.0f}" if show_in_idr else f"{currency_symbol}{high_24h:,.2f}"
                st.metric("24h High", fmt)
                
            with col3:
                fmt = f"{currency_symbol}{low_24h:,.0f}" if show_in_idr else f"{currency_symbol}{low_24h:,.2f}"
                st.metric("24h Low", fmt)
                
            with col4:
                st.metric("24h Volume", f"{volume:,.2f}")

            # 4. Chart Section
            st.subheader(f"Price Chart ({timeframe})")
            
            if not history_df.empty:
                # Candle Chart
                fig = go.Figure(data=[go.Candlestick(
                    x=history_df['timestamp'],
                    open=history_df['open'] * (idr_rate if show_in_idr else 1),
                    high=history_df['high'] * (idr_rate if show_in_idr else 1),
                    low=history_df['low'] * (idr_rate if show_in_idr else 1),
                    close=history_df['close'] * (idr_rate if show_in_idr else 1),
                    name=symbol
                )])
                
                fig.update_layout(
                    height=500,
                    margin=dict(l=0, r=0, t=0, b=0),
                    xaxis_rangeslider_visible=False,
                    template="plotly_dark",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("No historical data available.")
                
            # 5. AI Market Sentiment
            st.markdown("---")
            st.subheader("🤖 AI Market Sentiment (Social & Technical)")
            
            # Analyze
            analyzer = TechnicalAnalyzer(history_df)
            analyzer.add_all_indicators()
            metrics = analyzer.get_latest_metrics()
            
            sent_analyzer = SentimentAnalyzer()
            sentiment_results = sent_analyzer.analyze_market_sentiment(metrics)
            
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.metric("Global Sentiment (F&G)", 
                          f"{sentiment_results['global_sentiment']['value']}/100", 
                          sentiment_results['global_sentiment']['classification'])
            with sc2:
                 st.metric("Local Sentiment (Vol)", 
                           f"{sentiment_results['local_sentiment']['score']}/100", 
                           sentiment_results['local_sentiment']['label'])
            with sc3:
                 st.metric("Technical Score", 
                           f"{sentiment_results['technical_sentiment']['score']}/100", 
                           sentiment_results['technical_sentiment']['label'])
            with sc4:
                st.metric("Composite AI Score", 
                          f"{sentiment_results['composite_score']}/100", 
                          sentiment_results['composite_label'])
            
            st.info(f"💡 **AI Summary:** {sentiment_results['summary']}")

            # Timestamp
            st.caption(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Loop Control
        if not auto_refresh:
            if st.button("🔄 Refresh Data"):
                st.rerun()
            break
        else:
            time.sleep(60)
            # st.rerun() will be triggered by loop iteration in some streamlit versions, 
            # but explicit rerun is safer for refreshing
            st.rerun()

if __name__ == "__main__":
    main()
