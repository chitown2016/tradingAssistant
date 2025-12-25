"""
Date utility functions for trading calculations.
"""
import pandas as pd
from datetime import datetime
import pytz
import pandas_market_calendars as mcal


def get_calc_date():
    """
    Determine the calculation date based on New York time and NYSE trading days.
    
    Rules:
    - If current time is after 4:30 PM NY time AND today is a NYSE trading day, use today
    - Otherwise, use the previous NYSE trading day
    
    Returns:
        datetime.date: The date to use for calculations
    """
    # Get New York timezone
    ny_tz = pytz.timezone('America/New_York')
    
    # Get current time in NY timezone
    ny_now = datetime.now(ny_tz)
    ny_date = ny_now.date()
    ny_time = ny_now.time()
    
    # Check if it's after 4:30 PM (16:30)
    is_after_430 = ny_time >= datetime.strptime('16:30', '%H:%M').time()
    
    # Get NYSE calendar
    nyse = mcal.get_calendar('NYSE')
    
    # Check if today is a NYSE trading day
    is_trading_day = nyse.valid_days(start_date=ny_date, end_date=ny_date).size > 0
    
    if is_after_430 and is_trading_day:
        return ny_date
    else:
        # Get previous trading day
        # Get trading days up to today (exclusive) and take the last one
        end_date = ny_date - pd.Timedelta(days=1)  # Start from yesterday to avoid today
        trading_days = nyse.valid_days(start_date=end_date - pd.Timedelta(days=7), end_date=end_date)
        
        return trading_days[-1].date()
           

