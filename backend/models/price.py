"""
Pydantic models for price data endpoints
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PriceData(BaseModel):
    """OHLCV price data point"""
    timestamp: datetime = Field(..., description="Date and time of the price data")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., description="Closing price")
    volume: int = Field(..., description="Trading volume")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2024-01-15T00:00:00",
                "open": 150.25,
                "high": 152.30,
                "low": 149.80,
                "close": 151.50,
                "volume": 1000000
            }
        }


class SymbolMetadata(BaseModel):
    """Symbol metadata from tickers table"""
    symbol: str = Field(..., description="Stock symbol/ticker")
    asset_type: Optional[str] = Field(None, description="Asset type (EQUITY, ETF, INDEX, etc.)")
    country: Optional[str] = Field(None, description="Country code (ISO 3166-1 alpha-3)")
    first_date: Optional[datetime] = Field(None, description="First available date")
    last_date: Optional[datetime] = Field(None, description="Last available date")
    record_count: Optional[int] = Field(None, description="Number of price records")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "asset_type": "EQUITY",
                "country": "USA",
                "first_date": "2020-01-01T00:00:00",
                "last_date": "2024-01-15T00:00:00",
                "record_count": 1000,
                "last_updated": "2024-01-15T10:00:00"
            }
        }


class TimeSeriesResponse(BaseModel):
    """Response wrapper for time series price data"""
    symbol: str = Field(..., description="Stock symbol")
    data: List[PriceData] = Field(..., description="List of price data points")
    count: int = Field(..., description="Number of data points returned")
    start_date: Optional[datetime] = Field(None, description="Start date of the query")
    end_date: Optional[datetime] = Field(None, description="End date of the query")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "count": 30,
                "start_date": "2024-01-01T00:00:00",
                "end_date": "2024-01-30T00:00:00",
                "data": [
                    {
                        "timestamp": "2024-01-15T00:00:00",
                        "open": 150.25,
                        "high": 152.30,
                        "low": 149.80,
                        "close": 151.50,
                        "volume": 1000000
                    }
                ]
            }
        }


class LatestPriceResponse(BaseModel):
    """Response for latest price data"""
    symbol: str = Field(..., description="Stock symbol")
    price: PriceData = Field(..., description="Latest price data point")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "price": {
                    "timestamp": "2024-01-15T00:00:00",
                    "open": 150.25,
                    "high": 152.30,
                    "low": 149.80,
                    "close": 151.50,
                    "volume": 1000000
                }
            }
        }

