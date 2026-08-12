"""
Historical Backtesting Engine for AlphaPulse Strategy (Outperformance Optimized v2).
Simulates Dual-Regime Asset Allocation (60% QQQ Core Anchor in Bull Trends),
6-Month Relative Strength Momentum Ranking, Uncapped Winner Retention (letting winners run),
and 18% Trailing Stop-Loss across historical daily market data.
Compares strategy performance directly against SPY and QQQ Buy & Hold benchmarks.
"""

import os
import sys
import math
import time
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from backend.stock_universe import get_1000_tickers
from backend.rebalancer import CORE_ANCHOR_TICKER, MIN_TRADE_USD, WEIGHT_DRIFT_THRESHOLD

logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)


def run_historical_backtest(years=1.0, initial_capital=100000.0, start_date=None, end_date=None, rebalance_freq_days=14, universe_limit=180):
    """
    Executes historical backtest over custom date ranges or relative year horizons.
    """
    if start_date:
        fetch_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=60)).strftime("%Y-%m-%d")
        lbl = f"Custom Window ({start_date} to {end_date or 'Present'})"
    else:
        fetch_start = (datetime.now() - timedelta(days=int(years * 365) + 60)).strftime("%Y-%m-%d")
        lbl = f"{years}-Year Window"

    print(f"🚀 Initializing Outperformance Backtest [{lbl}] (${initial_capital:,.2f} initial capital)...")

    tickers = get_1000_tickers()[:universe_limit]
    if CORE_ANCHOR_TICKER not in tickers:
        tickers.append(CORE_ANCHOR_TICKER)
    if "SPY" not in tickers:
        tickers.append("SPY")

    print(f"📥 Downloading historical daily price data for {len(tickers)} tickers from {fetch_start}...")

    data = yf.download(tickers, start=fetch_start, end=end_date, progress=False, group_by='ticker', auto_adjust=True)

    close_dict = {}
    for t in tickers:
        try:
            if len(tickers) == 1:
                close_dict[t] = data['Close']
            else:
                if t in data and 'Close' in data[t]:
                    close_dict[t] = data[t]['Close']
        except Exception:
            pass

    close_df = pd.DataFrame(close_dict)
    close_df.dropna(how='all', inplace=True)
    close_df.ffill(inplace=True)

    # Slice to exact start_date if specified
    if start_date:
        close_df = close_df.loc[close_df.index >= start_date]
    elif len(close_df) > int(years * 252):
        close_df = close_df.iloc[-int(years * 252):]

    trading_dates = close_df.index
    print(f"✅ Downloaded {len(trading_dates)} trading days of historical data ({trading_dates[0].strftime('%Y-%m-%d')} to {trading_dates[-1].strftime('%Y-%m-%d')}).")

    cash = initial_capital
    holdings = {}
    portfolio_history = []
    trade_log = []

    spy_start_price = float(close_df["SPY"].iloc[0]) if "SPY" in close_df else 1.0
    qqq_start_price = float(close_df[CORE_ANCHOR_TICKER].iloc[0]) if CORE_ANCHOR_TICKER in close_df else 1.0

    spy_shares = initial_capital / spy_start_price
    qqq_shares = initial_capital / qqq_start_price

    winning_trades = 0
    losing_trades = 0
    total_trade_count = 0

    print("⚡ Running day-by-day market simulation & strategy evaluation...")

    for day_idx in range(len(trading_dates)):
        current_date = trading_dates[day_idx]
        current_prices = close_df.iloc[day_idx].dropna().to_dict()

        for t, hdata in holdings.items():
            cp = current_prices.get(t)
            if cp and cp > hdata.get("peak_price", 0):
                hdata["peak_price"] = cp

        holdings_val = sum(hdata["shares"] * current_prices.get(t, hdata["avg_cost"]) for t, hdata in holdings.items())
        total_equity = cash + holdings_val

        spy_val = spy_shares * current_prices.get("SPY", spy_start_price)
        qqq_val = qqq_shares * current_prices.get(CORE_ANCHOR_TICKER, qqq_start_price)

        # Trailing stop-loss (-18% from highest peak)
        for t in list(holdings.keys()):
            hdata = holdings[t]
            p = current_prices.get(t)
            if not p or hdata["shares"] <= 0:
                continue

            peak = hdata.get("peak_price", hdata["avg_cost"])
            drawdown_from_peak = (p - peak) / peak

            if drawdown_from_peak <= -0.18 and t != CORE_ANCHOR_TICKER:
                proceeds = hdata["shares"] * p
                cash += proceeds
                total_trade_count += 1

                pnl_from_entry = (p - hdata["avg_cost"]) / hdata["avg_cost"]
                if pnl_from_entry > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1

                trade_log.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "ticker": t,
                    "action": "SELL (Trailing Stop -18%)",
                    "shares": hdata["shares"],
                    "price": p,
                    "pnl_pct": round(pnl_from_entry * 100, 1),
                    "proceeds": round(proceeds, 2)
                })
                del holdings[t]

        # Rebalancing
        qqq_p = current_prices.get(CORE_ANCHOR_TICKER, qqq_start_price)
        hist_qqq = close_df[CORE_ANCHOR_TICKER].iloc[:day_idx+1].values
        qqq_sma200 = float(np.mean(hist_qqq[-200:])) if len(hist_qqq) >= 200 else qqq_p
        is_bull_regime = qqq_p >= qqq_sma200

        is_rebalance_day = (day_idx % rebalance_freq_days == 0) or (day_idx == 0)
        if is_rebalance_day:
            stock_scores = []
            for t in tickers:
                if t in ["SPY", CORE_ANCHOR_TICKER]:
                    continue

                hist_slice = close_df[t].iloc[:day_idx+1].values
                if len(hist_slice) < 60 or np.isnan(hist_slice[-1]):
                    continue

                p = float(hist_slice[-1])
                p_6m_ago = float(hist_slice[-126]) if len(hist_slice) >= 126 else float(hist_slice[0])
                rs_6m = (p - p_6m_ago) / p_6m_ago if p_6m_ago > 0 else 0.0

                sma200 = float(np.mean(hist_slice[-200:])) if len(hist_slice) >= 200 else p
                if p >= sma200:
                    rs_6m += 0.15

                stock_scores.append({
                    "ticker": t,
                    "price": p,
                    "score": rs_6m
                })

            stock_scores.sort(key=lambda x: x["score"], reverse=True)
            top_gem_picks = stock_scores[:4]

            # 60% QQQ Core Anchor in Bull Trends
            core_weight = 0.60 if is_bull_regime else 0.30
            cash_reserve_pct = 0.0 if is_bull_regime else 0.10

            allocatable_equity = total_equity * (1.0 - cash_reserve_pct)
            target_allocs = {CORE_ANCHOR_TICKER: core_weight}

            if top_gem_picks:
                gem_weight = (1.0 - core_weight - cash_reserve_pct) / len(top_gem_picks)
                for g in top_gem_picks:
                    target_allocs[g["ticker"]] = gem_weight

            for t, weight in target_allocs.items():
                target_val = allocatable_equity * weight
                p = current_prices.get(t)
                if not p or p <= 0:
                    continue

                curr_shares = holdings.get(t, {}).get("shares", 0)
                curr_val = curr_shares * p
                curr_weight = curr_val / total_equity if total_equity > 0 else 0

                if curr_shares == 0 or abs(weight - curr_weight) >= WEIGHT_DRIFT_THRESHOLD:
                    diff_val = target_val - curr_val
                    if diff_val >= MIN_TRADE_USD and cash >= diff_val:
                        add_shares = math.floor(diff_val / p)
                        if add_shares > 0:
                            cost_usd = add_shares * p
                            cash -= cost_usd

                            old_shares = holdings.get(t, {}).get("shares", 0)
                            old_cost = holdings.get(t, {}).get("avg_cost", p)
                            new_total_shares = old_shares + add_shares
                            new_avg_cost = ((old_shares * old_cost) + (add_shares * p)) / new_total_shares

                            holdings[t] = {
                                "shares": new_total_shares,
                                "avg_cost": new_avg_cost,
                                "peak_price": max(p, holdings.get(t, {}).get("peak_price", p))
                            }
                            trade_log.append({
                                "date": current_date.strftime("%Y-%m-%d"),
                                "ticker": t,
                                "action": "BUY",
                                "shares": add_shares,
                                "price": p,
                                "pnl_pct": 0.0,
                                "proceeds": round(cost_usd, 2)
                            })

        portfolio_history.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "strategy_equity": round(total_equity, 2),
            "spy_equity": round(spy_val, 2),
            "qqq_equity": round(qqq_val, 2),
            "cash": round(cash, 2)
        })

    hist_df = pd.DataFrame(portfolio_history)
    final_strat = hist_df["strategy_equity"].iloc[-1]
    final_spy = hist_df["spy_equity"].iloc[-1]
    final_qqq = hist_df["qqq_equity"].iloc[-1]

    strat_return_pct = ((final_strat - initial_capital) / initial_capital) * 100.0
    spy_return_pct = ((final_spy - initial_capital) / initial_capital) * 100.0
    qqq_return_pct = ((final_qqq - initial_capital) / initial_capital) * 100.0

    hist_df["strat_peak"] = hist_df["strategy_equity"].cummax()
    hist_df["strat_drawdown"] = (hist_df["strategy_equity"] - hist_df["strat_peak"]) / hist_df["strat_peak"]
    max_drawdown_pct = abs(float(hist_df["strat_drawdown"].min())) * 100.0

    hist_df["spy_peak"] = hist_df["spy_equity"].cummax()
    hist_df["spy_drawdown"] = (hist_df["spy_equity"] - hist_df["spy_peak"]) / hist_df["spy_peak"]
    spy_max_drawdown_pct = abs(float(hist_df["spy_drawdown"].min())) * 100.0

    hist_df["strat_daily_ret"] = hist_df["strategy_equity"].pct_change()
    mean_daily = hist_df["strat_daily_ret"].mean()
    std_daily = hist_df["strat_daily_ret"].std()
    sharpe_ratio = (mean_daily / std_daily) * math.sqrt(252) if std_daily > 0 else 0.0

    win_rate_pct = (winning_trades / total_trade_count * 100.0) if total_trade_count > 0 else 0.0

    results = {
        "period_years": years,
        "initial_capital": initial_capital,
        "final_strategy_equity": round(final_strat, 2),
        "final_spy_equity": round(final_spy, 2),
        "final_qqq_equity": round(final_qqq, 2),
        "strategy_return_pct": round(strat_return_pct, 2),
        "spy_return_pct": round(spy_return_pct, 2),
        "qqq_return_pct": round(qqq_return_pct, 2),
        "outperformance_vs_spy_pct": round(strat_return_pct - spy_return_pct, 2),
        "outperformance_vs_qqq_pct": round(strat_return_pct - qqq_return_pct, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "spy_max_drawdown_pct": round(spy_max_drawdown_pct, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "total_trades": total_trade_count,
        "win_rate_pct": round(win_rate_pct, 1),
        "portfolio_history": portfolio_history,
        "trade_log": trade_log
    }

    return results

if __name__ == "__main__":
    res = run_historical_backtest(years=1.0, initial_capital=100000.0)
    print("\n" + "="*80)
    print(f"📊 ALPHAPULSE BACKTEST RESULTS ({res['period_years']} Year):")
    print(f"  AlphaPulse Final Equity : ${res['final_strategy_equity']:,.2f} ({res['strategy_return_pct']:+.2f}%)")
    print(f"  S&P 500 (SPY) Benchmark : ${res['final_spy_equity']:,.2f} ({res['spy_return_pct']:+.2f}%)")
    print(f"  Nasdaq 100 (QQQ) Bench  : ${res['final_qqq_equity']:,.2f} ({res['qqq_return_pct']:+.2f}%)")
    print(f"  Alpha vs SPY Benchmark  : {res['outperformance_vs_spy_pct']:+.2f}%")
    print(f"  Sharpe Ratio            : {res['sharpe_ratio']}")
    print("="*80)
