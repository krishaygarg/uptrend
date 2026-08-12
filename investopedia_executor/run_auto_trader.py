#!/usr/bin/env python3
"""
Investopedia Automated Daily Rebalancer & Executor Script.
Imports core AlphaPulse quant engine & rebalancer modules (without modifying any existing code),
calculates daily high-asymmetry rebalance trades, executes trades on Investopedia Simulator,
and updates portfolio.json.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add project root to sys.path without modifying existing backend files
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.stock_universe import get_1000_tickers
from backend.quant_engine import batch_analyze_stocks
from backend.portfolio_manager import load_portfolio, update_portfolio_state, log_daily_snapshot
from backend.rebalancer import calculate_rebalance
from investopedia_executor.investopedia_client import InvestopediaClient, SESSION_STATE_PATH
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "auto_trader.log"))
    ]
)

logger = logging.getLogger("run_auto_trader")

def main():
    logger.info("=== Starting Daily AlphaPulse Investopedia Auto-Trader ===")
    
    # 1. Load Portfolio
    portfolio = load_portfolio()
    cash = portfolio.get("cash_balance", 0.0)
    holdings = portfolio.get("holdings", {})
    logger.info(f"Current Portfolio Valuation: Cash = ${cash:,.2f}, Active Holdings = {list(holdings.keys())}")

    # 2. Run Market Screener
    tickers_to_scan = get_1000_tickers()
    for ht in holdings.keys():
        if ht not in tickers_to_scan:
            tickers_to_scan.append(ht)

    logger.info(f"Scanning {len(tickers_to_scan)} stocks across market caps for high-asymmetry gems...")
    scanned_stocks = batch_analyze_stocks(tickers_to_scan, max_workers=25)
    scanned_stocks.sort(key=lambda x: (x["conviction_score"], x["asymmetry_ratio"]), reverse=True)
    logger.info(f"Scan complete. Found {len(scanned_stocks)} valid stocks.")

    # 3. Calculate Rebalancing Trades
    rebalance_data = calculate_rebalance(portfolio, scanned_stocks)
    trades = rebalance_data.get("rebalancing_trades", [])
    total_equity = rebalance_data.get("total_equity", 0.0)

    log_daily_snapshot(total_equity, cash)

    if not trades:
        logger.info("✓ Portfolio is currently optimal! No trade actions needed today.")
        print("\n✓ Portfolio is currently optimal! No trade actions needed today.")
        return

    logger.info(f"Found {len(trades)} trade actions suggested for today:")
    for tr in trades:
        logger.info(f"  [{tr['action']}] {tr['shares']} shares of {tr['ticker']} @ ~${tr['price']:,.2f} ({tr['reason']})")

    # 4. Attempt Investopedia Execution if credentials or saved session state present
    email = os.getenv("INVESTOPEDIA_EMAIL")
    password = os.getenv("INVESTOPEDIA_PASSWORD")

    executed_trades = []
    if (email and password) or os.path.exists(SESSION_STATE_PATH):
        logger.info("Connecting to Investopedia Simulator via Playwright...")
        client = InvestopediaClient(email=email, password=password, headless=True)
        try:
            client.start_session()
            if client.login():
                # Execute SELL orders first to free up capital
                sells = [t for t in trades if t["action"] == "SELL"]
                buys = [t for t in trades if t["action"] == "BUY"]

                for tr in sells:
                    success = client.execute_trade(tr["ticker"], "SELL", tr["shares"])
                    if success: executed_trades.append(tr)

                for tr in buys:
                    success = client.execute_trade(tr["ticker"], "BUY", tr["shares"])
                    if success: executed_trades.append(tr)

        except Exception as e:
            logger.error(f"Error during Investopedia execution: {e}")
        finally:
            client.close_session()
    else:
        logger.warning("INVESTOPEDIA_EMAIL / INVESTOPEDIA_PASSWORD or session_state.json not found.")
        logger.warning("Run ./venv/bin/python3 investopedia_executor/login_session.py to complete 1-time 2FA login.")

    # 5. Apply Rebalance to portfolio.json state
    new_holdings = {}
    for tp in rebalance_data["target_portfolio"]:
        t_ticker = tp["ticker"]
        t_shares = tp["target_shares"]
        if t_shares > 0:
            new_holdings[t_ticker] = {
                "shares": t_shares,
                "avg_cost": tp["price"]
            }
    
    new_cash = rebalance_data["target_cash_reserve"]
    update_portfolio_state(cash_balance=new_cash, holdings=new_holdings)
    logger.info("✓ portfolio.json state updated with new target holdings!")

    # 6. Log Trade Execution
    execution_record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_equity": total_equity,
        "trades_suggested": trades,
        "trades_executed": executed_trades
    }
    
    log_history_path = os.path.join(os.path.dirname(__file__), "trade_execution_log.json")
    history_log = []
    if os.path.exists(log_history_path):
        try:
            with open(log_history_path, "r") as f: history_log = json.load(f)
        except Exception: pass
    
    history_log.append(execution_record)
    with open(log_history_path, "w") as f:
        json.dump(history_log, f, indent=2)

    logger.info("=== Daily Auto-Trader Completed Successfully ===")

if __name__ == "__main__":
    main()
