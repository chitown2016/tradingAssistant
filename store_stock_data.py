from dotenv import load_dotenv
import time
import pandas as pd
import yfinance as yf
import os
import psycopg2
from datetime import datetime

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    port=os.getenv('DB_PORT'),
    dbname=os.getenv('DB_NAME')
)

def store_stock_data(symbol):
    """Store OHLC data for a single stock"""
    print(f"Fetching data for {symbol}...")
    
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="1y", auto_adjust=True)
    
    cursor = conn.cursor()
    count = 0
    
    for date, row in df.iterrows():
        cursor.execute("""
            INSERT INTO yahoo_adjusted_stock_prices 
            (timestamp, symbol, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, timestamp) DO NOTHING
        """, (
            date.to_pydatetime(),
            symbol,
            float(row['Open']),
            float(row['High']),
            float(row['Low']),
            float(row['Close']),
            int(row['Volume'])
        ))
        count += 1
    
    conn.commit()
    cursor.close()
    print(f"✓ Stored {count} records for {symbol}")

def get_all_us_tickers():
    """Get all US stock tickers from NASDAQ"""
    
    # NASDAQ traded stocks
    nasdaq_url = 'ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt'
    nasdaq_df = pd.read_csv(nasdaq_url, sep='|')
    nasdaq_symbols = nasdaq_df[nasdaq_df['Test Issue'] == 'N']['Symbol'].tolist()
    
    # Other exchanges traded on NASDAQ
    other_url = 'ftp://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt'
    other_df = pd.read_csv(other_url, sep='|')
    other_symbols = other_df[other_df['Test Issue'] == 'N']['ACT Symbol'].tolist()
    
    # Combine and clean
    all_symbols = list(set(nasdaq_symbols + other_symbols))
    
    # Remove test symbols and special characters
    all_symbols = [s for s in all_symbols if isinstance(s, str) and '$' not in s and '.' not in s]
    all_symbols = [s for s in all_symbols if s != 'Symbol']  # Remove header
    
    print(f"Found {len(all_symbols)} US stock tickers")
    return sorted(all_symbols)

def load_stock_list(filename='us_stock_tickers.txt'):
    """Load stock symbols from file"""
    with open(filename, 'r') as f:
        # Skip comment lines and empty lines
        return [line.strip().upper() for line in f 
                if line.strip() and not line.startswith('#')]

def get_completed_symbols(conn):
    """Get list of symbols already in database"""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT symbol FROM yahoo_adjusted_stock_prices")
    completed = set(row[0] for row in cursor.fetchall())
    cursor.close()
    return completed

