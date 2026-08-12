"""
FastAPI application for AlphaPulse Stock Recommendation & Portfolio Rebalancing Platform.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.stock_universe import get_1000_tickers, EXPANDED_UNIVERSE, get_ticker_category
from backend.quant_engine import analyze_stock, batch_analyze_stocks
from backend.portfolio_manager import load_portfolio, save_portfolio, update_portfolio_state, log_daily_snapshot
from backend.rebalancer import calculate_rebalance
from backend.backtester import run_historical_backtest

from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="UpTrend API",
    description="Quantitative Market Outperformance & Daily Portfolio Rebalancer Engine",
    version="1.0.0"
)

# Enable CORS for Vite React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dist")
if os.path.exists(DIST_DIR):
    app.mount("/static", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="static")

    @app.get("/")
    def serve_frontend():
        from fastapi.responses import FileResponse
        return FileResponse(os.path.join(DIST_DIR, "index.html"))
else:
    @app.get("/")
    def root():
        return {"message": "UpTrend Quantitative Market Engine API", "status": "running"}

@app.get("/api/portfolio")
def get_portfolio():
    """Retrieve current portfolio state and latest valuations."""
    portfolio = load_portfolio()
    cash = portfolio.get("cash_balance", 0.0)
    holdings = portfolio.get("holdings", {})
    
    holdings_detail = []
    total_holdings_val = 0.0
    
    for ticker, hdata in holdings.items():
        analysis = analyze_stock(ticker)
        if not analysis: continue
        curr_price = analysis["current_price"]
        shares = hdata.get("shares", 0)
        cost_basis = hdata.get("avg_cost", curr_price)
        market_val = round(shares * curr_price, 2)
        total_holdings_val += market_val
        pnl = round(market_val - (shares * cost_basis), 2)
        pnl_pct = round((pnl / (shares * cost_basis)) * 100, 1) if (shares * cost_basis) > 0 else 0.0

        holdings_detail.append({
            "ticker": ticker,
            "company_name": analysis["company_name"],
            "shares": shares,
            "avg_cost": cost_basis,
            "current_price": curr_price,
            "market_value": market_val,
            "unrealized_pnl": pnl,
            "unrealized_pnl_pct": pnl_pct,
            "asymmetry_ratio": analysis["asymmetry_ratio"],
            "conviction_score": analysis["conviction_score"],
            "category": get_ticker_category(ticker)
        })

    total_equity = round(cash + total_holdings_val, 2)
    log_daily_snapshot(total_equity, cash)

    return {
        "cash_balance": round(cash, 2),
        "total_holdings_value": round(total_holdings_val, 2),
        "total_equity": total_equity,
        "holdings": holdings_detail,
        "history": portfolio.get("history", [])
    }

@app.post("/api/portfolio/update")
def update_portfolio(req: PortfolioUpdateRequest):
    """Update holdings or cash balance."""
    updated = update_portfolio_state(
        cash_balance=req.cash_balance,
        holdings=req.holdings
    )
    return {"status": "success", "portfolio": updated}

@app.get("/api/hidden-gems")
def get_hidden_gems(category: Optional[str] = None):
    """
    Scan 1,000+ stocks in parallel for high asymmetry upside recommendations.
    """
    tickers_to_scan = get_1000_tickers()
    analyzed = batch_analyze_stocks(tickers_to_scan, max_workers=25)
    
    for item in analyzed:
        item["category"] = get_ticker_category(item["ticker"])

    if category and category != 'ALL':
        analyzed = [x for x in analyzed if x["category"] == category]

    analyzed.sort(key=lambda x: (x["conviction_score"], x["asymmetry_ratio"]), reverse=True)
    return {"count": len(analyzed), "recommendations": analyzed[:50]}

@app.get("/api/rebalance")
def get_rebalance_recommendations():
    """
    Generate daily rebalancing trades based on current portfolio state and scanned stocks.
    """
    portfolio = load_portfolio()
    tickers_to_scan = get_1000_tickers()
    for t in portfolio.get("holdings", {}).keys():
        if t not in tickers_to_scan:
            tickers_to_scan.append(t)

    all_scanned = batch_analyze_stocks(tickers_to_scan, max_workers=25)
    all_scanned.sort(key=lambda x: (x["conviction_score"], x["asymmetry_ratio"]), reverse=True)
    rebalance_data = calculate_rebalance(portfolio, all_scanned)
    return rebalance_data

@app.post("/api/portfolio/execute-rebalance")
def execute_rebalance():
    """Applies recommended rebalancing trades directly to portfolio.json."""
    rebalance_data = get_rebalance_recommendations()
    portfolio = load_portfolio()
    
    new_holdings = {}
    for tp in rebalance_data["target_portfolio"]:
        ticker = tp["ticker"]
        t_shares = tp["target_shares"]
        if t_shares > 0:
            analysis = get_cached_analysis(ticker)
            new_holdings[ticker] = {
                "shares": t_shares,
                "avg_cost": analysis["current_price"]
            }

    # New cash reserve
    new_cash = rebalance_data["target_cash_reserve"]
    updated = update_portfolio_state(cash_balance=new_cash, holdings=new_holdings)
    return {"status": "success", "message": "Rebalance executed successfully", "portfolio": updated}

@app.get("/api/stock/{ticker}")
def get_stock_detail(ticker: str):
    """Detailed quantitative breakdown for a single stock."""
    try:
        data = analyze_stock(ticker)
        if not data:
            raise HTTPException(status_code=404, detail=f"Stock ticker {ticker} not found")
        data["category"] = get_ticker_category(ticker)
        return data
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Stock ticker {ticker} not found: {e}")

@app.get("/api/backtest")
def get_backtest_results(years: float = 1.0, capital: float = 100000.0):
    """Run historical backtest and return risk & performance metrics vs SPY and QQQ."""
    try:
        res = run_historical_backtest(years=years, initial_capital=capital)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest error: {e}")
