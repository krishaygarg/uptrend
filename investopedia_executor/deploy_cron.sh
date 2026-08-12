#!/bin/bash
# Cron Deployment Script for AlphaPulse Investopedia Auto-Trader.
# Installs a daily crontab job to run run_auto_trader.py every weekday at 6:30 AM PST (Market Open).

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_EXEC="$PROJECT_DIR/venv/bin/python3"
SCRIPT_PATH="$PROJECT_DIR/investopedia_executor/run_auto_trader.py"
LOG_PATH="$PROJECT_DIR/investopedia_executor/cron_output.log"

# Cron timing: 6:30 AM PST every Monday through Friday (30 6 * * 1-5)
CRON_JOB="30 6 * * 1-5 cd $PROJECT_DIR && $PYTHON_EXEC $SCRIPT_PATH >> $LOG_PATH 2>&1"

# Check if cron job already exists
(crontab -l 2>/dev/null | grep -F "$SCRIPT_PATH") >/dev/null

if [ $? -eq 0 ]; then
    echo "✓ Daily cron job is already installed in crontab!"
else
    # Append to crontab
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✓ Daily cron job successfully installed in crontab!"
    echo "Schedule: Every Monday-Friday at 6:30 AM PST"
    echo "Command: $PYTHON_EXEC $SCRIPT_PATH"
fi
