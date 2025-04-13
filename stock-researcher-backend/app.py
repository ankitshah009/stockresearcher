from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv
import logging
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from tiingo import TiingoClient
import time
import threading
from pathlib import Path
import sqlite3
from bs4 import BeautifulSoup
import requests_cache

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
BASE_URL = 'https://www.alphavantage.co/query'

# Initialize Tiingo Client
TIINGO_API_KEY = os.environ.get('TIINGO_API_KEY', '0be74c81ad01d25c6b2fa702a38cab425fb0246c')
tiingo_config = {
    'api_key': TIINGO_API_KEY,
    'session': requests.Session()
}
tiingo_client = TiingoClient(tiingo_config)

# Initialize Polygon API
POLYGON_API_KEY = os.environ.get('POLYGON_API_KEY', '4mopO1RMkcELYJcjLzLDupoPJh_UAGj9')
POLYGON_BASE_URL = 'https://api.polygon.io'

# In-memory cache to avoid hitting API limits frequently
cache = {}

# Technical indicator explanations
INDICATOR_EXPLANATIONS = {
    "sma20": "20-Day Simple Moving Average: Short-term price trend indicator. Price above SMA20 suggests short-term bullish momentum.",
    "sma50": "50-Day Simple Moving Average: Medium-term price trend indicator, often watched by institutional investors.",
    "sma200": "200-Day Simple Moving Average: Long-term price trend indicator. Price above SMA200 suggests bull market.",
    "rsi": "Relative Strength Index: Momentum oscillator measuring speed and change of price movements. Values over 70 indicate overbought conditions; below 30 indicate oversold.",
    "atr": "Average True Range: Volatility indicator showing the average range between high and low prices. Higher values indicate higher volatility.",
    "volume_ratio": "Volume vs 20-Day Average: Compares current trading volume to its 20-day average. Values over 1.0 show above-average volume, suggesting strong conviction behind price moves.",
    "support": "Price levels where downward trends often pause or reverse due to concentrated buying interest.",
    "resistance": "Price levels where upward trends often pause or reverse due to concentrated selling pressure.",
    "relative_strength": "Compares the stock's performance to a benchmark (SPY/S&P 500). Positive values indicate outperformance."
}

# Enhanced in-memory cache with timestamps
timed_cache = {}

# Add a function to convert NumPy types to Python native types
def convert_to_json_serializable(obj):
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    elif isinstance(obj, (np.bool_)):
        return bool(obj)
    else:
        return obj

# Create a custom JSONEncoder to handle NumPy types
class NumpyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return convert_to_json_serializable(obj)
        except:
            return super(NumpyJSONEncoder, self).default(obj)

# Configure Flask to use the custom JSONEncoder
app.json_encoder = NumpyJSONEncoder

# Constants
CACHE_DURATION = 3600  # 1 hour in seconds

# Initialize SQLite database for persistent caching
DB_PATH = 'stock_data.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Create tables if they don't exist
    c.execute('''
    CREATE TABLE IF NOT EXISTS stock_cache (
        symbol TEXT PRIMARY KEY,
        data TEXT,
        timestamp INTEGER
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS technical_indicators (
        symbol TEXT,
        indicator TEXT,
        data TEXT,
        timestamp INTEGER,
        PRIMARY KEY (symbol, indicator)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS news_cache (
        symbol TEXT PRIMARY KEY,
        data TEXT,
        timestamp INTEGER
    )
    ''')
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

# Technical indicator explanations
TECHNICAL_INDICATORS = {
    'SMA': 'Simple Moving Average - Average price over a specified period.',
    'EMA': 'Exponential Moving Average - Weighted average giving more importance to recent prices.',
    'RSI': 'Relative Strength Index - Momentum oscillator measuring speed and change of price movements.',
    'MACD': 'Moving Average Convergence Divergence - Trend-following momentum indicator.',
    'BB': 'Bollinger Bands - Volatility bands placed above and below a moving average.',
    'STOCH': 'Stochastic Oscillator - Momentum indicator comparing closing price to price range.',
    'ADX': 'Average Directional Index - Measures trend strength without regard to direction.',
    'OBV': 'On-Balance Volume - Uses volume flow to predict changes in stock price.'
}

# Cache functions using SQLite
def get_from_cache(symbol, table='stock_cache'):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"SELECT data, timestamp FROM {table} WHERE symbol = ?", (symbol,))
    result = c.fetchone()
    conn.close()
    
    if result:
        data, timestamp = result
        current_time = int(time.time())
        if current_time - timestamp < CACHE_DURATION:
            logging.info(f"Retrieved {table} data for {symbol} from cache")
            return json.loads(data)
    return None

def save_to_cache(symbol, data, table='stock_cache'):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = int(time.time())
    c.execute(f"INSERT OR REPLACE INTO {table} (symbol, data, timestamp) VALUES (?, ?, ?)",
              (symbol, json.dumps(data), timestamp))
    conn.commit()
    conn.close()
    logging.info(f"Saved {table} data for {symbol} to cache")

def get_technical_indicator(symbol, indicator):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT data, timestamp FROM technical_indicators WHERE symbol = ? AND indicator = ?", 
              (symbol, indicator))
    result = c.fetchone()
    conn.close()
    
    if result:
        data, timestamp = result
        current_time = int(time.time())
        if current_time - timestamp < CACHE_DURATION:
            logging.info(f"Retrieved {indicator} data for {symbol} from cache")
            return json.loads(data)
    
    # Get fresh data from Alpha Vantage
    function = f"{indicator}"
    if indicator == 'SMA' or indicator == 'EMA':
        url = f"https://www.alphavantage.co/query?function={function}&symbol={symbol}&interval=daily&time_period=14&series_type=close&apikey={API_KEY}"
    elif indicator == 'RSI':
        url = f"https://www.alphavantage.co/query?function=RSI&symbol={symbol}&interval=daily&time_period=14&series_type=close&apikey={API_KEY}"
    elif indicator == 'MACD':
        url = f"https://www.alphavantage.co/query?function=MACD&symbol={symbol}&interval=daily&series_type=close&apikey={API_KEY}"
    elif indicator == 'BB':
        url = f"https://www.alphavantage.co/query?function=BBANDS&symbol={symbol}&interval=daily&time_period=20&series_type=close&apikey={API_KEY}"
    else:
        url = f"https://www.alphavantage.co/query?function={function}&symbol={symbol}&interval=daily&apikey={API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        # Check for error message
        if "Error Message" in data:
            logging.error(f"Alpha Vantage API error: {data['Error Message']}")
            return None
        
        # Check for API limit
        if "Note" in data and "API call frequency" in data["Note"]:
            logging.warning(f"Alpha Vantage API limit reached: {data['Note']}")
            return None
            
        # Save to cache
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        timestamp = int(time.time())
        c.execute("INSERT OR REPLACE INTO technical_indicators (symbol, indicator, data, timestamp) VALUES (?, ?, ?, ?)",
                  (symbol, indicator, json.dumps(data), timestamp))
        conn.commit()
        conn.close()
        
        return data
    except Exception as e:
        logging.error(f"Error fetching {indicator} data for {symbol}: {e}")
        return None

