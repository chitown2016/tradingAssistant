---
name: Stock Screening Feature
overview: Implement a TradingView-style stock screening feature that allows users to filter stocks by criteria (price, volume, indicators), with pre-computed metrics stored in the database for fast queries. Results are clickable to load the chart.
todos:
  - id: create_db_schema
    content: Add screening metrics columns to existing stock_indicators table via ALTER TABLE
    status: pending
  - id: metrics_calculation
    content: Create calculate_screening_metrics.py script to compute and store metrics in stock_indicators
    status: pending
    dependencies:
      - create_db_schema
  - id: screening_api
    content: Create backend API endpoint for screening (POST /api/v1/screening/scan)
    status: pending
    dependencies:
      - create_db_schema
  - id: screening_models
    content: Create Pydantic models for screening request/response
    status: pending
  - id: screening_page
    content: Create ScreeningPage.tsx with criteria form and results table
    status: pending
    dependencies:
      - screening_api
  - id: screening_service
    content: Create frontend screening service and TypeScript types
    status: pending
    dependencies:
      - screening_api
  - id: chart_integration
    content: Update ChartPage to accept symbol parameter and handle navigation from screening
    status: pending
    dependencies:
      - screening_page
  - id: daily_jobs
    content: Add screening metrics calculation to daily job pipeline
    status: pending
    dependencies:
      - metrics_calculation
---

# Stock Screening Feature Implementation

## Overview

Implement a stock screening system similar to TradingView where users can define criteria to filter stocks. The system will pre-compute common metrics and store them in the database for fast screening queries. Results will be displayed in a list that users can click to load the chart.

## Architecture Decision: Pre-compute vs On-demand

**Decision: Pre-compute common metrics** - Following the pattern of `stock_indicators` table (similar to relative strength calculation), we'll:

- Calculate common screening metrics daily and store them in the existing `stock_indicators` table
- Query pre-computed values for fast screening
- Support complex criteria by combining pre-computed metrics
- Reuse existing `pct_change_3mo`, `pct_change_6mo`, `pct_change_9mo`, `pct_change_12mo` columns for price change percentages

## Database Schema

### Extend Existing Table: `stock_indicators`

Add screening metrics columns to the existing `stock_indicators` table (which already has `symbol`, `calculation_date`, `rs_rating`, `weighted_change`, and percentage change columns):

```sql
-- Add screening metrics columns to stock_indicators
ALTER TABLE stock_indicators
ADD COLUMN IF NOT EXISTS current_price DECIMAL(16, 4),
ADD COLUMN IF NOT EXISTS price_change_1d DECIMAL(10, 4),
ADD COLUMN IF NOT EXISTS price_change_5d DECIMAL(10, 4),
ADD COLUMN IF NOT EXISTS price_change_1mo DECIMAL(10, 4),
-- Note: pct_change_3mo, pct_change_6mo, pct_change_9mo, pct_change_12mo already exist
ADD COLUMN IF NOT EXISTS price_change_1y DECIMAL(10, 4),
-- 52-week metrics
ADD COLUMN IF NOT EXISTS high_52w DECIMAL(16, 4),
ADD COLUMN IF NOT EXISTS low_52w DECIMAL(16, 4),
ADD COLUMN IF NOT EXISTS pct_from_52w_high DECIMAL(10, 4),  -- (current - 52w_high) / 52w_high * 100
ADD COLUMN IF NOT EXISTS pct_from_52w_low DECIMAL(10, 4),   -- (current - 52w_low) / 52w_low * 100
-- Volume metrics
ADD COLUMN IF NOT EXISTS current_volume BIGINT,
ADD COLUMN IF NOT EXISTS avg_volume_20d BIGINT,
ADD COLUMN IF NOT EXISTS volume_ratio DECIMAL(10, 4),  -- current_volume / avg_volume_20d
-- Moving averages
ADD COLUMN IF NOT EXISTS sma_20 DECIMAL(16, 4),
ADD COLUMN IF NOT EXISTS sma_50 DECIMAL(16, 4),
ADD COLUMN IF NOT EXISTS sma_200 DECIMAL(16, 4),
ADD COLUMN IF NOT EXISTS price_vs_sma20_pct DECIMAL(10, 4),  -- (current - sma20) / sma20 * 100
ADD COLUMN IF NOT EXISTS price_vs_sma50_pct DECIMAL(10, 4),
ADD COLUMN IF NOT EXISTS price_vs_sma200_pct DECIMAL(10, 4);

-- Add indexes for common screening queries
CREATE INDEX IF NOT EXISTS idx_stock_indicators_price 
ON stock_indicators(calculation_date DESC, current_price) 
WHERE current_price IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_stock_indicators_52w 
ON stock_indicators(calculation_date DESC, pct_from_52w_low) 
WHERE pct_from_52w_low IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_stock_indicators_volume_ratio 
ON stock_indicators(calculation_date DESC, volume_ratio) 
WHERE volume_ratio IS NOT NULL;
```

