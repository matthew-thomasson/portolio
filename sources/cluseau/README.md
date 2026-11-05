# Cluseau — Source Archive & Strategy Profile

- **URL**: `https://www.cluseau.com/`
- **Methodology**: Event-Driven, Distressed Equities, Global Deep Value, Options Collars & Real-Time Subscriber Chat Alerts.
- **Data Extracted**:
  - `api_posts/`: 52 full post JSONs unlocked with `connect.sid`.
  - `chat/chat_threads.json`: **404 live subscriber chat threads** fetched via authenticated Substack Chat REST API (`/api/v1/chat/channels/.../posts`).
  - `data/trade_events.csv`: 29 chronological trade events from quarterly reviews and real-time chat notices (`KIOXIA`, `GDDY`, `WYFI`, `HRTG`, `OPY`, `IFOS`, `402340.KS`, `CBL`, `POWL`, `EVC`, etc.).
- **2026 Performance (Start: Jan 01, 2026)**:
  - **Strategy A (Seed Active + Follow)**: **+$3,805.01** Net Profit | **+33.09% ROI** | **+40.63% XIRR** (vs SPY +15.84%).
  - **Strategy B (Fresh 2026 Trades & Exits)**: **+$4,214.42** Net Profit | **+42.14% ROI** | **+52.16% XIRR** (vs SPY +15.85%).
- **Risk Characteristics**:
  - Outstanding win rate on curated exits (**84.6% to 91.7%**).
  - Outlier winners: `EVC` (+175.0%), `POWL` (+136.0% options), `CBL` (+50.1% in 2026 / +114% total).
  - Speculative downside tail risk on microcaps: `WYFI` down **-45.6%**.
  - **Highest operational complexity**: Requires monitoring intraday chat alerts and managing multi-leg options collars (`MU`, `WDC`, `GOOGL`, `IESC`, `FIX`).
