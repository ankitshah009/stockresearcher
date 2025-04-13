# Stock Researcher Backend

This is the backend service for the Stock Researcher application, providing real-time financial data through multiple API providers with a fault-tolerant fallback system.

## Features

- **Multiple Data Sources**: Uses Alpha Vantage, Tiingo, and Polygon.io APIs with automatic fallback
- **Caching System**: Reduces API calls and improves performance
- **Technical Analysis**: Calculates various technical indicators
- **Stock News**: Fetches latest news for searched tickers
- **RESTful API**: Simple endpoints for frontend consumption

## API Providers

The backend uses three financial data providers in priority order:

1. **Alpha Vantage** (Primary)
   - Limited to 25 requests/day on free tier
   - Provides comprehensive fundamental and technical data
   - [Alpha Vantage Documentation](https://www.alphavantage.co/documentation/)

2. **Tiingo** (First Fallback)
   - Activates when Alpha Vantage fails or hits rate limits
   - Provides reliable price data and some fundamentals
   - [Tiingo API Documentation](https://api.tiingo.com/documentation/general/overview)

3. **Polygon.io** (Second Fallback)
   - Activates when both Alpha Vantage and Tiingo fail
   - Provides comprehensive market data including news
   - [Polygon.io Documentation](https://polygon.io/docs)

## Fallback System

The backend implements an intelligent fallback system:

1. First tries Alpha Vantage API
2. If Alpha Vantage fails or hits rate limits, switches to Tiingo
3. If Tiingo fails, switches to Polygon.io
4. Uses persistent caching to reduce API calls

## API Endpoints

### Core Endpoints

- `GET /api/search?symbol=AAPL`: Search for a stock by symbol
- `GET /api/stocks`: Get trending/popular stocks
- `GET /api/stocks/{symbol}`: Get detailed info for a specific stock
- `GET /api/technical-analysis/{symbol}`: Get technical indicators
- `GET /api/news/{symbol}`: Get latest news for a stock
- `GET /api/enriched/{symbol}`: Get combined data with technical explanations

### Polygon-Specific Endpoints

- `GET /api/polygon/aggregates/{symbol}`: Get OHLC data with custom parameters
- `GET /api/polygon/news/{symbol}`: Get news specifically from Polygon
- `GET /api/polygon/exchanges`: Get list of exchanges
- `GET /api/polygon/tickers`: Get list of tickers (supports filtering)

## Setup

1. Clone the repository
2. Create a `.env` file based on `.env.example`
3. Add your API keys:
   - ALPHA_VANTAGE_API_KEY
   - TIINGO_API_KEY
   - POLYGON_API_KEY
4. Install dependencies: `pip install -r requirements.txt`
5. Start the server: `gunicorn app:app`

## Environment Variables

```
# Alpha Vantage API key (primary data source)
ALPHA_VANTAGE_API_KEY=your_key_here

# Tiingo API key (first fallback)
TIINGO_API_KEY=your_key_here

# Polygon.io API key (second fallback)
POLYGON_API_KEY=your_key_here

# Optional: Port for the backend service (default: 5001)
PORT=5001
```

## Docker Usage

This service can be run as part of the docker-compose setup:

```bash
docker-compose up -d
```

The backend will be available at http://localhost:5001 or via the frontend's Nginx proxy at http://localhost/api/ 