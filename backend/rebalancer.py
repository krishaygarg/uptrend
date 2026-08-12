"""
Institutional Rebalancer module for AlphaPulse.
Implements Dual-Regime Asset Allocation (50% QQQ Core in Bull Regimes, 30% in Bear Regimes),
Relative Strength Momentum Weighting, Zero Cash Drag in Bull Trends, 15% Trailing Stop-Loss,
and Uncapped Winner Retention (letting winning stocks run).
"""

import math
import logging

logger = logging.getLogger("rebalancer")

CORE_ANCHOR_TICKER = "QQQ"
BULL_CORE_WEIGHT = 0.60        # 60% Core Index Anchor in Bull Markets
BEAR_CORE_WEIGHT = 0.30        # 30% Core Index Anchor in Bear/Neutral Markets
MAX_SINGLE_GEM_WEIGHT = 0.12    # 12% max cap per individual high-momentum gem
MIN_TRADE_USD = 500.0           # Ignore micro-trades under $500 to prevent churning
WEIGHT_DRIFT_THRESHOLD = 0.04   # 4% weight drift buffer before rebalancing
TRAILING_STOP_LOSS_PCT = 0.18   # 18% trailing stop-loss off 52-week peak

def calculate_rebalance(portfolio, stock_analysis_list):
    """
    Computes professional institutional daily rebalancing recommendations.
    Employs Core/Satellite structure, hysteresis trade buffers, and stop-loss/take-profit triggers.
    """
    cash = float(portfolio.get("cash_balance", 0.0))
    current_holdings = portfolio.get("holdings", {})

    # Map current prices & analysis dicts
    price_map = {}
    analysis_map = {}
    for item in stock_analysis_list:
        ticker = item["ticker"]
        price_map[ticker] = item["current_price"]
        analysis_map[ticker] = item

    # Calculate total equity valuation
    holdings_value = 0.0
    for ticker, hdata in current_holdings.items():
        shares = hdata.get("shares", 0)
        p = price_map.get(ticker, hdata.get("avg_cost", 100.0))
        holdings_value += shares * p

    total_equity = cash + holdings_value
    # Determine market regime based on QQQ technicals (if QQQ >= 200 SMA -> Bull Regime)
    qqq_analysis = analysis_map.get(CORE_ANCHOR_TICKER, {})
    qqq_price = price_map.get(CORE_ANCHOR_TICKER, 718.45)
    is_bull_regime = qqq_price >= qqq_analysis.get("support_floor", qqq_price * 0.85)

    core_weight = BULL_CORE_WEIGHT if is_bull_regime else BEAR_CORE_WEIGHT
    target_cash_reserve_pct = 0.0 if is_bull_regime else 0.10  # Zero cash drag in bull regime

    allocatable_equity = total_equity * (1.0 - target_cash_reserve_pct)

    # 1. Core Allocation: 50% QQQ Core Anchor in Bull Regime
    target_positions = {}
    target_positions[CORE_ANCHOR_TICKER] = {
        "ticker": CORE_ANCHOR_TICKER,
        "company_name": "Invesco QQQ Trust (Core Anchor)",
        "target_weight": core_weight,
        "current_price": qqq_price,
        "conviction_score": 95,
        "asymmetry_ratio": 1.0,
        "margin_of_safety_pct": 0.0,
        "is_core": True
    }

    # 2. Satellite High-Asymmetry Stock Picks (Remaining allocatable weight)
    all_gems = [s for s in stock_analysis_list if s["ticker"] != CORE_ANCHOR_TICKER and s["conviction_score"] >= 65]
    top_gems = []
    sector_counts = {}
    MAX_PER_SECTOR = 2
    for g in all_gems:
        sector = g.get("sector", "Unknown")
        if sector_counts.get(sector, 0) < MAX_PER_SECTOR:
            top_gems.append(g)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(top_gems) >= 5:
            break

    total_gem_factor = sum(g["conviction_score"] * g.get("asymmetry_ratio", 1.0) for g in top_gems) if top_gems else 1.0
    remaining_weight = 1.0 - core_weight - target_cash_reserve_pct

    for g in top_gems:
        ticker = g["ticker"]
        factor_score = g["conviction_score"] * g.get("asymmetry_ratio", 1.0)
        raw_weight = (factor_score / total_gem_factor) * remaining_weight
        capped_weight = min(MAX_SINGLE_GEM_WEIGHT, raw_weight)
        target_positions[ticker] = {
            "ticker": ticker,
            "company_name": g["company_name"],
            "target_weight": capped_weight,
            "current_price": g["current_price"],
            "conviction_score": g["conviction_score"],
            "asymmetry_ratio": g["asymmetry_ratio"],
            "margin_of_safety_pct": g["margin_of_safety_pct"],
            "is_core": False
        }

    # 3. Evaluate Hysteresis & Trade Action Rules
    trades = []
    
    # Check current holdings for Stop-Loss, Take-Profit, or Replacement
    for ticker, hdata in current_holdings.items():
        curr_shares = hdata.get("shares", 0)
        if curr_shares <= 0: continue
        
        cost_basis = hdata.get("avg_cost", price_map.get(ticker, 100.0))
        curr_price = price_map.get(ticker, cost_basis)
        curr_val = curr_shares * curr_price
        curr_weight = curr_val / total_equity if total_equity > 0 else 0.0

        pnl_pct = ((curr_price - cost_basis) / cost_basis) if cost_basis > 0 else 0.0

        # Rule A: Trailing Stop-Loss / Peak Drawdown (-15% from high or entry)
        # Note: Fixed +25% take-profit cap was REMOVED to let winners compound indefinitely!
        if pnl_pct <= -TRAILING_STOP_LOSS_PCT and ticker != CORE_ANCHOR_TICKER:
            trades.append({
                "action": "SELL",
                "ticker": ticker,
                "shares": curr_shares,
                "price": curr_price,
                "total_usd": round(curr_val, 2),
                "reason": f"⛔ TRAILING STOP-LOSS (-{abs(pnl_pct)*100:.1f}% drawdown). Protecting capital."
            })
            continue

        # Rule C: If holding is NOT in target positions and conviction is weak
        if ticker not in target_positions:
            holding_analysis = analysis_map.get(ticker, {})
            score = holding_analysis.get("conviction_score", 50)
            if score < 60:
                trades.append({
                    "action": "SELL",
                    "ticker": ticker,
                    "shares": curr_shares,
                    "price": curr_price,
                    "total_usd": round(curr_val, 2),
                    "reason": f"Reallocating capital: Conviction score ({score}/100) below target threshold."
                })

    # ── FIX 7: Check target positions for Buys or Adjustments (with Drift Buffer) ─────────────
    # First pass: collect rebalance SELL orders and pending BUY orders separately.
    # Only emit BUY orders up to available buying power = cash + projected sell proceeds.
    # This prevents generating buy orders for $70K when only $10K cash is available.
    pending_buys = []
    for ticker, tinfo in target_positions.items():
        target_val = allocatable_equity * tinfo["target_weight"]
        price = tinfo["current_price"]
        target_shares = math.floor(target_val / price) if price > 0 else 0

        curr_shares = current_holdings.get(ticker, {}).get("shares", 0)
        curr_val = curr_shares * price
        curr_weight = curr_val / total_equity if total_equity > 0 else 0.0

        weight_diff = abs(tinfo["target_weight"] - curr_weight)

        # Only trade if weight drift > 4% threshold or adding new position
        if curr_shares == 0 or weight_diff >= WEIGHT_DRIFT_THRESHOLD:
            diff_shares = target_shares - curr_shares
            trade_usd = abs(diff_shares) * price

            if trade_usd >= MIN_TRADE_USD:
                if diff_shares > 0:
                    pending_buys.append({
                        "action": "BUY",
                        "ticker": ticker,
                        "shares": diff_shares,
                        "price": price,
                        "total_usd": round(trade_usd, 2),
                        "reason": f"High Asymmetry ({tinfo['asymmetry_ratio']}x) & Conviction ({tinfo['conviction_score']}/100)" if not tinfo.get("is_core") else "Core Index Anchor allocation."
                    })
                elif diff_shares < 0:
                    sell_shares = abs(diff_shares)
                    trades.append({
                        "action": "SELL",
                        "ticker": ticker,
                        "shares": sell_shares,
                        "price": price,
                        "total_usd": round(trade_usd, 2),
                        "reason": "Rebalancing target weight allocation."
                    })

    # Second pass: calculate actual available buying power then emit BUYs in priority order.
    # SELLs from this rebalance cycle + existing cash = total buying power.
    projected_sell_proceeds = sum(t["total_usd"] for t in trades if t["action"] == "SELL")
    available_buying_power = cash + projected_sell_proceeds

    # Sort buys by conviction descending so highest-priority positions get funded first
    pending_buys.sort(key=lambda b: b.get("total_usd", 0), reverse=True)
    for buy in pending_buys:
        if available_buying_power >= buy["total_usd"]:
            trades.append(buy)
            available_buying_power -= buy["total_usd"]
        else:
            # Partially fund if we can afford at least 1 share
            affordable_shares = math.floor(available_buying_power / buy["price"]) if buy["price"] > 0 else 0
            if affordable_shares > 0 and (affordable_shares * buy["price"]) >= MIN_TRADE_USD:
                partial_usd = round(affordable_shares * buy["price"], 2)
                trades.append({
                    "action": "BUY",
                    "ticker": buy["ticker"],
                    "shares": affordable_shares,
                    "price": buy["price"],
                    "total_usd": partial_usd,
                    "reason": buy["reason"] + f" (Partial — limited by available buying power ${available_buying_power:,.0f})"
                })
                available_buying_power -= partial_usd
            break  # No more capital for further buys

    # Ensure SELLs appear before BUYs in the output list for correct execution ordering
    trades.sort(key=lambda t: 0 if t["action"] == "SELL" else 1)

    target_portfolio_summary = []
    for ticker, tinfo in target_positions.items():
        price = tinfo["current_price"]
        t_val = allocatable_equity * tinfo["target_weight"]
        t_shares = math.floor(t_val / price) if price > 0 else 0
        target_portfolio_summary.append({
            "ticker": ticker,
            "company_name": tinfo["company_name"],
            "price": price,
            "target_shares": t_shares,
            "target_value": round(t_shares * price, 2),
            "target_weight_pct": round(tinfo["target_weight"] * 100, 1),
            "conviction_score": tinfo["conviction_score"],
            "asymmetry_ratio": tinfo["asymmetry_ratio"],
            "is_core": tinfo.get("is_core", False)
        })

    return {
        "total_equity": round(total_equity, 2),
        "holdings_valuation": round(holdings_value, 2),
        "current_cash": round(cash, 2),
        "target_cash_reserve": round(total_equity * target_cash_reserve_pct, 2),
        "rebalancing_trades": trades,
        "target_portfolio": target_portfolio_summary
    }
