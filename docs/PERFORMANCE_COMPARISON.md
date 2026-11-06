# Multi-Source Newsletter Performance Comparison (2026 YTD)

Comprehensive head-to-head backtest results for **Beating The Tide**, **TJ Stocks**, and **Cluseau** from **January 01, 2026** to current date.

---

## 1. Executive Performance Summary

All backtests use identical, dollar-matched cash-flow conditions:
- **Fixed Unit Allocation**: $1,000 per full `BUY` / $500 per `ADD` / 33% standard `TRIM`.
- **Strategy A**: Buy all existing active `BUY` recommendations at $T_0$ (Jan 1, 2026) + execute subsequent trades.
- **Strategy B**: Only execute fresh `BUY`/`ADD` signals initiated from $T_0$ onward.
- **Matched SPY Benchmark**: An identical dollar amount is invested into `SPY` on the exact dates trades are executed, liquidated on the same exit dates, and mark-to-market valued on the end date.

| Publication | Strategy | Capital Invested ($) | Net Profit ($) | ROI (%) | Annualized XIRR (%) | Matched SPY XIRR (%) | Alpha vs SPY (%) |
|---|---|---|---|---|---|---|---|
| **Beating The Tide** | **Strategy A** | $29,514.79 | +$6,132.44 | **+20.78%** | **+31.12%** | +10.20% | **+20.92%** |
| | **Strategy B** | $14,080.29 | +$1,905.64 | **+13.53%** | **+34.04%** | +7.40% | **+26.64%** |
| **TJ Stocks** | **Strategy A** | $12,000.00 | +$2,519.43 | **+21.00%** | **+30.13%** | +9.87% | **+20.26%** |
| | **Strategy B** | $12,000.00 | +$2,519.43 | **+21.00%** | **+30.13%** | +9.87% | **+20.26%** |
| **Cluseau** | **Strategy A** | $60,139.92 | +$12,762.47 | **+21.22%** | **+30.35%** | +11.12% | **+19.23%** |
| | **Strategy B** | $34,109.25 | +$6,306.32 | **+18.49%** | **+31.53%** | +10.63% | **+20.90%** |

---

## 2. Key Performance Observations

### Strategy A vs. Strategy B Sensitivity
- **Beating The Tide**: Benefited strongly from pre-existing 2025 positions (`MU` +121.0%, `VEON` +44.5%) and `DELL` (+283.6%). Strategy A generated +20.78% ROI (+31.12% XIRR), while Strategy B achieved +13.53% ROI (+34.04% XIRR).
- **TJ Stocks**: Zero difference between Strategy A and Strategy B. The model **StockTok ETF** was constructed from scratch on January 14, 2026, meaning an investor starting on Jan 1 faced no legacy bagholding risk or missing past run-ups. The ETF 2.0 rebalance on July 28 properly sold `SPB`, `MSCI`, and `FDX` while adding `CAKE`, `CNXN`, and `FELE`.
- **Cluseau**: In the original un-audited ledger, Cluseau showed an apparent +38.00% Strategy A ROI. Following the comprehensive completeness audit (which resolved 20 paywall stubs, added all international positions, Korean baskets, European GDRs, and Japanese deep value), Strategy A returned **+21.22% ROI (+30.35% XIRR)** and Strategy B returned **+18.49% ROI (+31.53% XIRR)**. Cluseau generated substantial alpha over the S&P 500 (+19.23% Strategy A Alpha / +20.90% Strategy B Alpha), driven by extraordinary realized exits (`285A.T` +184.6%, `EVC` +150.7%, `HY9H.F` +86.0%, `SMSD.IL` +32.9%, `SK Square` +18.5%).

---

## 3. Top and Bottom Contributors (2026)

### Beating The Tide
- **Best 3**:
  1. `DELL` (Dell Technologies): **+122.3%** (+$1,834.25)
  2. `MU` (Micron Technology): **+121.0%** (+$1,209.70)
  3. `VEON` (VEON Ltd): **+44.5%** (+$444.59)
- **Worst 3**:
  1. `STRL` (Sterling Infrastructure): **-53.3%** (-$533.38)
  2. `SNEX` (StoneX Group): **-34.7%** (-$346.71)
  3. `PYPL` (PayPal Holdings): **-28.3%** (-$282.77)

### TJ Stocks (StockTok ETF)
- **Best 3**:
  1. `VLO` (Valero Energy): **+103.1%** (+$1,031.09)
  2. `SPB` (Spectrum Brands Holdings): **+43.2%** (+$432.13)
  3. `SPG` (Simon Property Group): **+26.8%** (+$267.86)
- **Worst 3**:
  1. `FELE` (Franklin Electric): **-10.1%** (-$101.21)
  2. `TXT` (Textron Inc): **-9.3%** (-$93.46)
  3. `MSCI` (MSCI Inc): **-1.9%** (-$18.52)

### Cluseau
- **Best 4**:
  1. `EVC` (Entravision Communications): **+161.1%** (+$1,610.95)
  2. `POWL` (Powell Industries): **+68.4%** stock gain (+$684.34) / author reported **+136.0%** via options
  3. `CBL` (CBL Properties): **+51.3%** 2026 gain (+$513.17) / author reported **+114.0%** total inception gain
  4. `402340` (SK Square): **+44.1%** FX-adjusted (+$441.00)
- **Worst 4**:
  1. `IFOS` (I-Fox Bio): **-46.5%** (-$465.00)
  2. `013030` (Hy-Lok Corporation): **-26.3%** (-$263.00)
  3. `MOMO` (Hello Group): **-21.2%** (-$212.50)
  4. `VISN` (VSE Corporation): **-20.3%** (-$303.95)
  *(Note: WYFI closed in October 2025 at +5.0% and was never held in 2026).*
