"""
Symbol endpoints - list symbols, metadata, and price data
"""
import logging
import os
from datetime import datetime, timedelta, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import psycopg2
from backend.db import get_db
from backend.models.price import SymbolMetadata, PriceData, TimeSeriesResponse, LatestPriceResponse, RelativeStrengthTimeseriesResponse, RelativeStrengthData

router = APIRouter()

# Set up file logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create file handler if not already exists
if not logger.handlers:
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    file_handler = logging.FileHandler(os.path.join(log_dir, 'api_performance.log'), mode='a')
    file_handler.setLevel(logging.DEBUG)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


@router.get("", response_model=List[SymbolMetadata])
async def list_symbols(
    asset_type: Optional[str] = Query(None, description="Filter by asset type (EQUITY, ETF, etc.)"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Limit number of results"),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    List all available symbols with metadata
    
    Query parameters:
    - asset_type: Filter by asset type
    - country: Filter by country code
    - limit: Limit number of results (max 10000)
    """
    cursor = db.cursor()
    
    try:
        # Build query with optional filters
        query = "SELECT symbol, asset_type, country, first_date, last_date, record_count, last_updated FROM tickers WHERE 1=1"
        params = []
        
        if asset_type:
            query += " AND asset_type = %s"
            params.append(asset_type)
        
        if country:
            query += " AND country = %s"
            params.append(country)
        
        query += " ORDER BY symbol"
        
        if limit:
            query += " LIMIT %s"
            params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        symbols = []
        for row in rows:
            symbols.append(SymbolMetadata(
                symbol=row[0],
                asset_type=row[1],
                country=row[2],
                first_date=row[3],
                last_date=row[4],
                record_count=row[5],
                last_updated=row[6]
            ))
        
        return symbols
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()

# Add after the list_symbols function, around line 71

@router.get("/search", response_model=List[SymbolMetadata])
async def search_symbols(
    q: str = Query(..., description="Search query (symbol name or ticker)"),
    limit: Optional[int] = Query(50, ge=1, le=1000, description="Limit number of results"),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Search symbols by name or ticker (case-insensitive partial match)
    
    Query parameters:
    - q: Search query string
    - limit: Maximum number of results to return (default: 50, max: 1000)
    """
    cursor = db.cursor()
    
    try:
        search_term = f"%{q.upper()}%"
        
        query = """
            SELECT symbol, asset_type, country, first_date, last_date, record_count, last_updated 
            FROM tickers 
            WHERE UPPER(symbol) LIKE %s
            ORDER BY 
                CASE 
                    WHEN UPPER(symbol) LIKE %s THEN 1  -- Exact match first
                    WHEN UPPER(symbol) LIKE %s THEN 2  -- Starts with query
                    ELSE 3  -- Contains query
                END,
                symbol
            LIMIT %s
        """
        
        exact_match = q.upper()
        starts_with = f"{q.upper()}%"
        
        cursor.execute(query, (search_term, exact_match, starts_with, limit))
        rows = cursor.fetchall()
        
        symbols = []
        for row in rows:
            symbols.append(SymbolMetadata(
                symbol=row[0],
                asset_type=row[1],
                country=row[2],
                first_date=row[3],
                last_date=row[4],
                record_count=row[5],
                last_updated=row[6]
            ))
        
        return symbols
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()


@router.get("/{symbol}/metadata", response_model=SymbolMetadata)
async def get_symbol_metadata(
    symbol: str,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get metadata for a specific symbol
    """
    cursor = db.cursor()
    
    try:
        cursor.execute(
            "SELECT symbol, asset_type, country, first_date, last_date, record_count, last_updated FROM tickers WHERE symbol = %s",
            (symbol.upper(),)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
        
        return SymbolMetadata(
            symbol=row[0],
            asset_type=row[1],
            country=row[2],
            first_date=row[3],
            last_date=row[4],
            record_count=row[5],
            last_updated=row[6]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()


def parse_interval(interval: str) -> str:
    """
    Parse interval string (1d, 1w, 1m) to SQL time_bucket interval
    Returns the interval for TimescaleDB time_bucket function
    """
    interval_map = {
        "1d": "1 day",
        "1w": "1 week",
        "1m": "1 month"
    }
    return interval_map.get(interval.lower(), "1 day")


@router.get("/{symbol}/prices", response_model=TimeSeriesResponse)
async def get_prices(
    symbol: str,
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    interval: Optional[str] = Query("1d", description="Aggregation interval: 1d, 1w, 1m"),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get OHLCV data for a symbol
    
    Query parameters:
    - start_date: Start date for the query (defaults to 1 year ago if not specified)
    - end_date: End date for the query (defaults to today if not specified)
    - interval: Aggregation interval - 1d (daily), 1w (weekly), 1m (monthly)
    """
    cursor = db.cursor()
    
    try:
        symbol_upper = symbol.upper()
        
        # Set default dates if not provided
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=365)
        
        # Convert timezone-aware datetimes to naive (database uses TIMESTAMP without timezone)
        # This ensures the composite index can be used efficiently
        if start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)
        
        # Validate interval
        if interval.lower() not in ["1d", "1w", "1m"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid interval. Must be one of: 1d, 1w, 1m"
            )
        
        # Check if symbol exists
        cursor.execute("SELECT COUNT(*) FROM tickers WHERE symbol = %s", (symbol_upper,))
        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
        
        # Build query based on interval
        if interval.lower() == "1d":
            # Daily data - no aggregation needed
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM yahoo_adjusted_stock_prices
                WHERE symbol = %s AND timestamp >= %s AND timestamp <= %s
                ORDER BY timestamp ASC
            """
            params = (symbol_upper, start_date, end_date)
        else:
            # Weekly or monthly - use time_bucket for aggregation
            # Try to use TimescaleDB FIRST/LAST functions, fallback to subquery if not available
            bucket_interval = parse_interval(interval)
            # Use window functions for better performance
            query = f"""
                WITH bucketed AS (
                    SELECT 
                        time_bucket('{bucket_interval}', timestamp) AS bucket,
                        timestamp,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        ROW_NUMBER() OVER (PARTITION BY time_bucket('{bucket_interval}', timestamp) ORDER BY timestamp ASC) AS rn_first,
                        ROW_NUMBER() OVER (PARTITION BY time_bucket('{bucket_interval}', timestamp) ORDER BY timestamp DESC) AS rn_last
                    FROM yahoo_adjusted_stock_prices
                    WHERE symbol = %s AND timestamp >= %s AND timestamp <= %s
                )
                SELECT 
                    bucket AS timestamp,
                    MAX(CASE WHEN rn_first = 1 THEN open END) AS open,
                    MAX(high) AS high,
                    MIN(low) AS low,
                    MAX(CASE WHEN rn_last = 1 THEN close END) AS close,
                    SUM(volume) AS volume
                FROM bucketed
                GROUP BY bucket
                ORDER BY bucket ASC
            """
            params = (symbol_upper, start_date, end_date)
        
        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No price data found for symbol '{symbol}' in the specified date range"
            )
        
        # Convert to PriceData objects
        price_data = []
        for row in rows:
            price_data.append(PriceData(
                timestamp=row[0],
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=int(row[5])
            ))
        
        return TimeSeriesResponse(
            symbol=symbol_upper,
            data=price_data,
            count=len(price_data),
            start_date=start_date,
            end_date=end_date
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_prices ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()


@router.get("/{symbol}/latest", response_model=LatestPriceResponse)
async def get_latest_price(
    symbol: str,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get the latest price data for a symbol
    Uses DISTINCT ON for efficient single-query lookup
    """
    cursor = db.cursor()
    
    try:
        symbol_upper = symbol.upper()
        
        # Get the last_date from tickers table to limit chunk scanning
        cursor.execute("""
            SELECT last_date 
            FROM tickers 
            WHERE symbol = %s
        """, (symbol_upper,))
        
        ticker_row = cursor.fetchone()
        if not ticker_row:
            raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
        
        last_date = ticker_row[0]
        if not last_date:
            raise HTTPException(
                status_code=404,
                detail=f"No price data found for symbol '{symbol}'"
            )
        
        # Use last_date to constrain the query to recent chunks only
        # This allows TimescaleDB to use chunk exclusion effectively
        # Query the last 30 days to ensure we get the latest, even if last_date is slightly stale
        query_start_date = last_date - timedelta(days=30)
        
        # Execute query for latest price
        cursor.execute("""
            SELECT timestamp, open, high, low, close, volume
            FROM yahoo_adjusted_stock_prices
            WHERE symbol = %s
              AND timestamp >= %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (symbol_upper, query_start_date))
        
        row = cursor.fetchone()
        
        # Fallback if constrained query fails
        if not row:
            cursor.execute("""
                SELECT timestamp, open, high, low, close, volume
                FROM yahoo_adjusted_stock_prices
                WHERE symbol = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (symbol_upper,))
            row = cursor.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No price data found for symbol '{symbol}'"
            )
        
        price_data = PriceData(
            timestamp=row[0],
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=int(row[5])
        )
        
        return LatestPriceResponse(
            symbol=symbol_upper,
            price=price_data
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_latest_price ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()


@router.get("/{symbol}/relative-strength", response_model=RelativeStrengthTimeseriesResponse)
async def get_relative_strength_timeseries(
    symbol: str,
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get relative strength timeseries data for a symbol
    
    Query parameters:
    - start_date: Start date for the query (defaults to 1 year ago if not specified)
    - end_date: End date for the query (defaults to today if not specified)
    """
    cursor = db.cursor()
    
    try:
        symbol_upper = symbol.upper()
        
        # Set default dates if not provided
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=365)
        
        # Convert timezone-aware datetimes to naive (database uses DATE without timezone)
        if start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)
        
        # Check if symbol exists
        cursor.execute("SELECT COUNT(*) FROM tickers WHERE symbol = %s", (symbol_upper,))
        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
        
        # Query relative strength data
        # Convert datetime to date for comparison with DATE column
        start_date_only = start_date.date() if isinstance(start_date, datetime) else start_date
        end_date_only = end_date.date() if isinstance(end_date, datetime) else end_date
        
        query = """
            SELECT calculation_date, rs_rating, weighted_change, 
                   pct_change_3mo, pct_change_6mo, pct_change_9mo, pct_change_12mo
            FROM stock_indicators
            WHERE symbol = %s 
              AND calculation_date >= %s 
              AND calculation_date <= %s
            ORDER BY calculation_date ASC
        """
        
        cursor.execute(query, (symbol_upper, start_date_only, end_date_only))
        rows = cursor.fetchall()
        
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No relative strength data found for symbol '{symbol}' in the specified date range"
            )
        
        # Convert to RelativeStrengthData objects
        rs_data = []
        for row in rows:
            # Convert date to datetime for consistency
            # PostgreSQL returns calculation_date as a date object
            if isinstance(row[0], date):
                calc_date = datetime.combine(row[0], datetime.min.time())
            elif isinstance(row[0], datetime):
                calc_date = row[0]
            else:
                # Try to parse if it's a string
                calc_date = datetime.fromisoformat(str(row[0])) if isinstance(row[0], str) else datetime.now()
            
            rs_data.append(RelativeStrengthData(
                calculation_date=calc_date,
                rs_rating=row[1],
                weighted_change=float(row[2]) if row[2] is not None else None,
                pct_change_3mo=float(row[3]) if row[3] is not None else None,
                pct_change_6mo=float(row[4]) if row[4] is not None else None,
                pct_change_9mo=float(row[5]) if row[5] is not None else None,
                pct_change_12mo=float(row[6]) if row[6] is not None else None,
            ))
        
        return RelativeStrengthTimeseriesResponse(
            symbol=symbol_upper,
            data=rs_data,
            count=len(rs_data),
            start_date=start_date,
            end_date=end_date
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"get_relative_strength_timeseries ERROR: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()

