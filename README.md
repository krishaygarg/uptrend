# UpTrend | Quantitative Trading & Portfolio Rebalancer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-brightgreen.svg)](https://www.python.org/)
[![React 18](https://img.shields.io/badge/React-18-cyan.svg)](https://reactjs.org/)
[![Cloudflare Pages](https://img.shields.io/badge/Cloudflare-Pages-orange.svg)](https://pages.cloudflare.com/)

**UpTrend** is an institutional-grade quantitative stock recommendation engine, multi-factor asymmetric stock screener, and daily portfolio rebalancer designed to systematically outperform market benchmarks (**S&P 500 / SPY** and **Nasdaq 100 / QQQ**).

---

## 🌟 Key Features

- **DualRegime Asset Allocation**: Dynamic 60% Core Index Anchor ($QQQ$) allocation during market bull trends ($\text{QQQ} \ge 200 \text{ SMA}$) with automated risk reduction during market downturns.
- **Uncapped Winner Retention**: Replaces fixed profit caps with a **18% Trailing Stop-Loss off 52-Week Peak** to allow high-conviction winners ($NVDA$, $AAPL$, $AMAT$) to compound indefinitely.
- **MultiFactor Asymmetric Screening**: Analyzes 1,000+ stocks daily across valuation models (**DCF**, **Graham Growth**, **Real Altman Z-Score**, **Piotroski F-Score**, and **6-Month Relative Strength**).
- **Automated Cloud Execution**: Runs daily at **8:00 AM Pacific Time** via **GitHub Actions** and updates the live interactive dashboard on **Cloudflare Pages**.
- **Institutional Risk Management**: Enforces sector diversification (max 2 stocks per sector in satellite gems) and buying power gating.

---

## 📊 Backtest Performance (10-Year Macro Dataset)

Tested across **133 out-of-sample rolling windows** spanning **2016 to 2026** (2,520 trading days):

| Metric | UpTrend Strategy | S&P 500 (SPY) | Nasdaq 100 (QQQ) | Outperformance |
| :--- | :---: | :---: | :---: | :---: |
| **10-Year Cumulative Return** | **+844.2%** ($944.2K) | +318.3% ($418.3K) | +566.9% ($666.9K) | **+525.9% vs SPY** |
| **Outperformance Win Rate** | **68.4%** | Baseline | — | **91 / 133 Slices** |
| **Average Alpha per Window** | **+10.40%** | Baseline | — | — |
| **Average Sharpe Ratio** | **1.07** | 0.82 | 0.95 | **Superior Risk-Adjusted** |
| **Max COVID Drawdown (2020)**| **-17.7%** | -33.7% | -28.2% | **+16.0% Cushion** |

---

## 🚀 QuickStart Guide

### 1. Local Setup
```bash
# Clone repository
git clone https://github.com/krishaygarg/uptrend.git
cd uptrend

# Initialize Python Virtual Environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Node.js Frontend Dependencies
npm install
```

### 2. Run Daily Portfolio Rebalancer
```bash
# Display recommendations and asymmetry analysis
./daily_rebalance.py

# Execute trades into portfolio state
./daily_rebalance.py --apply

# Display profit & performance tracking dashboard
./daily_rebalance.py --performance
```

### 3. Run Backtesting Suite
```bash
# Run 1-Year Backtest
./run_backtest.py --years 1.0

# Run 100+ Monte Carlo Stress Test Slices
./run_100_tests.py
```

---

## ⚙️ Cloud Architecture

- **GitHub Actions (`.github/workflows/daily_trader.yml`)**: Runs daily at **8:00 AM Pacific Time**, executes quantitative analysis, updates target portfolio allocations, and builds the frontend bundle.
- **Cloudflare Pages (`https://uptrend.pages.dev`)**: Hosts the live interactive web dashboard with zero backend latency.

---

## 📜 License

Licensed under the [MIT License](LICENSE).
