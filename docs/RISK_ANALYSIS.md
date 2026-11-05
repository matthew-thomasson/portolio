# Multi-Source Newsletter Risk & Volatility Analysis

This report evaluates the risk profiles of **Beating The Tide**, **TJ Stocks**, and **Cluseau** across five critical quantitative and operational dimensions:
1. Loss distribution & win rate
2. Downside skew & outlier risk
3. Concentration & single-stock exposure
4. Execution, instrument & operational complexity
5. Liquidity & exchange risk

---

## 1. Quantitative Risk Comparison Table

*Simulated from January 01, 2026 to November 04, 2026 under Fixed Unit allocation ($1,000 per BUY).*

| Metric | Beating The Tide (Strat A) | Beating The Tide (Strat B) | TJ Stocks (StockTok ETF) | Cluseau (Strat A) | Cluseau (Strat B) |
|---|---|---|---|---|---|
| **Win Rate (%)** | **56.0%** (14W / 11L) | **44.4%** (4W / 5L) | **84.6%** (11W / 2L) | **84.6%** (11W / 2L) | **91.7%** (11W / 1L) |
| **Average Win (%)** | +43.6% | +43.9% | +28.6% | +38.4% | +38.4% |
| **Average Loss (%)** | **-16.1%** | **-23.3%** | **-8.2%** | -23.4% | **-1.3%** |
| **Profit Factor** | 3.87 | 2.15 | **19.07** | 9.11 | **334.68** |
| **Worst Single Trade** | `STRL` (**-47.1%**) | `STRL` (**-47.1%**) | `FELE` (**-8.6%**) | `WYFI` (**-45.6%**) | `MOMO` (**-1.3%**) |
| **Second Worst Trade** | `SNEX` (**-31.6%**) | `SNEX` (**-31.6%**) | `TXT` (**-7.9%**) | `MOMO` (**-22.2%**) | N/A |
| **Third Worst Trade** | `PYPL` (**-28.3%**) | `CSTM` (**-22.1%**) | `HNI` (**-0.9%**) | `VISN` (**-20.0%**) | N/A |
| **Top 3 Open Concentration** | 28.8% | **60.6%** | **28.8%** | 100.0% (2 open) | 100.0% (1 open) |
| **Max Single Stock Weight** | 12.4% | **33.2%** | **11.2%** | 50.0% | 100.0% |

---

## 2. In-Depth Risk Assessment by Newsletter

### 1. TJ Stocks (StockTok ETF) — Rating: Low Risk / High Sharpe

- **Downside Protection (Grade: A+)**:
  - The single worst loss in the entire portfolio is `FELE` at just **-8.6%**, followed by `TXT` at **-7.9%**.
  - 11 out of 13 positions were profitable (84.6% win rate).
  - Profit Factor of **19.07** reflects that gross profits ($3,147) were almost 20 times larger than gross losses ($165).
- **Concentration Risk (Grade: A)**:
  - Strictly equal-weighted basket (approx. 8%–10% per ticker).
  - No single stock dominates portfolio value. The top 3 open holdings (`VLO`, `SPG`, `FDX`) represent just 28.8% of equity.
  - Sector exposure is balanced across 6 unrelated industries (Banking, Energy, Real Estate, Industrials, Consumer, Logistics).
- **Operational & Timing Risk (Grade: A+)**:
  - **Zero day-trading requirement**: Charts are analyzed on monthly timeframes using Volatility Contraction Patterns (VCP).
  - Rebalances occur semi-annually (e.g. Jan 14 launch $\rightarrow$ July 28 ETF 2.0 rebalance).
  - No options, no shorts, no foreign shares. Trades exclusively liquid NYSE/NASDAQ equities.

---

### 2. Beating The Tide — Rating: Moderate-to-High Risk / High Chasing Risk

- **Downside Protection (Grade: C+)**:
  - Win rate is close to a coin-flip on fresh 2026 trades (44.4%).
  - Suffers from severe single-stock drawdown outliers: `STRL` (**-47.1%**), `SNEX` (**-31.6%**), `PYPL` (**-28.3%**), `CSTM` (**-22.1%**).
  - Average loss on losing trades is steep (**-16.1% to -23.3%**).
- **Concentration Risk (Grade: C in Strategy B)**:
  - In Strategy B (fresh picks only), the portfolio held only 9 positions, resulting in extreme concentration: the top 3 open positions comprise **60.6% of portfolio equity**.
  - `DELL` alone represents **33.2% of open value**. If `DELL` had suffered an earnings miss similar to `STRL`, Strategy B would have ended deeply negative.
- **Timing & Chasing Risk (Grade: D)**:
  - High penalty for new subscribers entering late: Strategy B (+15.78% ROI) trailed Strategy A (+23.18% ROI) by over 7.4% because the biggest winners (`MU`, `CLS`, `PARR`, `RYAM`) were recommended prior to 2026.
  - Subscribers entering at $T_0$ took on the drawdown of late-stage cyclical picks without participating in the initial 2025 upside.

---

### 3. Cluseau — Rating: High Alpha / High Operational & Liquidity Risk

- **Downside Protection (Grade: B)**:
  - Outstanding win rate on curated closed positions (84.6% to 91.7%), driven by high-conviction exits (`CBL` +50% in 2026 / +114% total, `POWL` +136% via options, `EVC` +175%).
  - However, exhibits sharp speculative tail risk on experimental/microcap positions: `WYFI` is down **-45.6%** in open equity.
- **Instrument & Operational Risk (Grade: D)**:
  - **Highest execution burden**: Trade alerts, trims, and adjustments occur in real time via **Substack Subscriber Chat** (e.g., *"closing GoDaddy later today"*, *"bought OPY < 85"*).
  - Missing an intraday alert or entering after a gap-up substantially impacts realized returns.
  - Utilizes complex derivatives and short selling: options collars (`MU` 1,000–1,500 collar, `GOOGL` 325–390 collar), protective puts (`WDC` 350 puts, `IESC` 220 puts, `FIX` 1500 puts), and outright short positions (`Short ACIC`, `Short JPM`).
- **Liquidity & Multi-Exchange Risk (Grade: C)**:
  - Frequently trades international names that require a global broker: Korean equities (`SK Square 402340.KS`, `A Plus Asset Advisors 244920.KS`), Japanese equities (`Semitec 6626.T`, `Kioxia 285A.T`), and French equities (`ABC Arbitrage ABCA.PA`).

---

## 3. Investor Suitability Matrix

| Investor Profile | Recommended Publication | Primary Reason |
|---|---|---|
| **Passive / Busy Long-Term Investor** | **TJ Stocks** | Lowest drawdown, equal-weighted, monthly chart rules, no day-trading stress. |
| **Active Trader / Options Hedger** | **Cluseau** | Highest alpha, active options collars, catalyst/distressed event plays. |
| **Deep Value / Patient Cyclical Investor** | **Beating The Tide** | In-depth company research, but requires stomach for -30% to -47% drawdowns on individual picks. |
