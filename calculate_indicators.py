import pandas as pd
from datetime import datetime
from datetime import date
import argparse
import sys
from psycopg2.extras import execute_values
from store_stock_data import get_db_connection
from get_price import get_all_dates_with_prices
from backend.utils.date_utils import get_calc_date

def calculate_indicators_batch(conn, symbols_batch, calc_date):
    """
    Calculate stock indicators for a batch of symbols.
    Returns DataFrame with calculated values (without rs_rating).
    
    Args:
        conn: Database connection
        symbols_batch: List of symbols to process
        calc_date: Date to calculate for (datetime.date)
    
    Returns:
        DataFrame with columns: symbol, calculation_date, weighted_change, 
        pct_change_3mo, pct_change_6mo, pct_change_9mo, pct_change_12mo,
        close_price, daily_percent_range, pct_change_1d, adr20,
        low_52w, current_volume, avg_volume_30d
    """
    calc_timestamp = pd.Timestamp(calc_date)
    target_3mo = calc_timestamp - pd.DateOffset(months=3)
    target_6mo = calc_timestamp - pd.DateOffset(months=6)
    target_9mo = calc_timestamp - pd.DateOffset(months=9)
    target_12mo = calc_timestamp - pd.DateOffset(months=12)
    
    # Pull price data for this batch (13 months of data for relative strength + 52 weeks for low_52w)
    # Need at least 52 weeks + 30 days for volume calculations
    start_date = (calc_timestamp - pd.DateOffset(months=13)).date()
    
    # Convert dates to timestamps for efficient index usage
    start_timestamp = datetime.combine(start_date, datetime.min.time())
    end_timestamp = datetime.combine(calc_date, datetime.max.time())
    
    query = """
        SELECT symbol, timestamp::DATE as price_date, close, high, low, volume
        FROM yahoo_adjusted_stock_prices
        WHERE symbol = ANY(%s)
          AND timestamp >= %s
          AND timestamp <= %s
        ORDER BY symbol, timestamp DESC
    """
    
    # Use cursor directly for better array parameter handling and to avoid pandas warning
    cursor = conn.cursor()
    try:
        cursor.execute(query, (symbols_batch, start_timestamp, end_timestamp))
        
        # Fetch results and convert to DataFrame
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=columns)
    finally:
        cursor.close()
    
    if df.empty:
        return pd.DataFrame()
    
    results = []
    
    for symbol in symbols_batch:
        symbol_data = df[df['symbol'] == symbol].copy()
        if symbol_data.empty:
            continue
        
        symbol_data = symbol_data.sort_values('price_date', ascending=False)
        
        # Get current price (most recent on or before calc_date)
        current_mask = symbol_data['price_date'] <= calc_date
        if not current_mask.any():
            continue
        current_price = float(symbol_data[current_mask].iloc[0]['close'])
        current_date = symbol_data[current_mask].iloc[0]['price_date']
        current_high = float(symbol_data[current_mask].iloc[0]['high'])
        current_low = float(symbol_data[current_mask].iloc[0]['low'])
        current_volume = int(symbol_data[current_mask].iloc[0]['volume'])
        
        # Get price 1 day ago (for pct_change_1d)
        price_1d_ago = None
        pct_change_1d = None
        if len(symbol_data) > 1:
            # Get the next row (previous trading day)
            next_rows = symbol_data[symbol_data['price_date'] < current_date]
            if not next_rows.empty:
                price_1d_ago = float(next_rows.iloc[0]['close'])
                if price_1d_ago > 0:
                    pct_change_1d = ((current_price - price_1d_ago) / price_1d_ago * 100)
        
        # Calculate daily_percent_range: (high - low) / close * 100
        daily_percent_range = None
        if current_price > 0:
            daily_percent_range = ((current_high - current_low) / current_price * 100)
        
        # Calculate ADR20: Average Daily Range over 20 trading days
        # ADR20 = average of (high - low) / close * 100 over last 20 days
        adr20 = None
        last_20_days = symbol_data[symbol_data['price_date'] <= calc_date].head(20)
        if len(last_20_days) >= 20:
            daily_ranges = []
            for _, row in last_20_days.iterrows():
                if row['close'] > 0:
                    daily_range = ((row['high'] - row['low']) / row['close'] * 100)
                    daily_ranges.append(daily_range)
            if daily_ranges:
                adr20 = sum(daily_ranges) / len(daily_ranges)
        
        # Calculate low_52w: Minimum low price over last 52 weeks
        # Get data from 52 weeks ago to current date
        weeks_52_ago = (calc_timestamp - pd.DateOffset(weeks=52)).date()
        data_52w = symbol_data[
            (symbol_data['price_date'] >= weeks_52_ago) & 
            (symbol_data['price_date'] <= calc_date)
        ]
        low_52w = None
        if not data_52w.empty:
            low_52w = float(data_52w['low'].min())
        
        # Calculate avg_volume_30d: Average volume over last 30 trading days
        avg_volume_30d = None
        last_30_days = symbol_data[symbol_data['price_date'] <= calc_date].head(30)
        if len(last_30_days) >= 30:
            volumes = last_30_days['volume'].astype(float)
            avg_volume_30d = int(volumes.mean())
        
        # Get price 3 months ago (within 7-day window)
        target_3mo_date = target_3mo.date()
        window_start_3mo = (target_3mo - pd.Timedelta(days=7)).date()
        mask_3mo = (symbol_data['price_date'] <= target_3mo_date) & \
                   (symbol_data['price_date'] >= window_start_3mo)
        if not mask_3mo.any():
            continue
        price_3mo = float(symbol_data[mask_3mo].iloc[0]['close'])
        date_3mo = symbol_data[mask_3mo].iloc[0]['price_date']
        
        # Get price 6 months ago
        target_6mo_date = target_6mo.date()
        window_start_6mo = (target_6mo - pd.Timedelta(days=7)).date()
        mask_6mo = (symbol_data['price_date'] <= target_6mo_date) & \
                   (symbol_data['price_date'] >= window_start_6mo)
        if not mask_6mo.any():
            continue
        price_6mo = float(symbol_data[mask_6mo].iloc[0]['close'])
        date_6mo = symbol_data[mask_6mo].iloc[0]['price_date']
        
        # Get price 9 months ago
        target_9mo_date = target_9mo.date()
        window_start_9mo = (target_9mo - pd.Timedelta(days=7)).date()
        mask_9mo = (symbol_data['price_date'] <= target_9mo_date) & \
                   (symbol_data['price_date'] >= window_start_9mo)
        if not mask_9mo.any():
            continue
        price_9mo = float(symbol_data[mask_9mo].iloc[0]['close'])
        date_9mo = symbol_data[mask_9mo].iloc[0]['price_date']
        
        # Get price 12 months ago
        target_12mo_date = target_12mo.date()
        window_start_12mo = (target_12mo - pd.Timedelta(days=7)).date()
        mask_12mo = (symbol_data['price_date'] <= target_12mo_date) & \
                    (symbol_data['price_date'] >= window_start_12mo)
        if not mask_12mo.any():
            continue
        price_12mo = float(symbol_data[mask_12mo].iloc[0]['close'])
        date_12mo = symbol_data[mask_12mo].iloc[0]['price_date']
        
        # Calculate percentage changes
        pct_change_3mo = ((current_price - price_3mo) / price_3mo * 100) if price_3mo > 0 else None
        pct_change_6mo = ((price_3mo - price_6mo) / price_6mo * 100) if price_6mo > 0 and price_3mo > 0 else None
        pct_change_9mo = ((price_6mo - price_9mo) / price_9mo * 100) if price_9mo > 0 and price_6mo > 0 else None
        pct_change_12mo = ((price_9mo - price_12mo) / price_12mo * 100) if price_12mo > 0 and price_9mo > 0 else None
        
        # Calculate weighted change
        weighted_change = None
        if all(x is not None for x in [pct_change_3mo, pct_change_6mo, pct_change_9mo, pct_change_12mo]):
            weighted_change = (
                pct_change_3mo * 0.4 +
                pct_change_6mo * 0.2 +
                pct_change_9mo * 0.2 +
                pct_change_12mo * 0.2
            )
        
        results.append({
            'symbol': symbol,
            'calculation_date': calc_date,
            'weighted_change': round(weighted_change, 2) if weighted_change is not None else None,
            'pct_change_3mo': round(pct_change_3mo, 2) if pct_change_3mo is not None else None,
            'pct_change_6mo': round(pct_change_6mo, 2) if pct_change_6mo is not None else None,
            'pct_change_9mo': round(pct_change_9mo, 2) if pct_change_9mo is not None else None,
            'pct_change_12mo': round(pct_change_12mo, 2) if pct_change_12mo is not None else None,
            'close_price': round(current_price, 4),
            'daily_percent_range': round(daily_percent_range, 2) if daily_percent_range is not None else None,
            'pct_change_1d': round(pct_change_1d, 2) if pct_change_1d is not None else None,
            'adr20': round(adr20, 2) if adr20 is not None else None,
            'low_52w': round(low_52w, 4) if low_52w is not None else None,
            'current_volume': current_volume,
            'avg_volume_30d': avg_volume_30d,
            'current_price_date': current_date,
            'price_3mo_date': date_3mo,
            'price_6mo_date': date_6mo,
            'price_9mo_date': date_9mo,
            'price_12mo_date': date_12mo
        })
    
    return pd.DataFrame(results)


