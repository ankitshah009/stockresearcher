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
  const [newsData, setNewsData] = useState([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsError, setNewsError] = useState(null);
  const [enhancedMetrics, setEnhancedMetrics] = useState(null);
  const [enhancedLoading, setEnhancedLoading] = useState(false);
  const [enhancedError, setEnhancedError] = useState(null);
  
  useEffect(() => {
    const fetchStockData = async () => {
      try {
        const data = await api.getStockDetails(symbol);
        
        // Add reliableSources and unreliableSources if they don't exist
        if (!data.reliableSources && data.sources) {
          data.reliableSources = Object.entries(data.sources).map(([key, url]) => ({
            name: key.charAt(0).toUpperCase() + key.slice(1), // Capitalize first letter
            url: url
          }));
        }
        
        if (!data.unreliableSources) {
          data.unreliableSources = [];
        }
        
        // Map 52-week high/low properties
        if (!data.high52Week && data['52WeekHigh']) {
          data.high52Week = data['52WeekHigh'];
        }
        
        if (!data.low52Week && data['52WeekLow']) {
          data.low52Week = data['52WeekLow'];
        }
        
        // Add a summary if it doesn't exist
        if (!data.summary) {
          data.summary = `${data.name} (${data.symbol}) is currently trading at $${data.currentPrice}. ` +
            `The stock has changed by ${data.change >= 0 ? '+' : ''}${data.change} (${data.percentChange}%) recently. ` +
            `Data source: ${data.dataSource || 'Financial APIs'}`;
        }
        
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
      fetchNewsData(stockData.symbol);
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

  // Add a function to fetch news data
  const fetchNewsData = async (symbol) => {
    if (stockData && stockData.latestNews && stockData.latestNews.length > 0) {
      // News already exists in stockData, no need to fetch again
      return;
    }
    
    setNewsLoading(true);
    setNewsError(null);
    try {
      // Get news from Polygon API endpoint
      const response = await fetch(`/api/polygon/news/${symbol}?limit=10`);
      if (!response.ok) {
        throw new Error('Failed to fetch news data');
      }
      const data = await response.json();
      
      if (data && data.results) {
        setNewsData(data.results);
        // Add the news to stockData as well
        setStockData(prevData => ({
          ...prevData,
          latestNews: data.results.map(item => ({
            title: item.title,
            url: item.article_url,
            source: item.publisher.name,
            date: new Date(item.published_utc).toLocaleDateString()
          }))
        }));
      }
    } catch (error) {
      console.error('Error fetching news:', error);
      setNewsError(error.message);
    } finally {
      setNewsLoading(false);
    }
  };

  useEffect(() => {
    // Fetch enhanced technical metrics when the analysis tab is active
    if (activeTab === 'analysis' && stockData && !enhancedMetrics && !enhancedLoading) {
      const fetchEnhancedMetrics = async () => {
        setEnhancedLoading(true);
        try {
          const data = await api.getEnhancedTechnicalMetrics(symbol);
          setEnhancedMetrics(data);
          setEnhancedError(null);
        } catch (err) {
          console.error('Error fetching enhanced metrics:', err);
          setEnhancedError(err.error || 'Failed to load enhanced technical metrics');
        } finally {
          setEnhancedLoading(false);
        }
      };
      
      fetchEnhancedMetrics();
    }
  }, [activeTab, stockData, symbol, enhancedMetrics, enhancedLoading]);

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
            <span className="value">
              {stockData.marketCap && stockData.marketCap !== "N/A" 
                ? `$${stockData.marketCap}` 
                : (
                  <span className="unavailable">
                    <span className="unavailable-icon">ⓘ</span>
                    Not Available
                  </span>
                )
              }
            </span>
          </div>
          <div className="metric">
            <span className="label">P/E Ratio</span>
            <span className="value">
              {stockData.peRatio && stockData.peRatio !== "N/A" 
                ? stockData.peRatio 
                : (
                  <span className="unavailable">
                    <span className="unavailable-icon">ⓘ</span>
                    Not Available
                  </span>
                )
              }
            </span>
          </div>
          <div className="metric">
            <span className="label">52-Week High</span>
            <span className="value">
              {stockData.high52Week && stockData.high52Week !== "N/A" 
                ? `$${stockData.high52Week}` 
                : (
                  <span className="unavailable">
                    <span className="unavailable-icon">ⓘ</span>
                    Not Available
                  </span>
                )
              }
            </span>
          </div>
          <div className="metric">
            <span className="label">52-Week Low</span>
            <span className="value">
              {stockData.low52Week && stockData.low52Week !== "N/A" 
                ? `$${stockData.low52Week}` 
                : (
                  <span className="unavailable">
                    <span className="unavailable-icon">ⓘ</span>
                    Not Available
                  </span>
                )
              }
            </span>
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
          className={`tab ${activeTab === 'news' ? 'active' : ''}`} 
          onClick={() => setActiveTab('news')}
        >
          News
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
                    
                    {/* Price and Trend */}
                    <div className="trend-header">
                      <div className="current-trend">
                        <span className="trend-label">Current Trend:</span>
                        <span className={`trend-value ${technicalData.technicalAnalysis.trend === "Uptrend" ? "positive" : technicalData.technicalAnalysis.trend === "Downtrend" ? "negative" : "neutral"}`}>
                          {technicalData.technicalAnalysis.trend}
                          {technicalData.technicalAnalysis.trend === "Uptrend" && <span className="trend-icon">↗</span>}
                          {technicalData.technicalAnalysis.trend === "Downtrend" && <span className="trend-icon">↘</span>}
                          {technicalData.technicalAnalysis.trend === "Sideways" && <span className="trend-icon">↔</span>}
                        </span>
                      </div>
                      <div className="current-price">
                        <span className="price-label">Current Price:</span>
                        <span className="price-value">${technicalData.technicalAnalysis.price}</span>
                      </div>
                    </div>
                    
                    {/* RSI Indicator with Gauge */}
                    {technicalData.technicalAnalysis.momentum && (
                      <div className="indicator-card">
                        <h5>RSI Indicator</h5>
                        <div className="indicator-gauge">
                          <div className="gauge-container">
                            <div className="gauge-zones">
                              <div className="gauge-zone oversold">Oversold</div>
                              <div className="gauge-zone neutral">Neutral</div>
                              <div className="gauge-zone overbought">Overbought</div>
                            </div>
                            <div className="gauge-arrow" style={{ left: `${Math.min(Math.max(technicalData.technicalAnalysis.momentum.rsi, 0), 100)}%` }}>▼</div>
                            <div className="gauge-labels">
                              <span>0</span>
                              <span>30</span>
                              <span>70</span>
                              <span>100</span>
                            </div>
                          </div>
                          <div className="indicator-value">
                            RSI: <strong>{technicalData.technicalAnalysis.momentum.rsi.toFixed(1)}</strong> 
                            <span className={`indicator-zone ${technicalData.technicalAnalysis.momentum.rsiZone.toLowerCase()}`}>
                              ({technicalData.technicalAnalysis.momentum.rsiZone})
                            </span>
                          </div>
                          <div className="indicator-explanation">
                            <strong>What this means:</strong> {getRSIExplanation(technicalData.technicalAnalysis.momentum.rsi)}
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* Moving Averages Visualization */}
                    {technicalData.technicalAnalysis.movingAverages && (
                      <div className="indicator-card">
                        <h5>Moving Averages</h5>
                        <div className="ma-visualization">
                          <div className="ma-bars">
                            <div className="ma-bar-group">
                              <div className="ma-label">SMA20</div>
                              <div className={`ma-bar ${technicalData.technicalAnalysis.movingAverages.priceVsSMA20 > 0 ? 'positive' : 'negative'}`}>
                                <div className="ma-bar-fill" style={{ width: `${Math.min(Math.abs(technicalData.technicalAnalysis.movingAverages.priceVsSMA20), 30)}%` }}></div>
                                <span className="ma-bar-value">{technicalData.technicalAnalysis.movingAverages.priceVsSMA20.toFixed(2)}%</span>
                              </div>
                            </div>
                            <div className="ma-bar-group">
                              <div className="ma-label">SMA50</div>
                              <div className={`ma-bar ${technicalData.technicalAnalysis.movingAverages.priceVsSMA50 > 0 ? 'positive' : 'negative'}`}>
                                <div className="ma-bar-fill" style={{ width: `${Math.min(Math.abs(technicalData.technicalAnalysis.movingAverages.priceVsSMA50), 30)}%` }}></div>
                                <span className="ma-bar-value">{technicalData.technicalAnalysis.movingAverages.priceVsSMA50.toFixed(2)}%</span>
                              </div>
                            </div>
                            <div className="ma-bar-group">
                              <div className="ma-label">SMA200</div>
                              <div className={`ma-bar ${technicalData.technicalAnalysis.movingAverages.priceVsSMA200 > 0 ? 'positive' : 'negative'}`}>
                                <div className="ma-bar-fill" style={{ width: `${Math.min(Math.abs(technicalData.technicalAnalysis.movingAverages.priceVsSMA200), 30)}%` }}></div>
                                <span className="ma-bar-value">{technicalData.technicalAnalysis.movingAverages.priceVsSMA200.toFixed(2)}%</span>
                              </div>
                            </div>
                          </div>
                          <div className="indicator-explanation">
                            <strong>What this means:</strong> {getMAExplanation(technicalData.technicalAnalysis.movingAverages)}
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* Volatility Indicator */}
                    {technicalData.technicalAnalysis.volatility && (
                      <div className="indicator-card">
                        <h5>Volatility (ATR)</h5>
                        <div className="volatility-indicator">
                          <div className="volatility-value">
                            <div className="volatility-metric">
                              <span className="volatility-label">ATR:</span>
                              <span className="volatility-number">${technicalData.technicalAnalysis.volatility.atr.toFixed(2)}</span>
                            </div>
                            <div className="volatility-metric">
                              <span className="volatility-label">ATR%:</span>
                              <span className="volatility-number">{technicalData.technicalAnalysis.volatility.atrPercent.toFixed(2)}%</span>
                            </div>
                          </div>
                          <div className="volatility-level">
                            <div className="volatility-bars">
                              <div className={`volatility-bar ${getVolatilityLevel(technicalData.technicalAnalysis.volatility.atrPercent) === 'low' ? 'active' : ''}`}>Low</div>
                              <div className={`volatility-bar ${getVolatilityLevel(technicalData.technicalAnalysis.volatility.atrPercent) === 'medium' ? 'active' : ''}`}>Medium</div>
                              <div className={`volatility-bar ${getVolatilityLevel(technicalData.technicalAnalysis.volatility.atrPercent) === 'high' ? 'active' : ''}`}>High</div>
                            </div>
                          </div>
                          <div className="indicator-explanation">
                            <strong>What this means:</strong> {getVolatilityExplanation(technicalData.technicalAnalysis.volatility.atrPercent)}
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* Volume Analysis */}
                    {technicalData.technicalAnalysis.volume && (
                      <div className="indicator-card">
                        <h5>Volume Analysis</h5>
                        <div className="volume-indicator">
                          <div className="volume-ratio">
                            <div className="volume-gauge">
                              <div className="volume-fill" style={{ width: `${Math.min(technicalData.technicalAnalysis.volume.ratio * 100, 100)}%` }}></div>
                            </div>
                            <div className="volume-labels">
                              <span>0%</span>
                              <span>50%</span>
                              <span>100%</span>
                              <span>150%+</span>
                            </div>
                          </div>
                          <div className="volume-data">
                            <div>Current: {formatLargeNumber(technicalData.technicalAnalysis.volume.current)}</div>
                            <div>20-Day Avg: {formatLargeNumber(technicalData.technicalAnalysis.volume.average20Day)}</div>
                            <div>Ratio: {technicalData.technicalAnalysis.volume.ratio.toFixed(2)}x</div>
                          </div>
                          <div className="indicator-explanation">
                            <strong>What this means:</strong> {getVolumeExplanation(technicalData.technicalAnalysis.volume.ratio)}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {/* Relative Strength vs SPY Visualization */}
                {technicalData.relativeStrength && Object.keys(technicalData.relativeStrength).length > 0 && (
                  <div className="relative-strength">
                    <h4>Relative Strength (vs S&P 500)</h4>
                    <div className="rs-cards">
                      {Object.entries(technicalData.relativeStrength).map(([period, data]) => (
                        <div key={period} className="rs-card">
                          <div className="rs-period">{formatPeriod(period)}</div>
                          <div className="rs-comparison">
                            <div className="rs-ticker">
                              <div className="rs-label">{stockData.symbol}</div>
                              <div className={`rs-bar ${data.stock_performance >= 0 ? 'positive' : 'negative'}`}>
                                <div className="rs-bar-fill" style={{ width: `${Math.min(Math.abs(data.stock_performance), 30)}%` }}></div>
                                <span className="rs-bar-value">{data.stock_performance.toFixed(2)}%</span>
                              </div>
                            </div>
                            <div className="rs-spy">
                              <div className="rs-label">SPY</div>
                              <div className={`rs-bar ${data.spy_performance >= 0 ? 'positive' : 'negative'}`}>
                                <div className="rs-bar-fill" style={{ width: `${Math.min(Math.abs(data.spy_performance), 30)}%` }}></div>
                                <span className="rs-bar-value">{data.spy_performance.toFixed(2)}%</span>
                              </div>
                            </div>
                          </div>
                          <div className={`rs-status ${data.outperforming ? 'positive' : 'negative'}`}>
                            {data.outperforming 
                              ? `Outperforming by ${Math.abs(data.relative_strength).toFixed(2)}%` 
                              : `Underperforming by ${Math.abs(data.relative_strength).toFixed(2)}%`
                            }
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="rs-summary">
                      <strong>Summary:</strong> {getRelativeStrengthSummary(technicalData.relativeStrength)}
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
                          <div className="pattern-icon">{getPatternIcon(pattern.name)}</div>
                          <div className="pattern-details">
                            <span className="pattern-name">{pattern.name || 'Pattern'}</span>
                            {pattern.confidence && (
                              <div className="pattern-confidence">
                                <div className="confidence-label">Confidence:</div>
                                <div className="confidence-bar">
                                  <div className="confidence-fill" style={{ width: `${pattern.confidence}%` }}></div>
                                </div>
                                <div className="confidence-value">{pattern.confidence}%</div>
                              </div>
                            )}
                            {pattern.priceTarget && (
                              <span className="pattern-target">
                                Target: ${pattern.priceTarget}
                              </span>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {/* Enhanced Metrics Section */}
                {enhancedMetrics && (
                  <div className="enhanced-metrics-section">
                    <h4>Advanced Financial Metrics</h4>
                    
                    {/* Volatility Card */}
                    <div className="metrics-card">
                      <h5>Volatility & Risk</h5>
                      <div className="metrics-grid">
                        <div className="metric-item">
                          <span className="metric-label">Daily Volatility</span>
                          <span className="metric-value">
                            {enhancedMetrics.volatility.daily}%
                          </span>
                        </div>
                        <div className="metric-item">
                          <span className="metric-label">Annualized Volatility</span>
                          <span className="metric-value">
                            {enhancedMetrics.volatility.annualized}%
                          </span>
                        </div>
                        <div className="metric-item">
                          <span className="metric-label">Max Drawdown</span>
                          <span className="metric-value">
                            {enhancedMetrics.volatility.maxDrawdown !== "N/A" ? 
                              `${enhancedMetrics.volatility.maxDrawdown}%` : "N/A"}
                          </span>
                        </div>
                        <div className="metric-item">
                          <span className="metric-label">S&P Correlation</span>
                          <span className="metric-value">
                            {enhancedMetrics.spyCorrelation !== "N/A" ? 
                              enhancedMetrics.spyCorrelation : "N/A"}
                          </span>
                        </div>
                      </div>
                    </div>
                    
                    {/* Valuation Metrics */}
                    <div className="metrics-card">
                      <h5>Valuation Metrics</h5>
                      <div className="metrics-grid">
                        <div className="metric-item">
                          <span className="metric-label">Beta</span>
                          <span className="metric-value">
                            {enhancedMetrics.marketMetrics.beta !== "N/A" ? 
                              enhancedMetrics.marketMetrics.beta : "N/A"}
                          </span>
                        </div>
                        <div className="metric-item">
                          <span className="metric-label">Forward P/E</span>
                          <span className="metric-value">
                            {enhancedMetrics.marketMetrics.forwardPE !== "N/A" ? 
                              enhancedMetrics.marketMetrics.forwardPE : "N/A"}
                          </span>
                        </div>
                        <div className="metric-item">
                          <span className="metric-label">P/S Ratio</span>
                          <span className="metric-value">
                            {enhancedMetrics.marketMetrics.priceToSalesRatio !== "N/A" ? 
                              enhancedMetrics.marketMetrics.priceToSalesRatio : "N/A"}
                          </span>
                        </div>
                        <div className="metric-item">
                          <span className="metric-label">P/B Ratio</span>
                          <span className="metric-value">
                            {enhancedMetrics.marketMetrics.priceToBookRatio !== "N/A" ? 
                              enhancedMetrics.marketMetrics.priceToBookRatio : "N/A"}
                          </span>
                        </div>
                      </div>
                    </div>
                    
                    {/* Support and Resistance */}
                    <div className="metrics-card">
                      <h5>Price Levels</h5>
                      <div className="price-levels-chart">
                        <div className="price-line-container">
                          {/* Only show if we have valid price levels */}
                          {enhancedMetrics.priceLevels.resistance.strong !== "N/A" && (
                            <>
                              <div className="price-line resistance-strong" 
                                style={{ top: '0%' }}>
                                <span className="price-label">Strong Resistance</span>
                                <span className="price-value">${enhancedMetrics.priceLevels.resistance.strong}</span>
                              </div>
                              <div className="price-line resistance-weak" 
                                style={{ top: '25%' }}>
                                <span className="price-label">Weak Resistance</span>
                                <span className="price-value">${enhancedMetrics.priceLevels.resistance.weak}</span>
                              </div>
                              <div className="price-line current-price" 
                                style={{ top: '50%' }}>
                                <span className="price-label">Current</span>
                                <span className="price-value">${enhancedMetrics.priceLevels.current}</span>
                              </div>
                              <div className="price-line support-weak" 
                                style={{ top: '75%' }}>
                                <span className="price-label">Weak Support</span>
                                <span className="price-value">${enhancedMetrics.priceLevels.support.weak}</span>
                              </div>
                              <div className="price-line support-strong" 
                                style={{ top: '100%' }}>
                                <span className="price-label">Strong Support</span>
                                <span className="price-value">${enhancedMetrics.priceLevels.support.strong}</span>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="price-levels-explanation">
                        <p>
                          <strong>What this means:</strong> Support and resistance levels are price points where 
                          a stock historically struggles to move beyond. Support is where downward trends tend to pause, 
                          while resistance is where upward trends often stall.
                        </p>
                      </div>
                    </div>
                    
                    {/* Dividend Information */}
                    {enhancedMetrics.marketMetrics.dividend && 
                     enhancedMetrics.marketMetrics.dividend.yield !== "N/A" && 
                     enhancedMetrics.marketMetrics.dividend.yield !== "0.00" && (
                      <div className="metrics-card">
                        <h5>Dividend Information</h5>
                        <div className="metrics-grid">
                          <div className="metric-item">
                            <span className="metric-label">Dividend Yield</span>
                            <span className="metric-value">
                              {enhancedMetrics.marketMetrics.dividend.yield !== "N/A" ? 
                                `${enhancedMetrics.marketMetrics.dividend.yield}%` : "N/A"}
                            </span>
                          </div>
                          <div className="metric-item">
                            <span className="metric-label">Dividend Per Share</span>
                            <span className="metric-value">
                              {enhancedMetrics.marketMetrics.dividend.perShare !== "N/A" ? 
                                `$${enhancedMetrics.marketMetrics.dividend.perShare}` : "N/A"}
                            </span>
                          </div>
                          <div className="metric-item">
                            <span className="metric-label">Ex-Dividend Date</span>
                            <span className="metric-value">
                              {enhancedMetrics.marketMetrics.dividend.date !== "N/A" ? 
                                enhancedMetrics.marketMetrics.dividend.date : "N/A"}
                            </span>
                          </div>
                          <div className="metric-item">
                            <span className="metric-label">Payout Ratio</span>
                            <span className="metric-value">
                              {enhancedMetrics.marketMetrics.dividend.payoutRatio !== "N/A" ? 
                                `${enhancedMetrics.marketMetrics.dividend.payoutRatio}%` : "N/A"}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {/* Show loading indicator for enhanced metrics */}
                {enhancedLoading && !enhancedMetrics && (
                  <div className="loading-indicator">
                    <p>Loading advanced metrics...</p>
                  </div>
                )}
                
                {/* Show error for enhanced metrics */}
                {enhancedError && !enhancedMetrics && (
                  <div className="error-message">
                    <p>Error loading advanced metrics: {enhancedError}</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="not-found">No technical data available.</div>
            )}
            
            {/* Technical Analysis Legend and Help */}
            {technicalData && (
              <div className="technical-help">
                <h4>Understanding Technical Analysis</h4>
                <div className="help-content">
                  <p>Technical analysis uses historical price and volume data to identify patterns and predict future price movements.</p>
                  <div className="key-indicators">
                    <div className="indicator-help">
                      <strong>RSI (Relative Strength Index):</strong> Measures momentum on a scale of 0-100. Values below 30 indicate oversold conditions (potential buy), while values above 70 indicate overbought conditions (potential sell).
                    </div>
                    <div className="indicator-help">
                      <strong>Moving Averages:</strong> Show the average closing price over a period. Price above MA indicates bullish trend, below indicates bearish trend.
                    </div>
                    <div className="indicator-help">
                      <strong>ATR (Average True Range):</strong> Measures market volatility. Higher values indicate more volatility and potentially higher risk.
                    </div>
                    <div className="indicator-help">
                      <strong>Relative Strength:</strong> Compares performance against a benchmark (S&P 500). Outperformance may indicate stronger relative momentum.
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'news' && (
          <div className="news-tab">
            <h3>Latest News</h3>
            {newsLoading ? (
              <div className="loading-spinner">Loading news...</div>
            ) : newsError ? (
              <div className="error-message">Error: {newsError}</div>
            ) : stockData && stockData.latestNews && stockData.latestNews.length > 0 ? (
              <ul className="news-list">
                {stockData.latestNews.map((article, index) => (
                  <li key={index} className="news-item">
                    <a href={article.url} target="_blank" rel="noopener noreferrer" className="news-title">
                      {article.title}
                    </a>
                    <div className="news-metadata">
                      <span className="news-source">{article.source || 'Financial News'}</span>
                      <span className="news-date">{article.date || 'Recent'}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No recent news found for {stockData.name}.</p>
            )}
          </div>
        )}
        
        {activeTab === 'sources' && (
          <div className="sources-tab">
            <h3>Direct Source Analysis</h3>
            <p>
              Our AI has analyzed data directly from {stockData.name}'s official sources:
            </p>
            {stockData.reliableSources && stockData.reliableSources.length > 0 ? (
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
            ) : (
              <p>No reliable sources available.</p>
            )}
          </div>
        )}
        
        {activeTab === 'filtered' && (
          <div className="filtered-tab">
            <h3 className="noise-filter-heading">Filtered Noise</h3>
            <p>
              We've identified and filtered out these potentially unreliable sources:
            </p>
            {stockData.unreliableSources && stockData.unreliableSources.length > 0 ? (
              <ul className="filtered-noise">
                {stockData.unreliableSources.map((source, index) => (
                  <li key={index}>
                    <span className="source-name">{source.name}</span>
                    <span className="reliability-badge low">{source.reason}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No unreliable sources identified.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// Add helper functions at the end of the StockDetail component, after all the return statement

// Helper function to format large numbers (millions, billions)
const formatLargeNumber = (num) => {
  if (!num) return "N/A";
  
  if (num >= 1000000000) {
    return `${(num / 1000000000).toFixed(2)}B`;
  } else if (num >= 1000000) {
    return `${(num / 1000000).toFixed(2)}M`;
  } else {
    return num.toLocaleString();
  }
};

// Helper function to explain RSI values
const getRSIExplanation = (rsi) => {
  if (rsi < 30) {
    return "The stock is currently oversold, which may indicate a potential buying opportunity as the price could rebound. However, in strong downtrends, oversold conditions can persist.";
  } else if (rsi > 70) {
    return "The stock is currently overbought, which may indicate a potential selling opportunity as the price could pull back. However, in strong uptrends, overbought conditions can persist.";
  } else {
    return "The stock is currently in a neutral momentum zone, neither overbought nor oversold.";
  }
};

// Helper function to explain Moving Average values
const getMAExplanation = (ma) => {
  if (ma.priceVsSMA20 > 0 && ma.priceVsSMA50 > 0 && ma.priceVsSMA200 > 0) {
    return "Price is trading above all key moving averages, indicating a strong bullish trend.";
  } else if (ma.priceVsSMA20 < 0 && ma.priceVsSMA50 < 0 && ma.priceVsSMA200 < 0) {
    return "Price is trading below all key moving averages, indicating a strong bearish trend.";
  } else if (ma.priceVsSMA20 > 0 && ma.priceVsSMA50 < 0) {
    return "Price is above short-term but below medium-term averages, suggesting a potential trend change or rebound.";
  } else {
    return "Mixed signals from moving averages indicate potential consolidation or trend transition.";
  }
};

// Helper function to determine volatility level
const getVolatilityLevel = (atrPercent) => {
  if (atrPercent < 3) return 'low';
  if (atrPercent < 8) return 'medium';
  return 'high';
};

// Helper function to explain volatility values
const getVolatilityExplanation = (atrPercent) => {
  if (atrPercent < 3) {
    return "Low volatility suggests stable price action with smaller price swings, potentially better for conservative investors.";
  } else if (atrPercent < 8) {
    return "Medium volatility indicates moderate price fluctuations, balancing potential returns with risk.";
  } else {
    return "High volatility shows significant price swings, offering higher potential returns but with increased risk.";
  }
};

// Helper function to explain volume values
const getVolumeExplanation = (ratio) => {
  if (ratio < 0.5) {
    return "Volume is significantly below average, indicating low interest or conviction in the current price movement.";
  } else if (ratio < 0.8) {
    return "Volume is below average, suggesting moderate interest in current price action.";
  } else if (ratio < 1.2) {
    return "Volume is near average levels, indicating typical trading activity.";
  } else if (ratio < 2) {
    return "Above average volume suggests strong interest and may confirm the validity of the current price trend.";
  } else {
    return "Volume is exceptionally high, indicating significant market interest and potential trend acceleration or reversal points.";
  }
};

// Helper function to format period text
const formatPeriod = (period) => {
  switch(period) {
    case '21_day': return 'Short-term (21 days)';
    case '63_day': return 'Medium-term (63 days)';
    case '126_day': return 'Long-term (126 days)';
    default: return period.replace('_', ' ');
  }
};

// Helper function to get relative strength summary
const getRelativeStrengthSummary = (rs) => {
  const periods = Object.keys(rs);
  const underperforming = periods.filter(p => !rs[p].outperforming).length;
  const symbol = rs[periods[0]]?.symbol || 'This stock';
  
  if (underperforming === periods.length) {
    return `${symbol} is underperforming the S&P 500 across all time periods, which may indicate weakness relative to the broader market.`;
  } else if (underperforming === 0) {
    return `${symbol} is outperforming the S&P 500 across all time periods, which may indicate strength relative to the broader market.`;
  } else if (rs['21_day'] && rs['21_day'].outperforming && rs['63_day'] && !rs['63_day'].outperforming) {
    return `${symbol} is showing recent strength vs the S&P 500 in the short-term, but still underperforming in longer time frames.`;
  } else {
    return `${symbol} shows mixed performance relative to the S&P 500, outperforming in some periods while underperforming in others.`;
  }
};

// Helper function to get pattern icon
const getPatternIcon = (patternName) => {
  if (!patternName) return '📊';
  
  const pattern = patternName.toLowerCase();
  if (pattern.includes('head and shoulders')) return '👑';
  if (pattern.includes('double top')) return '🔝🔝';
  if (pattern.includes('double bottom')) return '⏬⏬';
  if (pattern.includes('triangle')) return '◢◣';
  if (pattern.includes('wedge')) return '⊿';
  if (pattern.includes('channel')) return '‖';
  if (pattern.includes('flag')) return '🚩';
  if (pattern.includes('cup')) return '☕';
  if (pattern.includes('island')) return '🏝️';
  if (pattern.includes('gap')) return '↕️';
  
  return '📊';
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
