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
| **Beating The Tide** | **Strategy A** | $21,929.76 | +$5,084.26 | **+23.18%** | **+32.12%** | +15.35% | **+16.77%** |
| | **Strategy B** | $8,500.00 | +$1,341.38 | **+15.78%** | **+34.26%** | +14.81% | **+19.45%** |
| **TJ Stocks** | **Strategy A** | $13,000.00 | +$2,982.15 | **+22.94%** | **+34.95%** | +15.00% | **+19.95%** |
| | **Strategy B** | $13,000.00 | +$2,982.15 | **+22.94%** | **+34.95%** | +15.00% | **+19.95%** |
| **Cluseau** | **Strategy A** | $11,500.00 | +$3,805.01 | **+33.09%** | **+40.63%** | +15.84% | **+24.79%** |
| | **Strategy B** | $10,000.00 | +$4,214.42 | **+42.14%** | **+52.16%** | +15.85% | **+36.31%** |

---

## 2. Key Performance Observations

### Strategy A vs. Strategy B Sensitivity
- **Beating The Tide**: High penalty for entering late if missing pre-existing winners. While Strategy B achieved +15.78% ROI, over 80% of its dollar gain was concentrated in a single ticker (`DELL` +150.4%). Without `DELL`, Strategy B was negative. In contrast, Strategy A was stabilized by 2025 positions (`MU` +152.3%, `VEON` +49.9%).
- **TJ Stocks**: Zero difference between Strategy A and Strategy B. The model **StockTok ETF** was constructed from scratch on January 14, 2026, meaning an investor starting on Jan 1 faced no legacy bagholding risk or missing past run-ups.
- **Cluseau**: Strategy B (+42.14% ROI / +52.16% XIRR) outperformed Strategy A (+33.09% ROI / +40.63% XIRR) because older positions held at $T_0$ had smaller remaining upside or experienced pullbacks (`MOMO` -21%, `VISN` -20%), whereas fresh 2026 entries and options-leveraged exits (`EVC` +175%, `POWL` +136%) generated massive alpha.

---

## 3. Top and Bottom Contributors (2026)

### Beating The Tide
- **Best 3**:
  1. `MU` (Micron Technology): **+152.3%** (+$1,523)
  2. `DELL` (Dell Technologies): **+150.4%** (+$2,257)
  3. `VEON` (VEON Ltd): **+49.9%** (+$499)
- **Worst 3**:
  1. `STRL` (Sterling Infrastructure): **-47.1%** (-$471)
  2. `SNEX` (StoneX Group): **-31.6%** (-$316)
  3. `PYPL` (PayPal Holdings): **-28.3%** (-$283)

### TJ Stocks (StockTok ETF)
- **Best 3**:
  1. `VLO` (Valero Energy): **+104.8%** (+$1,049)
  2. `SPB` (Spectrum Brands Holdings): **+43.2%** (+$432)
  3. `FDX` (FedEx Corporation): **+31.9%** (+$319)
- **Worst 3**:
  1. `FELE` (Franklin Electric): **-8.6%** (-$86)
  2. `TXT` (Textron Inc): **-7.9%** (-$79)
  3. `HNI` (HNI Corporation): **-0.9%** (-$9)

### Cluseau
- **Best 3**:
  1. `EVC` (Entravision Communications): **+175.0%** (+$1,750)
  2. `POWL` (Powell Industries): **+68.4%** stock gain / **+136.0%** options (+$684 to +$1,360)
  3. `CBL` (CBL Properties): **+50.1%** 2026 gain / **+114.0%** total (+$501 to +$1,140)
- **Worst 3**:
  1. `WYFI` (White Fiber): **-45.6%** (-$456)
  2. `MOMO` (Hello Group): **-22.2%** (-$222)
  3. `VISN` (Vistance Networks): **-20.0%** (-$200)
