#!/usr/bin/env python3
"""
UpTrend Institutional Multi-Regime Stress Testing Suite.
Simulates UpTrend strategy against 7 distinct historical market conditions:
 1. 2022 Fed Rate Hike Bear Market (-35% Tech Crash)
 2. 2020 COVID Market Crash & V-Bottom Liquidity Spike
 3. 2018 Fed Tightening & US-China Trade War Shock
 4. 2023 Post-Crash AI Recovery Year
 5. 2-Year Tech Expansion Horizon (2024-2026)
 6. 3-Year Mid-Term Horizon (2023-2026)
 7. 10-Year Full Decade Macro Cycle (2016-2026)
"""

import os
import sys
import logging

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

REGIMES = [
    {
        "name": "1. 2022 Fed Inflation & Rate Hike Crash",
        "start": "2021-11-01",
        "end": "2022-12-31",
        "desc": "-35% Tech Drop, Aggressive Fed Tightening"
    },
    {
        "name": "2. 2020 COVID Crash & V-Bottom Recovery",
        "start": "2020-01-01",
        "end": "2020-12-31",
        "desc": "-33% Liquidity Shock & Stimulus Boom"
    },
    {
        "name": "3. 2018 Trade War & Fed Hike Shock",
        "start": "2018-01-01",
        "end": "2018-12-31",
        "desc": "US-China Tariff Shock & Q4 Market Correction"
    },
    {
        "name": "4. 2023 Post-Crash AI Recovery",
        "start": "2023-01-01",
        "end": "2023-12-31",
        "desc": "Mega-cap Tech & Semiconductor Surge"
    },
    {
        "name": "5. 2-Year Horizon (2024-2026)",
        "start": "2024-08-01",
        "end": "2026-08-11",
        "desc": "Sustained Modern Tech Expansion"
    },
    {
        "name": "6. 3-Year Horizon (2023-2026)",
        "start": "2023-08-01",
        "end": "2026-08-11",
        "desc": "Post-Rate Hike Expansion Cycle"
    },
    {
        "name": "7. 10-Year Full Decade Macro Cycle",
        "start": "2016-08-01",
        "end": "2026-08-11",
        "desc": "Full 10-Year Economic & Monetary Cycle"
    }
]

def main():
    print(f"\n{CYAN}{BOLD}" + "="*110)
    print("      🧪 UPTREND MULTI-REGIME HISTORICAL STRESS TESTING SUITE (10-YEAR DATASET)      ")
    print("="*110 + f"{RESET}\n")

    summary_rows = []

    for r in REGIMES:
        print(f"\n{BOLD}▶ Running Regime: {r['name']} ({r['desc']})...{RESET}")
        try:
            res = run_historical_backtest(
                start_date=r['start'],
                end_date=r['end'],
                initial_capital=100000.0
            )

            alpha_spy = res['outperformance_vs_spy_pct']
            alpha_qqq = res['outperformance_vs_qqq_pct']

            summary_rows.append({
                "regime": r['name'],
                "period": f"{r['start']} to {r['end']}",
                "uptrend_ret": res['strategy_return_pct'],
                "spy_ret": res['spy_return_pct'],
                "qqq_ret": res['qqq_return_pct'],
                "alpha_spy": alpha_spy,
                "alpha_qqq": alpha_qqq,
                "sharpe": res['sharpe_ratio'],
                "drawdown": res['max_drawdown_pct'],
                "spy_drawdown": res['spy_max_drawdown_pct'],
                "win_rate": res['win_rate_pct']
            })
        except Exception as e:
            print(f"{RED}Error testing regime {r['name']}: {e}{RESET}")

    # Print Summary Matrix
    print("\n" + "="*120)
    print(f"{CYAN}{BOLD}📊 FINAL MULTI-REGIME STRESS TEST COMPARISON MATRIX ($100,000 STARTING CAPITAL){RESET}")
    print("="*120)
    header = f"{'MARKET REGIME':<36} | {'UPTREND':<9} | {'SPY (S&P)':<9} | {'QQQ (NASD)':<9} | {'ALPHA vs SPY':<12} | {'ALPHA vs QQQ':<12} | {'MAX DRAWDOWN':<12} | {'SHARPE':<6}"
    print(BOLD + header + RESET)
    print("-" * 120)

    for s in summary_rows:
        up_color = GREEN if s['uptrend_ret'] >= 0 else RED
        spy_alpha_c = GREEN if s['alpha_spy'] >= 0 else RED
        qqq_alpha_c = GREEN if s['alpha_qqq'] >= 0 else RED

        row_str = f"{s['regime']:<36} | {up_color}{s['uptrend_ret']:+6.1f}%{RESET}   | {s['spy_ret']:+6.1f}%   | {s['qqq_ret']:+6.1f}%   | {spy_alpha_c}{s['alpha_spy']:+8.1f}%{RESET}    | {qqq_alpha_c}{s['alpha_qqq']:+8.1f}%{RESET}    | {RED}-{s['drawdown']:<5.1f}%{RESET} (SPY -{s['spy_drawdown']:.1f}%) | {s['sharpe']:<5.2f}"
        print(row_str)

    print("="*120 + "\n")

if __name__ == "__main__":
    main()
