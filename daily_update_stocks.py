from dotenv import load_dotenv
import time
import pandas as pd
import yfinance as yf
import os
import psycopg2
from datetime import datetime, timedelta
from psycopg2.extras import execute_values
import sys
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from store_stock_data import get_db_connection, get_all_us_tickers

# Fix Windows Unicode encoding issues AND disable buffering
if sys.platform == 'win32':
    try:
        # This works in regular terminal
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    except (AttributeError, io.UnsupportedOperation):
        # Fallback for Jupyter Notebook or other environments
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, 
                encoding='utf-8',
                line_buffering=True
            )

load_dotenv()

def get_symbols_in_db(conn):
    """Get set of symbols that have data in database - uses fast tickers table"""
    cursor = conn.cursor()
    cursor.execute("SELECT symbol FROM tickers")
    symbols = set(row[0] for row in cursor.fetchall())
    cursor.close()
    return symbols

def has_recent_corporate_actions(symbol, days=5):
    """Check if symbol has corporate actions in the past N days"""
    try:
        ticker = yf.Ticker(symbol)
        actions = ticker.actions
        
        if actions.empty:
            return False
        
        # Check if any actions in the past N days
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Make cutoff_date timezone-aware to match actions index
        # Or convert actions index to timezone-naive
        if actions.index.tz is not None:
            # Actions index is timezone-aware, convert to naive
            actions.index = actions.index.tz_localize(None)
        
        recent_actions = actions[actions.index > cutoff_date]
        
        return not recent_actions.empty
    except Exception as e:
        # If we can't check, assume no corporate actions
        print(f"  Warning: Could not check corporate actions for {symbol}: {e}")
        return False

def normalize_timestamp(dt):
    """Convert any timestamp to timezone-naive datetime for database storage
    
    Args:
        dt: pandas Timestamp or datetime object (may have timezone)
    
    Returns:
        datetime object without timezone (naive)
    """
    if hasattr(dt, 'to_pydatetime'):
        dt = dt.to_pydatetime()
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt

def process_incremental_batch(batch_data, batch_tickers, new_tickers, max_tickers, conn, log):
    """Process a single batch of downloaded data incrementally (for 'max' period to save memory)
    
    Args:
        batch_data: DataFrame with downloaded data for this batch
        batch_tickers: List of ticker symbols in this batch
        new_tickers: Set of new ticker symbols
        max_tickers: Set of max ticker symbols (corporate actions)
        conn: Database connection
        log: Log file handle
    
    Returns:
        Dictionary with stats: {'new_success': int, 'new_records': int, 'max_success': int, 'max_records': int}
    """
    stats = {'new_success': 0, 'new_records': 0, 'max_success': 0, 'max_records': 0}
    
    # Separate batch tickers into new and max
    batch_new = [s for s in batch_tickers if s in new_tickers]
    batch_max = [s for s in batch_tickers if s in max_tickers]
    
    # Process new tickers from this batch
    if batch_new:
        for symbol in batch_new:
            try:
                # Extract data for this symbol
                if len(batch_data.columns.levels[0]) > 1 if hasattr(batch_data.columns, 'levels') else False:
                    if symbol not in batch_data.columns.levels[0]:
                        continue
                    df = batch_data[symbol]
                else:
                    df = batch_data
                
                if df.empty or df.dropna().empty:
                    continue
                
                # Process using existing insert_ticker_data function
                success, records = insert_ticker_data(conn, symbol, df, log)
                if success:
                    stats['new_success'] += 1
                    stats['new_records'] += records
            except Exception as e:
                log.write(f"  ✗ {symbol} (new, incremental): {e}\n")
    
    # Process max tickers from this batch
    if batch_max:
        for symbol in batch_max:
            try:
                # Extract data for this symbol
                if len(batch_data.columns.levels[0]) > 1 if hasattr(batch_data.columns, 'levels') else False:
                    if symbol not in batch_data.columns.levels[0]:
                        continue
                    df = batch_data[symbol]
                else:
                    df = batch_data
                
                if df.empty or df.dropna().empty:
                    continue
                
                # Process using existing delete_and_insert_ticker_data function
                success, records = delete_and_insert_ticker_data(conn, symbol, df, log)
                if success:
                    stats['max_success'] += 1
                    stats['max_records'] += records
            except Exception as e:
                log.write(f"  ✗ {symbol} (max, incremental): {e}\n")
    
    return stats

def download_data_in_batches(tickers, period='max', batch_size=200, delay=2, process_callback=None):
    """Download data in batches to avoid rate limiting
    
    Args:
        tickers: List of ticker symbols
        period: '5d', 'max', etc.
        batch_size: Number of tickers per batch (default 200)
        delay: Seconds to wait between batches (default 2)
        process_callback: Optional function(batch_data, batch_tickers) to process each batch immediately.
                         If provided and period=='max', batches are processed incrementally instead of combined.
    
    Returns:
        Combined DataFrame with all ticker data (or None if process_callback used)
    """
    if not tickers:
        return None
    
    # For 'max' period with callback, process incrementally to save memory
    if period == 'max' and process_callback is not None:
        print(f"  Downloading {len(tickers)} tickers in batches of {batch_size} (incremental processing)...")
        total_batches = (len(tickers) + batch_size - 1) // batch_size
        
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            print(f"    Batch {batch_num}/{total_batches}: Downloading {len(batch)} tickers...")
            
            try:
                batch_data = yf.download(
                    batch,
                    period=period,
                    group_by='ticker',
                    auto_adjust=True,
                    threads=True
                )
                
                if batch_data is not None and not batch_data.empty:
                    # Process immediately via callback
                    process_callback(batch_data, batch)
                    print(f"    ✓ Batch {batch_num} downloaded and processed")
                else:
                    print(f"    ⚠ Batch {batch_num} returned no data")
                    
            except Exception as e:
                print(f"    ✗ Batch {batch_num} error: {e}")
            
            # Delay between batches to avoid rate limiting
            if i + batch_size < len(tickers):
                time.sleep(delay)
        
        # Return None to indicate incremental processing was used
        return None
    
    # Original behavior: combine all batches (for shorter periods or no callback)
    print(f"  Downloading {len(tickers)} tickers in batches of {batch_size}...")
    
    all_data = []
    total_batches = (len(tickers) + batch_size - 1) // batch_size
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        print(f"    Batch {batch_num}/{total_batches}: Downloading {len(batch)} tickers...")
        
        try:
            batch_data = yf.download(
                batch,
                period=period,
                group_by='ticker',
                auto_adjust=True,
                threads=True
            )
            
            if batch_data is not None and not batch_data.empty:
                all_data.append(batch_data)
                print(f"    ✓ Batch {batch_num} complete")
            else:
                print(f"    ⚠ Batch {batch_num} returned no data")
                
        except Exception as e:
            print(f"    ✗ Batch {batch_num} error: {e}")
        
        # Delay between batches to avoid rate limiting
        if i + batch_size < len(tickers):
            time.sleep(delay)
    
    # Combine all batches
    if not all_data:
        return None
    
    if len(all_data) == 1:
        return all_data[0]
    
    # Concatenate along columns for multi-ticker data
    print(f"  Combining {len(all_data)} batches...")
    combined = pd.concat(all_data, axis=1)
    return combined

