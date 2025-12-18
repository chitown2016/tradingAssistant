# TradingView-Style Stock Charting Web Application

## Architecture Overview

The application will consist of:
- **Backend**: FastAPI (Python) REST API serving data from PostgreSQL/TimescaleDB
- **Frontend**: React + TypeScript with TradingView Lightweight Charts
- **Database**: Existing PostgreSQL with TimescaleDB (yahoo_adjusted_stock_prices, tickers, stock_indicators tables)

## Phase 1: Backend API Setup

### 1.1 FastAPI Project Structure
Create `backend/` directory with:
- `backend/main.py` - FastAPI app entry point
- `backend/api/` - API route handlers
- `backend/models/` - Pydantic models for request/response
- `backend/db/` - Database connection utilities (reuse from `store_stock_data.py`)
- `backend/utils/` - Helper functions

### 1.2 Database Connection Module
- Create `backend/db/connection.py` that wraps `get_db_connection()` from `store_stock_data.py`
- Add connection pooling for FastAPI
- Create dependency injection for database sessions

### 1.3 API Endpoints

**Price Data Endpoints:**
- `GET /api/v1/symbols` - List all available symbols with metadata
- `GET /api/v1/symbols/{symbol}/prices` - Get OHLCV data for a symbol
  - Query params: `start_date`, `end_date`, `interval` (1d, 1w, 1m)
- `GET /api/v1/symbols/{symbol}/latest` - Get latest price data

**Indicator Endpoints:**
- `GET /api/v1/symbols/{symbol}/indicators` - Get all indicators for a symbol
  - Query params: `date` (optional, defaults to latest)
- `GET /api/v1/indicators/relative-strength` - Get RS ratings for multiple symbols
  - Query params: `date`, `min_rating`, `limit`

**Search/Discovery:**
- `GET /api/v1/search` - Search symbols by name or ticker
- `GET /api/v1/symbols/{symbol}/metadata` - Get ticker metadata (asset_type, country, date ranges)

### 1.4 Response Models
Create Pydantic models in `backend/models/`:
- `PriceData` - OHLCV structure
- `IndicatorData` - Relative strength and other indicators
- `SymbolMetadata` - Ticker information
- `TimeSeriesResponse` - Wrapper for time series data

### 1.5 CORS Configuration
Enable CORS for frontend development and production

## Phase 2: Frontend Setup

### 2.1 React + TypeScript Project
Create `frontend/` directory:
- Initialize with Vite + React + TypeScript template
- Set up project structure:
  - `src/components/` - React components
  - `src/pages/` - Page components
  - `src/services/` - API client
  - `src/types/` - TypeScript interfaces
  - `src/hooks/` - Custom React hooks
  - `src/utils/` - Utility functions

### 2.2 API Client Setup
- Create `src/services/api.ts` with axios or fetch wrapper
- Define TypeScript interfaces matching backend Pydantic models
- Add error handling and request interceptors

### 2.3 TradingView Lightweight Charts Integration
- Install `lightweight-charts` package
- Create `src/components/Chart/Chart.tsx` - Main chart component
- Create chart configuration with:
  - Candlestick series
  - Volume histogram
  - Time scale configuration
  - Price scale configuration

## Phase 3: Core Chart Features

### 3.1 Basic Chart Display
- Implement candlestick chart with OHLCV data
- Add volume bars below price chart
- Implement time range selection (1D, 1W, 1M, 3M, 6M, 1Y, ALL)
- Add symbol search and selection
- Display current price, change, and percentage

### 3.2 Chart Controls
- Zoom in/out functionality
- Pan/scroll through time
- Crosshair with price/time display
- Chart type toggle (candlestick, line, area, baseline)
- Timeframe selector

### 3.3 Relative Strength Indicator
- Add RS rating display in chart overlay
- Show RS rating in symbol info panel
- Color-code based on RS rating (green for high, red for low)
- Display RS rating history on chart

