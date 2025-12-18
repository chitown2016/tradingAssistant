/**
 * TypeScript interfaces matching backend Pydantic models
 */

/**
 * OHLCV price data point
 */
export interface PriceData {
  timestamp: string; // ISO 8601 datetime string
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * Symbol metadata from tickers table
 */
export interface SymbolMetadata {
  symbol: string;
  asset_type: string | null;
  country: string | null;
  first_date: string | null; // ISO 8601 datetime string
  last_date: string | null; // ISO 8601 datetime string
  record_count: number | null;
  last_updated: string | null; // ISO 8601 datetime string
}

/**
 * Response wrapper for time series price data
 */
export interface TimeSeriesResponse {
  symbol: string;
  data: PriceData[];
  count: number;
  start_date: string | null; // ISO 8601 datetime string
  end_date: string | null; // ISO 8601 datetime string
}

/**
 * Response for latest price data
 */
export interface LatestPriceResponse {
  symbol: string;
  price: PriceData;
}

/**
 * Query parameters for getting prices
 */
export interface PriceQueryParams {
  start_date?: string; // ISO 8601 datetime string
  end_date?: string; // ISO 8601 datetime string
  interval?: '1d' | '1w' | '1m'; // Daily, weekly, or monthly
}

/**
 * Query parameters for listing symbols
 */
export interface SymbolQueryParams {
  asset_type?: string;
  country?: string;
  limit?: number; // Max 10000
}

/**
 * API Error response structure
 */
export interface ApiError {
  detail: string;
}

