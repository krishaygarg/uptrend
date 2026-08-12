#!/usr/bin/env python3
"""
AlphaPulse Historical Backtest CLI Runner.
Executes multi-period historical backtests (1-Year and 2-Year windows)
and benchmarks strategy performance against SPY (S&P 500) and QQQ (Nasdaq 100).
"""

import os
import sys
import argparse

# Auto-reexec under venv
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(PROJECT_DIR, "venv", "bin", "python3")

if os.path.exists(VENV_PYTHON) and sys.executable != os.path.abspath(VENV_PYTHON):
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

sys.path.insert(0, PROJECT_DIR)

from backend.backtester import run_historical_backtest

# Colors
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_results(res):
    print("\n" + "=" * 90)
    print(f"{CYAN}{BOLD}📈 ALPHAPULSE QUANT STRATEGY BACKTEST RESULTS ({res['period_years']} YEAR HORIZON){RESET}")
    print("=" * 90)
    print(f" Initial Portfolio Capital : ${res['initial_capital']:,.2f}")
    print(f" {BOLD}AlphaPulse Portfolio Value{RESET} : {GREEN}${res['final_strategy_equity']:,.2f} ({res['strategy_return_pct']:+.2f}%){RESET}")
    print(f" S&P 500 Index (SPY) Value  : ${res['final_spy_equity']:,.2f} ({res['spy_return_pct']:+.2f}%)")
    print(f" Nasdaq 100 Index (QQQ) Val : ${res['final_qqq_equity']:,.2f} ({res['qqq_return_pct']:+.2f}%)")
    print("-" * 90)

    alpha_spy = res['outperformance_vs_spy_pct']
    alpha_qqq = res['outperformance_vs_qqq_pct']

    spy_color = GREEN if alpha_spy > 0 else RED
    qqq_color = GREEN if alpha_qqq > 0 else RED

    print(f" {BOLD}Alpha vs S&P 500 (SPY){RESET}     : {spy_color}{alpha_spy:+.2f}% Outperformance{RESET}")
    print(f" {BOLD}Alpha vs Nasdaq 100 (QQQ){RESET}   : {qqq_color}{alpha_qqq:+.2f}% Outperformance{RESET}")
    print("-" * 90)
    print(f" Risk-Adjusted Sharpe Ratio: {BOLD}{res['sharpe_ratio']}{RESET}")
    print(f" Maximum Drawdown (Risk)   : {RED}-{res['max_drawdown_pct']:.2f}%{RESET} (SPY Max Drawdown: -{res['spy_max_drawdown_pct']:.2f}%)")
    print(f" Total Executed Trades     : {res['total_trades']}")
    print(f" Trade Win Rate (%)        : {GREEN}{res['win_rate_pct']:.1f}%{RESET}")
    print("=" * 90)

    if res['trade_log']:
        print(f"\n{BOLD}📋 SAMPLE HISTORICAL EXECUTED TRADES (Last 8 Trades):{RESET}")
        for t in res['trade_log'][-8:]:
            action_color = GREEN if "BUY" in t['action'] else (YELLOW if "Take Profit" in t['action'] else RED)
            print(f"  [{t['date']}] {action_color}{t['action']:<22}{RESET} | Ticker: {BOLD}{t['ticker']:<6}{RESET} | Shares: {t['shares']:<4} @ ${t['price']:<7.2f} | PnL/Total: ${t['proceeds']:,.2f}")
    print()

def main():
    parser = argparse.ArgumentParser(description="Run AlphaPulse Historical Backtest")
    parser.add_argument("--years", type=float, default=1.0, help="Backtest period in years (default: 1.0)")
    parser.add_argument("--capital", type=float, default=100000.0, help="Initial portfolio capital (default: 100000.0)")
    parser.add_argument("--start-date", type=str, default=None, help="Start date (YYYY-MM-DD) for custom window")
    parser.add_argument("--end-date", type=str, default=None, help="End date (YYYY-MM-DD) for custom window")
    args = parser.parse_args()

    results = run_historical_backtest(
        years=args.years,
        initial_capital=args.capital,
        start_date=args.start_date,
        end_date=args.end_date
    )
    print_results(results)

if __name__ == "__main__":
    main()
