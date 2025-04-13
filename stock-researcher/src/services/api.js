import axios from 'axios';

// API URL is now set via build-time environment variable
const API_URL = process.env.REACT_APP_API_URL;

// Add a check in case the variable wasn't set during build
if (!API_URL) {
  console.error("FATAL ERROR: REACT_APP_API_URL is not set. Check Docker build configuration.");
  // You might want to throw an error or render an error state in the app
}

const api = {
  // Get all stocks (simplified list)
  getAllStocks: async () => {
    try {
      const response = await axios.get(`${API_URL}/api/stocks`);
      return response.data;
    } catch (error) {
      console.error('Error fetching stocks:', error);
      throw error;
    }
  },

  // Get detailed info for a specific stock
  getStockDetails: async (symbol) => {
    try {
      const response = await axios.get(`${API_URL}/api/stocks/${symbol}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching details for ${symbol}:`, error);
      throw error;
    }
  },

  // Search for a stock by symbol
  searchStock: async (symbol) => {
    try {
      const response = await axios.get(`${API_URL}/api/search`, {
        params: { symbol }
      });
      return response.data;
    } catch (error) {
      if (error.response && error.response.status === 404) {
        return null; // Stock not found
      }
      console.error('Error searching for stock:', error);
      throw error;
    }
  }
};

export default api; 