**Note**: The table already has:
- `pct_change_3mo`, `pct_change_6mo`, `pct_change_9mo`, `pct_change_12mo` - These can be reused for screening criteria
- `rs_rating` - Relative strength rating (1-99) can also be used in screening
- Primary key: `(symbol, calculation_date)` - Perfect for daily metrics
- TimescaleDB hypertable on `calculation_date` - Already optimized for time-series queries

## Implementation Plan

### Phase 1: Backend - Metrics Calculation & Storage

#### 1.1 Create Metrics Calculation Script

**File**: `calculate_screening_metrics.py`

- Calculate metrics for all symbols for a given date
- Process in batches (similar to `relative_strength.py`)
- Calculate:
  - Current price and price changes (1d, 5d, 1mo, 1y)
  - 52-week high/low and percentages
  - Volume metrics (current, 20-day average, ratio)
  - Moving averages (SMA 20, 50, 200) and price vs MA percentages
- Store results in `stock_indicators` table using `ON CONFLICT` to update existing rows
- Support daily batch processing
- Can run alongside or after `relative_strength.py` calculation

**Key Functions**:

- `calculate_metrics_batch(conn, symbols_batch, calc_date)` - Calculate for a batch
- `calculate_and_store_metrics(calc_date=None, batch_size=500)` - Main function

**Storage Pattern**:
```python
# Use ON CONFLICT to update existing rows (from relative_strength calculation)
INSERT INTO stock_indicators 
(symbol, calculation_date, current_price, price_change_1d, high_52w, low_52w, ...)
VALUES %s
ON CONFLICT (symbol, calculation_date) 
DO UPDATE SET
    current_price = EXCLUDED.current_price,
    price_change_1d = EXCLUDED.price_change_1d,
    -- ... update all screening metric columns
```

#### 1.2 Create Screening API Endpoint

**File**: `backend/api/v1/screening.py`

**Endpoint**: `POST /api/v1/screening/scan`

**Request Body** (Pydantic model):

```python
class ScreeningCriteria(BaseModel):
    # Price criteria
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_change_1d_min: Optional[float] = None
    price_change_1d_max: Optional[float] = None
    # Reuse existing percentage change columns
    pct_change_3mo_min: Optional[float] = None
    pct_change_6mo_min: Optional[float] = None
    # 52-week criteria
    pct_from_52w_high_min: Optional[float] = None  # e.g., -20 means within 20% of 52W high
    pct_from_52w_low_min: Optional[float] = None  # e.g., 70 means 70% above 52W low
    # Volume criteria
    volume_ratio_min: Optional[float] = None  # e.g., 1.5 means 50% above average
    # Moving average criteria
    price_above_sma20: Optional[bool] = None
    price_above_sma50: Optional[bool] = None
    price_above_sma200: Optional[bool] = None
    # Relative strength criteria (reuse existing)
    rs_rating_min: Optional[int] = None
    rs_rating_max: Optional[int] = None
    # Asset filters
    asset_type: Optional[str] = None
    country: Optional[str] = None
    # Pagination
    limit: Optional[int] = 100
    offset: Optional[int] = 0
    # Sort
    sort_by: Optional[str] = "symbol"  # symbol, current_price, volume_ratio, rs_rating, etc.
    sort_order: Optional[str] = "asc"
```

**Response**:

