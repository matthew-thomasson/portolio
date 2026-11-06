# Cluseau — Source Archive & Strategy Profile

- **URL**: `https://www.cluseau.com/`
- **Methodology**: Event-Driven, Distressed Equities, Global Deep Value, Options Collars & Real-Time Subscriber Chat Alerts.
- **Data Extracted**:
  - `api_posts/`: 52 full post JSONs unlocked with `connect.sid` (resolved 20 paywall preview stubs).
  - `chat/chat_threads.json`: **404 live subscriber chat threads** fetched via authenticated Substack Chat REST API (`/api/v1/chat/channels/.../posts`).
  - `data/trade_events.csv`: **149 chronological trade events** (59 BUY, 52 ADD, 19 SELL, 19 TRIM) from quarterly reviews, research posts, and real-time chat notices (`402340.KS`, `453340.KS`, `139130.KS`, `013030.KQ`, `244920.KS`, `7089.T`, `9220.T`, `6626.T`, `285A.T`, `CCV.AX`, `HY9H.F`, `SMSD.IL`, `CBL`, `POWL`, `EVC`, `OPY`, `MOMO`, `VISN`, `IFOS`, etc.).
  - `data/portfolio_holdings.csv`: 59 baseline holdings.
  - `data/results/coverage_report.json`: Automated source-to-trade reconciliation report.
- **2026 Performance (Start: Jan 01, 2026, Fixed Unit)**:
  - **Strategy A (Seed Active + Follow)**: **+$12,762.47** Net Profit | **+21.22% ROI** | **+30.35% XIRR** (vs SPY +11.12%, Alpha **+19.23%**).
  - **Strategy B (Fresh 2026 Trades & Exits)**: **+$6,306.32** Net Profit | **+18.49% ROI** | **+31.53% XIRR** (vs SPY +10.63%, Alpha **+20.90%**).
- **Risk Characteristics**:
  - **Audited Win Rate**: **56.1%** (32 wins / 25 losses) in Strategy A; **61.5%** (24 wins / 15 losses) in Strategy B.
  - **Profit Factor**: **3.89** in Strategy A; **3.12** in Strategy B.
  - Outlier winners: `EVC` (+161.1%), `POWL` (+68.4% stock / +136.0% options), `CBL` (+51.3% in 2026 / +114% total), `SK Square 402340.KS` (+44.1% FX-adjusted).
  - Downside: `IFOS.V` (-30.0% closed in chat), `013030.KQ` (-26.3%), `MOMO` (-21.2%), `VISN` (-20.3%). *(WYFI was closed in Oct 2025 at +5.0% prior to 2026).*
  - **Multi-Currency FX Support**: Dynamically handles Korean Won (`013030.KQ`, `453340.KS`, `139130.KS`, `402340.KS`), Japanese Yen (`9478.T`, `7089.T`, `9220.T`, `6626.T`), Canadian Dollar (`IFOS.V`), and Australian Dollar (`CCV.AX`) converted daily to USD.
  - **Highest operational complexity**: Requires monitoring intraday chat alerts and managing multi-leg options collars (`MU`, `WDC`, `GOOGL`, `IESC`, `FIX`).
