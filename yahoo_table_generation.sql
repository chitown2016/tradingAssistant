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

-- CREATE stock_indicators TABLE
---------------------------------------
CREATE TABLE stock_indicators (
    symbol TEXT NOT NULL,
    calculation_date DATE NOT NULL,
    rs_rating INTEGER,  -- 1-99 percentile rank
    weighted_change DECIMAL(10, 2),  -- The weighted percentage change
    pct_change_3mo DECIMAL(10, 2),
    pct_change_6mo DECIMAL(10, 2),
    pct_change_9mo DECIMAL(10, 2),
    pct_change_12mo DECIMAL(10, 2),
    PRIMARY KEY (symbol, calculation_date)
);

-- Convert to hypertable
SELECT create_hypertable('stock_indicators', 'calculation_date');
CREATE INDEX idx_rs_date_rating ON stock_indicators(calculation_date, rs_rating);

-- Add indexes
CREATE INDEX idx_rs_calculation_date ON stock_indicators(calculation_date DESC);

ALTER TABLE stock_indicators
ADD COLUMN IF NOT EXISTS close_price DECIMAL(16, 4),
ADD COLUMN IF NOT EXISTS daily_percent_range DECIMAL(10, 2),
ADD COLUMN IF NOT EXISTS pct_change_1d DECIMAL(10, 2),
ADD COLUMN IF NOT EXISTS adr20 DECIMAL(6, 2),
ADD COLUMN IF NOT EXISTS low_52w DECIMAL(16, 4),
ADD COLUMN IF NOT EXISTS current_volume BIGINT,
ADD COLUMN IF NOT EXISTS avg_volume_30d BIGINT;