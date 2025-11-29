--Q@pCoktdmtqKF8

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create main table for stock prices
CREATE TABLE yahoo_adjusted_stock_prices (
    timestamp TIMESTAMP NOT NULL,
    symbol TEXT NOT NULL,
    open DECIMAL(16, 4) NOT NULL,
    high DECIMAL(16, 4) NOT NULL,
    low DECIMAL(16, 4) NOT NULL,
    close DECIMAL(16, 4) NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, timestamp)
);

-- Convert to hypertable for TimescaleDB
SELECT create_hypertable('yahoo_adjusted_stock_prices', 'timestamp');

-- Add indexes for performance
CREATE INDEX idx_stock_prices_symbol_time 
ON yahoo_adjusted_stock_prices (symbol, timestamp DESC);

CREATE INDEX idx_timestamp 
ON yahoo_adjusted_stock_prices (timestamp DESC);

-- Create tickers metadata table
CREATE TABLE tickers (
    symbol TEXT PRIMARY KEY,
    asset_type VARCHAR(20),      -- 'EQUITY', 'ETF', 'INDEX', etc.
    country VARCHAR(3),          -- ISO 3166-1 alpha-3
    first_date DATE,
    last_date DATE,
    record_count INTEGER,
    last_updated TIMESTAMP DEFAULT NOW()
);

-- Indexes for tickers table
CREATE INDEX idx_tickers_asset_type ON tickers(asset_type);
CREATE INDEX idx_tickers_country ON tickers(country);