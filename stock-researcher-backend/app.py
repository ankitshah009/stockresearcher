from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
BASE_URL = 'https://www.alphavantage.co/query'

# In-memory cache to avoid hitting API limits frequently
cache = {}

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
            'summary': f"Summary for {overview_data.get('Name', symbol)} based on available data. Industry: {overview_data.get('Industry', 'N/A')}. Sector: {overview_data.get('Sector', 'N/A')}."
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

if __name__ == '__main__':
    if not API_KEY:
        print("WARNING: ALPHA_VANTAGE_API_KEY environment variable not set.")
        print("API functionality will be limited.")
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False) # Turn off debug for production-like environment 