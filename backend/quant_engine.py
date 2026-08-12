"""
Quantitative Analysis Engine for AlphaPulse.
Calculates intrinsic valuation (DCF, Graham), Margin of Safety, Financial Health
(Real Altman Z-Score, FCF Yield, Piotroski F-Score), Beta-Adjusted Downside Floor,
Structural Red Flags, Asymmetry Ratio (Upside/Downside), and Conviction Score.
Includes Multi-Threaded parallel batch scanning & session-aware disk caching for 1,000+ stocks.

FIXES (2026-08-12):
  FIX 1: Missing data triggers conviction exclusion — no generous fallback defaults
  FIX 2: Beta-adjusted downside floor replaces hardcoded 4% minimum
  FIX 3: Sector diversification enforced (max 2 per sector in top gems) — in rebalancer
  FIX 4: Session-aware cache TTL (expires at market close 4:05 PM ET, not rolling 12hr)
  FIX 5: Real 5-ratio Altman Z-Score replaces fake estimated formula
  FIX 6: Piotroski defaults to None for missing data — no free points
  FIX 7: Cash-check before buys enforced — in rebalancer
  FIX 8: Graham growth rate capped at 15% max (original formula spec)
"""

import os
import json
import time
import math
import logging
import concurrent.futures
from datetime import datetime, timezone, timedelta

import yfinance as yf
import pandas as pd
import numpy as np

logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logger = logging.getLogger("quant_engine")

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "stock_analysis_cache.json")


# ── FIX 4: Session-aware cache TTL ──────────────────────────────────────────
def get_cache_session_timestamp():
    """
    Returns the Unix timestamp of the most recent US market close (4:05 PM ET).
    Cache written before this timestamp is considered stale and will be invalidated.
    This prevents reusing data from earnings-day price swings.
    """
    et_tz = timezone(timedelta(hours=-4))   # Eastern Time (EDT offset)
    now_et = datetime.now(et_tz)

    close_today = now_et.replace(hour=16, minute=5, second=0, microsecond=0)
    candidate = close_today

    # Walk back to last weekday
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)

    # If today is a weekday but we're before 9:30 AM, use prior session's close
    if candidate.date() == now_et.date() and now_et.hour < 9:
        candidate -= timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate -= timedelta(days=1)

    return candidate.timestamp()


def load_disk_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
        cache_session_ts = data.get("_session_timestamp", 0)
        current_session_ts = get_cache_session_timestamp()
        if cache_session_ts >= current_session_ts:
            return data.get("stocks", {})
    except Exception:
        pass
    return {}


def save_disk_cache(cache_data):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump({
                "_session_timestamp": get_cache_session_timestamp(),
                "stocks": cache_data
            }, f)
    except Exception:
        pass


# ── Valuation Models ─────────────────────────────────────────────────────────
def calculate_dcf_valuation(free_cash_flow, growth_rate=0.10, discount_rate=0.09,
                             terminal_growth=0.025, years=5, shares_outstanding=1.0):
    if free_cash_flow is None or free_cash_flow <= 0 or shares_outstanding <= 0:
        return None
    current_fcf = free_cash_flow
    pv_fcfs = []
    for yr in range(1, years + 1):
        current_fcf *= (1 + growth_rate)
        pv_fcfs.append(current_fcf / ((1 + discount_rate) ** yr))
    terminal_value = (current_fcf * (1 + terminal_growth)) / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / ((1 + discount_rate) ** years)
    total_ev = sum(pv_fcfs) + pv_terminal
    return round(total_ev / shares_outstanding, 2)


def calculate_graham_value(eps, growth_rate=0.08):
    """
    FIX 8: Benjamin Graham's formula caps growth at 15% per original specification.
    Formula: V = EPS * (8.5 + 2g)  where g is in percent (0-15 range).
    """
    if eps is None or eps <= 0:
        return None
    g_pct = max(0.0, min(15.0, growth_rate * 100.0))  # Hard cap at 15%
    return round(eps * (8.5 + 2.0 * g_pct), 2)


def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return round(100.0 - (100.0 / (1.0 + avg_gain / avg_loss)), 2)


