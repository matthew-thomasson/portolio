# Multi-Source Portfolio Trade History Hub

This document provides quick access to the complete chronological trade histories extracted from each of the three investment Substack publications.

---

## Direct Links to Trade Logs

| Publication | Total Signals | Trade Log Link | Date Range | Primary Trade Actions |
|---|---|---|---|---|
| **Beating The Tide** | **85 trades** | [**`sources/beatingthetide/TRADE_HISTORY.md`**](file:///C:/Users/matt/substackdownloader/sources/beatingthetide/TRADE_HISTORY.md) | 2024-01-02 to 2026-11-02 | 52 BUY, 26 SELL, 4 TRIM, 2 ADD |
| **TJ Stocks** | **16 trades** | [**`sources/tjstocks/TRADE_HISTORY.md`**](file:///C:/Users/matt/substackdownloader/sources/tjstocks/TRADE_HISTORY.md) | 2025-05-12 to 2026-11-03 | 14 BUY, 1 SELL, 1 TRIM |
| **Cluseau** | **29 trades** | [**`sources/cluseau/TRADE_HISTORY.md`**](file:///C:/Users/matt/substackdownloader/sources/cluseau/TRADE_HISTORY.md) | 2025-10-01 to 2026-11-02 | 14 BUY, 14 SELL, 1 ADD |

---

## Trade History Overview by Source

### 1. [Beating The Tide Trade History](file:///C:/Users/matt/substackdownloader/sources/beatingthetide/TRADE_HISTORY.md)
- **Source of Truth**: Extracted directly from 48 Datawrapper CSV tables embedded across weekly posts, plus rating changes (`HOLD to BUY`, `BUY to HOLD`, `SELL`).
- **Raw Data Files**:
  - Structured CSV: [`sources/beatingthetide/data/trade_events.csv`](file:///C:/Users/matt/substackdownloader/sources/beatingthetide/data/trade_events.csv)
  - Portfolio Holdings: [`sources/beatingthetide/data/portfolio_holdings.csv`](file:///C:/Users/matt/substackdownloader/sources/beatingthetide/data/portfolio_holdings.csv)

### 2. [TJ Stocks Trade History](file:///C:/Users/matt/substackdownloader/sources/tjstocks/TRADE_HISTORY.md)
- **Source of Truth**: Extracted from the model **StockTok ETF** launch (`only-10-stocks-made-the-cut` on 2026-01-14), the ETF 2.0 rebalance (`stocktok-etf-20` on 2026-07-28), and the performance updates (`stocktok-etf-doubles-the-s-and-p` on 2026-11-03).
- **Raw Data Files**:
  - Structured CSV: [`sources/tjstocks/data/trade_events.csv`](file:///C:/Users/matt/substackdownloader/sources/tjstocks/data/trade_events.csv)
  - Portfolio Holdings: [`sources/tjstocks/data/portfolio_holdings.csv`](file:///C:/Users/matt/substackdownloader/sources/tjstocks/data/portfolio_holdings.csv)

### 3. [Cluseau Trade History](file:///C:/Users/matt/substackdownloader/sources/cluseau/TRADE_HISTORY.md)
- **Source of Truth**: Extracted from quarterly portfolio reviews (`september-2026-portfolio-review`, `april-2026-portfolio-review`) and **404 live subscriber chat threads** (`sources/cluseau/chat/chat_threads.json`).
- **Raw Data Files**:
  - Structured CSV: [`sources/cluseau/data/trade_events.csv`](file:///C:/Users/matt/substackdownloader/sources/cluseau/data/trade_events.csv)
  - Chat Archive: [`sources/cluseau/chat/chat_threads.json`](file:///C:/Users/matt/substackdownloader/sources/cluseau/chat/chat_threads.json)

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
