#!/usr/bin/env python3
"""
EC2 Wrapper Script for daily_update_stocks.py

This script is designed to run on EC2 Linux instances.
It sets up the environment and calls the daily_update_stocks function.
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Set up paths for EC2 environment
SCRIPT_DIR = Path(__file__).parent.absolute()
os.chdir(SCRIPT_DIR)

# Add current directory to Python path
sys.path.insert(0, str(SCRIPT_DIR))

# Set up environment variables
os.environ['PYTHONUNBUFFERED'] = '1'  # Disable buffering for real-time logs

def main():
    """Main entry point for EC2 execution"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run daily stock update on EC2')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of tickers to process (for testing). Example: --limit 100')
    args = parser.parse_args()
    
    print(f"{'='*70}")
    print(f"EC2 Daily Stock Update - Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working Directory: {SCRIPT_DIR}")
    if args.limit:
        print(f"TEST MODE: Limited to {args.limit} tickers")
    print(f"{'='*70}\n")
    
    try:
        # Import the daily_update_stocks module
        from daily_update_stocks import daily_update_stocks
        
        # Call the main function with limit if provided
        daily_update_stocks(limit=args.limit)
        
        print(f"\n{'='*70}")
        print(f"EC2 Daily Stock Update - Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        return 130
        
    except Exception as e:
        print(f"\n✗ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Write error to a separate error log
        error_log_path = SCRIPT_DIR / "logs" / f"ec2_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        error_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(error_log_path, 'w') as f:
            f.write(f"Error at {datetime.now()}\n")
            f.write(f"{'='*70}\n")
            f.write(f"{str(e)}\n")
            f.write(f"{'='*70}\n")
            traceback.print_exc(file=f)
        
        print(f"Error log saved to: {error_log_path}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

