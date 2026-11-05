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
| [**Checkpoint Reconciliation**](CHECKPOINT_RECONCILIATION.md) | Universal quality-control framework auditing point-in-time portfolio snapshots across all publications. | 23 checkpoints audited across all 3 publications; mandatory validation runs automatically on every analysis command. |
| [**Root Cause Investigation**](ROOT_CAUSE_AUDIT.md) | Exhaustive investigation of omitted positions (`013030.KQ`, `453340.KS`, `139130.KS`, `IFOS`), paywall caching bugs, and static list flaws. | Resolved 20 paywall preview stubs via authenticated scraping, corrected KOSDAQ/KOSPI suffixes, and fixed tautological test harness. |
| [**Source Coverage Report**](COVERAGE_REPORT.md) | Independent source-to-trade inventory, orphan holding guards, disappearance alerts, and 8-point audit metrics. | 1,094 sources audited (100% coverage); 133 trades extracted; automated guards prevent future omissions across all 3 publications. |
| [**Performance Comparison**](PERFORMANCE_COMPARISON.md) | Head-to-head backtest results (2026-01-01 to present) under identical dollar-matched cash flows ($1,000 unit size). | Following full reconciliation, Cluseau delivered +22.7% Strat A / +15.0% Strat B (+33.1% / +29.7% XIRR), TJ Stocks delivered +21.0% (+30.1% XIRR), and Beating The Tide delivered +16.5% (+23.2% XIRR). |
| [**Risk & Volatility Analysis**](RISK_ANALYSIS.md) | Multi-dimensional risk matrix: win rates, downside skew, single-stock concentration, execution burden, and liquidity. | TJ Stocks demonstrated the highest consistency (Profit Factor 12.82, worst loss -10.1%). Cluseau demonstrated strong alpha (Profit Factor 4.32, 73.1% win rate) across global small-caps. |
| [**Author Claims Reconciliation**](AUTHOR_RECONCILIATION.md) | Line-by-line audit reconciling author-claimed returns against market quotes and our backtester calculations. | Reconciled Beating The Tide's +23.59% YTD, TJ Stocks' 2.99x SPY outperformance, and Cluseau's international basket and options overlays. |

---

## Publication Source Guides

- [**Beating The Tide Source Profile**](../sources/beatingthetide/README.md): 247 post JSONs, 48 Datawrapper CSV datasets, holdings, and trade events.
- [**TJ Stocks Source Profile**](../sources/tjstocks/README.md): 417 post JSONs, StockTok ETF holdings, and trade events.
- [**Cluseau Source Profile**](../sources/cluseau/README.md): 52 post JSONs, 404 subscriber chat threads, and trade events.
