/**
 * API client for backend FastAPI endpoints
 * Uses axios with error handling and request interceptors
 */
import axios, { type AxiosInstance, type AxiosError, type AxiosRequestConfig, type AxiosResponse } from 'axios';
import type {
  PriceData,
  SymbolMetadata,
  TimeSeriesResponse,
  LatestPriceResponse,
  PriceQueryParams,
  SymbolQueryParams,
  ApiError,
} from '../types';

/**
 * Get API base URL from environment variable or use default
 */
const getApiBaseUrl = (): string => {
  // In production, this would be set via environment variable
  // For development, default to localhost
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
};

/**
 * Create axios instance with default configuration
 */
const api: AxiosInstance = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000, // 30 seconds timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor - runs before every request
 * Can be used to add auth tokens, modify requests, etc.
 */
api.interceptors.request.use(
  (config) => {
    // Add any request modifications here
    // For example, add auth token:
    // const token = localStorage.getItem('authToken');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    
    return config;
  },
  (error) => {
    // Handle request error
    return Promise.reject(error);
  }
);

/**
 * Response interceptor - runs after every response
 * Handles errors globally and transforms responses
 */
api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  (error: AxiosError<ApiError>) => {
    // Handle response errors
    if (error.response) {
      // Server responded with error status
      const status = error.response.status;
      const errorData = error.response.data;
      
      console.error(`[API Error] ${status}:`, errorData?.detail || error.message);
      
      // Handle specific error cases
      switch (status) {
        case 401:
          // Unauthorized - could redirect to login
          console.error('Unauthorized - authentication required');
          break;
        case 403:
          // Forbidden
          console.error('Forbidden - insufficient permissions');
          break;
        case 404:
          // Not found
          console.error('Resource not found');
          break;
        case 500:
          // Server error
          console.error('Server error - please try again later');
          break;
        default:
          console.error(`API error: ${status}`);
      }
    } else if (error.request) {
      // Request was made but no response received
      console.error('[API Error] No response received:', error.message);
    } else {
      // Error setting up the request
      console.error('[API Error] Request setup error:', error.message);
    }
    
    return Promise.reject(error);
  }
);

/**
 * API service functions
 */
export const apiService = {
  /**
   * List all available symbols with metadata
   */
  async getSymbols(params?: SymbolQueryParams): Promise<SymbolMetadata[]> {
    const response = await api.get<SymbolMetadata[]>('/symbols', { params });
    return response.data;
  },

  /**
   * Get metadata for a specific symbol
   */
  async getSymbolMetadata(symbol: string): Promise<SymbolMetadata> {
    const response = await api.get<SymbolMetadata>(`/symbols/${symbol}/metadata`);
    return response.data;
  },

  /**
   * Get OHLCV price data for a symbol
   */
  async getPrices(symbol: string, params?: PriceQueryParams): Promise<TimeSeriesResponse> {
    const response = await api.get<TimeSeriesResponse>(`/symbols/${symbol}/prices`, { params });
    return response.data;
  },

  /**
   * Get latest price data for a symbol
   */
  async getLatestPrice(symbol: string): Promise<LatestPriceResponse> {
    const response = await api.get<LatestPriceResponse>(`/symbols/${symbol}/latest`);
    return response.data;
  },

  /**
   * Search symbols by name or ticker
   */
  async searchSymbols(query: string, limit: number = 50): Promise<SymbolMetadata[]> {
    const response = await api.get<SymbolMetadata[]>('/symbols/search', {
      params: { q: query, limit },
    });
    return response.data;
  },
};

/**
 * Export the axios instance for advanced usage
 */
export default api;

