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
| **Beating The Tide** | **Strategy A** | $17,929.76 | +$2,949.16 | **+16.45%** | **+23.23%** | +10.12% | **+13.11%** |
| | **Strategy B** | $8,500.00 | +$644.00 | **+7.58%** | **+15.83%** | +7.44% | **+8.39%** |
| **TJ Stocks** | **Strategy A** | $12,000.00 | +$2,519.43 | **+21.00%** | **+30.13%** | +9.87% | **+20.25%** |
| | **Strategy B** | $12,000.00 | +$2,519.43 | **+21.00%** | **+30.13%** | +9.87% | **+20.25%** |
| **Cluseau** | **Strategy A** | $12,314.80 | +$4,679.90 | **+38.00%** | **+51.25%** | +11.07% | **+40.18%** |
| | **Strategy B** | $5,950.62 | +$1,962.49 | **+32.98%** | **+68.41%** | +8.21% | **+60.21%** |

---

## 2. Key Performance Observations

### Strategy A vs. Strategy B Sensitivity
- **Beating The Tide**: Severe penalty for entering late if missing pre-existing winners. While Strategy B achieved +7.58% ROI (+15.83% XIRR), nearly the entire dollar gain was concentrated in a single ticker (`DELL` +122.3%, +$1,834.25). Without `DELL`, Strategy B was heavily underwater (-$1,190.25). In contrast, Strategy A benefited from 2025 positions (`MU` +121.0%, `VEON` +44.5%).
- **TJ Stocks**: Zero difference between Strategy A and Strategy B. The model **StockTok ETF** was constructed from scratch on January 14, 2026, meaning an investor starting on Jan 1 faced no legacy bagholding risk or missing past run-ups. The ETF 2.0 rebalance on July 28 properly sold `SPB`, `MSCI`, and `FDX` while adding `CAKE`, `CNXN`, and `FELE`.
- **Cluseau**: Strategy A (+38.00% ROI / +51.25% XIRR) captured both active holdings open on Jan 1 and 2026 fresh ideas, driven by high-conviction exits (`EVC` +161.1%, `POWL` +68.4%, `CBL` +51.3%). Strategy B (+32.98% ROI / +68.41% XIRR) reflects fresh 2026 entries exclusively (including `SK Square 402340.KS` entered April 29 at +44.1% FX-adjusted return), delivering extraordinary capital efficiency.

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
- **Best 3**:
  1. `EVC` (Entravision Communications): **+161.1%** (+$1,610.95)
  2. `POWL` (Powell Industries): **+68.4%** stock gain (+$684.34) / author reported **+136.0%** via options
  3. `CBL` (CBL Properties): **+51.3%** 2026 gain (+$513.17) / author reported **+114.0%** total inception gain
- **Worst 3**:
  1. `VISN` (VSE Corporation): **-20.3%** (-$303.95)
  2. `MOMO` (Hello Group): **-21.2%** (-$212.50)
  3. `BMBL` (Bumble Inc): **+4.9%** (+$49.38) *(Lowest positive — only 2 positions suffered net losses)*
  *(Note: WYFI closed in October 2025 at +5.0% and was never held in 2026).*
