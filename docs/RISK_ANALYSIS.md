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
| **Win Rate (%)** | **47.6%** (10W / 9L / 2F) | **33.3%** (3W / 5L / 1F) | **76.9%** (10W / 3L) | **73.1%** (19W / 7L) | **60.0%** (9W / 6L) |
| **Average Win (%)** | +42.7% | +45.9% | +27.3% | +39.2% | +34.5% |
| **Average Loss (%)** | **-21.5%** | **-26.9%** | **-7.1%** | -20.6% | -18.7% |
| **Profit Factor** | 2.53 | 1.48 | **12.82** | **4.22** | **2.79** |
| **Worst Single Trade** | `STRL` (**-53.3%**) | `STRL` (**-53.3%**) | `FELE` (**-10.1%**) | `IFOS.V` (**-46.5%**) | `013030.KQ` (**-26.3%**) |
| **Second Worst Trade** | `SNEX` (**-34.7%**) | `SNEX` (**-34.7%**) | `TXT` (**-9.3%**) | `013030.KQ` (**-26.3%**) | `MOMO` (**-21.2%**) |
| **Third Worst Trade** | `PYPL` (**-28.3%**) | `CSTM` (**-22.1%**) | `MSCI` (**-1.9%**) | `MOMO` (**-21.2%**) | `VISN` (**-20.3%**) |
| **Top 3 Open Concentration** | 33.5% | **60.0%** | **34.8%** | **28.5%** | 0.0% (fully cash) |
| **Max Single Stock Weight** | 16.0% (`DELL`) | **36.5%** (`DELL`) | **11.7%** (`SPG`) | **10.4%** (`OPY`) | N/A |

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

### 3. Cluseau — Rating: High Alpha / High Operational & Multi-Market Risk

- **Downside Protection (Grade: B+)**:
  - Following the complete reconciliation audit, Cluseau's win rate stands at **73.1% in Strategy A (19W / 7L)** and **60.0% in Strategy B (9W / 6L)**.
  - The previous un-audited 87.5% win rate was biased by omitting active drawdowns. Restoring the Korean Value Basket (`013030.KQ` -26.3%, `139130.KS` -12.1%, `453340.KS` -8.9%) and Canadian micro-cap `IFOS.V` (-46.5%) normalized the Profit Factor from 10.06 to **4.22 in Strategy A** and **2.79 in Strategy B**.
  - Despite the drawdowns, Cluseau generated extraordinary upside outliers: `EVC` (+161.1%), `POWL` (+68.4%), `CBL` (+51.3%), and `402340.KS` (+44.1%).
- **Instrument & Operational Risk (Grade: D)**:
  - **Highest execution burden**: Trade alerts, trims, and adjustments occur in real time via **Substack Subscriber Chat** (e.g., *"closing GoDaddy later today"*, *"bought OPY < 85"*).
  - Missing an intraday alert or entering after a gap-up substantially impacts realized returns.
  - Utilizes complex derivatives: protective put collars (`IESC` Nov 220 puts, `FIX` Nov 1500 puts, `WDC` Dec 350 puts, `GDDY` collar) and tactical short hedges (`SPY` intraday puts).
- **Liquidity & Multi-Exchange Risk (Grade: C)**:
  - Frequently trades international names that require a global broker and multi-currency FX execution: Korean equities (`SK Square 402340.KS`, `Hyundai Green Food 453340.KS`, `iM Financial 139130.KS`, `Hy-Lok 013030.KQ`), Japanese equities (`For Startups 7089.T`, `FB Care Services 9220.T`, `Semitec 6626.T`, `SE Holdings 9478.T`), Australian equities (`Cash Converters CCV.AX`), Hong Kong equities (`Modern Dental 3600.HK`), and Portuguese equities (`CTT.LS`).

---

## 3. Investor Suitability Matrix

| Investor Profile | Recommended Publication | Primary Reason |
|---|---|---|
| **Passive / Busy Long-Term Investor** | **TJ Stocks** | Lowest drawdown, equal-weighted, monthly chart rules, no day-trading stress. |
| **Active Trader / Options Hedger** | **Cluseau** | Highest alpha, active options collars, catalyst/distressed event plays. |
| **Deep Value / Patient Cyclical Investor** | **Beating The Tide** | In-depth company research, but requires stomach for -30% to -53% drawdowns on individual picks. |
