# Stock Researcher

A comprehensive stock research application that helps users cut through the noise of unreliable sources and access information directly from official company websites and trusted sources.

## Architecture

This project uses a modern, microservices architecture:

- **Frontend**: React application with responsive UI
- **Backend**: Python Flask API with RESTful endpoints
- **Containerization**: Docker for consistent deployment
- **AI Integration**: Gemini Pro AI for stock analysis insights

## Tech Stack

### Frontend
- **React**: JavaScript library for building user interfaces
- **CSS3**: Modern styling with flexbox and grid layouts
- **Windsurf**: Lightweight UI framework for responsive components
- **Axios**: Promise-based HTTP client for API requests
- **React Router**: Routing library for single-page applications

### Backend
- **Python 3.9**: Core programming language
- **Flask**: Lightweight web framework
- **SQLite**: Database for caching and persistent storage
- **Pandas**: Data analysis and manipulation
- **BeautifulSoup4**: Web scraping for financial data
- **Requests-Cache**: HTTP caching for improved performance
- **Gunicorn**: WSGI HTTP server

### Infrastructure
- **Docker**: Containerization platform
- **Docker Compose**: Multi-container Docker applications
- **Nginx**: Web server and reverse proxy

### External Services
- **Gemini Pro AI**: AI analysis and natural language processing
- **Alpha Vantage API**: Stock data provider
- **Tiingo API**: Alternative stock data provider
- **Polygon.io API**: Additional market data

## Features

- Direct source analysis from official company websites
- Filtering of unreliable sources and paid promotions
- AI-powered summaries of stock performance and outlook
- Advanced technical analysis with visual indicators
- AI-generated stock reports powered by Gemini
- Graceful handling of API rate limits with default data fallbacks
- Responsive design for all devices

## Running the Application

### Production Setup with Docker Compose

The easiest way to run the application is using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/yourusername/stockresearcher.git
cd stockresearcher

# Create a .env file with your API keys
echo "ALPHA_VANTAGE_API_KEY=your_api_key" > .env
echo "TIINGO_API_KEY=your_api_key" >> .env
echo "POLYGON_API_KEY=your_api_key" >> .env
echo "GEMINI_API_KEY=your_api_key" >> .env

# Build and start the containers
docker-compose up -d

# To view logs
docker-compose logs -f

# To stop the application
docker-compose down
```

The frontend will be available at http://localhost and the backend API at http://localhost:5001.

### Accessing the Application

Once running, you can access:
- Web interface: http://localhost
- API endpoint: http://localhost/api

### Rebuilding After Changes

If you make changes to the code, rebuild the containers:

```bash
docker-compose up -d --build
```

## API Keys

The application uses several external APIs for retrieving stock data:

- **Alpha Vantage**: Primary source for stock data 
- **Tiingo**: Fallback for when Alpha Vantage has rate limits
- **Polygon.io**: Additional data source for market information
- **Gemini AI**: Powers the AI analysis feature

You can set these API keys in the backend's `.env` file or as environment variables.

## Backend API Endpoints

- `GET /api/stocks` - Get a list of all available stocks
- `GET /api/stocks/:symbol` - Get detailed information for a specific stock
- `GET /api/search?symbol=:symbol` - Search for a stock by its ticker symbol
- `GET /api/technical-analysis/:symbol` - Get technical indicators for a stock
- `GET /api/technical/enhanced/:symbol` - Get enhanced technical metrics
- `GET /api/ai-analysis/:symbol` - Get AI-generated analysis report
- `GET /api/default-data/:symbol` - Get default data for common stocks when APIs are rate-limited

## Error Handling & Rate Limiting

The application includes several features to handle API rate limiting:

1. Multiple API fallbacks (Alpha Vantage → Tiingo → Web scraping)
2. Default data for common stocks when APIs are unavailable
3. Intelligent cache management to minimize API calls
4. User-friendly error messages with fallback options

## Development Setup

If you want to develop and modify the application locally:

### Frontend

```bash
cd stock-researcher
npm install
npm start
```

The frontend development server will run on http://localhost:3000

### Backend

```bash
cd stock-researcher-backend
pip install -r requirements.txt
python app.py
```

The backend development server will run on http://localhost:5001

## Using the AI Analysis Feature

The AI Analysis tab provides machine-generated insights about stocks using Gemini Pro:

1. Search for a stock symbol (e.g., AAPL)
2. Click on the "AI Analysis" tab
3. View the AI-generated report with:
   - Company situation summary
   - Technical analysis insights
   - Key strengths and risks
   - Short-term outlook

## Troubleshooting

- **API Rate Limit Errors**: If you see rate limit errors, the application will offer to use default data for common stocks. Alternatively, you can wait and try again later.
- **Docker Issues**: If containers fail to start, check `docker-compose logs` for errors.
- **Missing Data**: Some financial data may appear as "N/A" when APIs are limited. Try using the "?clear_cache=true" parameter on API endpoints to force refresh. 