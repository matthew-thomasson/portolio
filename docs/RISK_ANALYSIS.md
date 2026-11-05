# Multi-Source Newsletter Risk & Volatility Analysis

This report evaluates the risk profiles of **Beating The Tide**, **TJ Stocks**, and **Cluseau** across five critical quantitative and operational dimensions:
1. Loss distribution & win rate
2. Downside skew & outlier risk
3. Concentration & single-stock exposure
4. Execution, instrument & operational complexity
5. Liquidity & exchange risk

---

## 1. Quantitative Risk Comparison Table

*Simulated from January 01, 2026 to November 05, 2026 under Fixed Unit allocation ($1,000 per BUY).*

| Metric | Beating The Tide (Strat A) | Beating The Tide (Strat B) | TJ Stocks (StockTok ETF) | Cluseau (Strat A) | Cluseau (Strat B) |
|---|---|---|---|---|---|
| **Win Rate (%)** | **47.6%** (10W / 9L / 2F) | **33.3%** (3W / 5L / 1F) | **76.9%** (10W / 3L) | **87.5%** (14W / 2L) | **75.0%** (6W / 2L) |
| **Average Win (%)** | +42.7% | +45.9% | +27.3% | +36.8% | +42.1% |
| **Average Loss (%)** | **-21.5%** | **-26.9%** | **-7.1%** | -20.8% | -20.8% |
| **Profit Factor** | 2.53 | 1.48 | **12.82** | **10.06** | 4.80 |
| **Worst Single Trade** | `STRL` (**-53.3%**) | `STRL` (**-53.3%**) | `FELE` (**-10.1%**) | `MOMO` (**-21.2%**) | `MOMO` (**-21.2%**) |
| **Second Worst Trade** | `SNEX` (**-34.7%**) | `SNEX` (**-34.7%**) | `TXT` (**-9.3%**) | `VISN` (**-20.3%**) | `VISN` (**-20.3%**) |
| **Third Worst Trade** | `PYPL` (**-28.3%**) | `CSTM` (**-22.1%**) | `MSCI` (**-1.9%**) | N/A (14 profitable) | N/A (6 profitable) |
| **Top 3 Open Concentration** | 33.5% | **60.0%** | **34.8%** | 100.0% (1 open) | 0.0% (fully cash) |
| **Max Single Stock Weight** | 16.0% (`DELL`) | **36.5%** (`DELL`) | **11.7%** (`SPG`) | 100.0% (`OPY`) | N/A |

---

## 2. In-Depth Risk Assessment by Newsletter

### 1. TJ Stocks (StockTok ETF) — Rating: Low Risk / High Sharpe

- **Downside Protection (Grade: A+)**:
  - The single worst loss in the entire portfolio is `FELE` at just **-10.1%**, followed by `TXT` at **-9.3%**.
  - 10 out of 13 positions were profitable (76.9% win rate).
  - Profit Factor of **12.82** reflects that gross profits ($2,732.62) were nearly 13 times larger than gross losses ($213.19).
- **Concentration Risk (Grade: A)**:
  - Strictly equal-weighted basket (approx. 8%–10% per ticker).
  - No single stock dominates portfolio value. The top 3 open holdings (`SPG`, `PRU`, `UBSI`) represent 34.8% of equity.
  - Sector exposure is balanced across 6 unrelated industries (Banking, Energy, Real Estate, Industrials, Consumer, Logistics).
- **Operational & Timing Risk (Grade: A+)**:
  - **Zero day-trading requirement**: Charts are analyzed on monthly timeframes using Volatility Contraction Patterns (VCP).
  - Rebalances occur semi-annually (e.g. Jan 14 launch $\rightarrow$ July 28 ETF 2.0 rebalance, properly executing sales of `SPB`, `MSCI`, `FDX` alongside additions of `CAKE`, `CNXN`, `FELE`).
  - No options, no shorts, no foreign shares. Trades exclusively liquid NYSE/NASDAQ equities.

---

### 2. Beating The Tide — Rating: Moderate-to-High Risk / High Chasing Risk

- **Downside Protection (Grade: C)**:
  - Win rate is low on fresh 2026 trades (33.3% in Strategy B; 47.6% in Strategy A).
  - Suffers from severe single-stock drawdown outliers: `STRL` (**-53.3%**), `SNEX` (**-34.7%**), `PYPL` (**-28.3%**), `CSTM` (**-22.1%**).
  - Average loss on losing trades is steep (**-21.5% to -26.9%**).
- **Concentration Risk (Grade: C- in Strategy B)**:
  - In Strategy B (fresh picks only), the portfolio held only 9 positions, resulting in extreme concentration: the top 3 open positions comprise **60.0% of portfolio equity**.
  - `DELL` alone represents **36.5% of open equity value**. If `DELL` had suffered an earnings miss similar to `STRL`, Strategy B would have ended deeply negative.
- **Timing & Chasing Risk (Grade: D)**:
  - High penalty for new subscribers entering late: Strategy B (+7.58% ROI) trailed Strategy A (+16.45% ROI) significantly because the biggest winners (`MU`, `CLS`, `PARR`, `RYAM`) were recommended prior to 2026.
  - Subscribers entering at $T_0$ took on the drawdown of late-stage cyclical picks without participating in the initial 2025 upside.

---

### 3. Cluseau — Rating: High Alpha / High Operational & Liquidity Risk

- **Downside Protection (Grade: A-)**:
  - Exceptional win rate on curated closed positions (**87.5% in Strategy A, 75.0% in Strategy B**), driven by high-conviction exits (`CBL` +51.3% in 2026 / +114% total, `POWL` +68.4% / +136% via options, `EVC` +161.1%, `SK Square` +44.1%).
  - Controlled downside: only two losing closed trades in 2026 (`VISN` -20.3%, `MOMO` -21.2%).
  - *(Audit Note: WideOpenWest `WYFI` was closed in October 2025 at +5.0% and correctly excluded from the 2026 book).*
- **Instrument & Operational Risk (Grade: D)**:
  - **Highest execution burden**: Trade alerts, trims, and adjustments occur in real time via **Substack Subscriber Chat** (e.g., *"closing GoDaddy later today"*, *"bought OPY < 85"*).
  - Missing an intraday alert or entering after a gap-up substantially impacts realized returns.
  - Utilizes complex derivatives and short selling: options collars (`MU` 1,000–1,500 collar, `GOOGL` 325–390 collar), protective puts (`WDC` 350 puts, `IESC` 220 puts, `FIX` 1500 puts), and outright short positions (`Short ACIC`, `Short JPM`).
- **Liquidity & Multi-Exchange Risk (Grade: C)**:
  - Frequently trades international names that require a global broker and FX conversion: Korean equities (`SK Square 402340.KS`, `A Plus Asset Advisors 244920.KS`), Japanese equities (`Semitec 6626.T`, `Kioxia 285A.T`), and French equities (`ABC Arbitrage ABCA.PA`).

---

## 3. Investor Suitability Matrix

| Investor Profile | Recommended Publication | Primary Reason |
|---|---|---|
| **Passive / Busy Long-Term Investor** | **TJ Stocks** | Lowest drawdown, equal-weighted, monthly chart rules, no day-trading stress. |
| **Active Trader / Options Hedger** | **Cluseau** | Highest alpha, active options collars, catalyst/distressed event plays. |
| **Deep Value / Patient Cyclical Investor** | **Beating The Tide** | In-depth company research, but requires stomach for -30% to -53% drawdowns on individual picks. |
