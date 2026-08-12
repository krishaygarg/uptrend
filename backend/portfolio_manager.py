"""
Portfolio Manager module for AlphaPulse.
Reads, updates, and persists portfolio state (holdings, cash balance, cost basis) in portfolio.json.
"""

import os
import json
import logging
from datetime import datetime

PORTFOLIO_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "portfolio.json")

logger = logging.getLogger("portfolio_manager")

DEFAULT_PORTFOLIO = {
    "initial_capital": 100000.0,
    "cash_balance": 100000.0,
    "total_realized_pnl": 0.0,
    "holdings": {},
    "history": [
        {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_value": 100000.0,
            "cash": 100000.0,
            "daily_pnl": 0.0,
            "total_pnl_pct": 0.0
        }
    ],
    "trade_journal": []
}

def load_portfolio():
    """Load portfolio state from portfolio.json file or create default."""
    if not os.path.exists(PORTFOLIO_FILE):
        save_portfolio(DEFAULT_PORTFOLIO)
        return DEFAULT_PORTFOLIO
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            data = json.load(f)
            if "initial_capital" not in data:
                data["initial_capital"] = 100000.0
            if "cash_balance" not in data:
                data["cash_balance"] = 100000.0
            if "total_realized_pnl" not in data:
                data["total_realized_pnl"] = 0.0
            if "holdings" not in data:
                data["holdings"] = {}
            if "history" not in data:
                data["history"] = []
            if "trade_journal" not in data:
                data["trade_journal"] = []
            return data
    except Exception as e:
        logger.error(f"Error loading portfolio from {PORTFOLIO_FILE}: {e}")
        return DEFAULT_PORTFOLIO

def save_portfolio(portfolio_data):
    """Save portfolio state to portfolio.json."""
    try:
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump(portfolio_data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving portfolio to {PORTFOLIO_FILE}: {e}")
        return False

def update_portfolio_state(cash_balance=None, holdings=None):
    """Update cash and/or holdings dict in portfolio.json."""
    portfolio = load_portfolio()
    if cash_balance is not None:
        portfolio["cash_balance"] = max(0.0, float(cash_balance))
    if holdings is not None:
        portfolio["holdings"] = holdings
    save_portfolio(portfolio)
    return portfolio

def record_simulated_trade(action, ticker, shares, price, reason=""):
    """
    Executes a trade locally in portfolio.json, updating cash balance, holdings,
    cost basis, and realized PnL.
    """
    portfolio = load_portfolio()
    cash = portfolio.get("cash_balance", 100000.0)
    holdings = portfolio.get("holdings", {})
    realized_pnl = portfolio.get("total_realized_pnl", 0.0)

    action = action.upper()
    shares = int(shares)
    price = float(price)
    total_cost = shares * price

    if action == "BUY":
        if cash < total_cost:
            # Scale down to affordable shares
            shares = int(cash // price)
            total_cost = shares * price

        if shares <= 0:
            return False, "Insufficient cash balance"

        cash -= total_cost
        curr_shares = holdings.get(ticker, {}).get("shares", 0)
        curr_avg = holdings.get(ticker, {}).get("avg_cost", price)
        new_shares = curr_shares + shares
        new_avg = ((curr_shares * curr_avg) + total_cost) / new_shares

        holdings[ticker] = {"shares": new_shares, "avg_cost": round(new_avg, 2)}
        trade_entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "BUY",
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "total_usd": round(total_cost, 2),
            "realized_pnl": 0.0,
            "reason": reason
        }

    elif action == "SELL":
        curr_shares = holdings.get(ticker, {}).get("shares", 0)
        if curr_shares <= 0:
            return False, f"No shares of {ticker} held"

        sell_shares = min(shares, curr_shares)
        proceeds = sell_shares * price
        cost_basis = holdings[ticker].get("avg_cost", price)
        pnl = proceeds - (sell_shares * cost_basis)

        cash += proceeds
        realized_pnl += pnl
        rem_shares = curr_shares - sell_shares

        if rem_shares <= 0:
            del holdings[ticker]
        else:
            holdings[ticker]["shares"] = rem_shares

        trade_entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "SELL",
            "ticker": ticker,
            "shares": sell_shares,
            "price": price,
            "total_usd": round(proceeds, 2),
            "realized_pnl": round(pnl, 2),
            "reason": reason
        }

    portfolio["cash_balance"] = round(cash, 2)
    portfolio["holdings"] = holdings
    portfolio["total_realized_pnl"] = round(realized_pnl, 2)
    portfolio["trade_journal"].append(trade_entry)

    save_portfolio(portfolio)
    return True, f"Successfully executed {action} {shares} {ticker} @ ${price:.2f}"

def log_daily_snapshot(total_equity, cash):
    """Record daily total equity snapshot for performance tracking."""
    portfolio = load_portfolio()
    today_str = datetime.now().strftime("%Y-%m-%d")
    initial_cap = portfolio.get("initial_capital", 100000.0)

    total_pnl_pct = round(((total_equity - initial_cap) / initial_cap) * 100.0, 2)
    
    # Check if entry already exists for today
    for entry in portfolio["history"]:
        if entry.get("date") == today_str:
            entry["total_value"] = round(total_equity, 2)
            entry["cash"] = round(cash, 2)
            entry["total_pnl_pct"] = total_pnl_pct
            save_portfolio(portfolio)
            return portfolio

    prev_val = portfolio["history"][-1]["total_value"] if portfolio["history"] else initial_cap
    daily_pnl = round(total_equity - prev_val, 2)

    portfolio["history"].append({
        "date": today_str,
        "total_value": round(total_equity, 2),
        "cash": round(cash, 2),
        "daily_pnl": daily_pnl,
        "total_pnl_pct": total_pnl_pct
    })
    save_portfolio(portfolio)
    return portfolio
