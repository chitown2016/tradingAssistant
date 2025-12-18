"""
Database connection module for FastAPI
Provides connection pooling and dependency injection for database sessions
"""
import os
from contextlib import contextmanager
from typing import Generator
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool
from fastapi import Depends
from functools import lru_cache

# Load environment variables
load_dotenv()


class DatabasePool:
    """Manages PostgreSQL connection pool for FastAPI"""
    
    def __init__(self):
        self._pool: pool.ThreadedConnectionPool | None = None
    
    def initialize(self, min_conn: int = 1, max_conn: int = 10):
        """
        Initialize the connection pool
        
        Args:
            min_conn: Minimum number of connections in the pool
            max_conn: Maximum number of connections in the pool
        """
        if self._pool is not None:
            return
        
        try:
            self._pool = pool.ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                host=os.getenv('DB_HOST'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                port=os.getenv('DB_PORT'),
                dbname=os.getenv('DB_NAME')
            )
        except Exception as e:
            raise ConnectionError(f"Failed to create database connection pool: {e}")
    
    def get_connection(self, statement_timeout_seconds: int | None = None):
        """
        Get a connection from the pool
        
        Args:
            statement_timeout_seconds: Optional timeout in seconds for SQL statements.
                                     Default None uses server default.
        
        Returns:
            psycopg2 connection object
        """
        if self._pool is None:
            raise RuntimeError("Connection pool not initialized. Call initialize() first.")
        
        conn = self._pool.getconn()
        
        # Set statement timeout if specified
        if statement_timeout_seconds:
            cursor = conn.cursor()
            cursor.execute(f"SET statement_timeout = '{statement_timeout_seconds}s'")
            cursor.close()
        
        return conn
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        if self._pool is not None:
            self._pool.putconn(conn)
    
    def close_all(self):
        """Close all connections in the pool"""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None


# Global database pool instance
_db_pool = DatabasePool()


def get_db_connection(statement_timeout_seconds: int | None = None):
    """
    Create and return a direct database connection (non-pooled)
    This wraps the original get_db_connection() from store_stock_data.py
    for backward compatibility and non-FastAPI use cases.
    
    Args:
        statement_timeout_seconds: Optional timeout in seconds.
                                 Default None uses server default.
    
    Returns:
        psycopg2 connection object
    """
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT'),
        dbname=os.getenv('DB_NAME')
    )
    
    # Set statement timeout if specified
    if statement_timeout_seconds:
        cursor = conn.cursor()
        cursor.execute(f"SET statement_timeout = '{statement_timeout_seconds}s'")
        cursor.close()
    
    return conn


@contextmanager
def get_db_session(statement_timeout_seconds: int | None = None) -> Generator:
    """
    Context manager for database sessions using the connection pool.
    Use this for non-FastAPI code that needs connection pooling.
    
    Args:
        statement_timeout_seconds: Optional timeout in seconds.
    
    Yields:
        psycopg2 connection object
    
    Example:
        with get_db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tickers")
            results = cursor.fetchall()
    """
    conn = None
    try:
        conn = _db_pool.get_connection(statement_timeout_seconds)
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            _db_pool.return_connection(conn)


def get_db() -> Generator:
    """
    FastAPI dependency for database connections.
    Use this in FastAPI route handlers with Depends().
    
    Yields:
        psycopg2 connection object
    
    Example:
        @app.get("/api/v1/symbols")
        def get_symbols(db: psycopg2.extensions.connection = Depends(get_db)):
            cursor = db.cursor()
            cursor.execute("SELECT * FROM tickers")
            return cursor.fetchall()
    """
    conn = None
    try:
        conn = _db_pool.get_connection()
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            _db_pool.return_connection(conn)


def init_db_pool(min_conn: int = 1, max_conn: int = 10):
    """
    Initialize the database connection pool.
    Call this during FastAPI startup.
    
    Args:
        min_conn: Minimum number of connections in the pool (default: 1)
        max_conn: Maximum number of connections in the pool (default: 10)
    """
    _db_pool.initialize(min_conn=min_conn, max_conn=max_conn)


def close_db_pool():
    """
    Close all connections in the pool.
    Call this during FastAPI shutdown.
    """
    _db_pool.close_all()


# Convenience function for FastAPI dependency injection
DbDep = Depends(get_db)

