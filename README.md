# Multi-Source Substack Downloader & Portfolio Backtester

Downloads posts, images, attachments, and embedded portfolio tables for multiple investment Substack publications, parses recommendations, and backtests performance under identical cash-flow conditions against the **S&P 500 (`SPY`)**:

Supported publications:
1. **Beating The Tide** (`https://www.beatingthetide.com/`)
2. **Cluseau** (`https://www.cluseau.com/`)
3. **TJ Stocks** (`https://tjstocks.substack.com/`)

Data for each publication is kept completely segregated under `sources/<name>/` (`archive/`, `api_posts/`, `datawrapper/`, and `data/`).

---

## Documentation & In-Depth Reports

- [**Performance Comparison Report**](file:///C:/Users/matt/substackdownloader/docs/PERFORMANCE_COMPARISON.md): Detailed 2026 side-by-side performance, Strategy A vs Strategy B sensitivity, and top/bottom contributors.
- [**Risk & Volatility Analysis**](file:///C:/Users/matt/substackdownloader/docs/RISK_ANALYSIS.md): Comprehensive risk matrix, win rates, drawdown skew, single-stock concentration, and execution complexity.
- [**Author Claims Reconciliation**](file:///C:/Users/matt/substackdownloader/docs/AUTHOR_RECONCILIATION.md): Line-by-line audit reconciling author-claimed returns against market quotes and our backtester calculations.
- **Source-Specific Profiles**:
  - [Beating The Tide](file:///C:/Users/matt/substackdownloader/sources/beatingthetide/README.md)
  - [TJ Stocks (StockTok ETF)](file:///C:/Users/matt/substackdownloader/sources/tjstocks/README.md)
  - [Cluseau](file:///C:/Users/matt/substackdownloader/sources/cluseau/README.md)

---

## 2026 Performance Snapshot (Start Date: 2026-01-01)

| Publication | Strategy A ROI | Strategy A XIRR | Strategy B ROI | Strategy B XIRR | Matched SPY XIRR | Win Rate | Worst Loss |
|---|---|---|---|---|---|---|---|
| **Beating The Tide** | **+23.18%** | **+32.12%** | **+15.78%** | **+34.26%** | +15.35% | 56.0% | `STRL` (-47.1%) |
| **TJ Stocks** | **+22.94%** | **+34.95%** | **+22.94%** | **+34.95%** | +15.00% | **84.6%** | `FELE` (-8.6%) |
| **Cluseau** | **+33.09%** | **+40.63%** | **+42.14%** | **+52.16%** | +15.84% | **84.6%** | `WYFI` (-45.6%) |

---

## Quick Start Commands

```powershell
cd C:\Users\matt\substackdownloader

# 1. Verify session authentication for all publications
uv run btt --source all check-auth

# 2. Download a specific publication (or all)
uv run btt --source beatingthetide download
uv run btt --source cluseau download
uv run btt --source tjstocks download

# 3. Parse recommendations into holdings and trade events
uv run btt --source all parse

# 4. Compare all three publications side-by-side from Jan 1, 2026
uv run btt compare --start 2026-01-01

# 5. Run single source simulation
uv run btt --source beatingthetide simulate --start 2026-01-01
uv run btt --source cluseau simulate --start 2026-01-01
```
