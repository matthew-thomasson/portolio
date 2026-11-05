# Analysis & Research Documentation Hub

Welcome to the documentation and research archive for the **Multi-Source Substack Downloader & Portfolio Backtester**.

This directory contains in-depth quantitative studies, risk evaluations, and track-record audits across the three covered publications:
1. **Beating The Tide** (`https://www.beatingthetide.com`)
2. **TJ Stocks** (`https://tjstocks.substack.com`)
3. **Cluseau** (`https://www.cluseau.com`)

---

## Navigation Directory

| Report | Description | Key Takeaway |
|---|---|---|
| [**Performance Comparison**](PERFORMANCE_COMPARISON.md) | Head-to-head backtest results (2026-01-01 to present) under identical dollar-matched cash flows ($1,000 unit size). | Cluseau led raw ROI (+38.0% Strat A / +33.0% Strat B; +51.3% / +68.4% XIRR), followed by TJ Stocks (+21.0% ROI / +30.1% XIRR) and Beating The Tide (+16.5% Strat A / +7.6% Strat B; +23.2% / +15.8% XIRR). |
| [**Risk & Volatility Analysis**](RISK_ANALYSIS.md) | Multi-dimensional risk matrix: win rates, downside skew, single-stock concentration, execution burden, and liquidity. | TJ Stocks demonstrated the lowest risk (Profit Factor 12.82, worst loss -10.1%). Beating The Tide showed high chasing risk. Cluseau delivered high alpha (Profit Factor 10.06) but requires real-time chat execution. |
| [**Author Claims Reconciliation**](AUTHOR_RECONCILIATION.md) | Line-by-line audit reconciling author-claimed returns against market quotes and our backtester calculations. | Reconciled Beating The Tide's +23.59% YTD, TJ Stocks' 2.99x SPY outperformance, and Cluseau's quarterly closed trade reports (including FX adjustments and options overlay). |

---

## Publication Source Guides

- [**Beating The Tide Source Profile**](../sources/beatingthetide/README.md): 247 post JSONs, 48 Datawrapper CSV datasets, holdings, and trade events.
- [**TJ Stocks Source Profile**](../sources/tjstocks/README.md): 417 post JSONs, StockTok ETF holdings, and trade events.
- [**Cluseau Source Profile**](../sources/cluseau/README.md): 52 post JSONs, 404 subscriber chat threads, and trade events.
