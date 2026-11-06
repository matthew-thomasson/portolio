# TJ Stocks — Source Archive & Strategy Profile

- **URL**: `https://tjstocks.substack.com/`
- **Methodology**: Macro Volatility Contraction Pattern (VCP), Multi-Month Trend Following, Long-Term Model Portfolio (**StockTok ETF**).
- **Data Extracted**:
  - `api_posts/`: 417 full post JSONs unlocked with `substack.sid`.
  - `data/portfolio_holdings.csv`: 13 baseline holdings (`PRU`, `MTB`, `SPG`, `UBSI`, `TXT`, `HNI`, `SPB`, `FDX`, `MSCI`, `VLO`, `CAKE`, `CNXN`, `FELE`).
  - `data/trade_events.csv`: 17 trade events (13 BUY, 3 SELL, 1 TRIM) including the Jan 14 launch (10 BUYs), July 28 ETF 2.0 rebalance (sold `SPB`, `MSCI`, `FDX`; bought `CAKE`, `CNXN`, `FELE`), and Nov 3 `VLO` trim.
- **2026 Performance (Start: Jan 01, 2026)**:
  - **Strategy A & Strategy B**: **+$2,519.43** Net Profit | **+21.00% ROI** | **+30.13% XIRR** (vs SPY +9.87%, Alpha +20.26%).
  - Zero strategy divergence because the basket was newly assembled in mid-January 2026.
- **Risk Characteristics**:
  - **Win Rate**: **76.9%** (10 wins / 3 losses).
  - **Exceptionally shallow downside**: Worst single loss was `FELE` at **-10.1%**, followed by `TXT` at **-9.3%**, `MSCI` at **-1.9%**.
  - Profit Factor of **12.82**.
  - Equal-weighted across 6 uncorrelated sectors. Zero intraday timing risk.