def get_ticker_metadata(symbol):
    """Get asset type and country for a symbol"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        asset_type = info.get('quoteType', 'EQUITY')
        country = info.get('country', 'USA')
        
        # Map country names to ISO codes
        country_map = {
            'United States': 'USA',
            'Canada': 'CAN',
            'United Kingdom': 'GBR',
            'Germany': 'DEU',
            'France': 'FRA',
            'Japan': 'JPN',
            'China': 'CHN',
            'India': 'IND',
            'Australia': 'AUS',
            'Brazil': 'BRA',
            'Mexico': 'MEX',
            'South Korea': 'KOR',
            'Spain': 'ESP',
            'Italy': 'ITA',
            'Netherlands': 'NLD',
            'Switzerland': 'CHE',
            'Sweden': 'SWE',
            'Belgium': 'BEL',
            'Ireland': 'IRL',
            'Israel': 'ISR',
        }
        country_code = country_map.get(country, country if len(country) == 3 else 'USA')
        
        return asset_type, country_code
    except:
        return 'EQUITY', 'USA'

def detect_corporate_actions_and_get_data(existing_symbols, conn, lookback_days=5):
    """Detect corporate actions by comparing prices AND cache the lookback data
    
    Downloads lookback-day data once, compares first day's price with database to detect
    corporate actions, and returns both the symbols needing full reload and the
    lookback-day data (to reuse for symbols without corporate actions).
    
    Args:
        existing_symbols: List of symbols already in database
        conn: Database connection
        lookback_days: Number of days to look back (default: 5)
    
    Returns:
        symbols_with_changes: Set of symbols that need max reload (corporate actions detected)
        data_lookback: The lookback-day data we downloaded (reuse for other symbols!)
    """
    # Handle empty database case
    if not existing_symbols:
        print("\n  No existing symbols to check for corporate actions")
        return set(), None
    
    period_str = f"{lookback_days}d"
    print(f"\n  Downloading {lookback_days}-day data for {len(existing_symbols)} symbols...")
    
    # Download lookback-day data in batches to avoid rate limiting
    data_lookback = download_data_in_batches(
        existing_symbols,
        period=period_str,
        batch_size=500,
        delay=2
    )
    
    if data_lookback is None or data_lookback.empty:
        print(f"  ⚠ No {lookback_days}-day data downloaded")
        return set(), None
    
    print(f"  ✓ Downloaded, now comparing with database prices...")
    
    # Determine the first date from Yahoo data
    first_date = data_lookback.index[0].to_pydatetime().date()
    print(f"  Comparing prices for date: {first_date}")
    
    # OPTIMIZATION: Fetch all symbols' prices for that date in ONE query
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, close 
        FROM yahoo_adjusted_stock_prices
        WHERE timestamp = %s
    """, (first_date,))
    
    # Build dictionary - only keep symbols we care about
    all_prices = cursor.fetchall()
    db_prices = {row[0]: float(row[1]) for row in all_prices if row[0] in existing_symbols}
    cursor.close()
    
    print(f"  ✓ Fetched {len(db_prices)} prices from database in single query")
    
    # Now compare each symbol (no more database queries!)
    symbols_with_changes = set()
    
    # Create detailed log file for corporate action detection
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)
    log_file_path = os.path.join(logs_dir, f"corporate_actions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    with open(log_file_path, 'w', encoding='utf-8') as log:
        log.write(f"Corporate Action Detection - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"Comparing {len(existing_symbols)} symbols for date: {first_date}\n\n")
        log.write(f"{'Symbol':<10} {'DB Price':>12} {'Yahoo Price':>12} {'Abs Diff':>12} {'% Diff':>10}\n")
        log.write("="*60 + "\n")
        
        for i, symbol in enumerate(existing_symbols, 1):
            try:
                # Get Yahoo data for this symbol
                if len(existing_symbols) == 1:
                    df = data_lookback
                else:
                    if symbol not in data_lookback.columns.levels[0]:
                        continue
                    df = data_lookback[symbol]
                
                if df.empty or df.dropna().empty:
                    continue
                
                yahoo_close = float(df['Close'].iloc[0])
                
                # Compare with database price (already fetched in bulk)
                if symbol in db_prices:
                    db_close = db_prices[symbol]
                    
                    # Compare prices - ANY difference means adjustment needed (dividends, splits, etc.)
                    diff_abs = abs(yahoo_close - db_close)
                    diff_pct = (diff_abs / db_close * 100) if db_close > 0 else 0
                    
                    if diff_abs > 0.001:
                        symbols_with_changes.add(symbol)
                        
                        # Log to file
                        log.write(f"{symbol:<10} {db_close:>12.4f} {yahoo_close:>12.4f} {diff_abs:>12.4f} {diff_pct:>9.2f}%\n")
                        
                        # Print to console
                        print(f"    {symbol}: DB=${db_close:.2f}, Yahoo=${yahoo_close:.2f} (${diff_abs:.4f}, {diff_pct:.2f}%)")
            
            except Exception as e:
                print(f"    Warning: Error checking {symbol}: {e}")
            
            if i % 500 == 0:
                print(f"    Processed {i}/{len(existing_symbols)} symbols...")
        
        # Write summary
        log.write(f"\n{'='*60}\n")
        log.write(f"Total symbols flagged: {len(symbols_with_changes)}\n")
    
    print(f"\n  ✓ Found {len(symbols_with_changes)} symbols with price mismatches")
    print(f"  ✓ Corporate action log saved to '{log_file_path}'")
    return symbols_with_changes, data_lookback

def categorize_tickers(all_symbols, conn, lookback_days=5):
    """Categorize tickers into new_tickers, max_tickers, and tickers_lookback
    
    Args:
        all_symbols: List of all ticker symbols
        conn: Database connection
        lookback_days: Number of days to look back (default: 5)
    
    Returns:
        new_tickers: Symbols not in database (need full history)
        max_tickers: Symbols with corporate actions (need full history reload)
        tickers_lookback: Symbols without corporate actions (need lookback-day update)
        data_lookback_cached: The lookback-day data already downloaded (reuse it!)
    """
    print("\nCategorizing tickers by update strategy...")
    
    symbols_in_db = get_symbols_in_db(conn)
    
    new_tickers = []
    existing_tickers = []
    
    # First pass: separate new vs existing
    for symbol in all_symbols:
        if symbol not in symbols_in_db:
            new_tickers.append(symbol)
        else:
            existing_tickers.append(symbol)
    
    print(f"  New tickers: {len(new_tickers)}")
    print(f"  Existing tickers: {len(existing_tickers)}")
    
    # Detect corporate actions by price comparison AND get the lookback data
    symbols_with_changes, data_lookback_cached = detect_corporate_actions_and_get_data(existing_tickers, conn, lookback_days=lookback_days)
    
    # Categorize
    max_tickers = list(symbols_with_changes)
    tickers_lookback = [s for s in existing_tickers if s not in symbols_with_changes]
    
    print(f"\nCategorization complete:")
    print(f"  New tickers (INSERT only): {len(new_tickers)}")
    print(f"  Max tickers (DELETE + INSERT): {len(max_tickers)}")
    print(f"  {lookback_days}-day tickers (UPSERT): {len(tickers_lookback)}")
    
    return new_tickers, max_tickers, tickers_lookback, data_lookback_cached

def daily_update_stocks(limit=None, lookback_days=5):
    """Main function to perform daily stock update
    
    Args:
        limit: Optional int to limit number of symbols (for testing). Example: limit=10
        lookback_days: Number of days to look back for updates (default: 5). 
                      Use a higher value if the script hasn't run for several days.
    """
    start_time = datetime.now()
    
    # Setup logging - create logs directory if it doesn't exist
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, f"daily_update_{start_time.strftime('%Y%m%d_%H%M%S')}.log")
    
    print(f"{'='*70}")
    print(f"DAILY STOCK UPDATE - Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Lookback days: {lookback_days}")
    print(f"{'='*70}")
    
    # Step 1: Generate fresh ticker list
    print("\n[1/4] Generating fresh ticker list...")
    all_symbols = get_all_us_tickers(limit=limit)
    print(f"✓ Generated us_stock_tickers.txt with {len(all_symbols)} tickers")
    
    # Step 2: Connect to database and categorize tickers
    print("\n[2/4] Connecting to database and categorizing tickers...")
    conn = get_db_connection(statement_timeout_seconds=600)
    
    new_tickers, max_tickers, tickers_lookback, data_lookback_cached = categorize_tickers(all_symbols, conn, lookback_days=lookback_days)
    conn.close()  # Close connection before long download to prevent timeout
    print("  ✓ Connection closed after categorization")
    
    # Step 3: Download stock data (no active DB connection during this)
    print("\n[3/4] Downloading stock data...")
    
    # Download max data (new + corporate action tickers)
    max_download_tickers = new_tickers + max_tickers
    max_data = None
    incremental_stats = {'new_success': 0, 'new_records': 0, 'max_success': 0, 'max_records': 0}
    incremental_processing_used = False
    
    if max_download_tickers:
        print(f"\n  Downloading MAX history for {len(max_download_tickers)} tickers...")
        try:
            # For 'max' period, use incremental processing to avoid memory issues
            # Open connection and log file early for incremental processing
            conn_inc = get_db_connection(statement_timeout_seconds=600)
            log_inc = open(log_file, 'w', encoding='utf-8')
            log_inc.write(f"Daily Update Started: {start_time}\n")
            log_inc.write(f"Lookback days: {lookback_days}\n")
            log_inc.write(f"Total symbols: {len(all_symbols)}\n")
            log_inc.write(f"New tickers: {len(new_tickers)}\n")
            log_inc.write(f"Max tickers (corporate actions): {len(max_tickers)}\n")
            log_inc.write(f"{lookback_days}-day tickers: {len(tickers_lookback)}\n")
            if limit:
                log_inc.write(f"TEST MODE: Limited to {limit} symbols\n")
            log_inc.write("\n")
            
            # Create callback to process each batch immediately
            def process_max_batch(batch_data, batch_tickers):
                nonlocal incremental_stats
                # Process this batch incrementally
                batch_stats = process_incremental_batch(
                    batch_data, batch_tickers, 
                    set(new_tickers), set(max_tickers),
                    conn_inc, log_inc
                )
                # Accumulate stats
                incremental_stats['new_success'] += batch_stats['new_success']
                incremental_stats['new_records'] += batch_stats['new_records']
                incremental_stats['max_success'] += batch_stats['max_success']
                incremental_stats['max_records'] += batch_stats['max_records']
            
            max_data = download_data_in_batches(
                max_download_tickers,
                period='max',
                batch_size=200,
                delay=2,
                process_callback=process_max_batch
            )
            
            if max_data is None:
                # Incremental processing was used
                incremental_processing_used = True
                print(f"  ✓ Downloaded and processed MAX data incrementally")
                print(f"    New tickers: {incremental_stats['new_success']} processed, {incremental_stats['new_records']:,} records")
                print(f"    Max tickers: {incremental_stats['max_success']} processed, {incremental_stats['max_records']:,} records")
                # Keep connection and log open for lookback processing
                conn = conn_inc
                log_file_handle = log_inc
            else:
                print(f"  ✓ Downloaded MAX data")
                # Close incremental connection/log, will reopen for bulk processing
                conn_inc.close()
                log_inc.close()
        except Exception as e:
            print(f"  ✗ Error downloading MAX data: {e}")
            if 'conn_inc' in locals():
                conn_inc.close()
            if 'log_inc' in locals():
                log_inc.close()
    
    # Use cached lookback-day data (already downloaded during categorization!)
    if tickers_lookback:
        if data_lookback_cached is not None:
            print(f"\n  ✓ Using cached {lookback_days}-day data for {len(tickers_lookback)} tickers (already downloaded)")
        else:
            print(f"\n  ⚠ Warning: {len(tickers_lookback)} tickers need {lookback_days}-day update but data_lookback_cached is None")
            print(f"     This may indicate an issue during categorization step")
    
    # Step 4: Database updates
    print("\n[4/4] Updating database...")
    
    # If incremental processing was used, connection and log are already open
    # If incremental processing was used, connection and log are already open
    if not incremental_processing_used:
        conn = get_db_connection(statement_timeout_seconds=600)  # Fresh connection!
    else:
        # Close and reopen connection after heavy incremental processing
        # This prevents connection timeouts and lock accumulation
        print("  Closing connection after incremental processing, reopening for bulk operations...")
        conn_inc.close()
        conn = get_db_connection(statement_timeout_seconds=600)  # Fresh connection!
        print("  ✓ Connection reopened")
    
    try:
        # Open log file for writing (if not already open from incremental processing)
        if incremental_processing_used:
            log = log_file_handle
            # Log incremental stats
            log.write(f"\nIncremental Processing Stats:\n")
            log.write(f"  New tickers: {incremental_stats['new_success']} processed, {incremental_stats['new_records']:,} records\n")
            log.write(f"  Max tickers: {incremental_stats['max_success']} processed, {incremental_stats['max_records']:,} records\n")
            log.write("\n")
            log.write(f"[4/4] Updating database...\n")  # Log this step
            log.write(f"  Checking {lookback_days}-day tickers: {len(tickers_lookback) if tickers_lookback else 0} tickers\n")
            log.write(f"  data_lookback_cached is {'None' if data_lookback_cached is None else 'available'}\n")
            log.flush()  # Flush incremental stats
        else:
            log = open(log_file, 'w', encoding='utf-8')
            log.write(f"Daily Update Started: {start_time}\n")
            log.write(f"Lookback days: {lookback_days}\n")
            log.write(f"Total symbols: {len(all_symbols)}\n")
            log.write(f"New tickers: {len(new_tickers)}\n")
            log.write(f"Max tickers (corporate actions): {len(max_tickers)}\n")
            log.write(f"{lookback_days}-day tickers: {len(tickers_lookback)}\n")
            if limit:
                log.write(f"TEST MODE: Limited to {limit} symbols\n")
            log.write("\n")
        
        # Initialize stats - include incremental stats if used (MUST be outside else block!)
        if incremental_processing_used:
            stats = {
                'new_success': incremental_stats['new_success'],
                'new_failed': 0,
                'max_success': incremental_stats['max_success'],
                'max_failed': 0,
                'lookback_success': 0,
                'lookback_failed': 0,
                'total_records': incremental_stats['new_records'] + incremental_stats['max_records'],
                'failed_tickers': []
            }
        else:
            stats = {
                'new_success': 0,
                'new_failed': 0,
                'max_success': 0,
                'max_failed': 0,
                'lookback_success': 0,
                'lookback_failed': 0,
                'total_records': 0,
                'failed_tickers': []
            }
        
        # Process new tickers (BATCHED BULK INSERT)
        # Skip if already processed incrementally
        if new_tickers and max_data is not None and not incremental_processing_used:
            print(f"\n  Processing {len(new_tickers)} new tickers (BATCHED BULK INSERT)...")
            try:
                success_count, total_records = batched_bulk_insert_new_tickers(conn, new_tickers, max_data, log, batch_size=100)
                stats['new_success'] = success_count
                stats['total_records'] += total_records
                print(f"  ✓ Successfully processed {success_count} new tickers with {total_records:,} records")
            except Exception as e:
                print(f"  ✗ Batched bulk insert failed: {e}")
                log.write(f"  ✗ Batched bulk insert (new) failed: {e}\n")
                # Fallback to individual processing
                print(f"  Falling back to individual processing...")
                for symbol in new_tickers:
                    try:
                        success, records = insert_ticker_data(conn, symbol, max_data, log)
                        if success:
                            stats['new_success'] += 1
                            stats['total_records'] += records
                        else:
                            stats['new_failed'] += 1
                            stats['failed_tickers'].append((symbol, 'new', 'No data available'))
                    except Exception as e2:
                        stats['new_failed'] += 1
                        stats['failed_tickers'].append((symbol, 'new', str(e2)))
                        log.write(f"  ✗ {symbol} (new): {e2}\n")
        
        # Process max tickers (BATCHED BULK DELETE + INSERT)
        # Skip if already processed incrementally
        if max_tickers and max_data is not None and not incremental_processing_used:
            print(f"\n  Processing {len(max_tickers)} tickers with corporate actions (BATCHED BULK DELETE + INSERT)...")
            try:
                success_count, total_records = batched_bulk_delete_and_insert_max_tickers(conn, max_tickers, max_data, log, batch_size=50)
                stats['max_success'] = success_count
                stats['total_records'] += total_records
                print(f"  ✓ Successfully processed {success_count} tickers with {total_records:,} records")
            except Exception as e:
                print(f"  ✗ Batched bulk delete+insert failed: {e}")
                log.write(f"  ✗ Batched bulk delete+insert (max) failed: {e}\n")
                # Fallback to individual processing
                print(f"  Falling back to individual processing...")
                for symbol in max_tickers:
                    try:
                        success, records = delete_and_insert_ticker_data(conn, symbol, max_data, log)
                        if success:
                            stats['max_success'] += 1
                            stats['total_records'] += records
                        else:
                            stats['max_failed'] += 1
                            stats['failed_tickers'].append((symbol, 'max', 'No data available'))
                    except Exception as e2:
                        stats['max_failed'] += 1
                        stats['failed_tickers'].append((symbol, 'max', str(e2)))
                        log.write(f"  ✗ {symbol} (max): {e2}\n")
        
        # Process lookback-day tickers (BATCHED BULK UPSERT) - use cached data
        log.write(f"\n--- Starting {lookback_days}-day ticker processing ---\n")
        log.write(f"  tickers_lookback count: {len(tickers_lookback) if tickers_lookback else 0}\n")
        log.write(f"  data_lookback_cached is None: {data_lookback_cached is None}\n")
        log.flush()
        
        if tickers_lookback:
            if data_lookback_cached is not None:
                print(f"\n  Processing {len(tickers_lookback)} tickers ({lookback_days}-day BATCHED BULK UPSERT)...")
                log.write(f"\nProcessing {len(tickers_lookback)} tickers ({lookback_days}-day BATCHED BULK UPSERT)...\n")
                log.flush()
                try:
                    success_count, total_records = batched_bulk_upsert_ticker_data(conn, tickers_lookback, data_lookback_cached, log, batch_size=500)
                    stats['lookback_success'] = success_count
                    stats['total_records'] += total_records
                    print(f"  ✓ Successfully processed {success_count} tickers with {total_records:,} records")
                    log.write(f"  ✓ Successfully processed {success_count} tickers with {total_records:,} records\n")
                    log.flush()
                except Exception as e:
                    print(f"  ✗ Batched bulk upsert failed: {e}")
                    log.write(f"  ✗ Batched bulk upsert ({lookback_days}d) failed: {e}\n")
                    log.flush()
                    # Fallback to individual processing
                    print(f"  Falling back to individual processing...")
                    for symbol in tickers_lookback:
                        try:
                            success, records = upsert_ticker_data(conn, symbol, data_lookback_cached, log)
                            if success:
                                stats['lookback_success'] += 1
                                stats['total_records'] += records
                            else:
                                stats['lookback_failed'] += 1
                                stats['failed_tickers'].append((symbol, f'{lookback_days}d', 'No data available'))
                        except Exception as e2:
                            stats['lookback_failed'] += 1
                            stats['failed_tickers'].append((symbol, f'{lookback_days}d', str(e2)))
                            log.write(f"  ✗ {symbol} ({lookback_days}d): {e2}\n")
            else:
                # data_lookback_cached is None - log this issue
                print(f"\n  ⚠ Warning: {len(tickers_lookback)} tickers need {lookback_days}-day update but data_lookback_cached is None")
                print(f"     Skipping {lookback_days}-day ticker processing")
                log.write(f"\n⚠ Warning: {len(tickers_lookback)} tickers need {lookback_days}-day update but data_lookback_cached is None\n")
                log.write(f"  Skipping {lookback_days}-day ticker processing\n")
                log.write(f"  This means data_lookback_cached was not set during categorization step\n")
                log.flush()
                stats['lookback_failed'] = len(tickers_lookback)
                for symbol in tickers_lookback:
                    stats['failed_tickers'].append((symbol, f'{lookback_days}d', 'data_lookback_cached is None'))
        else:
            log.write(f"  No {lookback_days}-day tickers to process (tickers_lookback is empty or None)\n")
            log.flush()
        
        # Final summary - always write this even if there were errors
        log.write(f"\n--- Preparing final summary ---\n")
        log.flush()
        try:
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            
            total_success = stats['new_success'] + stats['max_success'] + stats['lookback_success']
            total_failed = stats['new_failed'] + stats['max_failed'] + stats['lookback_failed']
            total_processed = total_success + total_failed
            
            summary = f"""
{'='*70}
DAILY UPDATE COMPLETE!
{'='*70}
Start time:  {start_time.strftime('%Y-%m-%d %H:%M:%S')}
End time:    {end_time.strftime('%Y-%m-%d %H:%M:%S')}
Duration:    {elapsed/60:.1f} minutes
Lookback days: {lookback_days}

New tickers:
  ✓ Success: {stats['new_success']}
  ✗ Failed: {stats['new_failed']}

Corporate action tickers (MAX reload):
  ✓ Success: {stats['max_success']}
  ✗ Failed: {stats['max_failed']}

Regular update tickers ({lookback_days}-day):
  ✓ Success: {stats['lookback_success']}
  ✗ Failed: {stats['lookback_failed']}

Total:
  Processed: {total_processed}
  Success: {total_success} ({total_success/total_processed*100:.1f}% if total_processed > 0 else 0)
  Failed: {total_failed}
  Total records inserted/updated: {stats['total_records']:,}
{'='*70}
"""
            print(summary)
            log.write(summary)
            log.flush()  # Flush summary immediately
        except Exception as e:
            # Even if summary generation fails, try to write something
            error_msg = f"\n\nERROR generating final summary: {e}\n"
            print(error_msg)
            try:
                log.write(error_msg)
                log.flush()
            except:
                pass
        
        # Write failed tickers
        if stats['failed_tickers']:
            log.write("\n\nFailed Tickers:\n")
            log.write("="*70 + "\n")
            for symbol, category, error in stats['failed_tickers']:
                log.write(f"{symbol} ({category}): {error}\n")
            log.flush()
            
            # Save to file for retry
            failed_tickers_file = os.path.join(logs_dir, 'daily_update_failed.txt')
            with open(failed_tickers_file, 'w') as f:
                for symbol, category, error in stats['failed_tickers']:
                    f.write(f"{symbol}\n")
            print(f"\n✓ Failed tickers saved to '{failed_tickers_file}'")
        
        print(f"✓ Log saved to '{log_file}'")
        log.flush()  # Final flush before closing
    
    except Exception as e:
        # Catch any unhandled exceptions in the database update section
        error_msg = f"\n\n{'='*70}\nFATAL ERROR in database update section:\n{str(e)}\n{'='*70}\n"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
        # Try to log the error
        if 'log' in locals() and hasattr(log, 'write'):
            try:
                log.write(error_msg)
                log.write("\nTraceback:\n")
                traceback.print_exc(file=log)
                log.flush()
            except:
                pass
    
    finally:
        # Ensure log is flushed and closed before closing connection
        if 'log' in locals() and hasattr(log, 'close'):
            try:
                log.flush()  # Final flush before closing
                log.close()
            except:
                pass
        conn.close()
        print("\nConnection closed.")

def batched_bulk_insert_new_tickers(conn, new_tickers, max_data, log, batch_size=100):
    """Batched bulk insert for new tickers"""
    print(f"\n  Processing {len(new_tickers)} new tickers in batches of {batch_size}...")
    
    total_success = 0
    total_records = 0
    
    # Process in batches
    for i in range(0, len(new_tickers), batch_size):
        batch = new_tickers[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(new_tickers) + batch_size - 1) // batch_size
        
        print(f"  Batch {batch_num}/{total_batches}: Processing {len(batch)} tickers...")
        
        all_values = []
        ticker_metadata = {}  # {symbol: (first_date, last_date, record_count, asset_type, country)}
        
        # Collect data for this batch
        for symbol in batch:
            try:
                if len(max_data.columns.levels[0]) > 1 if hasattr(max_data.columns, 'levels') else False:
                    if symbol not in max_data.columns.levels[0]:
                        continue
                    df = max_data[symbol]
                else:
                    df = max_data
                
                if df.empty or df.dropna().empty:
                    continue
                
                symbol_values = []
                max_price_limit = 10**12
                
                # Convert to list of tuples with dates for sorting
                date_price_list = []
                for date, row in df.iterrows():
                    if pd.notna(row['Open']) and pd.notna(row['Close']):
                        open_price = float(row['Open'])
                        high_price = float(row['High'])
                        low_price = float(row['Low'])
                        close_price = float(row['Close'])
                        
                        date_price_list.append((
                            date,
                            open_price, high_price, low_price, close_price,
                            int(row['Volume'])
                        ))
                
                if not date_price_list:
                    continue
                
                # Sort by date descending (most recent first)
                date_price_list.sort(key=lambda x: x[0], reverse=True)
                
                # Find cutoff date: first date (going back from current) where price > 10^12
                cutoff_date = None
                for date, open_price, high_price, low_price, close_price, volume in date_price_list:
                    if (abs(open_price) >= max_price_limit or 
                        abs(high_price) >= max_price_limit or 
                        abs(low_price) >= max_price_limit or 
                        abs(close_price) >= max_price_limit):
                        cutoff_date = date
                        break
                
                # Filter: keep only dates > cutoff_date (if cutoff found, else keep all)
                if cutoff_date is not None:
                    # Keep dates after cutoff_date (excluding the problematic cutoff_date itself)
                    filtered_dates = [x for x in date_price_list if x[0] > cutoff_date]
                    if not filtered_dates:
                        log.write(f"  ✗ {symbol} (new): Skipped - all dates have prices > 10^12\n")
                        continue
                else:
                    # No problematic dates found, keep all
                    filtered_dates = date_price_list
                
                # Convert to symbol_values format
                for date, open_price, high_price, low_price, close_price, volume in filtered_dates:
                    dt = normalize_timestamp(date)
                    symbol_values.append((
                        dt, symbol,
                        open_price, high_price, low_price,
                        close_price, volume
                    ))
                
                if symbol_values:
                    all_values.extend(symbol_values)
                    first_date = min(v[0] for v in symbol_values)
                    last_date = max(v[0] for v in symbol_values)
                    asset_type, country = get_ticker_metadata(symbol)
                    ticker_metadata[symbol] = (first_date, last_date, len(symbol_values), asset_type, country)
            
            except Exception as e:
                log.write(f"  ✗ {symbol} (new): Error collecting data: {e}\n")
        
        if not all_values:
            print(f"    ⚠ Batch {batch_num}: No data to insert")
            continue
        
        # Process this batch
        cursor = conn.cursor()
        try:
            # Bulk insert price data
            execute_values(
                cursor,
                """
                INSERT INTO yahoo_adjusted_stock_prices 
                (timestamp, symbol, open, high, low, close, volume)
                VALUES %s
                ON CONFLICT (symbol, timestamp) DO NOTHING
                """,
                all_values,
                page_size=10000
            )
            
            # Bulk insert tickers metadata
            ticker_records = [
                (symbol, asset_type, country, first_date, last_date, record_count, datetime.now())
                for symbol, (first_date, last_date, record_count, asset_type, country) in ticker_metadata.items()
            ]
            
            execute_values(
                cursor,
                """
                INSERT INTO tickers (symbol, asset_type, country, first_date, last_date, record_count, last_updated)
                VALUES %s
                ON CONFLICT (symbol) DO NOTHING
                """,
                ticker_records,
                page_size=1000
            )
            
            conn.commit()
            cursor.close()
            
            total_success += len(ticker_metadata)
            total_records += len(all_values)
            print(f"    ✓ Batch {batch_num}: {len(ticker_metadata)} tickers, {len(all_values):,} records")
        
        except Exception as e:
            conn.rollback()
            cursor.close()
            print(f"    ✗ Batch {batch_num} failed: {e}")
            log.write(f"  ✗ Batch {batch_num} (new) failed: {e}\n")
            # Continue with next batch
    
    print(f"  ✓ Completed: {total_success} tickers, {total_records:,} total records")
    return total_success, total_records

def batched_bulk_delete_and_insert_max_tickers(conn, max_tickers, max_data, log, batch_size=50):
    """Batched bulk delete and insert for corporate action tickers"""
    print(f"\n  Processing {len(max_tickers)} corporate action tickers in batches of {batch_size}...")
    
    total_success = 0
    total_records = 0
    
    # Process in batches
    for i in range(0, len(max_tickers), batch_size):
        batch = max_tickers[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(max_tickers) + batch_size - 1) // batch_size
        
        print(f"  Batch {batch_num}/{total_batches}: Processing {len(batch)} tickers...")
        
        all_values = []
        ticker_metadata = {}  # {symbol: (first_date, last_date, record_count)}
        
        # Collect data for this batch
        for symbol in batch:
            try:
                if len(max_data.columns.levels[0]) > 1 if hasattr(max_data.columns, 'levels') else False:
                    if symbol not in max_data.columns.levels[0]:
                        continue
                    df = max_data[symbol]
                else:
                    df = max_data
                
                if df.empty or df.dropna().empty:
                    continue
                
                symbol_values = []
                max_price_limit = 10**12
                
                # Convert to list of tuples with dates for sorting
                date_price_list = []
                for date, row in df.iterrows():
                    if pd.notna(row['Open']) and pd.notna(row['Close']):
                        open_price = float(row['Open'])
                        high_price = float(row['High'])
                        low_price = float(row['Low'])
                        close_price = float(row['Close'])
                        
                        date_price_list.append((
                            date,
                            open_price, high_price, low_price, close_price,
                            int(row['Volume'])
                        ))
                
                if not date_price_list:
                    continue
                
                # Sort by date descending (most recent first)
                date_price_list.sort(key=lambda x: x[0], reverse=True)
                
                # Find cutoff date: first date (going back from current) where price > 10^12
                cutoff_date = None
                for date, open_price, high_price, low_price, close_price, volume in date_price_list:
                    if (abs(open_price) >= max_price_limit or 
                        abs(high_price) >= max_price_limit or 
                        abs(low_price) >= max_price_limit or 
                        abs(close_price) >= max_price_limit):
                        cutoff_date = date
                        break
                
                # Filter: keep only dates > cutoff_date (if cutoff found, else keep all)
                if cutoff_date is not None:
                    # Keep dates after cutoff_date (excluding the problematic cutoff_date itself)
                    filtered_dates = [x for x in date_price_list if x[0] > cutoff_date]
                    if not filtered_dates:
                        log.write(f"  ✗ {symbol} (max): Skipped - all dates have prices > 10^12\n")
                        continue
                else:
                    # No problematic dates found, keep all
                    filtered_dates = date_price_list
                
                # Convert to symbol_values format
                for date, open_price, high_price, low_price, close_price, volume in filtered_dates:
                    dt = normalize_timestamp(date)
                    symbol_values.append((
                        dt, symbol,
                        open_price, high_price, low_price,
                        close_price, volume
                    ))
                
                if symbol_values:
                    all_values.extend(symbol_values)
                    first_date = min(v[0] for v in symbol_values)
                    last_date = max(v[0] for v in symbol_values)
                    ticker_metadata[symbol] = (first_date, last_date, len(symbol_values))
            
            except Exception as e:
                log.write(f"  ✗ {symbol} (max): Error collecting data: {e}\n")
        
        if not all_values:
            print(f"    ⚠ Batch {batch_num}: No data to insert")
            continue
        
        # Process this batch
        cursor = conn.cursor()
        try:
            # Delete for this batch
            cursor.execute("""
                DELETE FROM yahoo_adjusted_stock_prices 
                WHERE symbol = ANY(%s)
            """, (batch,))
            deleted = cursor.rowcount
            
            # Bulk insert this batch
            execute_values(
                cursor,
                """
                INSERT INTO yahoo_adjusted_stock_prices 
                (timestamp, symbol, open, high, low, close, volume)
                VALUES %s
                """,
                all_values,
                page_size=10000
            )
            
            # Update tickers metadata for this batch
            for symbol, (first_date, last_date, record_count) in ticker_metadata.items():
                cursor.execute("""
                    UPDATE tickers 
                    SET first_date = %s, last_date = %s, record_count = %s, last_updated = NOW()
                    WHERE symbol = %s
                """, (first_date, last_date, record_count, symbol))
            
            conn.commit()
            cursor.close()
            
            total_success += len(ticker_metadata)
            total_records += len(all_values)
            print(f"    ✓ Batch {batch_num}: {len(ticker_metadata)} tickers, {len(all_values):,} records (deleted {deleted} old records)")
        
        except Exception as e:
            conn.rollback()
            cursor.close()
            print(f"    ✗ Batch {batch_num} failed: {e}")
            log.write(f"  ✗ Batch {batch_num} (max) failed: {e}\n")
            # Continue with next batch
    
    print(f"  ✓ Completed: {total_success} tickers, {total_records:,} total records")
    return total_success, total_records

def batched_bulk_upsert_ticker_data(conn, tickers_lookback, data_lookback_cached, log, batch_size=500):
    """Batched bulk upsert for lookback-day tickers"""
    print(f"\n  Processing {len(tickers_lookback)} lookback-day tickers in batches of {batch_size}...")
    
    total_success = 0
    total_records = 0
    
    # Process in batches
    for i in range(0, len(tickers_lookback), batch_size):
        batch = tickers_lookback[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(tickers_lookback) + batch_size - 1) // batch_size
        
        print(f"  Batch {batch_num}/{total_batches}: Processing {len(batch)} tickers...")
        
        all_values = []
        ticker_metadata = {}  # {symbol: last_date}
        
        # Collect data for this batch
        for symbol in batch:
            try:
                if len(data_lookback_cached.columns.levels[0]) > 1 if hasattr(data_lookback_cached.columns, 'levels') else False:
                    if symbol not in data_lookback_cached.columns.levels[0]:
                        continue
                    df = data_lookback_cached[symbol]
                else:
                    df = data_lookback_cached
                
                if df.empty or df.dropna().empty:
                    continue
                
                symbol_values = []
                for date, row in df.iterrows():
                    if pd.notna(row['Open']) and pd.notna(row['Close']):
                        dt = date.to_pydatetime()
                        symbol_values.append((
                            dt, symbol,
                            float(row['Open']), float(row['High']), float(row['Low']),
                            float(row['Close']), int(row['Volume'])
                        ))
                
                if symbol_values:
                    all_values.extend(symbol_values)
                    last_date = max(v[0] for v in symbol_values)
                    ticker_metadata[symbol] = last_date
            
            except Exception as e:
                log.write(f"  ✗ {symbol} (lookback): Error collecting data: {e}\n")
        
        if not all_values:
            print(f"    ⚠ Batch {batch_num}: No data to insert")
            continue
        
        # Process this batch
        cursor = conn.cursor()
        try:
            # Bulk upsert price data
            execute_values(
                cursor,
                """
                INSERT INTO yahoo_adjusted_stock_prices 
                (timestamp, symbol, open, high, low, close, volume)
                VALUES %s
                ON CONFLICT (symbol, timestamp) 
                DO UPDATE SET 
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
                """,
                all_values,
                page_size=10000
            )
            
            # Update tickers metadata for this batch
            for symbol, last_date in ticker_metadata.items():
                cursor.execute("""
                    UPDATE tickers 
                    SET last_date = %s,
                        record_count = (
                            SELECT COUNT(*) 
                            FROM yahoo_adjusted_stock_prices 
                            WHERE symbol = %s
                        ),
                        last_updated = NOW()
                    WHERE symbol = %s
                """, (last_date, symbol, symbol))
            
            conn.commit()
            cursor.close()
            
            total_success += len(ticker_metadata)
            total_records += len(all_values)
            print(f"    ✓ Batch {batch_num}: {len(ticker_metadata)} tickers, {len(all_values):,} records")
        
        except Exception as e:
            conn.rollback()
            cursor.close()
            print(f"    ✗ Batch {batch_num} failed: {e}")
            log.write(f"  ✗ Batch {batch_num} (lookback) failed: {e}\n")
            # Continue with next batch
    
    print(f"  ✓ Completed: {total_success} tickers, {total_records:,} total records")
    return total_success, total_records

def insert_ticker_data(conn, symbol, data, log):
    """Insert data for a new ticker (INSERT only)"""
    try:
        # Handle both single ticker and multi-ticker downloads
        if len(data.columns.levels[0]) > 1 if hasattr(data.columns, 'levels') else False:
            # Multi-ticker download
            if symbol not in data.columns.levels[0]:
                return (False, 0)
            df = data[symbol]
        else:
            # Single ticker download
            df = data
        
        if df.empty or df.dropna().empty:
            return (False, 0)
        
        # Prepare values for bulk insert
        values = []
        for date, row in df.iterrows():
            if pd.notna(row['Open']) and pd.notna(row['Close']):
                values.append((
                    normalize_timestamp(date),
                    symbol,
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    int(row['Volume'])
                ))
        
        if not values:
            return (False, 0)
        
        cursor = conn.cursor()
        
        # Insert price data
        execute_values(
            cursor,
            """
            INSERT INTO yahoo_adjusted_stock_prices 
            (timestamp, symbol, open, high, low, close, volume)
            VALUES %s
            ON CONFLICT (symbol, timestamp) DO NOTHING
            """,
            values,
            page_size=5000
        )
        
        # Get dates for tickers table
        first_date = min(v[0] for v in values)
        last_date = max(v[0] for v in values)
        
        # Get metadata
        asset_type, country = get_ticker_metadata(symbol)
        
        # Insert into tickers table
        cursor.execute("""
            INSERT INTO tickers (symbol, asset_type, country, first_date, last_date, record_count, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (symbol) DO NOTHING
        """, (symbol, asset_type, country, first_date, last_date, len(values)))
        
        conn.commit()
        cursor.close()
        
        log.write(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: ✓ {symbol} (new): {len(values)} records\n")
        print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: ✓ {symbol} (new): {len(values)} records")
        return (True, len(values))
        
    except Exception as e:
        conn.rollback()
        raise e

def delete_and_insert_ticker_data(conn, symbol, data, log):
    """Delete existing data and insert fresh data for ticker with corporate actions"""
    try:
        # Handle both single ticker and multi-ticker downloads
        if len(data.columns.levels[0]) > 1 if hasattr(data.columns, 'levels') else False:
            # Multi-ticker download
            if symbol not in data.columns.levels[0]:
                return (False, 0)
            df = data[symbol]
        else:
            # Single ticker download
            df = data
        
        if df.empty or df.dropna().empty:
            return (False, 0)
        
        # Prepare values for bulk insert
        values = []
        for date, row in df.iterrows():
            if pd.notna(row['Open']) and pd.notna(row['Close']):
                values.append((
                    normalize_timestamp(date),
                    symbol,
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    int(row['Volume'])
                ))
        
        if not values:
            return (False, 0)
        
        cursor = conn.cursor()
        
        # Delete existing price data
        cursor.execute("DELETE FROM yahoo_adjusted_stock_prices WHERE symbol = %s", (symbol,))
        
        # Insert fresh price data
        execute_values(
            cursor,
            """
            INSERT INTO yahoo_adjusted_stock_prices 
            (timestamp, symbol, open, high, low, close, volume)
            VALUES %s
            """,
            values,
            page_size=5000
        )
        
        # Update tickers table with new dates/counts
        first_date = min(v[0] for v in values)
        last_date = max(v[0] for v in values)
        
        cursor.execute("""
            UPDATE tickers 
            SET first_date = %s,
                last_date = %s,
                record_count = %s,
                last_updated = NOW()
            WHERE symbol = %s
        """, (first_date, last_date, len(values), symbol))
        
        conn.commit()
        cursor.close()
        
        log.write(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: ✓ {symbol} (max): {len(values)} records\n")
        print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: ✓ {symbol} (max): {len(values)} records")
        return (True, len(values))
        
    except Exception as e:
        conn.rollback()
        raise e

def upsert_ticker_data(conn, symbol, data, log):
    """Upsert lookback-day data for ticker without corporate actions"""
    try:
        # Handle both single ticker and multi-ticker downloads
        if len(data.columns.levels[0]) > 1 if hasattr(data.columns, 'levels') else False:
            # Multi-ticker download
            if symbol not in data.columns.levels[0]:
                return (False, 0)
            df = data[symbol]
        else:
            # Single ticker download
            df = data
        
        if df.empty or df.dropna().empty:
            return (False, 0)
        
        # Prepare values for bulk upsert
        values = []
        for date, row in df.iterrows():
            if pd.notna(row['Open']) and pd.notna(row['Close']):
                values.append((
                    date.to_pydatetime(),
                    symbol,
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    int(row['Volume'])
                ))
        
        if not values:
            return (False, 0)
        
        cursor = conn.cursor()
        
        # Upsert price data
        execute_values(
            cursor,
            """
            INSERT INTO yahoo_adjusted_stock_prices 
            (timestamp, symbol, open, high, low, close, volume)
            VALUES %s
            ON CONFLICT (symbol, timestamp) 
            DO UPDATE SET 
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
            """,
            values,
            page_size=5000
        )
        
        # Update tickers table - update last_date and record count
        last_date = max(v[0] for v in values)
        
        cursor.execute("""
            UPDATE tickers 
            SET last_date = %s,
                record_count = (
                    SELECT COUNT(*) 
                    FROM yahoo_adjusted_stock_prices 
                    WHERE symbol = %s
                ),
                last_updated = NOW()
            WHERE symbol = %s
        """, (last_date, symbol, symbol))
        
        conn.commit()
        cursor.close()
        
        log.write(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: ✓ {symbol} (lookback): {len(values)} records\n")
        print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: ✓ {symbol} (lookback): {len(values)} records")
        return (True, len(values))
        
    except Exception as e:
        conn.rollback()
        raise e

if __name__ == "__main__":
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Daily stock update script')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of tickers to process (for testing). Example: --limit 100')
    parser.add_argument('--lookback-days', type=int, default=5, dest='lookback_days',
                        help='Number of days to look back for updates (default: 5). Use a higher value if the script hasn\'t run for several days.')
    args = parser.parse_args()
    
    try:
        # Call with limit and lookback_days if provided
        daily_update_stocks(limit=args.limit, lookback_days=args.lookback_days)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

