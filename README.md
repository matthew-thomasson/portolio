# Multi-Source Substack Downloader & Portfolio Backtester

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end investment research system that archives, parses, and backtests recommendations from multiple paid Substack stock pickers against the **S&P 500 (`SPY`)** under dollar-matched cash-flow conditions.

Currently supported publications:
1. **Beating The Tide** (`https://www.beatingthetide.com`) — Deep Fundamental Value, Special Situations & Cyclicals.
2. **TJ Stocks** (`https://tjstocks.substack.com`) — Macro Volatility Contraction Patterns (VCP) & Model Portfolio (**StockTok ETF**).
3. **Cluseau** (`https://www.cluseau.com`) — Event-Driven, Distressed Equities, Options Collars & Real-Time Subscriber Chat Alerts.

Data for each publication is kept completely segregated under `sources/<name>/` (`archive/`, `api_posts/`, `datawrapper/`, `chat/`, and `data/`).

---

## 📑 In-Depth Research & Analysis Reports

All findings, quantitative risk metrics, and track-record reconciliations are permanently documented in the [`docs/`](docs/) directory:

| Report | Direct Link | Key Focus |
|---|---|---|
| 📊 **Performance Comparison** | [**`docs/PERFORMANCE_COMPARISON.md`**](docs/PERFORMANCE_COMPARISON.md) | Head-to-head backtest results (Jan 1, 2026 to present), Strategy A vs. Strategy B sensitivity, and top/bottom performers. |
| 🛡️ **Risk & Volatility Analysis** | [**`docs/RISK_ANALYSIS.md`**](docs/RISK_ANALYSIS.md) | Win rates, downside loss distributions, profit factors, single-stock concentration, and execution complexity. |
| 🔍 **Author Claims Reconciliation** | [**`docs/AUTHOR_RECONCILIATION.md`**](docs/AUTHOR_RECONCILIATION.md) | Line-by-line audit reconciling author-claimed returns (+23.59% YTD, 2.55x SPY, 11 closed trades) against market quotes. |
| 📁 **Documentation Index** | [**`docs/README.md`**](docs/README.md) | Central hub linking all research reports and source profiles. |

---

## 🏆 2026 Head-to-Head Performance Snapshot

*Backtested from January 01, 2026 to present under identical dollar-matched cash flows ($1,000 unit size):*

| Newsletter / Publication | Strategy A ROI | Strategy A XIRR | Strategy B ROI | Strategy B XIRR | Matched SPY XIRR | Win Rate | Worst Loss |
|---|---|---|---|---|---|---|---|
| **Beating The Tide** | **+23.18%** | **+32.12%** | **+15.78%** | **+34.26%** | +15.35% | 56.0% | `STRL` (-47.1%) |
| **TJ Stocks** | **+22.94%** | **+34.95%** | **+22.94%** | **+34.95%** | +15.00% | **84.6%** | `FELE` (-8.6%) |
| **Cluseau** | **+33.09%** | **+40.63%** | **+42.14%** | **+52.16%** | +15.84% | **84.6%** | `WYFI` (-45.6%) |

> **Strategy Definitions**:
> - **Strategy A**: Buy all existing active `BUY` recommendations at $T_0$ (Jan 1, 2026) + execute subsequent buys/adds/trims/sells.
> - **Strategy B**: Only execute fresh `BUY`/`ADD` signals initiated from $T_0$ onward.
> - **Matched SPY Benchmark**: An identical dollar cash flow invested into `SPY` on the exact dates trades are executed and liquidated on the same exit dates.

---

## ⚖️ Portfolio Risk Matrix Summary

| Risk Dimension | Beating The Tide | TJ Stocks (StockTok ETF) | Cluseau |
|---|---|---|---|
| **Win Rate** | 56.0% (Strat A) / 44.4% (Strat B) | **84.6%** (11 wins / 2 losses) | **84.6% – 91.7%** (Curated exits) |
| **Average Loss** | -16.1% to -23.3% | **-8.2%** (Very mild) | **-1.3%** (Closed) / -45.6% (Speculative tail) |
| **Worst Single Trade** | `STRL` (**-47.1%**), `SNEX` (**-31.6%**) | `FELE` (**-8.6%**), `TXT` (**-7.9%**) | `WYFI` (**-45.6%** open), `VISN` (**-20.0%**) |
| **Profit Factor** | 2.15 – 3.87 | **19.07** | 9.11 – 334.68 |
| **Top 3 Concentration** | 28.8% (Strat A) / **60.6%** (Strat B) | **28.8%** (Evenly distributed) | **High** (Focused themes) |
| **Execution Complexity** | Low (Weekly tables) | **Lowest** (Semi-annual rebalances) | **Highest** (Real-time chat alerts & options) |

---

## 📂 Project Organization & Directory Layout

```text
├── btt_sim/                   # Core Python Simulation Engine
│   ├── cli.py                 # Command-line interface (btt)
│   ├── config.py              # Multi-source environment settings
│   ├── downloader.py          # API scraper, Datawrapper redirect resolver & Chat archiver
│   ├── parser.py              # Source-specific trade event & holdings parser
│   ├── prices.py              # Multi-exchange yfinance price provider & local caching
│   └── simulator.py           # Cash-flow matching engine, irregular XIRR & mark-to-market
├── docs/                      # In-Depth Research & Reconciliations
│   ├── README.md              # Documentation navigation index
│   ├── PERFORMANCE_COMPARISON.md  # Detailed performance backtest results
│   ├── RISK_ANALYSIS.md       # Quantitative risk matrix & volatility study
│   └── AUTHOR_RECONCILIATION.md   # Line-by-line audit of author-claimed returns
├── sources/                   # Segregated Data Per Publication
│   ├── beatingthetide/        # 247 post JSONs, 48 Datawrapper CSVs, holdings, trade events
│   ├── tjstocks/              # 417 post JSONs, StockTok ETF holdings, trade events
│   └── cluseau/               # 52 post JSONs, 404 subscriber chat threads, trade events
├── tests/                     # Automated Test Suite (pytest)
│   └── test_simulator.py      # XIRR, parser, and strategy verification tests
├── .env.example               # Sanitized template for session cookies
├── pyproject.toml             # Python package dependencies & configuration (uv)
└── README.md                  # Main project guide
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Environment Setup
Clone the repository and install dependencies using `uv` (or `pip`):
```powershell
git clone https://github.com/matthew-thomasson/portolio.git
cd portolio

# Copy environment template and fill in cookies
cp .env.example .env
```

### 2. Verify Session Cookies
```powershell
uv run btt --source all check-auth
```

### 3. Download Publication Data
```powershell
# Download all publications (or specify --source beatingthetide / tjstocks / cluseau)
uv run btt --source all download
```

### 4. Parse Recommendations into Trade Events
```powershell
uv run btt --source all parse
```

### 5. Run Simulations & Head-to-Head Comparison
```powershell
# Compare all 3 publications from Jan 1, 2026 side-by-side
uv run btt compare --start 2026-01-01

# Run detailed single-source simulation
uv run btt --source tjstocks simulate --start 2026-01-01
uv run btt --source cluseau simulate --start 2026-01-01
uv run btt --source beatingthetide simulate --start 2026-01-01
```

### 6. Run Test Suite
```powershell
uv run pytest
```
