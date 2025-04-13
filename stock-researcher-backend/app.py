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

# In-memory cache to avoid hitting API limits frequently
cache = {}

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

def get_stock_data_from_api(symbol):
    """Fetches stock data from Alpha Vantage API"""
    if not API_KEY:
        logging.error("Alpha Vantage API key not found.")
        return None, "API key missing"

    symbol = symbol.upper()
    if symbol in cache:
        logging.info(f"Cache hit for {symbol}")
        return cache[symbol], None

    logging.info(f"Fetching data from Alpha Vantage for {symbol}...")
    params_quote = {
        'function': 'GLOBAL_QUOTE',
        'symbol': symbol,
        'apikey': API_KEY
    }
    params_overview = {
        'function': 'OVERVIEW',
        'symbol': symbol,
        'apikey': API_KEY
    }

    try:
        response_quote = requests.get(BASE_URL, params=params_quote)
        response_quote.raise_for_status() 
        quote_data = response_quote.json().get('Global Quote')
        
        response_overview = requests.get(BASE_URL, params=params_overview)
        response_overview.raise_for_status()
        overview_data = response_overview.json()
        
        if not quote_data or not overview_data or 'Symbol' not in overview_data or not overview_data.get('Symbol'):
            logging.warning(f"Incomplete data received for {symbol}")
            return None, "Data not found or incomplete"

        # Check for API limit note
        if "Note" in quote_data or "Note" in overview_data:
             logging.warning(f"Alpha Vantage API limit likely reached for {symbol}. Using cached/mock data if possible.")
             # You might want to return an error or specific message here in a real app
             # For now, we'll return None to indicate an issue
             return None, "API limit reached or temporary issue"

        # --- Simulate Analyst Data --- 
        # In a real app, this data would come from a dedicated (likely premium) API
        simulated_analysts = [
            {'analystName': 'Future Finance Inc.', 'rating': 'Buy', 'accuracyScore': 78, 'targetPrice': float(quote_data.get('05. price', 0)) * 1.20, 'date': '2025-04-10'},
            {'analystName': 'Market Insights Co.', 'rating': 'Buy', 'accuracyScore': 85, 'targetPrice': float(quote_data.get('05. price', 0)) * 1.25, 'date': '2025-04-08'},
            {'analystName': 'Global Growth Grp.', 'rating': 'Hold', 'accuracyScore': 65, 'targetPrice': float(quote_data.get('05. price', 0)) * 1.10, 'date': '2025-04-05'},
            {'analystName': 'Value Ventures', 'rating': 'Buy', 'accuracyScore': 72, 'targetPrice': float(quote_data.get('05. price', 0)) * 1.18, 'date': '2025-03-28'}
        ]
        
        # Calculate consensus (simple mode calculation)
        ratings = [a['rating'] for a in simulated_analysts]
        consensus_rating = max(set(ratings), key=ratings.count) if ratings else 'N/A'
        
        # Calculate average target price
        target_prices = [a['targetPrice'] for a in simulated_analysts if a.get('targetPrice')]
        average_target_price = round(sum(target_prices) / len(target_prices), 2) if target_prices else None
        # --- End Simulate Analyst Data ---

        stock_info = {
            'symbol': quote_data.get('01. symbol'),
            'name': overview_data.get('Name'),
            'currentPrice': float(quote_data.get('05. price', 0)),
            'change': float(quote_data.get('09. change', 0)),
            'percentChange': float(quote_data.get('10. change percent', '0%').replace('%', '')),
            'marketCap': overview_data.get('MarketCapitalization', 'N/A'),
            'peRatio': overview_data.get('PERatio', 'N/A'),
            'high52Week': overview_data.get('52WeekHigh', 'N/A'),
            'low52Week': overview_data.get('52WeekLow', 'N/A'),
            # Mocking sources and summary for now as AV doesn't provide this
            'reliableSources': [
                {'url': f'https://finance.yahoo.com/quote/{symbol}', 'name': 'Yahoo Finance', 'reliability': 'medium'},
                {'url': f'https://www.google.com/finance/quote/{symbol}:NASDAQ', 'name': 'Google Finance', 'reliability': 'medium'}, # Assuming NASDAQ, adjust if needed
                {'url': f'https://www.sec.gov/edgar/search/#/q={symbol}&dateRange=custom&startdt=2023-01-01&enddt=2024-01-01', 'name': 'SEC Filings', 'reliability': 'high'} # Example search link
            ],
            'unreliableSources': [
                {'name': 'ExampleStockForum.com', 'reason': 'User Generated Content'},
                {'name': 'HypedStockNews', 'reason': 'Potential Bias'}
            ],
            'summary': f"Summary for {overview_data.get('Name', symbol)} based on available data. Industry: {overview_data.get('Industry', 'N/A')}. Sector: {overview_data.get('Sector', 'N/A')}.",
            
            # Add simulated analyst data to response
            'analystData': {
                'ratings': simulated_analysts,
                'consensusRating': consensus_rating,
                'averageTargetPrice': average_target_price
            }
        }
        
        # Basic validation
        if not stock_info['symbol'] or not stock_info['name']:
            logging.warning(f"Validation failed for {symbol} data.")
            return None, "Invalid data received"
            
        cache[symbol] = stock_info # Cache the result
        return stock_info, None

    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed for {symbol}: {e}")
        return None, "API request failed"
    except ValueError as e:
        logging.error(f"Data parsing error for {symbol}: {e}")
        return None, "Error parsing API data"
    except Exception as e:
        logging.error(f"An unexpected error occurred for {symbol}: {e}")
        return None, "An unexpected error occurred"

# --- Routes --- 

@app.route('/api/stocks/<symbol>', methods=['GET'])
def get_stock_detail(symbol):
    """Get detailed info for a specific stock from API"""
    stock_data, error = get_stock_data_from_api(symbol)
    
    if error:
        status_code = 500
        if "not found" in error.lower():
            status_code = 404
        elif "API key" in error.lower():
            status_code = 503 # Service Unavailable
        elif "API limit" in error.lower():
             status_code = 429 # Too Many Requests
        return jsonify({'message': error}), status_code

    if not stock_data:
        return jsonify({'message': f'Could not retrieve data for symbol {symbol}'}), 500
    
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

@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    """Get a list of trending/popular stocks (using API for a few)"""
    # Alpha Vantage free tier doesn't have a direct trending endpoint.
    # We'll fetch a few predefined popular stocks instead.
    popular_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA'] 
    stock_list = []
    errors = []

    for symbol in popular_symbols:
        stock_data, error = get_stock_data_from_api(symbol)
        if stock_data:
            stock_list.append({
                'symbol': stock_data['symbol'],
                'name': stock_data['name'],
                'currentPrice': stock_data['currentPrice'],
                'change': stock_data['change'],
                'percentChange': stock_data['percentChange']
            })
        elif error:
            errors.append(f"{symbol}: {error}")
            
    if not stock_list and errors:
        # If all API calls failed, return an error
        return jsonify({'message': 'Failed to fetch trending stocks.', 'details': errors}), 500
        
    # Even if some fail, return the ones that succeeded
    return jsonify(stock_list)

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

if __name__ == '__main__':
    if not API_KEY:
        print("WARNING: ALPHA_VANTAGE_API_KEY environment variable not set.")
        print("API functionality will be limited.")
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False) # Turn off debug for production-like environment 