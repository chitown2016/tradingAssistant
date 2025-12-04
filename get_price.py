from store_stock_data import get_db_connection

def get_all_dates_with_prices():
    """
    Get all unique dates from yahoo_adjusted_stock_prices table.
    
    Returns:
        List of datetime.date objects, sorted ascending
    """
    conn = get_db_connection(statement_timeout_seconds=600)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT time_bucket('1 day', timestamp)::DATE as price_date
            FROM yahoo_adjusted_stock_prices
            WHERE close IS NOT NULL
            GROUP BY time_bucket('1 day', timestamp)
            ORDER BY price_date ASC
        """)
        dates = [row[0] for row in cursor.fetchall()]
        return dates
    finally:
        cursor.close()
        conn.close()
