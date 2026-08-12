#!/usr/bin/env python3
"""
Continuous Background Daemon for AlphaPulse Investopedia Auto-Trader.
Runs run_auto_trader.py automatically every weekday (Mon-Fri) at 06:30 AM PST (Market Open).
"""

import os
import sys
import time
import subprocess
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_EXEC = os.path.join(PROJECT_DIR, "venv", "bin", "python3")
SCRIPT_PATH = os.path.join(PROJECT_DIR, "investopedia_executor", "run_auto_trader.py")

TARGET_HOUR = 6   # 6:30 AM PST
TARGET_MINUTE = 30

def is_weekday():
    return datetime.now().weekday() < 5  # Mon = 0, Fri = 4

def run_job():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Triggering daily Investopedia auto-trader...")
    try:
        subprocess.run([PYTHON_EXEC, SCRIPT_PATH], check=True)
    except Exception as e:
        print(f"Error running auto-trader job: {e}")

def main():
    print(f"🤖 AlphaPulse Investopedia Background Daemon started.")
    print(f"Scheduled to run every weekday at {TARGET_HOUR:02d}:{TARGET_MINUTE:02d} AM PST.")
    
    last_run_day = None
    while True:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # Check if weekday, target time reached, and hasn't run yet today
        if is_weekday() and now.hour == TARGET_HOUR and now.minute >= TARGET_MINUTE and last_run_day != today_str:
            last_run_day = today_str
            run_job()
            
        time.sleep(30)

if __name__ == "__main__":
    main()
