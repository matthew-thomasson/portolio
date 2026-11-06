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
| **Beating The Tide** | **Strategy A** | $30,188.49 | +$5,940.86 | **+19.68%** | **+29.24%** | +10.27% | **+18.97%** |
| | **Strategy B** | $13,753.99 | +$1,747.11 | **+12.70%** | **+32.99%** | +6.70% | **+26.29%** |
| **TJ Stocks** | **Strategy A** | $12,000.00 | +$2,519.43 | **+21.00%** | **+30.13%** | +9.87% | **+20.26%** |
| | **Strategy B** | $12,000.00 | +$2,519.43 | **+21.00%** | **+30.13%** | +9.87% | **+20.26%** |
| **Cluseau** | **Strategy A** | $61,256.89 | +$10,277.80 | **+16.78%** | **+24.75%** | +10.35% | **+14.39%** |
| | **Strategy B** | $37,405.79 | +$5,993.76 | **+16.02%** | **+27.90%** | +9.46% | **+18.44%** |

---

## 2. Key Performance Observations

### Strategy A vs. Strategy B Sensitivity
- **Beating The Tide**: Benefited strongly from pre-existing 2025 positions (`MU` +121.0%, `VEON` +44.5%) and `DELL` (+283.6%). Strategy A generated +20.78% ROI (+31.12% XIRR), while Strategy B achieved +13.53% ROI (+34.04% XIRR).
- **TJ Stocks**: Zero difference between Strategy A and Strategy B. The model **StockTok ETF** was constructed from scratch on January 14, 2026, meaning an investor starting on Jan 1 faced no legacy bagholding risk or missing past run-ups. The ETF 2.0 rebalance on July 28 properly sold `SPB`, `MSCI`, and `FDX` while adding `CAKE`, `CNXN`, and `FELE`.
- **Cluseau**:
  - In the un-audited baseline, Cluseau showed an apparent +38.00% Strategy A ROI because ~50% of trades were missing behind paywall stubs, omitting the entire Korean equity basket and ignoring foreign currency conversions.
  - After ingesting full articles and enabling FX conversion (commit `16a465f`), Strategy A stood at **+21.22% ROI (+30.35% XIRR)** with $60,139.92 invested and +$12,762.47 profit.
  - In targeted hardening (commit `0f07cf8`), isolating multi-security pricing (CUBI at 73 vs OPBK at 14) and eliminating the false NECB buy brought Strategy A to **+19.86% ROI (+28.60% XIRR)** with $57,639.92 invested and +$11,445.71 profit.
  - In the final accuracy pass (v3.6.0), removing unsupported transactions (SK Square May 1 future intention, SK Square May 6 advisory trim, Hynix March 25 market commentary, Hynix April 1 static holding statement) and attributing the June 3 allocation to BARAX instead of SE Holdings brought Strategy A to **+16.78% ROI (+24.75% XIRR)** with $61,256.89 invested, +$10,277.80 net profit, and **+14.39% Alpha** over the dollar-matched SPY benchmark (+10.35% SPY XIRR). Strategy B returned **+16.02% ROI (+27.90% XIRR)** with **+18.44% Alpha**.

### Attribution of Cluseau Strategy A Evolution (+21.22% -> +19.86% -> +16.78%)

| Milestone / Commit | Strategy A ROI | Strategy A XIRR | Capital Deployed | Net Profit | Primary Drivers |
|---|---|---|---|---|---|
| **Baseline (Pre-Repair)** | ~+38.00% | N/A | ~$25,000 | ~$9,500 | 20 of 38 articles were 200-word paywall previews; entire Korean basket and foreign exchange omitted. |
| **Full Ingestion (`16a465f`)** | **+21.22%** | +30.35% | $60,139.92 | $12,762.47 | Full post texts & chats ingested; multi-currency FX added; Korean basket & Frankfurt GDRs incorporated. Multi-security pricing collisions present. |
| **Multi-Security Hardening (`0f07cf8`)** | **+19.86%** | +28.60% | $57,639.92 | $11,445.71 | Disentangled CUBI ($73) and OPBK ($14); removed false NECB buy on chat 'monitoring'; removed duplicate Kioxia buy. (-1.36% ROI delta) |
| **Final Accuracy Pass (v3.6.0)** | **+16.78%** | +24.75% | $61,256.89 | $10,277.80 | Eliminated synthetic dip-buys (SK Square May 1, Hynix Mar 25/Apr 1), removed false advisory trim (SK Square May 6 which artificially locked in gains before a retrace), and re-attributed 9478.T false trigger to BARAX. (-3.08% ROI delta) |

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
