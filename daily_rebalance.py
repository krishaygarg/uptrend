#!/usr/bin/env python3
"""
AlphaPulse Daily Portfolio Rebalancer CLI tool.
Run this script once a day to:
 1. Analyze 1,000+ stocks across Small-Cap, Mid-Cap, Growth, Deep Value, and Moats in parallel.
 2. Review your current portfolio valuation and holdings.
 3. Generate concrete BUY / SELL / HOLD rebalancing recommendations for today.
"""

import os
import sys
import json
import time
from datetime import datetime

# Auto-reexec under venv if venv Python is not currently active
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(PROJECT_DIR, "venv", "bin", "python3")

if os.path.exists(VENV_PYTHON) and sys.executable != os.path.abspath(VENV_PYTHON):
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

sys.path.insert(0, PROJECT_DIR)

import argparse
from backend.stock_universe import get_1000_tickers
from backend.quant_engine import batch_analyze_stocks, analyze_stock
from backend.portfolio_manager import load_portfolio, log_daily_snapshot, record_simulated_trade
from backend.rebalancer import calculate_rebalance

# Terminal styling ANSI colors
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    print(f"{CYAN}{BOLD}")
    print("=" * 80)
    print("  💎 UPTREND: DAILY PORTFOLIO REBALANCER & HIGH-ASYMMETRY SCREENER 💎  ")
    print("=" * 80)
    print(f"{RESET}")

def show_performance_summary():
    portfolio = load_portfolio()
    initial_cap = portfolio.get("initial_capital", 100000.0)
    cash = portfolio.get("cash_balance", 100000.0)
    holdings = portfolio.get("holdings", {})
    realized_pnl = portfolio.get("total_realized_pnl", 0.0)
    history = portfolio.get("history", [])
    trade_journal = portfolio.get("trade_journal", [])

    holdings_val = 0.0
    unrealized_pnl = 0.0
    for t, hdata in holdings.items():
        analysis = analyze_stock(t)
        p = analysis["current_price"] if analysis else hdata.get("avg_cost", 100.0)
        mval = hdata["shares"] * p
        cost = hdata["shares"] * hdata.get("avg_cost", p)
        holdings_val += mval
        unrealized_pnl += (mval - cost)

    total_equity = cash + holdings_val
    total_net_profit = total_equity - initial_cap
    total_net_profit_pct = (total_net_profit / initial_cap) * 100.0

    print(f"\n{CYAN}{BOLD}" + "="*80)
    print("  📈 ALPHAPULSE PORTFOLIO PROFIT & PERFORMANCE TRACKER  ")
    print("="*80 + f"{RESET}\n")

    pnl_color = GREEN if total_net_profit >= 0 else RED
    realized_color = GREEN if realized_pnl >= 0 else RED
    unrealized_color = GREEN if unrealized_pnl >= 0 else RED

    print(f"  Initial Starting Capital : ${initial_cap:,.2f}")
    print(f"  Current Cash Balance     : ${cash:,.2f}")
    print(f"  Holdings Valuation       : ${holdings_val:,.2f}")
    print(f"  {BOLD}Total Portfolio Value{RESET}    : {BOLD}${total_equity:,.2f}{RESET}")
    print("-" * 80)
    print(f"  {BOLD}Total Net Profit / Loss{RESET}  : {pnl_color}{BOLD}${total_net_profit:,.2f} ({total_net_profit_pct:+.2f}%){RESET}")
    print(f"  Realized Capital Gain    : {realized_color}${realized_pnl:,.2f}{RESET}")
    print(f"  Unrealized Open Profit   : {unrealized_color}${unrealized_pnl:,.2f}{RESET}")
    print("-" * 80)

    if trade_journal:
        sells = [t for t in trade_journal if t["action"] == "SELL"]
        wins = [t for t in sells if t.get("realized_pnl", 0) > 0]
        win_rate = (len(wins) / len(sells) * 100.0) if sells else 0.0
        print(f"  Total Trades Executed    : {len(trade_journal)}")
        print(f"  Completed Sell Trades    : {len(sells)}")
        print(f"  Trade Win Rate           : {GREEN}{win_rate:.1f}%{RESET}")
        print("\n  " + f"{BOLD}RECENT TRADE JOURNAL LOG:{RESET}")
        for tj in trade_journal[-6:]:
            action_c = GREEN if tj["action"] == "BUY" else YELLOW
            pnl_str = f" | Realized PnL: ${tj.get('realized_pnl', 0):+,.2f}" if tj["action"] == "SELL" else ""
            print(f"   [{tj['date'][:10]}] {action_c}{tj['action']:<4}{RESET} {tj['shares']} shares of {BOLD}{tj['ticker']:<5}{RESET} @ ${tj['price']:<7.2f} (Total: ${tj['total_usd']:,.2f}){pnl_str}")

    print("\n" + "="*80 + "\n")

