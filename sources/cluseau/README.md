# Cluseau — Source Archive & Strategy Profile

- **URL**: `https://www.cluseau.com/`
- **Methodology**: Event-Driven, Distressed Equities, Global Deep Value, Options Collars & Real-Time Subscriber Chat Alerts.
- **Data Extracted**:
  - `api_posts/`: 52 full post JSONs unlocked with `connect.sid` (resolved 20 paywall preview stubs).
  - `chat/chat_threads.json`: **404 live subscriber chat threads** fetched via authenticated Substack Chat REST API (`/api/v1/chat/channels/.../posts`).
  - `data/trade_events.csv`: **52 chronological trade events** (27 BUY, 18 SELL, 5 TRIM, 2 ADD) from quarterly reviews, research posts, and real-time chat notices (`402340.KS`, `453340.KS`, `139130.KS`, `013030.KQ`, `7089.T`, `9220.T`, `6626.T`, `CCV.AX`, `CBL`, `POWL`, `EVC`, `OPY`, `MOMO`, `VISN`, `IFOS`, etc.).
  - `data/portfolio_holdings.csv`: 12 baseline holdings (`9478.T`, `3600.HK`, `IFOS.V`, `IESC`, `FIX`, `WDC`, etc.).
  - `data/results/coverage_report.json`: Automated source-to-trade reconciliation report.
- **2026 Performance (Start: Jan 01, 2026, Fixed Unit)**:
  - **Strategy A (Seed Active + Follow)**: **+$4,829.21** Net Profit | **+22.66% ROI** | **+33.12% XIRR** (vs SPY +10.26%, Alpha **+22.86%**).
  - **Strategy B (Fresh 2026 Trades & Exits)**: **+$1,792.65** Net Profit | **+15.00% ROI** | **+29.74% XIRR** (vs SPY +8.07%, Alpha **+21.67%**).
- **Risk Characteristics**:
  - **Audited Win Rate**: **73.1%** (19 wins / 7 losses) in Strategy A; **60.0%** (9 wins / 6 losses) in Strategy B.
  - **Profit Factor**: **4.32** in Strategy A; **2.79** in Strategy B.
  - Outlier winners: `EVC` (+161.1%), `POWL` (+68.4% stock / +136.0% options), `CBL` (+51.3% in 2026 / +114% total), `SK Square 402340.KS` (+44.1% FX-adjusted).
  - Downside: `IFOS.V` (-30.0% closed in chat), `013030.KQ` (-26.3%), `MOMO` (-21.2%), `VISN` (-20.3%). *(WYFI was closed in Oct 2025 at +5.0% prior to 2026).*
  - **Multi-Currency FX Support**: Dynamically handles Korean Won (`013030.KQ`, `453340.KS`, `139130.KS`, `402340.KS`), Japanese Yen (`9478.T`, `7089.T`, `9220.T`, `6626.T`), Canadian Dollar (`IFOS.V`), and Australian Dollar (`CCV.AX`) converted daily to USD.
  - **Highest operational complexity**: Requires monitoring intraday chat alerts and managing multi-leg options collars (`MU`, `WDC`, `GOOGL`, `IESC`, `FIX`).