def get_stock_news(symbol):
    # Check cache first
    cached_news = get_from_cache(symbol, table='news_cache')
    if cached_news:
        return cached_news
    
    # If not in cache, fetch from Alpha Vantage
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={symbol}&apikey={API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        # Check for error message
        if "Error Message" in data:
            logging.error(f"Alpha Vantage API error: {data['Error Message']}")
            return None
        
        # Check for API limit
        if "Note" in data and "API call frequency" in data["Note"]:
            logging.warning(f"Alpha Vantage API limit reached: {data['Note']}")
            return None
            
        # Process news data
        news_items = []
        if 'feed' in data:
            for item in data['feed'][:10]:  # Limit to 10 news items
                news_items.append({
                    'title': item.get('title', ''),
                    'summary': item.get('summary', ''),
                    'url': item.get('url', ''),
                    'source': item.get('source', ''),
                    'time_published': item.get('time_published', ''),
                    'sentiment': item.get('overall_sentiment_score', 0)
                })
        
        result = {'news': news_items}
        
        # Save to cache
        save_to_cache(symbol, result, table='news_cache')
        
        return result
    except Exception as e:
        logging.error(f"Error fetching news for {symbol}: {e}")
        return None

def scrape_company_info(symbol):
    """Scrape additional info from various sources including Yahoo Finance and MarketWatch"""
    try:
        # Initialize data dictionary
        data = {
            "description": "",
            "sector": "",
            "industry": "",
            "marketCap": "N/A",
            "peRatio": "N/A", 
            "high52Week": "N/A",
            "low52Week": "N/A"
        }
        
        # Try Yahoo Finance first
        yahoo_data = scrape_from_yahoo(symbol)
        for key, value in yahoo_data.items():
            if value and value != "N/A":
                data[key] = value
                
        # If we're still missing data, try MarketWatch as a backup
        if data["marketCap"] == "N/A" or data["peRatio"] == "N/A" or data["high52Week"] == "N/A":
            market_watch_data = scrape_from_marketwatch(symbol)
            for key, value in market_watch_data.items():
                if (key in data and data[key] == "N/A") and value and value != "N/A":
                    data[key] = value
        
        logging.info(f"Scraped data for {symbol}: Market Cap: {data['marketCap']}, P/E: {data['peRatio']}, 52W High: {data['high52Week']}, 52W Low: {data['low52Week']}")
        return data
    except Exception as e:
        logging.error(f"Error scraping company info for {symbol}: {e}")
        return {}

def scrape_from_yahoo(symbol):
    """Scrape data from Yahoo Finance"""
    try:
        data = {
            "description": "",
            "sector": "",
            "industry": "",
            "marketCap": "N/A",
            "peRatio": "N/A", 
            "high52Week": "N/A",
            "low52Week": "N/A"
        }
        
        # Yahoo Finance URL
        yahoo_url = f"https://finance.yahoo.com/quote/{symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(yahoo_url, headers=headers, timeout=10)
        if response.status_code != 200:
            logging.warning(f"Failed to fetch Yahoo Finance data for {symbol}: Status code {response.status_code}")
            return data
        
        soup = BeautifulSoup(response.text, 'lxml')
        logging.info(f"Successfully fetched Yahoo Finance page for {symbol}")
        
        # Try to extract market data using multiple approaches
        try:
            # First approach: Look for market cap in the summary table
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        label = cells[0].text.strip()
                        value = cells[1].text.strip()
                        
                        if "Market Cap" in label:
                            logging.info(f"Found Market Cap for {symbol} (Yahoo): {value}")
                            data["marketCap"] = value
                        elif "PE Ratio" in label or "P/E" in label:
                            logging.info(f"Found P/E Ratio for {symbol} (Yahoo): {value}")
                            data["peRatio"] = value
                        elif "52 Week Range" in label or "52-Week Range" in label:
                            logging.info(f"Found 52 Week Range for {symbol} (Yahoo): {value}")
                            # Format might be "low - high"
                            if "-" in value:
                                parts = value.split("-")
                                if len(parts) == 2:
                                    data["low52Week"] = parts[0].strip()
                                    data["high52Week"] = parts[1].strip()
                        elif "52-Week High" in label or "52 Week High" in label:
                            logging.info(f"Found 52 Week High for {symbol} (Yahoo): {value}")
                            data["high52Week"] = value
                        elif "52-Week Low" in label or "52 Week Low" in label:
                            logging.info(f"Found 52 Week Low for {symbol} (Yahoo): {value}")
                            data["low52Week"] = value
            
            # Second approach: Look for specific data-test attributes
            for test_id in ["MARKET_CAP-value", "PE_RATIO-value", "FIFTY_TWO_WK_RANGE-value"]:
                element = soup.find('td', {'data-test': test_id})
                if element:
                    value = element.text.strip()
                    logging.info(f"Found {test_id} for {symbol} (Yahoo): {value}")
                    
                    if "MARKET_CAP" in test_id:
                        data["marketCap"] = value
                    elif "PE_RATIO" in test_id:
                        data["peRatio"] = value
                    elif "FIFTY_TWO_WK_RANGE" in test_id and "-" in value:
                        parts = value.split("-")
                        if len(parts) == 2:
                            data["low52Week"] = parts[0].strip()
                            data["high52Week"] = parts[1].strip()
        except Exception as e:
            logging.warning(f"Error extracting market data for {symbol} from Yahoo Finance: {e}")
        
        # Try to get description from company profile
        try:
            description_section = soup.find('section', {'data-test': 'company-profile'})
            if description_section:
                description_p = description_section.find('p')
                if description_p:
                    data["description"] = description_p.text.strip()
                    
            # Get sector and industry if available
            sector_span = soup.find('span', string='Sector')
            if sector_span and sector_span.find_next('span'):
                data["sector"] = sector_span.find_next('span').text.strip()
                
            industry_span = soup.find('span', string='Industry')
            if industry_span and industry_span.find_next('span'):
                data["industry"] = industry_span.find_next('span').text.strip()
        except Exception as e:
            logging.warning(f"Error extracting company info for {symbol} from Yahoo Finance: {e}")
            
        # Format the market cap
        if data["marketCap"] != "N/A" and data["marketCap"]:
            # Yahoo formats like "2.68T" or "965.16B"
            try:
                if data["marketCap"][-1] == "T":
                    value = float(data["marketCap"][:-1]) * 1000
                    data["marketCap"] = f"{value:.2f}B"
                elif data["marketCap"][-1] == "B":
                    data["marketCap"] = data["marketCap"][:-1] + "B"
                elif data["marketCap"][-1] == "M":
                    data["marketCap"] = data["marketCap"][:-1] + "M"
            except Exception as e:
                logging.warning(f"Error formatting market cap for {symbol} from Yahoo Finance: {e}")
                
        return data
    except Exception as e:
        logging.error(f"Error in Yahoo Finance scraping for {symbol}: {e}")
        return {}

def scrape_from_marketwatch(symbol):
    """Scrape data from MarketWatch as a backup source"""
    try:
        data = {
            "description": "",
            "sector": "",
            "industry": "",
            "marketCap": "N/A",
            "peRatio": "N/A", 
            "high52Week": "N/A",
            "low52Week": "N/A"
        }
        
        # MarketWatch URL
        mw_url = f"https://www.marketwatch.com/investing/stock/{symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(mw_url, headers=headers, timeout=10)
        if response.status_code != 200:
            logging.warning(f"Failed to fetch MarketWatch data for {symbol}: Status code {response.status_code}")
            return data
        
        soup = BeautifulSoup(response.text, 'lxml')
        logging.info(f"Successfully fetched MarketWatch page for {symbol}")
        
        # Extract key stats from MarketWatch
        try:
            # Find all the key data points
            items = soup.find_all('li', class_='kv__item')
            for item in items:
                label_el = item.find('small', class_='label')
                value_el = item.find('span', class_='primary')
                
                if label_el and value_el:
                    label = label_el.text.strip()
                    value = value_el.text.strip()
                    
                    if "Market Cap" in label:
                        logging.info(f"Found Market Cap for {symbol} (MarketWatch): {value}")
                        data["marketCap"] = value
                    elif "P/E Ratio" in label:
                        logging.info(f"Found P/E Ratio for {symbol} (MarketWatch): {value}")
                        data["peRatio"] = value
                    elif "52 Week High" in label:
                        logging.info(f"Found 52 Week High for {symbol} (MarketWatch): {value}")
                        data["high52Week"] = value
                    elif "52 Week Low" in label:
                        logging.info(f"Found 52 Week Low for {symbol} (MarketWatch): {value}")
                        data["low52Week"] = value
        except Exception as e:
            logging.warning(f"Error extracting market data from MarketWatch for {symbol}: {e}")
            
        # Format the market cap
        if data["marketCap"] != "N/A" and data["marketCap"]:
            try:
                # MarketWatch might format as "$2.68T" or "$965.16B"
                mc = data["marketCap"].replace("$", "")
                if "T" in mc:
                    value = float(mc.replace("T", "")) * 1000
                    data["marketCap"] = f"{value:.2f}B"
                elif "B" in mc:
                    data["marketCap"] = mc.replace("B", "") + "B"
                elif "M" in mc:
                    data["marketCap"] = mc.replace("M", "") + "M"
            except Exception as e:
                logging.warning(f"Error formatting market cap from MarketWatch for {symbol}: {e}")
                
        return data
    except Exception as e:
        logging.error(f"Error in MarketWatch scraping for {symbol}: {e}")
        return {}

def get_stock_data_from_polygon(symbol):
    """Fetch stock data from Polygon.io API as fallback when Alpha Vantage and Tiingo fail"""
    try:
        logging.info(f"Fetching data for {symbol} from Polygon.io API (second fallback)")
        
        # Get ticker details
        ticker_url = f"{POLYGON_BASE_URL}/v3/reference/tickers/{symbol}?apiKey={POLYGON_API_KEY}"
        ticker_response = requests.get(ticker_url)
        ticker_data = ticker_response.json()
        
        if "error" in ticker_data or ticker_data.get("status") == "ERROR":
            logging.error(f"Polygon API error for ticker {symbol}: {ticker_data.get('error')}")
            return None, f"No data found for symbol: {symbol}"
            
        ticker_result = ticker_data.get("results", {})
        
        # Get latest price data using Previous Close endpoint
        price_url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{symbol}/prev?apiKey={POLYGON_API_KEY}"
        price_response = requests.get(price_url)
        price_data = price_response.json()
        
        if "error" in price_data or price_data.get("status") == "ERROR" or not price_data.get("results"):
            logging.error(f"Polygon API error for price data {symbol}: {price_data.get('error')}")
            return None, f"No price data found for symbol: {symbol}"
            
        latest_price = price_data.get("results")[0]
        
        # Get 52-week high and low
        try:
            # Get data for the past year
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            
            range_url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}?apiKey={POLYGON_API_KEY}"
            range_response = requests.get(range_url)
            range_data = range_response.json()
            
            if "results" in range_data and range_data["results"]:
                results = range_data["results"]
                highs = [result["h"] for result in results if "h" in result]
                lows = [result["l"] for result in results if "l" in result]
                
                if highs:
                    high_52_week = max(highs)
                else:
                    high_52_week = "N/A"
                    
                if lows:
                    low_52_week = min(lows)
                else:
                    low_52_week = "N/A"
            else:
                high_52_week = "N/A"
                low_52_week = "N/A"
        except Exception as e:
            logging.error(f"Error getting 52-week range from Polygon for {symbol}: {e}")
            high_52_week = "N/A"
            low_52_week = "N/A"
            
        # Try to get market cap and PE ratio
        market_cap = ticker_result.get("market_cap", "N/A")
        
        # Get news for the symbol
        news_url = f"{POLYGON_BASE_URL}/v2/reference/news?ticker={symbol}&limit=5&apiKey={POLYGON_API_KEY}"
        news_response = requests.get(news_url)
        news_data = news_response.json()
        
        # Scrape additional info from Yahoo Finance
        scraped_info = scrape_company_info(symbol)
        
        # Use market cap from ticker result or scraped data
        if market_cap == "N/A" or not market_cap:
            market_cap = scraped_info.get("marketCap", "N/A")
            
        # Use PE ratio from scraped data
        pe_ratio = scraped_info.get("peRatio", "N/A")
        
        # Use 52-week high/low from API or scraped data
        if high_52_week == "N/A":
            high_52_week = scraped_info.get("high52Week", "N/A")
        if low_52_week == "N/A":
            low_52_week = scraped_info.get("low52Week", "N/A")
            
        # Calculate price change and percentage
        current_price = latest_price.get("c", 0)  # Close price
        previous_close = latest_price.get("o", current_price)  # Open price as fallback
        change = current_price - previous_close
        percent_change = (change / previous_close) * 100 if previous_close > 0 else 0
        
        # Construct stock info
        stock_info = {
            "symbol": symbol,
            "name": ticker_result.get("name", symbol),
            "currentPrice": round(current_price, 2),
            "change": round(change, 2),
            "percentChange": str(round(percent_change, 2)),
            "marketCap": market_cap,
            "peRatio": pe_ratio,
            "dividendYield": "N/A",  # Not directly available from Polygon without calculation
            "52WeekHigh": high_52_week,
            "52WeekLow": low_52_week,
            "description": scraped_info.get("description") or ticker_result.get("description", "N/A"),
            "sector": scraped_info.get("sector") or ticker_result.get("sic_description", "N/A"),
            "industry": scraped_info.get("industry", "N/A"),
            "dataSource": "Polygon.io API (second fallback)",
            "sources": {
                "company": f"https://www.{symbol}.com",
                "yahoo": f"https://finance.yahoo.com/quote/{symbol}",
                "marketwatch": f"https://www.marketwatch.com/investing/stock/{symbol}",
                "sec": f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={symbol}&owner=exclude&action=getcompany"
            }
        }
        
        # Format values appropriately
        if stock_info["marketCap"] and stock_info["marketCap"] != "N/A":
            stock_info["marketCap"] = format_value(stock_info["marketCap"], is_market_cap=True)
        if stock_info["peRatio"] and stock_info["peRatio"] != "N/A":
            stock_info["peRatio"] = format_value(stock_info["peRatio"], is_ratio=True)
        if stock_info["52WeekHigh"] and stock_info["52WeekHigh"] != "N/A":
            stock_info["52WeekHigh"] = format_value(stock_info["52WeekHigh"], is_price=True)
        if stock_info["52WeekLow"] and stock_info["52WeekLow"] != "N/A":
            stock_info["52WeekLow"] = format_value(stock_info["52WeekLow"], is_price=True)
            
        # Make sure we have the high52Week/low52Week properties as well for the frontend
        stock_info["high52Week"] = stock_info["52WeekHigh"]
        stock_info["low52Week"] = stock_info["52WeekLow"]
        
        # Add news if available
        if news_data.get("results"):
            stock_info["latestNews"] = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("article_url", "")
                } 
                for item in news_data.get("results", [])[:3]
            ]
        
        # Save to cache
        save_to_cache(symbol, stock_info)
        
        return stock_info, None
    except Exception as e:
        logging.error(f"Error fetching Polygon data for {symbol}: {e}")
        return None, f"Error fetching stock data from fallback source: {str(e)}"

