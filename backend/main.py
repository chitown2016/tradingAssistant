"""
FastAPI application entry point for TradingView-style stock charting web app
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from backend.db import init_db_pool, close_db_pool

# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown events"""
    # Startup: Initialize database connection pool
    init_db_pool(min_conn=1, max_conn=10)
    yield
    # Shutdown: Close database connection pool
    close_db_pool()


app = FastAPI(
    title="Stock Charting API",
    description="REST API for stock price data and indicators",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
# Get allowed origins from environment variable or use defaults
# CORS_ORIGINS can be a comma-separated list of origins, or "*" for all origins
# Example: CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://yourdomain.com
cors_origins_env = os.getenv("CORS_ORIGINS", "*")

# Parse CORS origins
if cors_origins_env == "*":
    # Development: Allow all origins
    allow_origins = ["*"]
else:
    # Production: Use specific origins from environment variable
    allow_origins = [origin.strip() for origin in cors_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "message": "Stock Charting API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# Import API routes
from backend.api.v1 import symbols

# Include routers
app.include_router(symbols.router, prefix="/api/v1/symbols", tags=["symbols"])

# TODO: Add indicators router in Phase 1.3
# from backend.api.v1 import indicators
# app.include_router(indicators.router, prefix="/api/v1", tags=["indicators"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