def calculate_and_store_indicators(calc_date=None, batch_size=500):
    """
    Calculate and store stock indicators for all symbols in batches.
    
    Process:
    1. Process symbols in batches, calculating all indicators
    2. Store to stock_indicators table (without rs_rating)
    3. After all batches, calculate percentile ranks and update rs_rating
    
    Args:
        calc_date: Date to calculate for (default: determined by get_calc_date())
        batch_size: Number of symbols to process per batch
    """

    
    if calc_date is None:
        calc_date = get_calc_date()
    
    print(f"\n{'='*70}")
    print(f"STOCK INDICATORS CALCULATION - {calc_date}")
    print(f"{'='*70}")
    
    # Get all symbols
    conn = get_db_connection(statement_timeout_seconds=600)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT symbol 
    FROM yahoo_adjusted_stock_prices
    WHERE timestamp >= %s
      AND timestamp < %s + INTERVAL '1 day'
      AND close IS NOT NULL
""", (calc_date, calc_date))
    all_symbols = [row[0] for row in cursor.fetchall()]
    cursor.close()
    print(f"\nProcessing {len(all_symbols)} symbols in batches of {batch_size}")
    
    # Step 1: Process in batches and store indicators (without rs_rating)
    total_processed = 0
    batch_num = 0
    
    for i in range(0, len(all_symbols), batch_size):
        batch = all_symbols[i:i + batch_size]
        batch_num += 1
        total_batches = (len(all_symbols) + batch_size - 1) // batch_size
        
        print(f"\nBatch {batch_num}/{total_batches}: Processing {len(batch)} symbols...")
        
        # Calculate for this batch
        batch_results = calculate_indicators_batch(conn, batch, calc_date)
        
        if batch_results.empty:
            print(f"  ⚠ No results for this batch")
            continue
        
        # Store to database (UPSERT - update if exists, insert if new)
        cursor = conn.cursor()
        try:
            values = [
                (
                    row['symbol'],
                    row['calculation_date'],
                    row['weighted_change'],
                    row['pct_change_3mo'],
                    row['pct_change_6mo'],
                    row['pct_change_9mo'],
                    row['pct_change_12mo'],
                    row['close_price'],
                    row['daily_percent_range'],
                    row['pct_change_1d'],
                    row['adr20'],
                    row['low_52w'],
                    row['current_volume'],
                    row['avg_volume_30d']
                )
                for _, row in batch_results.iterrows()
            ]
            
            execute_values(
                cursor,
                """
                INSERT INTO stock_indicators 
                (symbol, calculation_date, weighted_change, pct_change_3mo, 
                 pct_change_6mo, pct_change_9mo, pct_change_12mo,
                 close_price, daily_percent_range, pct_change_1d, adr20,
                 low_52w, current_volume, avg_volume_30d)
                VALUES %s
                ON CONFLICT (symbol, calculation_date) 
                DO UPDATE SET
                    weighted_change = EXCLUDED.weighted_change,
                    pct_change_3mo = EXCLUDED.pct_change_3mo,
                    pct_change_6mo = EXCLUDED.pct_change_6mo,
                    pct_change_9mo = EXCLUDED.pct_change_9mo,
                    pct_change_12mo = EXCLUDED.pct_change_12mo,
                    close_price = EXCLUDED.close_price,
                    daily_percent_range = EXCLUDED.daily_percent_range,
                    pct_change_1d = EXCLUDED.pct_change_1d,
                    adr20 = EXCLUDED.adr20,
                    low_52w = EXCLUDED.low_52w,
                    current_volume = EXCLUDED.current_volume,
                    avg_volume_30d = EXCLUDED.avg_volume_30d
                """,
                values,
                page_size=batch_size
            )
            
            conn.commit()
            cursor.close()
            
            total_processed += len(batch_results)
            print(f"  ✓ Stored {len(batch_results)} results")
            
        except Exception as e:
            conn.rollback()
            cursor.close()
            print(f"  ✗ Error storing batch: {e}")
    
    print(f"\n✓ Step 1 complete: {total_processed} symbols processed")
    
    # Step 2: Calculate percentile ranks (rs_rating) for all symbols
    print(f"\nStep 2: Calculating percentile ranks (rs_rating)...")
    
    cursor = conn.cursor()
    try:
        # Get all weighted_change values for this date
        cursor.execute("""
            SELECT symbol, weighted_change
            FROM stock_indicators
            WHERE calculation_date = %s
              AND weighted_change IS NOT NULL
            ORDER BY weighted_change DESC
        """, (calc_date,))
        
        all_results = cursor.fetchall()
        
        if not all_results:
            print("  ⚠ No data found for percentile ranking")
            return
        
        # Convert to DataFrame for easy percentile calculation
        df = pd.DataFrame(all_results, columns=['symbol', 'weighted_change'])
        
        # Calculate percentile rank (1-99 scale)
        # Higher weighted_change = higher rank
        df['rs_rating'] = df['weighted_change'].rank(pct=True, method='min')
        df['rs_rating'] = (df['rs_rating'] * 98 + 1).round().astype(int)
        df['rs_rating'] = df['rs_rating'].clip(1, 99)
        
        # Update rs_rating in database
        update_values = [
            (row['rs_rating'], row['symbol'], calc_date)
            for _, row in df.iterrows()
        ]
        
        execute_values(
            cursor,
            """
            UPDATE stock_indicators
            SET rs_rating = v.rs_rating
            FROM (VALUES %s) AS v(rs_rating, symbol, calculation_date)
            WHERE stock_indicators.symbol = v.symbol
              AND stock_indicators.calculation_date = v.calculation_date
            """,
            update_values,
            page_size=1000,
            template="(%s::INTEGER, %s::TEXT, %s::DATE)"
        )
        
        conn.commit()
        cursor.close()
        
        print(f"  ✓ Updated rs_rating for {len(df)} symbols")
        print(f"    RS Rating range: {df['rs_rating'].min()} - {df['rs_rating'].max()}")
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        print(f"  ✗ Error calculating percentile ranks: {e}")
        raise
    
    conn.close()
    print(f"\n{'='*70}")
    print(f"STOCK INDICATORS CALCULATION COMPLETE")
    print(f"{'='*70}")

def calculate_and_store_indicators_for_all_dates(batch_size=500, start_date=None, end_date=None, skip_existing=False):
    """
    Calculate and store stock indicators for all dates with price data.
    
    Args:
        batch_size: Number of symbols to process per batch
        start_date: Optional start date (datetime.date) - only process dates >= this
        end_date: Optional end date (datetime.date) - only process dates <= this
        skip_existing: If True, skip dates that already have calculations
    """
    print(f"\n{'='*70}")
    print(f"STOCK INDICATORS CALCULATION - ALL DATES")
    print(f"{'='*70}")
    
    # Get all dates
    all_dates = get_all_dates_with_prices()
    
    if not all_dates:
        print("No dates found in database")
        return
    
    # Filter by date range if provided
    if start_date:
        all_dates = [d for d in all_dates if d >= start_date]
    if end_date:
        all_dates = [d for d in all_dates if d <= end_date]
    
    if not all_dates:
        print(f"No dates in specified range")
        return
    
    print(f"\nFound {len(all_dates)} dates to process")
    print(f"Date range: {all_dates[0]} to {all_dates[-1]}")
    
    # Check for existing calculations if skip_existing is True
    dates_to_process = all_dates
    if skip_existing:
        conn = get_db_connection(statement_timeout_seconds=600)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT calculation_date
                FROM stock_indicators
            """)
            existing_dates = {row[0] for row in cursor.fetchall()}
            dates_to_process = [d for d in all_dates if d not in existing_dates]
            skipped = len(all_dates) - len(dates_to_process)
            if skipped > 0:
                print(f"Skipping {skipped} dates that already have calculations")
        finally:
            cursor.close()
            conn.close()
    
    if not dates_to_process:
        print("All dates already processed")
        return
    
    print(f"Processing {len(dates_to_process)} dates...\n")
    
    # Process each date
    successful = 0
    failed = 0
    failed_dates = []
    
    for i, calc_date in enumerate(dates_to_process, 1):
        print(f"\n{'='*70}")
        print(f"Processing date {i}/{len(dates_to_process)}: {calc_date}")
        print(f"{'='*70}")
        
        try:
            calculate_and_store_indicators(calc_date=calc_date, batch_size=batch_size)
            successful += 1
        except Exception as e:
            failed += 1
            failed_dates.append((calc_date, str(e)))
            print(f"\n✗ ERROR processing {calc_date}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n{'='*70}")
    print(f"BATCH PROCESSING COMPLETE")
    print(f"{'='*70}")
    print(f"Total dates: {len(dates_to_process)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Calculate and store stock indicators (including relative strength ratings)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process only today's date (default)
  python calculate_indicators.py
  
  # Process all dates from a specific start date
  python calculate_indicators.py --start-date 2005-12-30
  
  # Process dates within a range
  python calculate_indicators.py --start-date 2020-01-01 --end-date 2024-12-31
  
  # Skip dates that already have calculations
  python calculate_indicators.py --start-date 2005-12-30 --skip-existing

Note: Date format must be YYYY-MM-DD (e.g., 2005-12-30)
        """
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        metavar='YYYY-MM-DD',
        help='Start date for batch processing. If provided, processes all dates from start_date onwards. If not provided, processes only today. Format: YYYY-MM-DD'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        metavar='YYYY-MM-DD',
        help='End date for batch processing. Only used with --start-date. Format: YYYY-MM-DD'
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Skip dates that already have calculations in the database'
    )
    
    args = parser.parse_args()
    
    # If no start_date provided, process only today
    if not args.start_date:
        calculate_and_store_indicators()
    else:
        # Parse the start_date string into a date object
        try:
            start_date_obj = datetime.strptime(args.start_date, '%Y-%m-%d').date()
            end_date_obj = None
            
            if args.end_date:
                try:
                    end_date_obj = datetime.strptime(args.end_date, '%Y-%m-%d').date()
                except ValueError:
                    print(f"Error: Invalid end-date format '{args.end_date}'. Please use YYYY-MM-DD format (e.g., 2024-12-31)")
                    sys.exit(1)
            
            print("=" * 70)
            print(f"Processing all dates from {start_date_obj}", end="")
            if end_date_obj:
                print(f" to {end_date_obj}", end="")
            print("...")
            print("=" * 70)
            
            calculate_and_store_indicators_for_all_dates(
                start_date=start_date_obj,
                end_date=end_date_obj,
                skip_existing=args.skip_existing
            )
        except ValueError:
            print("=" * 70)
            print(f"ERROR: Invalid date format '{args.start_date}'")
            print("=" * 70)
            print("\nPlease use YYYY-MM-DD format (e.g., 2005-12-30)")
            print("Run with --help to see usage examples\n")
            sys.exit(1)