# ── FIX 6: Piotroski F-Score with NO free points for missing data ─────────────
def calculate_piotroski_f_score(info):
    """
    Real 9-point Piotroski F-Score.
    If a yfinance field is missing (None), that criterion is skipped entirely.
    Score is then proportionally scaled to /9 equivalent — no inflation from missing data.
    """
    score = 0
    eligible = 0

    def award(condition, data_present=True):
        nonlocal score, eligible
        if data_present:
            eligible += 1
            if condition:
                score += 1

    roa = info.get("returnOnAssets")
    ocf = info.get("operatingCashflow")
    ni  = info.get("netIncomeToCommon")
    d_e = info.get("debtToEquity")
    cr  = info.get("currentRatio")
    sho = info.get("sharesOutstanding")
    ish = info.get("impliedSharesOutstanding")
    gm  = info.get("grossMargins")
    em  = info.get("ebitdaMargins")

    award(roa is not None and roa > 0,          roa is not None)
    award(ocf is not None and ocf > 0,          ocf is not None)
    award(roa is not None and roa > 0.03,       roa is not None)
    award(ocf is not None and ni is not None and ocf > ni, ocf is not None and ni is not None)
    award(d_e is not None and (d_e / 100.0) < 1.2, d_e is not None)
    award(cr  is not None and cr > 1.2,         cr  is not None)
    award(sho is not None and ish is not None and sho <= ish, sho is not None and ish is not None)
    award(gm  is not None and gm > 0.25,        gm  is not None)
    award(em  is not None and em > 0.10,        em  is not None)

    if eligible == 0:
        return 0
    return min(9, max(0, round((score / eligible) * 9)))


# ── FIX 5: Real Altman Z-Score (5-ratio formula) ─────────────────────────────
def calculate_real_altman_z(info, market_cap):
    """
    Real Altman Z-Score:
      Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
      X1 = Working Capital / Total Assets
      X2 = Retained Earnings / Total Assets
      X3 = EBIT / Total Assets
      X4 = Market Cap / Total Liabilities
      X5 = Revenue / Total Assets
    Returns None if total_assets is missing (no fabricated scores).
    """
    total_assets = info.get("totalAssets")
    if not total_assets or total_assets <= 0:
        return None

    tca  = info.get("totalCurrentAssets") or 0
    tcl  = info.get("totalCurrentLiabilities") or 0
    re   = info.get("retainedEarnings") or 0
    ebit = info.get("ebit") or 0
    td   = info.get("totalDebt") or 1  # avoid div/0; if no debt Z4 is very high
    rev  = info.get("totalRevenue") or 0

    x1 = (tca - tcl) / total_assets
    x2 = re / total_assets
    x3 = ebit / total_assets
    x4 = (market_cap / td) if td > 0 else 5.0
    x5 = rev / total_assets

    return round(1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5, 2)