def main():
    parser = argparse.ArgumentParser(description="AlphaPulse Daily Rebalancer")
    parser.add_argument("--apply", action="store_true", help="Automatically execute recommended trades into local portfolio state")
    parser.add_argument("--performance", action="store_true", help="Display full profit tracking performance dashboard")
    args = parser.parse_args()

    if args.performance:
        show_performance_summary()
        return

    print_banner()
    portfolio = load_portfolio()
    cash = portfolio.get("cash_balance", 0.0)
    holdings = portfolio.get("holdings", {})

    print(f"{BOLD}📊 CURRENT PORTFOLIO STATE ({datetime.now().strftime('%Y-%m-%d')}){RESET}")
    print(f"  Available Liquid Cash: {GREEN}${cash:,.2f}{RESET}")
    print(f"  Active Holdings Count: {len(holdings)}")
    for ticker, hinfo in holdings.items():
        print(f"    - {BOLD}{ticker:<6}{RESET}: {hinfo.get('shares')} shares @ Avg Cost ${hinfo.get('avg_cost', 0):,.2f}")
    print()

    tickers_to_scan = get_1000_tickers()
    # Add holdings tickers if not in list
    for ht in holdings.keys():
        if ht not in tickers_to_scan:
            tickers_to_scan.append(ht)

    total_all = len(tickers_to_scan)
    print(f"{YELLOW}🔎 High-Speed Parallel Scanning of {total_all} stocks across market caps...{RESET}")
    
    start_time = time.time()
    def update_progress(done, missing_total, last_ticker):
        pct = int((done / missing_total) * 100)
        sys.stdout.write(f"\rScanning [{done}/{missing_total}] network batch ({pct}%): {last_ticker:<6}")
        sys.stdout.flush()

    analyzed_stocks = batch_analyze_stocks(tickers_to_scan, max_workers=25, progress_callback=update_progress)
    elapsed = time.time() - start_time
    print(f"\n{GREEN}✓ Scan complete! Screened {len(analyzed_stocks)} valid stocks out of {total_all} in universe in {elapsed:.1f} seconds.{RESET}\n")

    # Sort analyzed stocks by Conviction Score & Asymmetry Ratio
    analyzed_stocks.sort(key=lambda x: (x["conviction_score"], x["asymmetry_ratio"]), reverse=True)

    print(f"{BOLD}🌟 TOP 10 HIGH ASYMMETRY STOCK OPPORTUNITIES FOUND TODAY:{RESET}")
    print("-" * 105)
    print(f"{'TICKER':<8} {'PRICE':<8} {'FAIR VAL':<10} {'UPSIDE%':<10} {'DOWN%':<8} {'ASYM':<8} {'PIOTROSKI':<11} {'CONVICTION':<11} {'STRUCTURAL FLAGS'}")
    print("-" * 105)
    for s in analyzed_stocks[:10]:
        asym_str = f"{s['asymmetry_ratio']:.1f}x"
        upside_str = f"+{s['upside_potential_pct']:.1f}%"
        down_str = f"-{s['downside_risk_pct']:.1f}%"
        piot_str = f"{s['piotroski_f_score']}/9"
        conv_str = f"{s['conviction_score']}/100"
        flags_str = ", ".join(s.get("structural_flags", [])) if s.get("structural_flags") else "Clean ✓"
        if len(flags_str) > 28: flags_str = flags_str[:25] + "..."
        print(f"{BOLD}{s['ticker']:<8}{RESET} ${s['current_price']:<7.2f} ${s['fair_value']:<9.2f} {GREEN}{upside_str:<10}{RESET} {RED}{down_str:<8}{RESET} {CYAN}{asym_str:<8}{RESET} {BOLD}{piot_str:<11}{RESET} {BOLD}{conv_str:<11}{RESET} {YELLOW}{flags_str}{RESET}")
    print("-" * 105)
    print()

    # Calculate Rebalancing Trades
    rebalance_result = calculate_rebalance(portfolio, analyzed_stocks)
    total_eq = rebalance_result["total_equity"]
    trades = rebalance_result["rebalancing_trades"]
    target_portfolio = rebalance_result["target_portfolio"]

    # Log daily total equity
    log_daily_snapshot(total_eq, cash)

    print(f"{BOLD}💰 TOTAL PORTFOLIO VALUATION: {GREEN}${total_eq:,.2f}{RESET}")
    print(f"Target Liquidity Cushion (10%): ${rebalance_result['target_cash_reserve']:,.2f}\n")

    print(f"{BOLD}🎯 RECOMMENDED DAILY REBALANCING TRADES TODAY:{RESET}")
    print("=" * 80)
    if not trades:
        print(f"{GREEN}✓ Portfolio is currently optimal! No trade actions needed today.{RESET}")
    else:
        for idx, tr in enumerate(trades, start=1):
            if tr["action"] == "BUY":
                action_str = f"{GREEN}{BOLD}BUY{RESET}"
                details = f"{tr['shares']} shares of {tr['ticker']} @ ~${tr['price']:,.2f} (Total: ${tr['total_usd']:,.2f})"
            else:
                action_str = f"{RED}{BOLD}SELL{RESET}"
                details = f"{tr['shares']} shares of {tr['ticker']} @ ~${tr['price']:,.2f} (Proceeds: ${tr['total_usd']:,.2f})"
            print(f" {idx}. [{action_str}] {details}")
            print(f"    ↳ Rationale: {tr['reason']}")
    print("=" * 80)
    print()

    print(f"{BOLD}🎯 RECOMMENDED TARGET ALLOCATION:{RESET}")
    for tp in target_portfolio:
        print(f"  - {BOLD}{tp['ticker']:<6}{RESET}: {tp['target_shares']} shares ({tp['target_weight_pct']}% of portfolio ~ ${tp['target_value']:,.2f}) | Asymmetry: {tp['asymmetry_ratio']}x")
    print()

    print(f"{CYAN}To view interactive web dashboard, run: ./venv/bin/uvicorn backend.app:app --port 8000{RESET}")
    print(f"{YELLOW}To automatically execute these trades and update profit tracking, run: ./daily_rebalance.py --apply{RESET}\n")

    # If --apply flag is passed, execute trades locally
    if args.apply and trades:
        print(f"{BOLD}⚡ APPLYING TRADES TO PORTFOLIO STATE...{RESET}")
        for tr in trades:
            success, msg = record_simulated_trade(
                action=tr["action"],
                ticker=tr["ticker"],
                shares=tr["shares"],
                price=tr["price"],
                reason=tr["reason"]
            )
            color = GREEN if success else RED
            print(f"  {color}↳ {msg}{RESET}")
        print(f"\n{GREEN}✓ Trades executed! Run './daily_rebalance.py --performance' to view profit tracker.{RESET}\n")

if __name__ == "__main__":
    main()