def get_stock_data_from_tiingo(symbol):
    """Fetch stock data from Tiingo API with Polygon as fallback"""
    # Check cache first
    cached_data = get_from_cache(symbol)
    if cached_data:
        return cached_data, None
        
    if not TIINGO_API_KEY:
        logging.warning("TIINGO_API_KEY is not set, falling back to Polygon")
        return get_stock_data_from_polygon(symbol)
        
    # Headers for Tiingo API
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Token {TIINGO_API_KEY}'
    }
    
    # URL for Tiingo API
    url = f"https://api.tiingo.com/tiingo/daily/{symbol}"
    
    try:
        # Get basic info
        response = requests.get(url, headers=headers)
        data = response.json()
        
        # Check for error
        if 'detail' in data:
            if 'not found' in data['detail'].lower():
                return None, f"Symbol {symbol} not found"
            return None, data['detail']
            
        # Get price data
        prices_url = f"{url}/prices"
        prices_response = requests.get(prices_url, headers=headers)
        prices_data = prices_response.json()
        
        if not prices_data or isinstance(prices_data, dict) and 'detail' in prices_data:
            return None, f"No price data available for {symbol}"
            
        # Get most recent price data
        latest_price = prices_data[0]
        
        # Add some info
        company_name = data.get('name', symbol)
        current_price = latest_price.get('close', 0)
        open_price = latest_price.get('open', current_price)
        prev_close = prices_data[1].get('close', current_price) if len(prices_data) > 1 else current_price
        
        # Calculate change and percent change
        change = current_price - prev_close
        percent_change = (change / prev_close * 100) if prev_close > 0 else 0
        
        # Get the longest historical data to analyze 52-week high/low
        try:
            # Try to get a year of historical data for 52 week calculations
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            
            # Get historical data for 52-week high/low
            historical_url = f"{url}/prices?startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}"
            historical_response = requests.get(historical_url, headers=headers)
            historical_data = historical_response.json()
            
            if historical_data and len(historical_data) > 20:
                # Calculate 52-week high and low
                high_52_week = max(item.get('high', 0) for item in historical_data)
                low_52_week = min(item.get('low', float('inf')) for item in historical_data if item.get('low', 0) > 0)
                
                if high_52_week == 0:
                    high_52_week = "N/A"
                if low_52_week == float('inf'):
                    low_52_week = "N/A"
            else:
                high_52_week = "N/A"
                low_52_week = "N/A"
        except Exception as e:
            logging.error(f"Error calculating 52-week high/low: {e}")
            high_52_week = "N/A"
            low_52_week = "N/A"
        
        # Scrape additional info
        scraped_info = scrape_company_info(symbol)
        
        # Construct stock info object with scraped data as fallback
        stock_info = {
            "symbol": symbol,
            "name": company_name,
            "currentPrice": round(current_price, 2),
            "change": round(change, 2),
            "percentChange": str(round(percent_change, 2)),
            "marketCap": scraped_info.get("marketCap", "N/A"),
            "peRatio": scraped_info.get("peRatio", "N/A"),
            "dividendYield": "N/A",
            "52WeekHigh": high_52_week if high_52_week != "N/A" else scraped_info.get("high52Week", "N/A"),
            "52WeekLow": low_52_week if low_52_week != "N/A" else scraped_info.get("low52Week", "N/A"),
            "description": scraped_info.get("description", "N/A"),
            "sector": scraped_info.get("sector", "N/A"),
            "industry": scraped_info.get("industry", "N/A"),
            "dataSource": "Tiingo API (Alpha Vantage fallback)",
            "sources": {
                "company": f"https://www.{symbol}.com",
                "yahoo": f"https://finance.yahoo.com/quote/{symbol}",
                "marketwatch": f"https://www.marketwatch.com/investing/stock/{symbol}",
                "sec": f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={symbol}&owner=exclude&action=getcompany"
            }
        }
        
        # Format values appropriately
        if stock_info["marketCap"] and stock_info["marketCap"] != "N/A":
            stock_info["marketCap"] = format_value(stock_info["marketCap"], is_market_cap=True)
        if stock_info["peRatio"] and stock_info["peRatio"] != "N/A":
            stock_info["peRatio"] = format_value(stock_info["peRatio"], is_ratio=True)
        if stock_info["52WeekHigh"] and stock_info["52WeekHigh"] != "N/A":
            stock_info["52WeekHigh"] = format_value(stock_info["52WeekHigh"], is_price=True)
        if stock_info["52WeekLow"] and stock_info["52WeekLow"] != "N/A":
            stock_info["52WeekLow"] = format_value(stock_info["52WeekLow"], is_price=True)
            
        # Make sure we have the high52Week/low52Week properties as well for the frontend
        stock_info["high52Week"] = stock_info["52WeekHigh"]
        stock_info["low52Week"] = stock_info["52WeekLow"]
        
        # Save to cache
        save_to_cache(symbol, stock_info)
        
        return stock_info, None
    except Exception as e:
        logging.error(f"Error fetching Tiingo data for {symbol}: {e}, trying Polygon")
        return get_stock_data_from_polygon(symbol)

