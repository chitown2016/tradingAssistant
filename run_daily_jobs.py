#!/usr/bin/env python3
"""
Orchestrator script to run daily_update_stocks and calculate_indicators consecutively
with Telegram notifications for success/failure.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Set up environment variables
os.environ['PYTHONUNBUFFERED'] = '1'  # Disable buffering for real-time logs

# Set up paths
SCRIPT_DIR = Path(__file__).parent.absolute()
os.chdir(SCRIPT_DIR)
sys.path.insert(0, str(SCRIPT_DIR))

# Import telegram notifier
from telegram_notifier import send_telegram_message, format_job_status

def run_script(script_name: str, args: List[str] = None) -> Dict:
    """Run a script and capture results"""
    if args is None:
        args = []
    
    script_path = SCRIPT_DIR / script_name
    start_time = datetime.now()
    
    print(f"\n{'='*70}")
    print(f"Running: {script_name}")
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            capture_output=False,  # Let output go to console
            check=False  # Don't raise on non-zero exit
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        success = result.returncode == 0
        
        return {
            'script': script_name,
            'success': success,
            'exit_code': result.returncode,
            'start_time': start_time,
            'end_time': end_time,
            'duration_seconds': duration,
        }
        
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            'script': script_name,
            'success': False,
            'exit_code': -1,
            'start_time': start_time,
            'end_time': end_time,
            'duration_seconds': duration,
            'error': str(e),
        }

def main():
    """Main orchestrator"""
    overall_start = datetime.now()
    
    print(f"{'='*70}")
    print(f"JOB ORCHESTRATOR - Started: {overall_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    # Run scripts sequentially
    results = []
    
    # Script 1: Daily Update
    result1 = run_script('run_daily_update_ec2.py')
    results.append(result1)
    
    if not result1['success']:
        print(f"\n✗ {result1['script']} FAILED with exit code {result1['exit_code']}")
        print("Stopping - not running calculate_indicators.py")
        
        # Send failure notification and exit
        overall_end = datetime.now()
        overall_duration = (overall_end - overall_start).total_seconds()
        message = format_job_status(results, False, overall_duration)
        send_telegram_message(message)
        
        print(f"\n{'='*70}")
        print(f"✗ JOB FAILED - Stopped after first script failure")
        print(f"Total duration: {overall_duration:.2f} seconds")
        print(f"{'='*70}")
        
        return 1
    
    # Script 2: Stock Indicators (only runs if first succeeded)
    result2 = run_script('calculate_indicators.py')
    results.append(result2)
    
    if not result2['success']:
        print(f"\n✗ {result2['script']} FAILED with exit code {result2['exit_code']}")
    
    # Overall status
    overall_end = datetime.now()
    overall_duration = (overall_end - overall_start).total_seconds()
    all_success = all(r['success'] for r in results)
    
    # Send Telegram notification
    message = format_job_status(results, all_success, overall_duration)
    send_telegram_message(message)
    
    # Print summary
    print(f"\n{'='*70}")
    if all_success:
        print(f"✓ ALL SCRIPTS COMPLETED SUCCESSFULLY")
    else:
        print(f"✗ SOME SCRIPTS FAILED")
    print(f"Total duration: {overall_duration:.2f} seconds")
    print(f"{'='*70}")
    
    return 0 if all_success else 1

if __name__ == "__main__":
    sys.exit(main())



