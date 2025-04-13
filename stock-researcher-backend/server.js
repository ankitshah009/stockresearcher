const express = require('express');
const cors = require('cors');
const axios = require('axios');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());

// Mock data for now - in a real app, you would use a real financial API
const mockStocks = {
  'AAPL': {
    symbol: 'AAPL',
    name: 'Apple Inc.',
    currentPrice: 175.34,
    change: 2.45,
    percentChange: 1.42,
    marketCap: '2.7T',
    peRatio: '28.5',
    high52Week: '182.94',
    low52Week: '124.17',
    reliableSources: [
      { url: 'https://investor.apple.com', name: 'Investor Relations Website', reliability: 'high' },
      { url: 'https://www.apple.com/newsroom/', name: 'Apple Newsroom', reliability: 'high' },
      { url: 'https://www.sec.gov/edgar/browse/?CIK=320193', name: 'SEC Filings', reliability: 'high' }
    ],
    unreliableSources: [
      { name: 'StockPromoter.com', reason: 'Paid Promotion' },
      { name: 'InvestorBuzz', reason: 'Clickbait Content' },
      { name: 'TrendTraderDaily', reason: 'Unverified Claims' }
    ],
    summary: 'Based on our analysis of reliable sources, Apple\'s recent product announcements and strong financial performance indicate continued growth potential. However, investors should be aware of increasing competition in key markets and potential regulatory challenges.'
  },
  'MSFT': {
    symbol: 'MSFT',
    name: 'Microsoft Corporation',
    currentPrice: 417.88,
    change: 3.25,
    percentChange: 0.78,
    marketCap: '3.1T',
    peRatio: '36.2',
    high52Week: '425.31',
    low52Week: '309.98',
    reliableSources: [
      { url: 'https://www.microsoft.com/en-us/investor', name: 'Investor Relations Website', reliability: 'high' },
      { url: 'https://news.microsoft.com/', name: 'Microsoft News', reliability: 'high' },
      { url: 'https://www.sec.gov/edgar/browse/?CIK=789019', name: 'SEC Filings', reliability: 'high' }
    ],
    unreliableSources: [
      { name: 'TechStockGuru.com', reason: 'Paid Promotion' },
      { name: 'MarketMoverToday', reason: 'Clickbait Content' },
      { name: 'StockTipAlerts', reason: 'Unverified Claims' }
    ],
    summary: 'Microsoft continues to show strong growth in its cloud services segment, with Azure revenue increasing significantly year-over-year. The company\'s diverse product portfolio and strategic acquisitions position it well for future growth in AI and enterprise solutions.'
  },
  'AMZN': {
    symbol: 'AMZN',
    name: 'Amazon.com Inc.',
    currentPrice: 182.41,
    change: -0.95,
    percentChange: -0.52,
    marketCap: '1.9T',
    peRatio: '42.7',
    high52Week: '189.77',
    low52Week: '118.35',
    reliableSources: [
      { url: 'https://ir.aboutamazon.com/', name: 'Investor Relations Website', reliability: 'high' },
      { url: 'https://www.aboutamazon.com/news', name: 'Amazon News', reliability: 'high' },
      { url: 'https://www.sec.gov/edgar/browse/?CIK=1018724', name: 'SEC Filings', reliability: 'high' }
    ],
    unreliableSources: [
      { name: 'RetailStockBets', reason: 'Paid Promotion' },
      { name: 'TechMomentumWatch', reason: 'Clickbait Content' },
      { name: 'GigEconomyGurus', reason: 'Unverified Claims' }
    ],
    summary: 'Amazon continues to dominate e-commerce and cloud services with AWS. Recent investments in logistics and fulfillment will likely strengthen their competitive position, though regulatory scrutiny remains a concern in multiple markets.'
  }
};

// Routes
// Get all stocks (simplified list)
app.get('/api/stocks', (req, res) => {
  const stockList = Object.values(mockStocks).map(stock => ({
    symbol: stock.symbol,
    name: stock.name,
    currentPrice: stock.currentPrice,
    change: stock.change,
    percentChange: stock.percentChange
  }));
  
  res.json(stockList);
});

// Get detailed info for a specific stock
app.get('/api/stocks/:symbol', (req, res) => {
  const symbol = req.params.symbol.toUpperCase();
  const stock = mockStocks[symbol];
  
  if (!stock) {
    return res.status(404).json({ message: `Stock with symbol ${symbol} not found` });
  }
  
  res.json(stock);
});

// Search for a stock by symbol
app.get('/api/search', (req, res) => {
  const { symbol } = req.query;
  
  if (!symbol) {
    return res.status(400).json({ message: 'Symbol query parameter is required' });
  }
  
  const upperSymbol = symbol.toUpperCase();
  
  // If exact match
  if (mockStocks[upperSymbol]) {
    return res.json({
      symbol: mockStocks[upperSymbol].symbol,
      name: mockStocks[upperSymbol].name,
      currentPrice: mockStocks[upperSymbol].currentPrice,
      change: mockStocks[upperSymbol].change,
      percentChange: mockStocks[upperSymbol].percentChange
    });
  }
  
  // If no exact match but we want to provide some response
  // In a real app, you'd query an API for partial matches
  return res.status(404).json({ message: `No stocks found matching ${symbol}` });
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
}); 