def get_stock_data_from_api(symbol):
    """Fetch stock data from Alpha Vantage API with Tiingo and Polygon fallbacks"""
    # Check cache first
    cached_data = get_from_cache(symbol)
    if cached_data:
        return cached_data, None

    if not API_KEY:
        logging.warning("ALPHA_VANTAGE_API_KEY is not set, falling back to Tiingo")
        return get_stock_data_from_tiingo(symbol)

    # Global quote endpoint for current price
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={API_KEY}"
    
    try:
        response = requests.get(url)
        quote_data = response.json()
        
        # Check for error message or empty response
        if "Error Message" in quote_data:
            logging.error(f"Alpha Vantage API error: {quote_data['Error Message']}, falling back to Tiingo")
            return get_stock_data_from_tiingo(symbol)
            
        # Check for API limit
        if "Note" in quote_data and "API call frequency" in quote_data["Note"]:
            logging.warning(f"Alpha Vantage API limit reached: {quote_data['Note']}, falling back to Tiingo")
            return get_stock_data_from_tiingo(symbol)
            
        # Check for empty or incomplete data
        if not quote_data.get("Global Quote", {}).get("05. price"):
            logging.warning(f"Incomplete data received for {symbol} from Alpha Vantage, falling back to Tiingo")
            return get_stock_data_from_tiingo(symbol)
        
        # Company overview for more details
        overview_url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={API_KEY}"
        overview_response = requests.get(overview_url)
        overview_data = overview_response.json()
        
        # Check if overview data is empty (just {})
        if not overview_data or "Symbol" not in overview_data:
            logging.warning(f"No company overview data for {symbol} from Alpha Vantage")
            
        # Extract price data
        quote = quote_data.get("Global Quote", {})
        current_price = float(quote.get("05. price", 0))
        previous_close = float(quote.get("08. previous close", 0))
        change = float(quote.get("09. change", 0))
        percent_change = quote.get("10. change percent", "0%").strip("%")
        
        # Get company name from overview or use symbol if not available
        company_name = overview_data.get("Name", symbol)
        
        # Scrape additional info
        scraped_info = scrape_company_info(symbol)
        
        # Construct stock info
        stock_info = {
            "symbol": symbol,
            "name": company_name,
            "currentPrice": round(current_price, 2),
            "change": round(change, 2),
            "percentChange": percent_change,
            "marketCap": format_value(overview_data.get("MarketCapitalization", "N/A"), is_market_cap=True),
            "peRatio": format_value(overview_data.get("PERatio", "N/A"), is_ratio=True),
            "dividendYield": format_value(overview_data.get("DividendYield", "N/A"), is_ratio=True),
            "52WeekHigh": format_value(overview_data.get("52WeekHigh", "N/A"), is_price=True),
            "52WeekLow": format_value(overview_data.get("52WeekLow", "N/A"), is_price=True),
            "description": scraped_info.get("description", overview_data.get("Description", "N/A")),
            "sector": scraped_info.get("sector", overview_data.get("Sector", "N/A")),
            "industry": scraped_info.get("industry", overview_data.get("Industry", "N/A")),
            "dataSource": "Alpha Vantage API",
            "sources": {
                "company": f"https://www.{symbol}.com",
                "yahoo": f"https://finance.yahoo.com/quote/{symbol}",
                "marketwatch": f"https://www.marketwatch.com/investing/stock/{symbol}",
                "sec": f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={symbol}&owner=exclude&action=getcompany"
            }
        }
        
        # Save to cache
        save_to_cache(symbol, stock_info)
        
        return stock_info, None
    except Exception as e:
        logging.error(f"Error fetching Alpha Vantage data for {symbol}: {e}, falling back to Tiingo")
        return get_stock_data_from_tiingo(symbol)

def get_polygon_trending_stocks():
    """Get trending stocks from Polygon.io API"""
    try:
        # Use Polygon's most active stocks endpoint
        url = f"{POLYGON_BASE_URL}/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        if "error" in data or data.get("status") == "ERROR" or not data.get("tickers"):
            logging.error(f"Polygon API error for trending stocks: {data.get('error')}")
            return []
            
        stocks_list = []
        for ticker in data.get("tickers", [])[:5]:  # Get top 5 gainers
            symbol = ticker.get("ticker")
            last_price = ticker.get("day", {}).get("c", 0)  # Close price
            prev_close = ticker.get("prevDay", {}).get("c", last_price)  # Previous day close
            change = last_price - prev_close
            percent_change = (change / prev_close) * 100 if prev_close > 0 else 0
            
            stocks_list.append({
                "symbol": symbol,
                "name": ticker.get("name", symbol),
                "currentPrice": round(last_price, 2),
                "change": round(change, 2),
                "percentChange": str(round(percent_change, 2)),
                "dataSource": "Polygon.io API"
            })
            
        return stocks_list
    except Exception as e:
        logging.error(f"Error fetching trending stocks from Polygon: {e}")
        return []

@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    """Get a list of trending/popular stocks with Tiingo and Polygon as fallbacks"""
    # Alpha Vantage free tier doesn't have a direct trending endpoint.
    # Try Polygon first for trending stocks
    polygon_stocks = get_polygon_trending_stocks()
    if polygon_stocks:
        return jsonify(polygon_stocks)
    
    # If Polygon fails, use our predefined list with Tiingo/Alpha Vantage data
    popular_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA'] 
    stock_list = []

    for symbol in popular_symbols:
        stock_data, error = get_stock_data_from_api(symbol)
        if stock_data:
            stock_list.append({
                'symbol': stock_data['symbol'],
                'name': stock_data['name'],
                'currentPrice': stock_data['currentPrice'],
                'change': stock_data['change'],
                'percentChange': stock_data['percentChange'],
                'dataSource': stock_data.get('dataSource', 'API')
            })
            
    # If we got no data at all (very unlikely with the fallbacks)
    if not stock_list:
        return jsonify({'message': 'Failed to fetch trending stocks from all sources.'}), 500
        
    return jsonify(stock_list)

