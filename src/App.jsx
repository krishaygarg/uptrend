import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, TrendingDown, DollarSign, Shield, Zap, RefreshCw, 
  Layers, ChevronRight, AlertTriangle, CheckCircle2, PieChart, 
  BarChart2, Edit3, X, Sliders, Info
} from 'lucide-react';
import { ResponsiveContainer, PieChart as RePie, Pie, Cell, Tooltip } from 'recharts';

const COLORS = ['#38bdf8', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#6366f1'];

export default function App() {
  const [portfolio, setPortfolio] = useState(null);
  const [rebalance, setRebalance] = useState(null);
  const [gems, setGems] = useState([]);
  const [category, setCategory] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [rebalancingLoading, setRebalancingLoading] = useState(false);
  const [selectedStock, setSelectedStock] = useState(null);
  const [showEditPortfolioModal, setShowEditPortfolioModal] = useState(false);
  const [editCash, setEditCash] = useState(10000);
  
  // Custom DCF Sandbox state for selected stock
  const [dcfGrowth, setDcfGrowth] = useState(10);
  const [dcfDiscount, setDcfDiscount] = useState(9);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      fetchData();
    }, 60000);
    return () => clearInterval(interval);
  }, [category]);

  const fetchData = async () => {
    setLoading(true);
    const ts = Date.now();
    try {
      // Fetch portfolio (FastAPI endpoint or Cloudflare Pages static fallback)
      let portData = null;
      try {
        const resPort = await fetch('/api/portfolio');
        const cType = resPort.headers.get("content-type") || "";
        if (resPort.ok && cType.includes("application/json")) {
          portData = await resPort.json();
        }
      } catch (e) {}

      if (!portData || portData.cash_balance === undefined) {
        const resStaticPort = await fetch(`/portfolio.json?t=${ts}`);
        if (resStaticPort.ok) portData = await resStaticPort.json();
      }

      // Normalize holdings from object to array if loaded from static portfolio.json
      if (portData && !Array.isArray(portData.holdings)) {
        const holdingsDict = portData.holdings || {};
        let totalHoldingsVal = 0;
        const holdingsArray = Object.entries(holdingsDict).map(([ticker, hdata]) => {
          const shares = hdata.shares || 0;
          const avgCost = hdata.avg_cost || 0;
          const marketVal = shares * avgCost;
          totalHoldingsVal += marketVal;
          return {
            ticker,
            company_name: ticker,
            shares,
            avg_cost: avgCost,
            current_price: avgCost,
            market_value: marketVal,
            unrealized_pnl: 0,
            unrealized_pnl_pct: 0,
            asymmetry_ratio: 1.0,
            conviction_score: 90
          };
        });
        portData = {
          ...portData,
          total_holdings_value: totalHoldingsVal,
          total_equity: (portData.cash_balance || 0) + totalHoldingsVal,
          holdings: holdingsArray
        };
      }

      // Fetch live market quotes for holdings in real time
      if (portData && Array.isArray(portData.holdings) && portData.holdings.length > 0) {
        try {
          let updatedTotalHoldings = 0;
          const updatedHoldings = await Promise.all(
            portData.holdings.map(async (h) => {
              let cp = h.current_price || h.avg_cost;
              try {
                let resQuote = null;
                try {
                  resQuote = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${h.ticker}`);
                } catch (err) {
                  resQuote = await fetch(`https://api.allorigins.win/raw?url=${encodeURIComponent(`https://query1.finance.yahoo.com/v8/finance/chart/${h.ticker}`)}`);
                }
                if (resQuote && resQuote.ok) {
                  const qData = await resQuote.json();
                  const meta = qData?.chart?.result?.[0]?.meta;
                  if (meta && meta.regularMarketPrice) {
                    cp = meta.regularMarketPrice;
                  }
                }
              } catch (e) {}

              const shares = h.shares || 0;
              const avgCost = h.avg_cost || 0;
              const mktVal = shares * cp;
              const unPnl = (cp - avgCost) * shares;
              const unPnlPct = avgCost > 0 ? ((cp - avgCost) / avgCost) * 100 : 0;
              updatedTotalHoldings += mktVal;

              return {
                ...h,
                current_price: Math.round(cp * 100) / 100,
                market_value: Math.round(mktVal * 100) / 100,
                unrealized_pnl: Math.round(unPnl * 100) / 100,
                unrealized_pnl_pct: Math.round(unPnlPct * 100) / 100
              };
            })
          );

          portData = {
            ...portData,
            total_holdings_value: Math.round(updatedTotalHoldings * 100) / 100,
            total_equity: Math.round(((portData.cash_balance || 0) + updatedTotalHoldings) * 100) / 100,
            holdings: updatedHoldings
          };
        } catch (e) {}
      }

      setPortfolio(portData);
      if (portData && portData.cash_balance !== undefined) setEditCash(portData.cash_balance);

      // Fetch rebalance instructions
      let rebData = null;
      try {
        const resReb = await fetch('/api/rebalance');
        const cType = resReb.headers.get("content-type") || "";
        if (resReb.ok && cType.includes("application/json")) {
          rebData = await resReb.json();
        }
      } catch (e) {}
      if (!rebData) {
        const resStaticReb = await fetch(`/rebalance_snapshot.json?t=${ts}`);
        if (resStaticReb.ok) rebData = await resStaticReb.json();
      }
      setRebalance(rebData);

      // Fetch gems
      let gemsData = null;
      try {
        const resGems = await fetch('/api/gems');
        const cType = resGems.headers.get("content-type") || "";
        if (resGems.ok && cType.includes("application/json")) {
          gemsData = await resGems.json();
        }
      } catch (e) {}
      if (!gemsData) {
        const resStaticGems = await fetch(`/gems_snapshot.json?t=${ts}`);
        if (resStaticGems.ok) gemsData = await resStaticGems.json();
      }

      const gemsArray = Array.isArray(gemsData)
        ? gemsData
        : (gemsData?.recommendations || gemsData?.top_gems || []);
      setGems(gemsArray);
    } catch (err) {
      console.error("Failed to load portfolio data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteRebalance = async () => {
    if (!window.confirm("Execute recommended daily rebalancing trades and update portfolio state?")) return;
    setRebalancingLoading(true);
    try {
      const res = await fetch('/api/portfolio/execute-rebalance', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        alert("Rebalance trades executed successfully!");
        fetchData();
      }
    } catch (err) {
      alert("Failed to execute rebalance.");
    } finally {
      setRebalancingLoading(false);
    }
  };

  const handleUpdateCash = async (e) => {
    e.preventDefault();
    try {
      await fetch('/api/portfolio/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cash_balance: parseFloat(editCash) })
      });
      setShowEditPortfolioModal(false);
      fetchData();
    } catch (err) {
      alert("Failed to update portfolio cash.");
    }
  };

  const openStockModal = (stock) => {
    setSelectedStock(stock);
    setDcfGrowth(10);
    setDcfDiscount(9);
  };

  // Interactive DCF Intrinsic Value calculator logic
  const calculateSandboxDCF = () => {
    if (!selectedStock) return 0;
    const baseVal = selectedStock.fair_value || selectedStock.current_price;
    const factor = (1 + (dcfGrowth - 10) * 0.05) / (1 + (dcfDiscount - 9) * 0.08);
    return Math.max(1, Math.round(baseVal * factor * 100) / 100);
  };

  const holdingsList = Array.isArray(portfolio?.holdings) ? portfolio.holdings : [];
  const pieData = holdingsList.map(h => ({
    name: h.ticker,
    value: h.market_value
  }));

  if (portfolio?.cash_balance > 0) {
    pieData.push({ name: 'Cash Cushion', value: portfolio.cash_balance });
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header-bar">
        <div className="logo-group">
          <div className="logo-icon">💎</div>
          <div>
            <h1 className="logo-title">UpTrend</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Market Outperformance & Daily Portfolio Rebalancer
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button onClick={fetchData} className="tab-btn" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh Market Data
          </button>

          <button onClick={() => setShowEditPortfolioModal(true)} className="tab-btn active" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Edit3 size={14} /> Adjust Capital (${portfolio?.cash_balance.toLocaleString() || '0'})
          </button>
        </div>
      </header>

      {/* Metric Overview Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1.25rem', marginBottom: '2rem' }}>
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            <span>TOTAL PORTFOLIO EQUITY</span>
            <DollarSign size={16} color="var(--accent-cyan)" />
          </div>
          <div className="mono" style={{ fontSize: '2rem', fontWeight: '700', margin: '0.5rem 0', color: '#fff' }}>
            ${portfolio?.total_equity?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <TrendingUp size={14} /> Active Daily Tracking
          </div>
        </div>

        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            <span>LIQUID CASH RESERVE</span>
            <Shield size={16} color="var(--accent-emerald)" />
          </div>
          <div className="mono" style={{ fontSize: '2rem', fontWeight: '700', margin: '0.5rem 0', color: '#fff' }}>
            ${portfolio?.cash_balance?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Available for high-conviction trades
          </div>
        </div>

        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            <span>TOP ASYMMETRY RATIO</span>
            <Zap size={16} color="var(--accent-violet)" />
          </div>
          <div className="mono" style={{ fontSize: '2rem', fontWeight: '700', margin: '0.5rem 0', color: 'var(--accent-cyan)' }}>
            {gems.length > 0 ? `${gems[0].asymmetry_ratio}x` : 'N/A'}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {gems.length > 0 ? `Target: +${gems[0].upside_potential_pct}% Upside` : 'Scanning...'}
          </div>
        </div>
      </div>

      {/* Daily Rebalance Action Banner */}
      {rebalance && (
        <div className="rebalance-banner">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <span className="badge-tag badge-cyan">DAILY REBALANCE ACTION</span>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Recommended trades for today's market conditions
                </span>
              </div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '700' }}>
                {rebalance.rebalancing_trades.length === 0 
                  ? "✓ Your portfolio is perfectly balanced!" 
                  : `${rebalance.rebalancing_trades.length} Trade Actions Suggested Today`}
              </h2>
            </div>

            {rebalance.rebalancing_trades.length > 0 && (
              <button 
                onClick={handleExecuteRebalance} 
                className="action-btn"
                disabled={rebalancingLoading}
              >
                <CheckCircle2 size={16} /> {rebalancingLoading ? "Executing..." : "Execute Rebalance Trades"}
              </button>
            )}
          </div>

          {rebalance.rebalancing_trades.length > 0 && (
            <div style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem' }}>
              {(Array.isArray(rebalance?.rebalancing_trades) ? rebalance.rebalancing_trades : []).map((tr, idx) => (
                <div key={idx} style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '0.75rem 1rem', borderRadius: '10px', borderLeft: tr.action === 'BUY' ? '4px solid #10b981' : '4px solid #f43f5e' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: '600', fontSize: '0.9rem' }}>
                    <span style={{ color: tr.action === 'BUY' ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                      {tr.action} {tr.shares} {tr.ticker}
                    </span>
                    <span className="mono">${tr.total_usd.toLocaleString()}</span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    {tr.reason}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Main Tabs for Strategy / Categories */}
      <div className="tab-group">
        {[
          { id: 'ALL', label: '🔥 All High Asymmetry Gems' },
          { id: 'SmallCap_Gems', label: '💎 Small-Cap Gems' },
          { id: 'MidCap_Growth', label: '🚀 Mid-Cap Growth' },
          { id: 'High_Growth_Tech', label: '⚡ High Growth Tech' },
          { id: 'Deep_Value_Moat', label: '🛡️ Deep Value Moats' },
          { id: 'Dividend_Compounders', label: '💰 Dividend Compounders' }
        ].map(t => (
          <button 
            key={t.id} 
            onClick={() => setCategory(t.id)} 
            className={`tab-btn ${category === t.id ? 'active' : ''}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Stock Screener Grid */}
      <h2 style={{ fontSize: '1.25rem', fontWeight: '700', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span>Recommended Stocks</span>
        <span className="badge-tag badge-cyan">{gems.length} Candidates</span>
      </h2>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-muted)' }}>
          Analyzing stock fundamentals, DCF intrinsic values, and asymmetry ratios...
        </div>
      ) : (
        <div className="stock-grid">
          {(Array.isArray(gems) ? gems : []).map(stock => (
            <div 
              key={stock.ticker} 
              className="glass-card stock-card"
              onClick={() => openStockModal(stock)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: '1.25rem', fontWeight: '800', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span>{stock.ticker}</span>
                    <span className="badge-tag badge-cyan" style={{ fontSize: '0.65rem' }}>{stock.category}</span>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: '200px' }}>
                    {stock.company_name}
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div className="badge-tag badge-emerald" style={{ fontSize: '0.85rem' }}>
                    {stock.asymmetry_ratio}x Ratio
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    Conviction: {stock.conviction_score}/100
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Current Price</div>
                  <div className="mono" style={{ fontWeight: '600' }}>${stock.current_price.toFixed(2)}</div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Fair Value</div>
                  <div className="mono" style={{ fontWeight: '600', color: 'var(--accent-emerald)' }}>
                    ${stock.fair_value.toFixed(2)}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Upside Potential</div>
                  <div className="mono" style={{ fontWeight: '600', color: 'var(--accent-emerald)' }}>
                    +{stock.upside_potential_pct}%
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Downside Floor</div>
                  <div className="mono" style={{ fontWeight: '600', color: 'var(--accent-rose)' }}>
                    -${stock.downside_risk_pct}% (${stock.support_floor})
                  </div>
                </div>
              </div>

              <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span>Margin of Safety: {stock.margin_of_safety_pct}%</span>
                <ChevronRight size={14} color="var(--accent-cyan)" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Current Holdings & Target Allocation Chart Section */}
      {portfolio && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem', marginTop: '3rem' }}>
          <div className="glass-card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <PieChart size={18} color="var(--accent-cyan)" /> Portfolio Allocation breakdown
            </h3>
            
            <div style={{ height: '240px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <RePie>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(val) => `$${val.toLocaleString()}`} />
                </RePie>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BarChart2 size={18} color="var(--accent-emerald)" /> Active Positions
            </h3>

            <table className="custom-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Shares</th>
                  <th>Avg Cost</th>
                  <th>Market Value</th>
                  <th>PnL</th>
                </tr>
              </thead>
              <tbody>
                {holdingsList.map(h => (
                  <tr key={h.ticker}>
                    <td className="mono" style={{ fontWeight: '700' }}>{h.ticker}</td>
                    <td>{h.shares}</td>
                    <td className="mono">${h.avg_cost.toFixed(2)}</td>
                    <td className="mono" style={{ fontWeight: '600' }}>${h.market_value.toLocaleString()}</td>
                    <td className="mono" style={{ color: h.unrealized_pnl >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                      {h.unrealized_pnl >= 0 ? '+' : ''}${h.unrealized_pnl} ({h.unrealized_pnl_pct}%)
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Stock Deep-Dive Sandbox Modal */}
      {selectedStock && (
        <div className="modal-overlay" onClick={() => setSelectedStock(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <div>
                <h2 style={{ fontSize: '1.75rem', fontWeight: '800', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span>{selectedStock.ticker}</span>
                  <span className="badge-tag badge-cyan">{selectedStock.asymmetry_ratio}x Asymmetry</span>
                </h2>
                <p style={{ color: 'var(--text-muted)' }}>{selectedStock.company_name} | {selectedStock.sector}</p>
              </div>
              <button onClick={() => setSelectedStock(null)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>
                <X size={24} />
              </button>
            </div>

            {/* Key Valuation Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              <div style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '1rem', borderRadius: '12px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Current Price</div>
                <div className="mono" style={{ fontSize: '1.25rem', fontWeight: '700' }}>${selectedStock.current_price.toFixed(2)}</div>
              </div>

              <div style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '1rem', borderRadius: '12px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Consensus Fair Value</div>
                <div className="mono" style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--accent-emerald)' }}>
                  ${selectedStock.fair_value.toFixed(2)}
                </div>
              </div>

              <div style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '1rem', borderRadius: '12px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Downside Floor Risk</div>
                <div className="mono" style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--accent-rose)' }}>
                  -${selectedStock.downside_risk_pct}% (${selectedStock.support_floor})
                </div>
              </div>

              <div style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '1rem', borderRadius: '12px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>FCF Yield</div>
                <div className="mono" style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--accent-cyan)' }}>
                  {selectedStock.fcf_yield_pct}%
                </div>
              </div>
            </div>

            {/* Financial Health & Structural Risk Scorecard */}
            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '1.25rem', borderRadius: '12px', marginBottom: '1.5rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: '700', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Shield size={16} color="var(--accent-emerald)" /> Balance Sheet & Structural Health
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem', fontSize: '0.85rem' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Piotroski F-Score:</span>
                  <div className="mono" style={{ fontWeight: '700', color: selectedStock.piotroski_f_score >= 6 ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}>
                    {selectedStock.piotroski_f_score} / 9 {selectedStock.piotroski_f_score >= 6 ? '(Strong)' : '(Watch)'}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Altman Z-Score:</span>
                  <div className="mono" style={{ fontWeight: '600' }}>{selectedStock.altman_z_score} (&gt; 2.8 Safe)</div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Debt to Equity:</span>
                  <div className="mono" style={{ fontWeight: '600' }}>{selectedStock.debt_to_equity}</div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>RSI (14):</span>
                  <div className="mono" style={{ fontWeight: '600' }}>{selectedStock.rsi_14}</div>
                </div>
              </div>

              {/* Structural Flags Warning Box */}
              {selectedStock.structural_flags && selectedStock.structural_flags.length > 0 && (
                <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--accent-rose)', fontWeight: '600', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                    <AlertTriangle size={15} /> Structural Red Flags Detected
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.25rem' }}>
                    {selectedStock.structural_flags.map((flag, i) => (
                      <span key={i} className="badge-tag badge-rose" style={{ fontSize: '0.7rem' }}>
                        {flag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Interactive DCF Sandbox */}
            <div style={{ background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.08), rgba(139, 92, 246, 0.08))', border: '1px solid rgba(56, 189, 248, 0.2)', padding: '1.25rem', borderRadius: '12px' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: '700', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Sliders size={16} color="var(--accent-cyan)" /> Interactive DCF Sandbox
              </h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                Adjust 5-year FCF growth and discount rates to see live intrinsic value sensitivity.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                <div>
                  <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Projected FCF Growth Rate: {dcfGrowth}%</label>
                  <input 
                    type="range" min="2" max="30" value={dcfGrowth} 
                    onChange={(e) => setDcfGrowth(Number(e.target.value))} 
                    style={{ width: '100%', marginTop: '0.5rem' }} 
                  />
                </div>

                <div>
                  <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>WACC Discount Rate: {dcfDiscount}%</label>
                  <input 
                    type="range" min="6" max="15" value={dcfDiscount} 
                    onChange={(e) => setDcfDiscount(Number(e.target.value))} 
                    style={{ width: '100%', marginTop: '0.5rem' }} 
                  />
                </div>
              </div>

              <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255, 255, 255, 0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Simulated Intrinsic Fair Value:</span>
                <span className="mono" style={{ fontSize: '1.25rem', fontWeight: '800', color: 'var(--accent-cyan)' }}>
                  ${calculateSandboxDCF()}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Adjust Capital Modal */}
      {showEditPortfolioModal && (
        <div className="modal-overlay" onClick={() => setShowEditPortfolioModal(false)}>
          <div className="modal-content" style={{ maxWidth: '450px' }} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: '700', marginBottom: '1rem' }}>Update Available Liquid Cash</h2>
            <form onSubmit={handleUpdateCash}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.5rem' }}>
                  Liquid Cash Available (USD):
                </label>
                <input 
                  type="number" 
                  step="100" 
                  value={editCash} 
                  onChange={(e) => setEditCash(e.target.value)} 
                  style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', fontSize: '1.1rem' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button type="button" onClick={() => setShowEditPortfolioModal(false)} className="tab-btn">Cancel</button>
                <button type="submit" className="action-btn">Save Cash</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