```python
class ScreeningResult(BaseModel):
    symbol: str
    current_price: Optional[float]
    price_change_1d: Optional[float]
    pct_change_3mo: Optional[float]  # Reuse existing column
    pct_change_6mo: Optional[float]  # Reuse existing column
    pct_from_52w_high: Optional[float]
    pct_from_52w_low: Optional[float]
    volume_ratio: Optional[float]
    rs_rating: Optional[int]  # Reuse existing column
    sma_20: Optional[float]
    sma_50: Optional[float]
    sma_200: Optional[float]
    # ... other metrics

class ScreeningResponse(BaseModel):
    results: List[ScreeningResult]
    total: int
    limit: int
    offset: int
```

**Implementation**:

- Query `stock_indicators` table for latest `calculation_date`
- Build dynamic SQL WHERE clause based on criteria
- Support complex conditions (e.g., `pct_from_52w_low >= 70`)
- Join with `tickers` table for asset_type/country filters
- Return paginated results
- Leverage existing indexes on `calculation_date` and `rs_rating`

#### 1.3 Update Daily Jobs

**File**: `run_daily_jobs.py` or create new script

- Add `calculate_screening_metrics` to daily job pipeline
- Can run after `daily_update_stocks` and `relative_strength` (or in parallel if using ON CONFLICT properly)
- Both scripts update the same `stock_indicators` table with different columns

### Phase 2: Frontend - Screening UI

#### 2.1 Create Screening Page Component

**File**: `frontend/src/pages/ScreeningPage.tsx`

**Features**:
- Form with criteria inputs (price, volume, 52W metrics, RS rating, etc.)
- "Scan" button to execute screening
- Results table showing:
  - Symbol (clickable)
  - Current price
  - Price change %
  - 52W high/low percentages
  - Volume ratio
  - RS Rating (reuse existing)
  - Other relevant metrics
- Pagination controls
- Sortable columns
- Loading states

#### 2.2 Create Screening Service

**File**: `frontend/src/services/screening.ts`

- `scanStocks(criteria: ScreeningCriteria)` - Call screening API
- TypeScript interfaces matching backend models

#### 2.3 Integrate with Chart Page

**File**: `frontend/src/pages/ChartPage.tsx`

- When symbol is clicked in screening results, navigate to ChartPage or update ChartPage state
- Pass symbol as URL parameter or use React Router navigation
- ChartPage should accept `symbol` prop/param and load that symbol's chart

#### 2.4 Add Routing

**File**: `frontend/src/App.tsx` or router config

- Add route: `/screening` → `ScreeningPage`
- Update navigation to include "Screening" link

### Phase 3: Advanced Features (Future)

- Save screening criteria as presets
- Real-time screening (WebSocket updates)
- Additional indicators (RSI, MACD, Bollinger Bands)
- Custom formula builder
- Export results to CSV

## File Structure

```
backend/
├── api/v1/
│   └── screening.py          # Screening API endpoint
├── models/
│   └── screening.py          # Pydantic models for screening
└── utils/
    └── screening_metrics.py  # Metrics calculation utilities

calculate_screening_metrics.py  # Daily metrics calculation script

frontend/src/
├── pages/
│   ├── ScreeningPage.tsx      # Screening UI
│   └── ChartPage.tsx         # Update to accept symbol param
├── services/
│   └── screening.ts          # Screening API client
└── types/
    └── screening.ts           # TypeScript interfaces
```

## Example Usage Flow

1. User navigates to `/screening`
2. User sets criteria: "Price > $10", "Price > 70% of 52W Low", "RS Rating > 80", "Volume > 1.5x average"
3. User clicks "Scan"
4. Backend queries `stock_indicators` with latest date, applies filters
5. Returns list of matching symbols with metrics (including RS rating)
6. User clicks on "AAPL" in results
7. Navigates to `/chart?symbol=AAPL` or updates ChartPage
8. Chart loads with AAPL data

## Performance Considerations

- Pre-computed metrics enable fast queries (no on-the-fly calculations)
- Existing index on `calculation_date` for efficient latest-date queries
- New indexes on `current_price`, `pct_from_52w_low`, `volume_ratio` for common filters
- Batch processing for metrics calculation (500 symbols at a time)
- Pagination to limit result set size
- Single table query (no joins needed for basic screening)
- TimescaleDB hypertable already optimized for time-series queries

## Database Migration

Create SQL migration file: `migrations/add_screening_metrics_to_stock_indicators.sql`

- ALTER TABLE to add new columns
- Add indexes for common screening queries
- Document column purposes and calculation methods