@app.route('/api/polygon/aggregates/<symbol>', methods=['GET'])
def get_polygon_aggregates(symbol):
    """Get aggregated data from Polygon"""
    try:
        # Get query parameters
        multiplier = request.args.get('multiplier', '1')
        timespan = request.args.get('timespan', 'day')
        from_date = request.args.get('from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        to_date = request.args.get('to', datetime.now().strftime('%Y-%m-%d'))
        
        # Call Polygon API
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}?apiKey={POLYGON_API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        if "error" in data or data.get("status") == "ERROR":
            return jsonify({"error": data.get("error", "Failed to get aggregates")}), 400
            
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error getting aggregates for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500
        
@app.route('/api/polygon/news/<symbol>', methods=['GET'])
def get_polygon_news(symbol):
    """Get news from Polygon API"""
    try:
        # Get query parameters
        limit = request.args.get('limit', '10')
        
        # Call Polygon API
        url = f"{POLYGON_BASE_URL}/v2/reference/news?ticker={symbol}&limit={limit}&apiKey={POLYGON_API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        if "error" in data or data.get("status") == "ERROR":
            return jsonify({"error": data.get("error", "Failed to get news")}), 400
            
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error getting news for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/polygon/exchanges', methods=['GET'])
def get_polygon_exchanges():
    """Get list of exchanges from Polygon"""
    try:
        url = f"{POLYGON_BASE_URL}/v3/reference/exchanges?apiKey={POLYGON_API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        if "error" in data or data.get("status") == "ERROR":
            return jsonify({"error": data.get("error", "Failed to get exchanges")}), 400
            
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error getting exchanges: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/polygon/tickers', methods=['GET'])
def get_polygon_tickers():
    """Get list of tickers from Polygon"""
    try:
        # Get query parameters
        market = request.args.get('market', 'stocks')
        limit = request.args.get('limit', '50')
        search = request.args.get('search', '')
        active = request.args.get('active', 'true')
        
        # Build URL with query parameters
        url = f"{POLYGON_BASE_URL}/v3/reference/tickers?market={market}&active={active}&limit={limit}&apiKey={POLYGON_API_KEY}"
        
        if search:
            url += f"&search={search}"
            
        response = requests.get(url)
        data = response.json()
        
        if "error" in data or data.get("status") == "ERROR":
            return jsonify({"error": data.get("error", "Failed to get tickers")}), 400
            
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error getting tickers: {e}")
        return jsonify({"error": str(e)}), 500

# --- Routes --- 

def clear_cache_for_symbol(symbol):
    """Clear all cached data for a specific symbol"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Clear from stock_cache
        cursor.execute("DELETE FROM stock_cache WHERE symbol = ?", (symbol,))
        # Clear from technical_indicators
        cursor.execute("DELETE FROM technical_indicators WHERE symbol = ?", (symbol,))
        # Clear from news_cache
        cursor.execute("DELETE FROM news_cache WHERE symbol = ?", (symbol,))
        conn.commit()
        conn.close()
        logging.info(f"Successfully cleared all cached data for {symbol}")
        
        # Also clear from memory caches
        if symbol in timed_cache:
            del timed_cache[symbol]
        if symbol in cache:
            del cache[symbol]
    except Exception as e:
        logging.error(f"Error clearing cache for {symbol}: {e}")

@app.route('/api/stocks/<symbol>', methods=['GET'])
def get_stock_detail(symbol):
    """Get detailed info for a specific stock from API"""
    # Get query parameters
    clear_cache = request.args.get('clear_cache', 'false').lower() == 'true'
    use_defaults = request.args.get('use_defaults', 'false').lower() == 'true'
    
    # If defaults are explicitly requested, serve them directly
    if use_defaults:
        # Forward to default data endpoint
        default_response = get_default_data(symbol)
        if isinstance(default_response, tuple):
            # Error case
            pass  # Continue with normal flow
        else:
            # Success case, return the default data
            return default_response
            
    # Clear cache if requested or always for direct API calls
    if clear_cache:
        clear_cache_for_symbol(symbol)
    
    stock_data, error = get_stock_data_from_api(symbol)
    
    if error:
        status_code = 500
        if "not found" in error.lower():
            status_code = 404
        elif "API key" in error.lower():
            status_code = 503 # Service Unavailable
        
        # Do NOT use default data as fallback unless explicitly requested
        return jsonify({"error": error}), status_code
    
    if not stock_data:
        return jsonify({"error": f"Symbol {symbol} not found"}), 404
    
    # No automatic filling of missing data from defaults
    
    # Format 52 week data
    if "52WeekHigh" in stock_data and stock_data["52WeekHigh"] != "N/A":
        stock_data["high52Week"] = stock_data["52WeekHigh"]
    if "52WeekLow" in stock_data and stock_data["52WeekLow"] != "N/A":
        stock_data["low52Week"] = stock_data["52WeekLow"]
    if "high52Week" in stock_data and stock_data["high52Week"] != "N/A" and "52WeekHigh" not in stock_data:
        stock_data["52WeekHigh"] = stock_data["high52Week"]
    if "low52Week" in stock_data and stock_data["low52Week"] != "N/A" and "52WeekLow" not in stock_data:
        stock_data["52WeekLow"] = stock_data["low52Week"]
    
    return jsonify(stock_data)

@app.route('/api/search', methods=['GET'])
def search_stock():
    """Search for a stock by symbol using API"""
    symbol = request.args.get('symbol')
    
    if not symbol:
        return jsonify({'message': 'Symbol query parameter is required'}), 400
    
    stock_data, error = get_stock_data_from_api(symbol)
    
    if error:
        status_code = 500
        if "not found" in error.lower():
            status_code = 404
        elif "API key" in error.lower():
            status_code = 503 
        elif "API limit" in error.lower():
             status_code = 429
        return jsonify({'message': error}), status_code
        
    if not stock_data:
         return jsonify({'message': f'No stocks found matching {symbol}'}), 404
    
    # Return simplified data for search results
    return jsonify({
        'symbol': stock_data['symbol'],
        'name': stock_data['name'],
        'currentPrice': stock_data['currentPrice'],
        'change': stock_data['change'],
        'percentChange': stock_data['percentChange']
    })

@app.route('/api/technical-analysis/<symbol>', methods=['GET'])
def get_technical_analysis(symbol):
    """Get technical analysis data directly from Tiingo API"""
    try:
        # Get historical price data for the last 200 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)  # 1 year of data
        
        # Fetch historical data from Tiingo
        historical_data = tiingo_client.get_ticker_price(
            ticker=symbol,
            startDate=start_date.strftime('%Y-%m-%d'),
            endDate=end_date.strftime('%Y-%m-%d'),
            frequency='daily'
        )
        
        # Convert to pandas DataFrame for easier analysis
        df = pd.DataFrame(historical_data)
        
        # Calculate technical indicators
        # Moving Averages
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma50'] = df['close'].rolling(window=50).mean()
        df['sma200'] = df['close'].rolling(window=200).mean()
        
        # Momentum - RSI (Relative Strength Index)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volatility - ATR (Average True Range)
        df['tr1'] = abs(df['high'] - df['low'])
        df['tr2'] = abs(df['high'] - df['close'].shift())
        df['tr3'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        # Volume analysis
        df['volume_sma20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma20']
        
        # Trend determination
        current_price = df['close'].iloc[-1]
        sma20 = df['sma20'].iloc[-1]
        sma50 = df['sma50'].iloc[-1]
        sma200 = df['sma200'].iloc[-1]
        
        # Determine trend
        if current_price > sma50 and sma50 > sma200:
            trend = "Strong Uptrend"
        elif current_price > sma50:
            trend = "Uptrend"
        elif current_price < sma50 and sma50 < sma200:
            trend = "Strong Downtrend"
        elif current_price < sma50:
            trend = "Downtrend"
        else:
            trend = "Sideways"
            
        # Calculate relative strength vs SPY (S&P 500 ETF)
        spy_data = tiingo_client.get_ticker_price(
            ticker='SPY',
            startDate=start_date.strftime('%Y-%m-%d'),
            endDate=end_date.strftime('%Y-%m-%d'),
            frequency='daily'
        )
        spy_df = pd.DataFrame(spy_data)
        
        # Calculate relative performance over different periods
        periods = [21, 63, 126, 252]  # Approximately 1 month, 3 months, 6 months, 1 year
        relative_strength = {}
        
        for period in periods:
            if len(df) >= period and len(spy_df) >= period:
                # Stock performance
                stock_start = df['close'].iloc[-period]
                stock_end = df['close'].iloc[-1]
                stock_perf = (stock_end / stock_start - 1) * 100
                
                # SPY performance
                spy_start = spy_df['close'].iloc[-period]
                spy_end = spy_df['close'].iloc[-1]
                spy_perf = (spy_end / spy_start - 1) * 100
                
                # Relative strength
                rs_value = stock_perf - spy_perf
                
                relative_strength[f'{period}_day'] = {
                    'stock_performance': round(stock_perf, 2),
                    'spy_performance': round(spy_perf, 2),
                    'relative_strength': round(rs_value, 2),
                    'outperforming': rs_value > 0
                }
        
        # Prepare full technical analysis response
        last_row = df.iloc[-1]
        analysis_result = {
            "technicalAnalysis": {
                "price": round(current_price, 2),
                "trend": trend,
                "movingAverages": {
                    "sma20": round(last_row['sma20'], 2) if not pd.isna(last_row['sma20']) else None,
                    "sma50": round(last_row['sma50'], 2) if not pd.isna(last_row['sma50']) else None,
                    "sma200": round(last_row['sma200'], 2) if not pd.isna(last_row['sma200']) else None,
                    "priceVsSMA20": round((current_price / last_row['sma20'] - 1) * 100, 2) if not pd.isna(last_row['sma20']) else None,
                    "priceVsSMA50": round((current_price / last_row['sma50'] - 1) * 100, 2) if not pd.isna(last_row['sma50']) else None,
                    "priceVsSMA200": round((current_price / last_row['sma200'] - 1) * 100, 2) if not pd.isna(last_row['sma200']) else None
                },
                "momentum": {
                    "rsi": round(last_row['rsi'], 2) if not pd.isna(last_row['rsi']) else None,
                    "rsiZone": "Overbought" if last_row['rsi'] > 70 else "Oversold" if last_row['rsi'] < 30 else "Neutral"
                },
                "volatility": {
                    "atr": round(last_row['atr'], 2) if not pd.isna(last_row['atr']) else None,
                    "atrPercent": round((last_row['atr'] / current_price) * 100, 2) if not pd.isna(last_row['atr']) else None
                },
                "volume": {
                    "current": last_row['volume'],
                    "average20Day": round(last_row['volume_sma20'], 0) if not pd.isna(last_row['volume_sma20']) else None,
                    "ratio": round(last_row['volume_ratio'], 2) if not pd.isna(last_row['volume_ratio']) else None
                }
            },
            "relativeStrength": relative_strength,
            "historicalData": {
                "dates": [str(date) for date in df.index[-30:].tolist()],
                "prices": df['close'][-30:].tolist(),
                "volumes": df['volume'][-30:].tolist()
            }
        }
        
        # Detect support and resistance levels
        if len(df) > 30:
            # Simplistic approach - use recent highs and lows
            recent_df = df[-30:]
            
            # Find local maxima (resistance) and minima (support)
            resistance_levels = []
            support_levels = []
            
            for i in range(1, len(recent_df) - 1):
                # Potential resistance
                if recent_df['high'].iloc[i] > recent_df['high'].iloc[i-1] and recent_df['high'].iloc[i] > recent_df['high'].iloc[i+1]:
                    resistance_levels.append(round(recent_df['high'].iloc[i], 2))
                
                # Potential support
                if recent_df['low'].iloc[i] < recent_df['low'].iloc[i-1] and recent_df['low'].iloc[i] < recent_df['low'].iloc[i+1]:
                    support_levels.append(round(recent_df['low'].iloc[i], 2))
            
            # Cluster close levels
            def cluster_levels(levels, threshold_percent=1.0):
                if not levels:
                    return []
                
                clustered = []
                levels.sort()
                
                current_cluster = [levels[0]]
                
                for level in levels[1:]:
                    # If this level is within threshold% of the cluster average
                    cluster_avg = sum(current_cluster) / len(current_cluster)
                    if abs(level - cluster_avg) / cluster_avg * 100 < threshold_percent:
                        current_cluster.append(level)
                    else:
                        # Start a new cluster
                        clustered.append(round(sum(current_cluster) / len(current_cluster), 2))
                        current_cluster = [level]
                
                # Add the last cluster
                if current_cluster:
                    clustered.append(round(sum(current_cluster) / len(current_cluster), 2))
                
                return clustered
            
            # Add support and resistance levels to the response
            analysis_result["supportResistance"] = {
                "support": cluster_levels(support_levels),
                "resistance": cluster_levels(resistance_levels)
            }
        
        return jsonify(analysis_result)
    except Exception as e:
        error_msg = f"Error getting technical analysis: {str(e)}"
        app.logger.error(error_msg)
        return jsonify({"error": error_msg}), 500

def get_or_cache_technical_data(symbol, max_age_seconds=1800):
    """Get technical data with intelligent caching"""
    symbol = symbol.upper()
    
    # Check cache first
    if symbol in timed_cache:
        cache_entry = timed_cache[symbol]
        # If cache is fresh (less than max_age_seconds old)
        if time.time() - cache_entry['timestamp'] < max_age_seconds:
            logging.info(f"Using cached technical data for {symbol}")
            return cache_entry['data']
    
    # If no cache or cache is stale, get fresh data
    try:
        # Get technical analysis data directly from API function
        # but get it as data instead of JSON response
        analysis_result = get_technical_analysis_data(symbol)
        
        # Store in timed cache
        timed_cache[symbol] = {
            'data': analysis_result,
            'timestamp': time.time()
        }
        
        return analysis_result
    except Exception as e:
        logging.error(f"Error getting technical analysis for {symbol}: {e}")
        # If we have stale cache data, return it with a warning
        if symbol in timed_cache:
            logging.warning(f"Using stale cache for {symbol} due to API error")
            timed_cache[symbol]['data']['warning'] = "Data may be outdated due to API error"
            return timed_cache[symbol]['data']
        raise

def get_technical_analysis_data(symbol):
    """Non-route version of get_technical_analysis that returns data instead of JSON response"""
    try:
        # Get historical price data for the last 200 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)  # 1 year of data
        
        # Fetch historical data from Tiingo
        historical_data = tiingo_client.get_ticker_price(
            ticker=symbol,
            startDate=start_date.strftime('%Y-%m-%d'),
            endDate=end_date.strftime('%Y-%m-%d'),
            frequency='daily'
        )
        
        # Convert to pandas DataFrame for easier analysis
        df = pd.DataFrame(historical_data)
        
        # Calculate technical indicators
        # Moving Averages
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma50'] = df['close'].rolling(window=50).mean()
        df['sma200'] = df['close'].rolling(window=200).mean()
        
        # Momentum - RSI (Relative Strength Index)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volatility - ATR (Average True Range)
        df['tr1'] = abs(df['high'] - df['low'])
        df['tr2'] = abs(df['high'] - df['close'].shift())
        df['tr3'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        # Volume analysis
        df['volume_sma20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma20']
        
        # Trend determination
        current_price = df['close'].iloc[-1]
        sma20 = df['sma20'].iloc[-1]
        sma50 = df['sma50'].iloc[-1]
        sma200 = df['sma200'].iloc[-1]
        
        # Determine trend
        if current_price > sma50 and sma50 > sma200:
            trend = "Strong Uptrend"
        elif current_price > sma50:
            trend = "Uptrend"
        elif current_price < sma50 and sma50 < sma200:
            trend = "Strong Downtrend"
        elif current_price < sma50:
            trend = "Downtrend"
        else:
            trend = "Sideways"
            
        # Calculate relative strength vs SPY (S&P 500 ETF)
        spy_data = tiingo_client.get_ticker_price(
            ticker='SPY',
            startDate=start_date.strftime('%Y-%m-%d'),
            endDate=end_date.strftime('%Y-%m-%d'),
            frequency='daily'
        )
        spy_df = pd.DataFrame(spy_data)
        
        # Calculate relative performance over different periods
        periods = [21, 63, 126, 252]  # Approximately 1 month, 3 months, 6 months, 1 year
        relative_strength = {}
        
        for period in periods:
            if len(df) >= period and len(spy_df) >= period:
                # Stock performance
                stock_start = df['close'].iloc[-period]
                stock_end = df['close'].iloc[-1]
                stock_perf = (stock_end / stock_start - 1) * 100
                
                # SPY performance
                spy_start = spy_df['close'].iloc[-period]
                spy_end = spy_df['close'].iloc[-1]
                spy_perf = (spy_end / spy_start - 1) * 100
                
                # Relative strength
                rs_value = stock_perf - spy_perf
                
                relative_strength[f'{period}_day'] = {
                    'stock_performance': round(stock_perf, 2),
                    'spy_performance': round(spy_perf, 2),
                    'relative_strength': round(rs_value, 2),
                    'outperforming': rs_value > 0
                }
        
        # Prepare full technical analysis response
        last_row = df.iloc[-1]
        analysis_result = {
            "technicalAnalysis": {
                "price": round(current_price, 2),
                "trend": trend,
                "movingAverages": {
                    "sma20": round(last_row['sma20'], 2) if not pd.isna(last_row['sma20']) else None,
                    "sma50": round(last_row['sma50'], 2) if not pd.isna(last_row['sma50']) else None,
                    "sma200": round(last_row['sma200'], 2) if not pd.isna(last_row['sma200']) else None,
                    "priceVsSMA20": round((current_price / last_row['sma20'] - 1) * 100, 2) if not pd.isna(last_row['sma20']) else None,
                    "priceVsSMA50": round((current_price / last_row['sma50'] - 1) * 100, 2) if not pd.isna(last_row['sma50']) else None,
                    "priceVsSMA200": round((current_price / last_row['sma200'] - 1) * 100, 2) if not pd.isna(last_row['sma200']) else None
                },
                "momentum": {
                    "rsi": round(last_row['rsi'], 2) if not pd.isna(last_row['rsi']) else None,
                    "rsiZone": "Overbought" if last_row['rsi'] > 70 else "Oversold" if last_row['rsi'] < 30 else "Neutral"
                },
                "volatility": {
                    "atr": round(last_row['atr'], 2) if not pd.isna(last_row['atr']) else None,
                    "atrPercent": round((last_row['atr'] / current_price) * 100, 2) if not pd.isna(last_row['atr']) else None
                },
                "volume": {
                    "current": last_row['volume'],
                    "average20Day": round(last_row['volume_sma20'], 0) if not pd.isna(last_row['volume_sma20']) else None,
                    "ratio": round(last_row['volume_ratio'], 2) if not pd.isna(last_row['volume_ratio']) else None
                }
            },
            "relativeStrength": relative_strength,
            "historicalData": {
                "dates": [str(date) for date in df.index[-30:].tolist()],
                "prices": df['close'][-30:].tolist(), 
                "volumes": df['volume'][-30:].tolist()
            }
        }
        
        # Detect support and resistance levels
        if len(df) > 30:
            # Simplistic approach - use recent highs and lows
            recent_df = df[-30:]
            
            # Find local maxima (resistance) and minima (support)
            resistance_levels = []
            support_levels = []
            
            for i in range(1, len(recent_df) - 1):
                # Potential resistance
                if recent_df['high'].iloc[i] > recent_df['high'].iloc[i-1] and recent_df['high'].iloc[i] > recent_df['high'].iloc[i+1]:
                    resistance_levels.append(round(recent_df['high'].iloc[i], 2))
                
                # Potential support
                if recent_df['low'].iloc[i] < recent_df['low'].iloc[i-1] and recent_df['low'].iloc[i] < recent_df['low'].iloc[i+1]:
                    support_levels.append(round(recent_df['low'].iloc[i], 2))
            
            # Cluster close levels
            def cluster_levels(levels, threshold_percent=1.0):
                if not levels:
                    return []
                
                clustered = []
                levels.sort()
                
                current_cluster = [levels[0]]
                
                for level in levels[1:]:
                    # If this level is within threshold% of the cluster average
                    cluster_avg = sum(current_cluster) / len(current_cluster)
                    if abs(level - cluster_avg) / cluster_avg * 100 < threshold_percent:
                        current_cluster.append(level)
                    else:
                        # Start a new cluster
                        clustered.append(round(sum(current_cluster) / len(current_cluster), 2))
                        current_cluster = [level]
                
                # Add the last cluster
                if current_cluster:
                    clustered.append(round(sum(current_cluster) / len(current_cluster), 2))
                
                return clustered
            
            # Add support and resistance levels to the response
            analysis_result["supportResistance"] = {
                "support": cluster_levels(support_levels),
                "resistance": cluster_levels(resistance_levels)
            }
        
        return analysis_result
    except Exception as e:
        error_msg = f"Error getting technical analysis: {str(e)}"
        app.logger.error(error_msg)
        raise

# Populate Alpha Vantage cache in background without waiting
def background_cache_alpha_vantage_data(symbols):
    """Fetch and cache data for multiple symbols in background"""
    for symbol in symbols:
        try:
            get_stock_data_from_api(symbol)
        except Exception as e:
            logging.error(f"Error background caching {symbol}: {e}")

# New route that combines data and adds explanations
@app.route('/api/enriched/<symbol>', methods=['GET'])
def get_enriched_data(symbol):
    """Get combined data with technical explanations and improved caching"""
    try:
        symbol = symbol.upper()
        
        # Start background fetching Alpha Vantage data
        # This will populate the cache in the background without blocking this request
        threading.Thread(
            target=background_cache_alpha_vantage_data, 
            args=([symbol],), 
            daemon=True
        ).start()
        
        # Get technical analysis with smart caching
        technical_data = get_or_cache_technical_data(symbol)
        
        # Add explanations for technical indicators
        technical_data["indicatorExplanations"] = INDICATOR_EXPLANATIONS
        
        # Try to get stock data from Alpha Vantage cache
        stock_data, _ = get_stock_data_from_api(symbol)
        
        # Prepare combined response
        combined_data = {
            "technical": technical_data,
            "fundamentalData": stock_data if stock_data else {"status": "unavailable"},
            "dataTimestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "cache": {
                "technicalDataSource": "Tiingo API" + (" (cached)" if symbol in timed_cache else ""),
                "fundamentalDataSource": "Alpha Vantage API" + (" (cached)" if symbol in cache else "")
            }
        }
        
        return jsonify(combined_data)
    except Exception as e:
        error_msg = f"Error retrieving enriched data: {str(e)}"
        app.logger.error(error_msg)
        return jsonify({"error": error_msg}), 500

@app.route('/api/technical/<symbol>/<indicator>', methods=['GET'])
def get_technical(symbol, indicator):
    """API endpoint to get technical indicators for a stock"""
    if indicator not in TECHNICAL_INDICATORS:
        return jsonify({"error": f"Invalid indicator: {indicator}. Available indicators: {', '.join(TECHNICAL_INDICATORS.keys())}"}), 400
        
    data = get_technical_indicator(symbol, indicator)
    if not data:
        return jsonify({"error": f"Failed to retrieve {indicator} data for {symbol}"}), 404
        
    # Add explanation
    data['explanation'] = TECHNICAL_INDICATORS.get(indicator, "")
    
    return jsonify(data)

@app.route('/api/news/<symbol>', methods=['GET'])
def get_news(symbol):
    """API endpoint to get news for a stock"""
    data = get_stock_news(symbol)
    if not data:
        return jsonify({"error": f"Failed to retrieve news for {symbol}"}), 404
        
    return jsonify(data)

@app.route('/api/combined/<symbol>', methods=['GET'])
def get_combined_data(symbol):
    """API endpoint to get combined stock data, technical indicators, and news"""
    # Get basic stock data
    stock_data = get_stock_data_from_api(symbol)
    if "error" in stock_data:
        return jsonify(stock_data), 404
        
    # Get technical indicators (SMA and RSI as examples)
    sma_data = get_technical_indicator(symbol, 'SMA')
    rsi_data = get_technical_indicator(symbol, 'RSI')
    
    technical = {
        'SMA': sma_data,
        'RSI': rsi_data,
        'explanations': {k: TECHNICAL_INDICATORS[k] for k in ['SMA', 'RSI']}
    }
    
    # Get news
    news_data = get_stock_news(symbol)
    
    # Combine all data
    combined_data = {
        'stock': stock_data,
        'technical': technical,
        'news': news_data.get('news', []) if news_data else []
    }
    
    return jsonify(combined_data)

def format_value(value, is_price=False, is_market_cap=False, is_ratio=False):
    """Format a value based on its type and context"""
    if value is None or value == "N/A" or value == "":
        return "N/A"
    
    try:
        # Try to convert to float
        float_value = float(value)
        
        # Format market cap
        if is_market_cap:
            if float_value >= 1_000_000_000:
                return f"{float_value / 1_000_000_000:.2f}B"
            elif float_value >= 1_000_000:
                return f"{float_value / 1_000_000:.2f}M"
            else:
                return f"{float_value:,.0f}"
        
        # Format price values
        if is_price:
            return f"{float_value:.2f}"
        
        # Format ratios
        if is_ratio:
            return f"{float_value:.2f}"
            
        # Default number formatting
        return str(float_value)
    except (ValueError, TypeError):
        # Return as is if conversion fails
        return value

@app.route('/api/technical/enhanced/<symbol>', methods=['GET'])
def get_enhanced_technical(symbol):
    """Get enhanced technical metrics for a stock"""
    try:
        # Use the cache for historical data requests
        session = requests_cache.CachedSession('technical_cache', expire_after=3600)
        
        # Get query parameters
        lookback = request.args.get('lookback', '180')  # Default to 180 days
        try:
            lookback_days = int(lookback)
        except ValueError:
            lookback_days = 180
            
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Fetch stock data from API
        stock_data, error = get_stock_data_from_api(symbol)
        if error:
            return jsonify({"error": error}), 400
            
        # Try fetching historical data from Alpha Vantage first
        hist_data = None
        alpha_vantage_error = None
        try:
            url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize=full&apikey={API_KEY}"
            response = session.get(url)
            data = response.json()
            
            if "Error Message" in data:
                alpha_vantage_error = data["Error Message"]
            elif "Note" in data and "API call frequency" in data["Note"]:
                alpha_vantage_error = data["Note"]
            elif "Time Series (Daily)" not in data:
                alpha_vantage_error = "Missing time series data"
            else:
                # Convert to usable format
                time_series = data.get("Time Series (Daily)", {})
                hist_data = []
                
                for date, values in time_series.items():
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                    if date_obj >= start_date and date_obj <= end_date:
                        hist_data.append({
                            "date": date,
                            "open": float(values.get("1. open", 0)),
                            "high": float(values.get("2. high", 0)),
                            "low": float(values.get("3. low", 0)),
                            "close": float(values.get("4. close", 0)),
                            "volume": float(values.get("5. volume", 0))
                        })
                
                # Sort by date
                hist_data.sort(key=lambda x: x["date"])
        except Exception as e:
            alpha_vantage_error = str(e)
            logging.error(f"Alpha Vantage historical data error for {symbol}: {e}")
        
        # If Alpha Vantage failed, try Tiingo as fallback
        if not hist_data or alpha_vantage_error:
            logging.info(f"Falling back to Tiingo for historical data for {symbol}")
            try:
                # Fetch historical data from Tiingo
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Token {TIINGO_API_KEY}'
                }
                
                tiingo_url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices?startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}"
                tiingo_response = requests.get(tiingo_url, headers=headers)
                tiingo_data = tiingo_response.json()
                
                if not tiingo_data or 'detail' in tiingo_data:
                    return jsonify({"error": f"Failed to get historical data: {alpha_vantage_error}"}), 400
                
                # Convert to same format as Alpha Vantage data
                hist_data = []
                for item in tiingo_data:
                    hist_data.append({
                        "date": item.get("date", "").split("T")[0],  # Get just the date part
                        "open": float(item.get("open", 0)),
                        "high": float(item.get("high", 0)),
                        "low": float(item.get("low", 0)),
                        "close": float(item.get("close", 0)),
                        "volume": float(item.get("volume", 0))
                    })
                
                # Sort by date
                hist_data.sort(key=lambda x: x["date"])
            except Exception as e:
                logging.error(f"Tiingo historical data error for {symbol}: {e}")
                return jsonify({"error": f"Failed to get historical data from all sources: {e}"}), 400
        
        if not hist_data or len(hist_data) < 20:  # Need at least 20 data points
            return jsonify({"error": "Insufficient historical data"}), 400
            
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(hist_data)
        
        # Calculate technical indicators
        # Calculate Beta (vs S&P 500) if enough data
        beta = None
        spy_correlation = None
        try:
            # Try to get SPY data for the same period from Tiingo which is more reliable
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Token {TIINGO_API_KEY}'
            }
            
            spy_url = f"https://api.tiingo.com/tiingo/daily/SPY/prices?startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}"
            spy_response = requests.get(spy_url, headers=headers)
            spy_data = spy_response.json()
            
            if spy_data and not isinstance(spy_data, dict):
                spy_prices = []
                
                for item in spy_data:
                    spy_prices.append({
                        "date": item.get("date", "").split("T")[0],  # Get just the date part
                        "close": float(item.get("close", 0))
                    })
                        
                # Sort by date
                spy_prices.sort(key=lambda x: x["date"])
                spy_df = pd.DataFrame(spy_prices)
                
                # Ensure dates match
                merged_df = pd.merge(df[["date", "close"]], spy_df[["date", "close"]], on="date", suffixes=('_stock', '_spy'))
                
                if len(merged_df) > 20:  # Need enough data points for meaningful calculation
                    # Calculate daily returns
                    merged_df["stock_return"] = merged_df["close_stock"].pct_change()
                    merged_df["spy_return"] = merged_df["close_spy"].pct_change()
                    
                    # Remove NaN values
                    merged_df = merged_df.dropna()
                    
                    # Calculate beta
                    covariance = merged_df["stock_return"].cov(merged_df["spy_return"])
                    spy_variance = merged_df["spy_return"].var()
                    
                    if spy_variance > 0:
                        beta = covariance / spy_variance
                        
                    # Calculate correlation
                    spy_correlation = merged_df["stock_return"].corr(merged_df["spy_return"])
        except Exception as e:
            logging.error(f"Error calculating beta for {symbol}: {e}")
            
        # Calculate volatility metrics
        daily_returns = df["close"].pct_change().dropna()
        volatility = {
            "daily": daily_returns.std() * 100,  # Daily volatility in percent
            "annualized": daily_returns.std() * (252 ** 0.5) * 100,  # Annualized volatility
            "max_drawdown": 0
        }
        
        # Calculate max drawdown
        if len(df) > 1:
            rolling_max = df["close"].expanding().max()
            drawdown = (df["close"] / rolling_max - 1.0) * 100
            volatility["max_drawdown"] = drawdown.min()
        
        # Package the response with the data we have
        response_data = {
            "symbol": symbol,
            "name": stock_data.get("name", symbol),
            "volatility": {
                "daily": round(volatility["daily"], 2),
                "annualized": round(volatility["annualized"], 2),
                "maxDrawdown": round(volatility["max_drawdown"], 2) if volatility["max_drawdown"] != 0 else "N/A"
            },
            "marketMetrics": {
                "beta": format_value(beta, is_ratio=True) if beta is not None else "N/A",
                "dividend": {
                    "yield": stock_data.get("dividendYield", "N/A"),
                    "perShare": "N/A",
                    "date": "N/A",
                    "payoutRatio": "N/A"
                }
            },
            "spyCorrelation": round(spy_correlation, 2) if spy_correlation is not None else "N/A",
            "priceLevels": {
                "support": {
                    "strong": round(df["low"].min(), 2),
                    "weak": round(df["close"].quantile(0.1), 2) if len(df) >= 10 else "N/A"
                },
                "resistance": {
                    "strong": round(df["high"].max(), 2),
                    "weak": round(df["close"].quantile(0.9), 2) if len(df) >= 10 else "N/A"
                },
                "current": round(df["close"].iloc[-1], 2) if len(df) > 0 else "N/A"
            },
            "dataPoints": len(df),
            "dataSource": "Tiingo API" if alpha_vantage_error else "Alpha Vantage API"
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Error getting enhanced technical metrics for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

# Add required imports at the top of the file
try:
    import google.genai as genai
except ImportError:
    print("Google Genai library not found. Installing...")
    import subprocess
    subprocess.check_call(["pip", "install", "--upgrade", "google-genai"])
    import google.genai as genai

# Gemini API key configuration
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyCfm2xX5Lsnpcq18u4Hzv3zbbXkEFbHn44')

@app.route('/api/ai-analysis/<symbol>', methods=['GET'])
def get_ai_analysis(symbol):
    """Use Gemini API to analyze stock data and provide insights"""
    try:
        # Get stock data from our API
        stock_data, error = get_stock_data_from_api(symbol)
        if error:
            return jsonify({"error": f"Failed to get stock data: {error}"}), 400
        
        # Prepare prompt for Gemini
        prompt = f"""
        You are a professional stock analyst providing insights on {symbol} ({stock_data.get('name', '')}).
        
        Here's the current stock data:
        - Current Price: ${stock_data.get('currentPrice', 'N/A')}
        - Market Cap: {stock_data.get('marketCap', 'N/A')}
        - P/E Ratio: {stock_data.get('peRatio', 'N/A')}
        - 52 Week High: ${stock_data.get('52WeekHigh', 'N/A')}
        - 52 Week Low: ${stock_data.get('52WeekLow', 'N/A')}
        - Sector: {stock_data.get('sector', 'N/A')}
        - Industry: {stock_data.get('industry', 'N/A')}
        
        Based on this information, please provide:
        1. A summary of the company's current situation
        2. Technical analysis insights
        3. Key strengths and risks
        4. A short-term outlook (1-3 months)
        
        Format your response as a professional analyst report with clear sections.
        Include numerical data when relevant, and make specific observations about price levels, trend direction, and comparative performance.
        Keep your analysis concise and data-driven, focusing on the most important insights an investor should know.
        """
        
        # Call Gemini API using direct API requests
        logging.info(f"Calling Gemini API for AI analysis of {symbol}")
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }
        
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 1024
            }
        }
        
        gemini_url = "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent"
        gemini_response = requests.post(
            gemini_url,
            headers=headers,
            json=payload
        )
        
        if gemini_response.status_code != 200:
            logging.error(f"Gemini API error: {gemini_response.text}")
            return jsonify({"error": f"AI analysis failed: {gemini_response.text}"}), 500
        
        response_data = gemini_response.json()
        if not response_data.get("candidates") or not response_data["candidates"][0].get("content"):
            return jsonify({"error": "Empty response from AI model"}), 500
        
        analysis_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Package the response
        return jsonify({
            "symbol": symbol,
            "name": stock_data.get("name", symbol),
            "analysis": analysis_text,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "dataSource": "Gemini AI"
        })
        
    except Exception as e:
        logging.error(f"Error generating AI analysis for {symbol}: {e}")
        return jsonify({"error": f"AI analysis error: {str(e)}"}), 500

@app.route('/api/default-data/<symbol>', methods=['GET'])
def get_default_data(symbol):
    # ... existing code ...
    pass

if __name__ == '__main__':
    if not API_KEY:
        print("WARNING: ALPHA_VANTAGE_API_KEY environment variable not set.")
        print("API functionality will be limited.")
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False) # Turn off debug for production-like environment 