def store_stock_data_safe(symbol, conn):
    """
    Store stock data with error handling
    Returns: (success: bool, records: int, error: str)
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y", auto_adjust=True)
        
        if df.empty:
            return (False, 0, "No data available")
        
        cursor = conn.cursor()
        count = 0
        
        for date, row in df.iterrows():
            cursor.execute("""
                INSERT INTO yahoo_adjusted_stock_prices 
                (timestamp, symbol, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, timestamp) DO NOTHING
            """, (
                date.to_pydatetime(),
                symbol,
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                int(row['Volume'])
            ))
            count += 1
        
        conn.commit()
        cursor.close()
        return (True, count, None)
        
    except Exception as e:
        return (False, 0, str(e))

def bulk_load_stocks(symbols, conn, resume=True):
    """
    Bulk load stocks with progress tracking and resume capability
    """
    start_time = datetime.now()
    
    # Setup logging
    log_file = f"bulk_load_{start_time.strftime('%Y%m%d_%H%M%S')}.log"
    
    print(f"{'='*70}")
    print(f"BULK STOCK LOAD - Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    
    # Resume from previous run if requested
    if resume:
        completed = get_completed_symbols(conn)
        symbols = [s for s in symbols if s not in completed]
        print(f"Resume mode: {len(completed)} already loaded, {len(symbols)} remaining")
    
    total = len(symbols)
    stats = {
        'success': 0,
        'failed': 0,
        'total': total,
        'total_records': 0,
        'failed_symbols': []
    }
    
    print(f"Loading {total} stocks...")
    print(f"Estimated time: {total * 2 / 3600:.1f} hours")
    print(f"Log file: {log_file}\n")
    
    # Open log file
    with open(log_file, 'w') as log:
        log.write(f"Bulk Load Started: {start_time}\n")
        log.write(f"Total symbols: {total}\n\n")
        
        for i, symbol in enumerate(symbols, 1):
            # Store data
            success, records, error = store_stock_data_safe(symbol, conn)
            
            # Update stats
            if success:
                stats['success'] += 1
                stats['total_records'] += records
                message = f"[{i}/{total}] {symbol}: ✓ {records} records"
                print(message)
                log.write(f"{message}\n")
            else:
                stats['failed'] += 1
                stats['failed_symbols'].append((symbol, error))
                message = f"[{i}/{total}] {symbol}: ✗ {error}"
                print(message)
                log.write(f"{message}\n")
            
            # Progress report every 100 stocks
            if i % 100 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = i / elapsed if elapsed > 0 else 0
                remaining_time = (total - i) / rate / 60 if rate > 0 else 0
                
                progress_msg = f"""
{'='*70}
PROGRESS UPDATE: {i}/{total} ({i/total*100:.1f}%)
Elapsed: {elapsed/60:.1f} minutes
Success: {stats['success']}, Failed: {stats['failed']}
Rate: {rate:.2f} stocks/sec
Estimated remaining: {remaining_time:.1f} minutes
{'='*70}
"""
                print(progress_msg)
                log.write(progress_msg + "\n")
                log.flush()  # Force write to disk
            
            # Rate limiting - be nice to Yahoo Finance
            time.sleep(1)  # 1 second between requests
        
        # Final summary
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        summary = f"""
{'='*70}
BULK LOAD COMPLETE!
{'='*70}
Start time:  {start_time.strftime('%Y-%m-%d %H:%M:%S')}
End time:    {end_time.strftime('%Y-%m-%d %H:%M:%S')}
Duration:    {elapsed/3600:.2f} hours ({elapsed/60:.1f} minutes)

Total symbols processed: {total}
✓ Successful: {stats['success']} ({stats['success']/total*100:.1f}%)
✗ Failed: {stats['failed']} ({stats['failed']/total*100:.1f}%)
Total records inserted: {stats['total_records']:,}

Average rate: {total/elapsed:.2f} stocks/second
{'='*70}
"""
        print(summary)
        log.write(summary)
        
        # Write failed symbols
        if stats['failed_symbols']:
            log.write("\n\nFailed Symbols:\n")
            log.write("="*70 + "\n")
            for symbol, error in stats['failed_symbols']:
                log.write(f"{symbol}: {error}\n")
    
    # Save failed symbols to retry later
    if stats['failed_symbols']:
        with open('failed_symbols.txt', 'w') as f:
            for symbol, error in stats['failed_symbols']:
                f.write(f"{symbol}\n")
        print(f"\n✓ Failed symbols saved to 'failed_symbols.txt' for retry")
    
    return stats

# Test with a single stock
if __name__ == "__main__":
    try:
        # Test with single stock
        # store_stock_data("AAPL")
        
        # Bulk load all stocks
        symbols = load_stock_list('us_stock_tickers.txt')
        print(f"Loaded {len(symbols)} symbols from file")
        
        # Ask for confirmation
        response = input(f"\nReady to load {len(symbols)} stocks. This will take several hours. Continue? (yes/no): ")
        
        if response.lower() == 'yes':
            stats = bulk_load_stocks(symbols, conn, resume=True)
            print(f"\n✓ Bulk load complete!")
            print(f"Success rate: {stats['success']/stats['total']*100:.1f}%")
        else:
            print("Cancelled.")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Progress has been saved.")
        print("You can resume by running the script again (resume mode is automatic).")
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()
        print("Connection closed.")