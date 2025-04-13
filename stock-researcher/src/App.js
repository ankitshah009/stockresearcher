import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useParams, useNavigate } from 'react-router-dom';
import api from './services/api';
import './App.css';

// Main components
const Home = () => {
  const navigate = useNavigate();
  const [trendingStocks, setTrendingStocks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTrendingStocks = async () => {
      try {
        const stocks = await api.getAllStocks();
        setTrendingStocks(stocks);
      } catch (err) {
        console.error('Error fetching trending stocks:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchTrendingStocks();
  }, []);

  const handleStockClick = (symbol) => {
    navigate(`/stock/${symbol}`);
  };

  return (
    <div className="home-container">
      <h1>Welcome to Stock Researcher</h1>
      <p>Your trusted source for reliable stock analysis and information</p>
      
      <div className="feature-cards">
        <div className="feature-card">
          <h3>Direct Source Analysis</h3>
          <p>Access primary data directly from company websites and trusted sources</p>
        </div>
        <div className="feature-card">
          <h3>Filter the Noise</h3>
          <p>Cut through biased information and paid promotions in the financial world</p>
        </div>
        <div className="feature-card">
          <h3>AI-Powered Research</h3>
          <p>Leverage intelligent analysis to find what matters for your investment decisions</p>
        </div>
      </div>

      <div className="trending-stocks-section">
        <h2>Trending Stocks</h2>
        {loading ? (
          <div className="stocks-loading">Loading trending stocks...</div>
        ) : (
          <div className="stocks-grid">
            {trendingStocks.map((stock) => (
              <div 
                key={stock.symbol} 
                className="stock-card" 
                onClick={() => handleStockClick(stock.symbol)}
              >
                <div className="stock-symbol">{stock.symbol}</div>
                <div className="stock-name">{stock.name}</div>
                <div className="stock-price">${stock.currentPrice}</div>
                <div className={`stock-change ${stock.change >= 0 ? 'positive' : 'negative'}`}>
                  {stock.change >= 0 ? '+' : ''}{stock.change} ({stock.percentChange}%)
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      <div className="cta-section">
        <h2>Start Your Research Now</h2>
        <p>Search for any stock to get detailed, reliable analysis</p>
        <button onClick={() => navigate('/search')} className="cta-button">
          Search Stocks
        </button>
      </div>
    </div>
  );
};

const StockSearch = () => {
  const [ticker, setTicker] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [recentSearches, setRecentSearches] = useState(() => {
    const saved = localStorage.getItem('recentSearches');
    return saved ? JSON.parse(saved) : [];
  });

  useEffect(() => {
    localStorage.setItem('recentSearches', JSON.stringify(recentSearches));
  }, [recentSearches]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!ticker) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const result = await api.searchStock(ticker);
      setSearchResults(result);
      
      // Add to recent searches
      if (result) {
        const newSearch = {
          symbol: result.symbol,
          name: result.name
        };
        
        setRecentSearches(prev => {
          const filtered = prev.filter(item => item.symbol !== newSearch.symbol);
          return [newSearch, ...filtered].slice(0, 5);
        });
      }
    } catch (err) {
      setError('Error searching for stock. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleRecentSearch = (symbol) => {
    setTicker(symbol);
    handleSearch({ preventDefault: () => {} });
  };

  return (
    <div className="stock-search-container">
      <h2>Search for a Stock</h2>
      <form onSubmit={handleSearch} className="search-form">
        <input
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Enter stock ticker (e.g., AAPL)"
          className="search-input"
        />
        <button type="submit" className="search-button" disabled={loading}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {error && <div className="error-message">{error}</div>}
      
      {recentSearches.length > 0 && !searchResults && (
        <div className="recent-searches">
          <h3>Recent Searches</h3>
          <div className="recent-searches-list">
            {recentSearches.map((item, index) => (
              <div 
                key={index} 
                className="recent-search-item" 
                onClick={() => handleRecentSearch(item.symbol)}
              >
                <span className="recent-symbol">{item.symbol}</span>
                <span className="recent-name">{item.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {searchResults && (
        <div className="search-results">
          <h3>{searchResults.name}</h3>
          <div className="stock-price">
            <span className="current-price">${searchResults.currentPrice}</span>
            <span className={`price-change ${searchResults.change >= 0 ? 'positive' : 'negative'}`}>
              {searchResults.change >= 0 ? '+' : ''}{searchResults.change} ({searchResults.percentChange}%)
            </span>
          </div>
          <div className="action-buttons">
            <Link to={`/stock/${searchResults.symbol}`} className="view-analysis-btn">
              View Detailed Analysis
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};

const StockDetail = () => {
  const { symbol } = useParams();
  const [stockData, setStockData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('analysis');
  const [technicalData, setTechnicalData] = useState(null);
  const [technicalLoading, setTechnicalLoading] = useState(false);
  const [technicalError, setTechnicalError] = useState(null);
  
  useEffect(() => {
    const fetchStockData = async () => {
      try {
        const data = await api.getStockDetails(symbol);
        setStockData(data);
        setLoading(false);
      } catch (err) {
        setError('Error loading stock details. Please try again.');
        setLoading(false);
        console.error(err);
      }
    };
    
    fetchStockData();
  }, [symbol]);
  
  // Fetch technical analysis data when stockData changes
  useEffect(() => {
    if (stockData && stockData.symbol) {
      fetchTechnicalData(stockData.symbol);
    }
  }, [stockData]);
  
  // Function to fetch technical analysis data
  const fetchTechnicalData = async (symbol) => {
    setTechnicalLoading(true);
    setTechnicalError(null);
    try {
      const response = await fetch(`/api/technical-analysis/${symbol}`);
      if (!response.ok) {
        throw new Error('Failed to fetch technical data');
      }
      const data = await response.json();
      setTechnicalData(data);
    } catch (error) {
      console.error('Error fetching technical data:', error);
      setTechnicalError(error.message);
    } finally {
      setTechnicalLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading stock details...</div>;
  }
  
  if (error) {
    return <div className="error-message">{error}</div>;
  }
  
  if (!stockData) {
    return <div className="not-found">Stock not found.</div>;
  }
  
  return (
    <div className="stock-detail-container">
      <div className="stock-header">
        <h2>{stockData.name} ({stockData.symbol})</h2>
        <div className="stock-badge">{stockData.change >= 0 ? 'BULLISH' : 'BEARISH'}</div>
      </div>
      
      <div className="stock-overview">
        <div className="price-section">
          <h3>${stockData.currentPrice}</h3>
          <span className={`change ${stockData.change >= 0 ? 'positive' : 'negative'}`}>
            {stockData.change >= 0 ? '+' : ''}{stockData.change} ({stockData.percentChange}%)
          </span>
          <p className="last-updated">Last updated: {new Date().toLocaleDateString()}</p>
        </div>
        
        <div className="key-metrics">
          <div className="metric">
            <span className="label">Market Cap</span>
            <span className="value">{stockData.marketCap}</span>
          </div>
          <div className="metric">
            <span className="label">P/E Ratio</span>
            <span className="value">{stockData.peRatio}</span>
          </div>
          <div className="metric">
            <span className="label">52-Week High</span>
            <span className="value">${stockData.high52Week}</span>
          </div>
          <div className="metric">
            <span className="label">52-Week Low</span>
            <span className="value">${stockData.low52Week}</span>
          </div>
        </div>
      </div>
      
      <div className="tabs">
        <div 
          className={`tab ${activeTab === 'analysis' ? 'active' : ''}`} 
          onClick={() => setActiveTab('analysis')}
        >
          Summary
        </div>
        <div 
          className={`tab ${activeTab === 'analyst' ? 'active' : ''}`} 
          onClick={() => setActiveTab('analyst')}
        >
          Analyst Views
        </div>
        <div 
          className={`tab ${activeTab === 'technical' ? 'active' : ''}`} 
          onClick={() => setActiveTab('technical')}
        >
          Technical Analysis
        </div>
        <div 
          className={`tab ${activeTab === 'sources' ? 'active' : ''}`} 
          onClick={() => setActiveTab('sources')}
        >
          Sources
        </div>
        <div 
          className={`tab ${activeTab === 'filtered' ? 'active' : ''}`} 
          onClick={() => setActiveTab('filtered')}
        >
          Filtered Noise
        </div>
      </div>
      
      <div className="tab-content">
        {activeTab === 'analysis' && (
          <div className="analysis-tab">
            <div className="recommendation-section">
              <h3>AI-Powered Summary</h3>
              <p>{stockData.summary}</p>
            </div>
          </div>
        )}
        
        {activeTab === 'analyst' && (
          <div className="analyst-tab">
            <h3>Analyst Views</h3>
            <p>
              Our AI has analyzed data directly from {stockData.name}'s official sources:
            </p>
            <ul className="source-list">
              {stockData.reliableSources.map((source, index) => (
                <li key={index}>
                  <a href={source.url} target="_blank" rel="noopener noreferrer">
                    {source.name}
                  </a>
                  <span className="reliability-badge high">High Reliability</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        
        {activeTab === 'technical' && (
          <div className="technical-tab">
            <h3>Advanced Technical Analysis</h3>
            {technicalLoading ? (
              <div className="loading-spinner">Loading technical analysis...</div>
            ) : technicalError ? (
              <div className="error-message">Error: {technicalError}</div>
            ) : technicalData ? (
              <div className="technical-analysis">
                {/* Technical Analysis Summary */}
                {technicalData.technicalAnalysis && (
                  <div className="trend-summary">
                    <h4>Trend Analysis</h4>
                    <div className="technical-metrics">
                      {Object.keys(technicalData.technicalAnalysis).map((key) => (
                        <div key={key} className="metric-item">
                          <span className="metric-label">{key}:</span>
                          <span className="metric-value">{JSON.stringify(technicalData.technicalAnalysis[key])}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Relative Strength */}
                {technicalData.relativeStrength && Object.keys(technicalData.relativeStrength).length > 0 && (
                  <div className="relative-strength">
                    <h4>Relative Strength (vs SPY)</h4>
                    <div className="rs-metrics">
                      {Object.keys(technicalData.relativeStrength).map((key) => (
                        <div key={key} className="rs-item">
                          <span className="rs-label">{key}:</span>
                          <span className="rs-value">{JSON.stringify(technicalData.relativeStrength[key])}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Chart Patterns */}
                {technicalData.patterns && technicalData.patterns.length > 0 && (
                  <div className="chart-patterns">
                    <h4>Detected Chart Patterns</h4>
                    <ul className="pattern-list">
                      {technicalData.patterns.map((pattern, index) => (
                        <li key={index} className="pattern-item">
                          <span className="pattern-name">{pattern.name || 'Pattern'}</span>
                          {pattern.confidence && (
                            <span className="pattern-confidence">
                              Confidence: {pattern.confidence}%
                            </span>
                          )}
                          {pattern.priceTarget && (
                            <span className="pattern-target">
                              Target: ${pattern.priceTarget}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {/* Volume Profile */}
                {technicalData.volumeProfile && Object.keys(technicalData.volumeProfile).length > 0 && (
                  <div className="volume-profile">
                    <h4>Volume Profile (60-Day)</h4>
                    <div className="volume-metrics">
                      {Object.keys(technicalData.volumeProfile).map((key) => (
                        <div key={key} className="volume-item">
                          <span className="volume-label">{key}:</span>
                          <span className="volume-value">{JSON.stringify(technicalData.volumeProfile[key])}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="not-found">No technical data available.</div>
            )}
          </div>
        )}
        
        {activeTab === 'sources' && (
          <div className="sources-tab">
            <h3>Direct Source Analysis</h3>
            <p>
              Our AI has analyzed data directly from {stockData.name}'s official sources:
            </p>
            <ul className="source-list">
              {stockData.reliableSources.map((source, index) => (
                <li key={index}>
                  <a href={source.url} target="_blank" rel="noopener noreferrer">
                    {source.name}
                  </a>
                  <span className="reliability-badge high">High Reliability</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        
        {activeTab === 'filtered' && (
          <div className="filtered-tab">
            <h3 className="noise-filter-heading">Filtered Noise</h3>
            <p>
              We've identified and filtered out these potentially unreliable sources:
            </p>
            <ul className="filtered-noise">
              {stockData.unreliableSources.map((source, index) => (
                <li key={index}>
                  <span className="source-name">{source.name}</span>
                  <span className="reliability-badge low">{source.reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

function App() {
  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <div className="logo">
            <Link to="/">StockResearcher</Link>
          </div>
          <ul className="nav-links">
            <li><Link to="/">Home</Link></li>
            <li><Link to="/search">Search Stocks</Link></li>
          </ul>
        </nav>
        
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/search" element={<StockSearch />} />
            <Route path="/stock/:symbol" element={<StockDetail />} />
          </Routes>
        </main>
        
        <footer className="footer">
          <div className="footer-content">
            <div className="footer-logo">StockResearcher</div>
            <p>Providing reliable stock analysis powered by AI</p>
            <div className="footer-links">
              <a href="#">Terms of Use</a>
              <a href="#">Privacy Policy</a>
              <a href="#">Contact Us</a>
            </div>
            <p className="copyright">© {new Date().getFullYear()} Stock Researcher</p>
          </div>
        </footer>
      </div>
    </Router>
  );
}

export default App;