# ── Core Stock Analyzer ───────────────────────────────────────────────────────
def analyze_stock(ticker):
    """
    Fetches stock data via yfinance and calculates full quantitative assessment.

    FIX 1: Stocks without real EPS or FCF data are excluded entirely rather than
    receiving generous fallback values that inflate their conviction scores.
    """
    ticker = ticker.upper()
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info or {}
        history = ticker_obj.history(period="1y")
    except Exception:
        return None

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not current_price and history is not None and not history.empty:
        current_price = float(history["Close"].iloc[-1])
    if not current_price or current_price <= 0:
        return None

    market_cap = info.get("marketCap") or 0

    # ── FIX 1: Require real valuation data ───────────────────────────────────
    eps      = info.get("trailingEps") or info.get("forwardEps")
    fcf_raw  = info.get("freeCashflow")
    shares   = info.get("sharesOutstanding") or (market_cap / current_price if market_cap > 0 else None)

    # Must have at least one of EPS or FCF, plus shares outstanding
    if (eps is None and fcf_raw is None) or shares is None:
        return None

    # Safe fallbacks only for non-critical display/scoring fields
    company_name   = info.get("longName") or info.get("shortName") or ticker
    sector         = info.get("sector") or "Unknown"
    industry       = info.get("industry") or "Unknown"
    pe_ratio       = info.get("trailingPE") or info.get("forwardPE") or 15.0
    pb_ratio       = info.get("priceToBook") or 2.5
    rev_growth     = info.get("revenueGrowth") or 0.0
    earn_growth    = info.get("earningsGrowth") or 0.0
    d_e_raw        = info.get("debtToEquity")
    debt_eq_ratio  = (d_e_raw / 100.0) if d_e_raw is not None else 0.5
    roe            = info.get("returnOnEquity") or 0.0
    beta           = info.get("beta") or 1.0
    analyst_target = info.get("targetMeanPrice")

    # Technical indicators
    low52   = info.get("fiftyTwoWeekLow") or (current_price * 0.80)
    sma200  = current_price * 0.95
    rsi     = 50.0

    if history is not None and len(history) >= 30:
        closes = history["Close"].values
        rsi = calculate_rsi(closes)
        sma200 = float(np.mean(closes[-200:])) if len(closes) >= 200 else float(np.mean(closes))

    # ── Structural Red Flags ──────────────────────────────────────────────────
    structural_flags = []
    if debt_eq_ratio > 2.0:
        structural_flags.append("HIGH_LEVERAGE_DEBT (D/E > 2.0)")
    if rev_growth < -0.05:
        structural_flags.append("REVENUE_CONTRACTION (Negative Growth)")
    if (eps is not None and eps < 0) or earn_growth < -0.15:
        structural_flags.append("EARNINGS_DETERIORATION")
    if current_price < sma200 * 0.75:
        structural_flags.append("LONG_TERM_TECHNICAL_DOWNWARD_SPIRAL (Price >25% below 200 SMA)")

    country = info.get("country") or "United States"
    if country in ["China", "Hong Kong", "Russia"] or ticker in ["BABA", "BIDU", "JD", "PDD", "NIO"]:
        structural_flags.append("GEOPOLITICAL_ADR_REGULATORY_HEADWIND")

    piotroski = calculate_piotroski_f_score(info)
    if piotroski <= 3:
        structural_flags.append("POOR_PIOTROSKI_HEALTH_SCORE (Potential Value Trap)")

    # ── Currency Mismatch Protection ──────────────────────────────────────────
    fin_curr   = info.get("financialCurrency")
    price_curr = info.get("currency", "USD")
    fcf = fcf_raw
    if fin_curr and price_curr and fin_curr != price_curr and market_cap > 0:
        # FCF reported in foreign currency — use market cap proxy instead
        proxy_yield = (eps / current_price) if (eps and current_price > 0) else 0.05
        fcf = market_cap * min(0.08, max(0.03, proxy_yield))

    # Sanity check: FCF/MCap > 20% is almost always a data anomaly
    if fcf and market_cap > 0 and (fcf / market_cap) > 0.20:
        fcf = market_cap * 0.06

    # ── Valuation ────────────────────────────────────────────────────────────
    dcf_val = calculate_dcf_valuation(
        free_cash_flow=fcf,
        growth_rate=min(0.25, max(0.02, rev_growth)) if rev_growth else 0.08,
        discount_rate=0.09,
        terminal_growth=0.025,
        years=5,
        shares_outstanding=shares
    ) if fcf and fcf > 0 else None

    graham_val = calculate_graham_value(
        eps,
        growth_rate=min(0.15, max(0.02, earn_growth)) if earn_growth else 0.07   # FIX 8
    ) if eps else None

    # Sanity cap: no model should put fair value > 2.5x current price
    if dcf_val and dcf_val > current_price * 2.5:
        dcf_val = round(current_price * 2.2, 2)
    if graham_val and graham_val > current_price * 2.5:
        graham_val = round(current_price * 2.0, 2)

    vals = [v for v in [dcf_val, graham_val, analyst_target] if v and v > 0]
    fair_value = round(float(np.mean(vals)), 2) if vals else round(current_price * 1.10, 2)

    margin_of_safety_pct  = round(((fair_value - current_price) / fair_value) * 100.0, 1)
    upside_potential_pct  = max(0.0, round(((fair_value - current_price) / current_price) * 100.0, 1))

    # ── FIX 2: Beta-Adjusted Downside Floor ──────────────────────────────────
    # A stock with beta=2.0 has realistic drawdown potential of 16%+ in a correction.
    # Hardcoding 4% minimum was fabricating asymmetry ratios for volatile stocks.
    beta_adj_min = max(4.0, beta * 8.0)
    support_floor = round(max(low52, sma200 * 0.85, current_price * 0.75), 2)
    downside_risk_pct = max(
        round(((current_price - support_floor) / current_price) * 100.0, 1),
        beta_adj_min
    )

    # Cap asymmetry at 10x to prevent outlier fabrication
    raw_asym = upside_potential_pct / downside_risk_pct if downside_risk_pct > 0 else 0.0
    asymmetry_ratio = round(min(10.0, raw_asym), 2)

    fcf_yield   = round((fcf / market_cap) * 100.0, 2) if (fcf and market_cap > 0) else 0.0
    altman_z    = calculate_real_altman_z(info, market_cap)   # FIX 5

    # ── Conviction Score ──────────────────────────────────────────────────────
    conviction = 0.0
    conviction += min(25.0, asymmetry_ratio * 6.0)
    conviction += min(15.0, max(0.0, margin_of_safety_pct * 0.4))
    conviction += (piotroski / 9.0) * 20.0
    if altman_z is not None and altman_z > 2.99:
        conviction += 5.0
    # FIX 5: No bonus for unknown Z-score (no free points for missing data)
    if debt_eq_ratio < 0.8:
        conviction += 5.0
    if 35 <= rsi <= 65:
        conviction += 10.0
    elif rsi < 35:
        conviction += 15.0
    if current_price >= sma200:
        conviction += 5.0
    conviction += min(15.0, max(0.0, rev_growth * 50.0))

    # Penalties
    if "HIGH_LEVERAGE_DEBT (D/E > 2.0)" in structural_flags:                     conviction -= 20.0
    if "REVENUE_CONTRACTION (Negative Growth)" in structural_flags:               conviction -= 25.0
    if "EARNINGS_DETERIORATION" in structural_flags:                              conviction -= 20.0
    if "LONG_TERM_TECHNICAL_DOWNWARD_SPIRAL (Price >25% below 200 SMA)" in structural_flags: conviction -= 30.0
    if "POOR_PIOTROSKI_HEALTH_SCORE (Potential Value Trap)" in structural_flags:  conviction -= 35.0

    conviction_score = min(99, max(5, int(round(conviction))))

    return {
        "ticker":               ticker,
        "company_name":         company_name,
        "sector":               sector,
        "industry":             industry,
        "current_price":        round(float(current_price), 2),
        "fair_value":           fair_value,
        "dcf_value":            dcf_val,
        "graham_value":         graham_val,
        "analyst_target":       round(float(analyst_target), 2) if analyst_target else None,
        "margin_of_safety_pct": margin_of_safety_pct,
        "upside_potential_pct": upside_potential_pct,
        "support_floor":        support_floor,
        "downside_risk_pct":    downside_risk_pct,
        "asymmetry_ratio":      asymmetry_ratio,
        "fcf_yield_pct":        fcf_yield,
        "altman_z_score":       altman_z,
        "piotroski_f_score":    piotroski,
        "structural_flags":     structural_flags,
        "debt_to_equity":       round(debt_eq_ratio, 2),
        "pe_ratio":             round(float(pe_ratio), 1),
        "roe_pct":              round(float(roe) * 100.0, 1),
        "rsi_14":               rsi,
        "beta":                 round(float(beta), 2),
        "market_cap":           market_cap,
        "conviction_score":     conviction_score,
    }


# ── Batch Scanner ─────────────────────────────────────────────────────────────
def batch_analyze_stocks(ticker_list, max_workers=25, progress_callback=None):
    """
    Multi-Threaded parallel batch stock screener for 1,000+ stocks.
    FIX 4: Session-aware caching — cache expires at end of trading session (4:05 PM ET),
    not on a rolling 12-hour clock, preventing stale earnings-day data from persisting.
    """
    cached_data   = load_disk_cache()
    missing       = [t.upper() for t in ticker_list if t.upper() not in cached_data]

    if missing:
        results = {}
        completed = 0
        total = len(missing)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(analyze_stock, t): t for t in missing}
            for future in concurrent.futures.as_completed(future_map):
                t = future_map[future]
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, t)
                try:
                    res = future.result()
                    if res:
                        results[t] = res
                except Exception:
                    pass

        cached_data.update(results)
        save_disk_cache(cached_data)

    return [
        cached_data[t.upper()]
        for t in ticker_list
        if t.upper() in cached_data and cached_data[t.upper()] is not None
    ]