### 3.4 Additional Indicators (Phase 3)
Implement common technical indicators:
- Moving Averages (SMA, EMA) - 20, 50, 200 day
- Volume indicators
- RSI (Relative Strength Index)
- MACD
- Bollinger Bands

Each indicator should be:
- Toggleable on/off
- Configurable (periods, colors)
- Displayed in separate panes or overlay

## Phase 4: Advanced Chart Features

### 4.1 Drawing Tools
Implement TradingView-style drawing tools:
- Trend lines
- Horizontal/vertical lines
- Rectangles
- Fibonacci retracements
- Text annotations
- Save/load drawings (localStorage initially)

### 4.2 Multiple Timeframes
- Support for intraday aggregation (if data available)
- Switch between daily, weekly, monthly views
- Maintain zoom/pan state per timeframe

### 4.3 Chart Layouts
- Multiple chart panes (price + indicators)
- Resizable panes
- Save/load chart layouts
- Preset layouts (default, technical analysis, etc.)

### 4.4 Performance Optimizations
- Implement data pagination for large date ranges
- Virtual scrolling for chart data
- Debounce chart updates
- Memoize indicator calculations

## Phase 5: UI/UX Polish

### 5.1 Symbol Search & Watchlist
- Symbol search with autocomplete
- Watchlist functionality (localStorage initially)
- Quick symbol switcher
- Symbol comparison (multiple symbols on one chart)

### 5.2 Information Panels
- Symbol info panel (metadata, latest price, change)
- Indicator values panel
- News/events panel (placeholder for future)
- Statistics panel (52-week high/low, etc.)

### 5.3 Responsive Design
- Mobile-responsive layout
- Touch gestures for chart interaction
- Collapsible panels for mobile

### 5.4 Styling
- Modern, clean UI design
- Dark/light theme toggle
- Customizable chart colors
- Professional TradingView-like appearance

## Phase 6: Data Management & Caching

### 6.1 Frontend Caching
- Cache price data in IndexedDB or localStorage
- Implement cache invalidation strategy
- Background data refresh

### 6.2 Backend Optimizations
- Add database query optimizations for time series
- Implement response caching (Redis optional, or in-memory)
- Add pagination for large datasets
- Optimize TimescaleDB queries for chart data

## Technical Stack Summary

**Backend:**
- FastAPI (Python web framework)
- psycopg2 (PostgreSQL driver, reuse existing)
- Pydantic (data validation)
- python-dotenv (environment variables, reuse existing)

**Frontend:**
- React 18+ with TypeScript
- Vite (build tool)
- TradingView Lightweight Charts
- Axios or fetch API
- React Query or SWR (data fetching/caching)
- Tailwind CSS or styled-components (styling)

**Development:**
- TypeScript for type safety
- ESLint + Prettier
- Separate package.json for frontend
- Environment variables for API URLs

## File Structure

```
tradingAssistant/
├── backend/
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── prices.py
│   │       ├── indicators.py
│   │       └── symbols.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── price.py
│   │   └── indicator.py
│   ├── db/
│   │   ├── __init__.py
│   │   └── connection.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chart/
│   │   │   ├── Indicators/
│   │   │   ├── Search/
│   │   │   └── Watchlist/
│   │   ├── pages/
│   │   │   └── ChartPage.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── store_stock_data.py (existing)
├── relative_strength.py (existing)
└── daily_update_stocks.py (existing)
```

## Future Extensibility

The architecture will support:
- Real-time WebSocket connections for live price updates
- User authentication (add auth middleware to FastAPI)
- Scanning engine (new API endpoints for condition scanning)
- Trading automation (separate service that can call API)
- Multiple chart instances
- Custom indicator development

## Implementation Order

1. Backend API foundation (Phase 1)
2. Basic frontend setup and chart display (Phase 2 + 3.1)
3. Core chart features (Phase 3)
4. Advanced features (Phase 4)
5. Polish and optimization (Phase 5 + 6)

