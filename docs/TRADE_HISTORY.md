# Multi-Source Portfolio Trade History Hub

This document provides quick access to the complete chronological trade histories extracted from each of the three investment Substack publications.

---

## Direct Links to Trade Logs

| Publication | Total Signals | Trade Log Link | Date Range | Primary Trade Actions |
|---|---|---|---|---|
| **Beating The Tide** | **85 trades** | [**`sources/beatingthetide/TRADE_HISTORY.md`**](../sources/beatingthetide/TRADE_HISTORY.md) | 2024-01-02 to 2026-11-02 | 45 BUY, 18 SELL, 11 TRIM, 10 ADD, 1 HOLD |
| **TJ Stocks** | **17 trades** | [**`sources/tjstocks/TRADE_HISTORY.md`**](../sources/tjstocks/TRADE_HISTORY.md) | 2025-05-12 to 2026-11-03 | 13 BUY, 3 SELL, 1 TRIM |
| **Cluseau** | **149 trades** | [**`sources/cluseau/TRADE_HISTORY.md`**](../sources/cluseau/TRADE_HISTORY.md) | 2024-11-20 to 2026-11-04 | 59 BUY, 52 ADD, 19 SELL, 19 TRIM |

---

## Trade History Overview by Source

### 1. [Beating The Tide Trade History](../sources/beatingthetide/TRADE_HISTORY.md)
- **Source of Truth**: Extracted directly from 48 Datawrapper CSV tables embedded across weekly posts, plus rating changes (`HOLD to BUY`, `BUY to HOLD`, `SELL`).
- **Raw Data Files**:
  - Structured CSV: [`sources/beatingthetide/data/trade_events.csv`](../sources/beatingthetide/data/trade_events.csv)
  - Portfolio Holdings: [`sources/beatingthetide/data/portfolio_holdings.csv`](../sources/beatingthetide/data/portfolio_holdings.csv)

### 2. [TJ Stocks Trade History](../sources/tjstocks/TRADE_HISTORY.md)
- **Source of Truth**: Extracted from the model **StockTok ETF** launch (`only-10-stocks-made-the-cut` on 2026-01-14), the ETF 2.0 rebalance (`stocktok-etf-20` on 2026-07-28), and the performance updates (`stocktok-etf-doubles-the-s-and-p` on 2026-11-03).
- **Raw Data Files**:
  - Structured CSV: [`sources/tjstocks/data/trade_events.csv`](../sources/tjstocks/data/trade_events.csv)
  - Portfolio Holdings: [`sources/tjstocks/data/portfolio_holdings.csv`](../sources/tjstocks/data/portfolio_holdings.csv)

### 3. [Cluseau Trade History](../sources/cluseau/TRADE_HISTORY.md)
- **Source of Truth**: Extracted from quarterly portfolio reviews (`september-2026-portfolio-review`, `june-2026-portfolio-review`, `april-2026-portfolio-review`, `march-2026-trade-review`), standalone research publications (`boring-is-beautiful`, `opening-the-gates`, `go-stub-yourself`, `buying-the-buyback`), and **404 live subscriber chat threads** (`sources/cluseau/chat/chat_threads.json`).
- **Raw Data Files**:
  - Structured CSV: [`sources/cluseau/data/trade_events.csv`](../sources/cluseau/data/trade_events.csv) (149 trades)
  - Baseline Holdings: [`sources/cluseau/data/portfolio_holdings.csv`](../sources/cluseau/data/portfolio_holdings.csv) (59 baseline positions)
  - Coverage Report: [`sources/cluseau/data/results/coverage_report.json`](../sources/cluseau/data/results/coverage_report.json)
  - Chat Archive: [`sources/cluseau/chat/chat_threads.json`](../sources/cluseau/chat/chat_threads.json)

---

## CLI Command to View Trades

You can also view the trade log directly in your terminal at any time:

```powershell
# View trades for a specific publication
uv run btt --source tjstocks trades
uv run btt --source cluseau trades
uv run btt --source beatingthetide trades

# Or view the most recent N trades
uv run btt --source all trades --limit 20
```
