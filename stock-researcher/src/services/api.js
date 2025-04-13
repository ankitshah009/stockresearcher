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
      // Append only the specific endpoint, not /api/ again
      const response = await axios.get(`${API_URL}/stocks`); 
      return response.data;
    } catch (error) {
      console.error('Error fetching stocks:', error);
      throw error;
    }
  },

  // Get detailed info for a specific stock
  getStockDetails: async (symbol) => {
    try {
      // Append only the specific endpoint, not /api/ again
      const response = await axios.get(`${API_URL}/stocks/${symbol}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching details for ${symbol}:`, error);
      throw error;
    }
  },

  // Search for a stock by symbol
  searchStock: async (symbol) => {
    try {
      // Append only the specific endpoint, not /api/ again
      const response = await axios.get(`${API_URL}/search`, {
        params: { symbol }
      });
      return response.data;
    } catch (error) {
      if (error.response && error.response.status === 404) {
        // Changed to return specific error message from backend if available
        return { error: error.response.data.message || `Stock symbol ${symbol} not found` };
      } 
      // Handle other errors like API limits (429) or server errors (5xx)
      else if (error.response) { 
        console.error('API Error:', error.response.status, error.response.data);
        return { error: error.response.data.message || 'An API error occurred' };
      } 
      // Handle network errors
      else {
        console.error('Network Error searching for stock:', error.message);
        return { error: 'Network error. Please check connection.' };
      }
      // Removed the generic throw error here to return structured error info
    }
  }
};

export default api; 