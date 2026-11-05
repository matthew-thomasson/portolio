# Cluseau — Source Archive & Strategy Profile

- **URL**: `https://www.cluseau.com/`
- **Methodology**: Event-Driven, Distressed Equities, Global Deep Value, Options Collars & Real-Time Subscriber Chat Alerts.
- **Data Extracted**:
  - `api_posts/`: 52 full post JSONs unlocked with `connect.sid`.
  - `chat/chat_threads.json`: **404 live subscriber chat threads** fetched via authenticated Substack Chat REST API (`/api/v1/chat/channels/.../posts`).
  - `data/trade_events.csv`: 41 chronological trade events (17 BUY, 17 SELL, 5 TRIM, 2 ADD) from quarterly reviews and real-time chat notices (`402340.KS`, `CBL`, `POWL`, `EVC`, `OPY`, `MOMO`, `VISN`, etc.).
- **2026 Performance (Start: Jan 01, 2026)**:
  - **Strategy A (Seed Active + Follow)**: **+$4,679.90** Net Profit | **+38.00% ROI** | **+51.25% XIRR** (vs SPY +11.07%, Alpha +40.18%).
  - **Strategy B (Fresh 2026 Trades & Exits)**: **+$1,962.49** Net Profit | **+32.98% ROI** | **+68.41% XIRR** (vs SPY +8.21%, Alpha +60.21%).
- **Risk Characteristics**:
  - **Exceptional Win Rate**: **87.5%** (14 wins / 2 losses) in Strategy A; **75.0%** (6 wins / 2 losses) in Strategy B.
  - **Profit Factor**: **10.06** in Strategy A; **4.80** in Strategy B.
  - Outlier winners: `EVC` (+161.1%), `POWL` (+68.4% stock / +136.0% options), `CBL` (+51.3% in 2026 / +114% total), `SK Square 402340.KS` (+44.1% FX-adjusted).
  - Downside: only 2 losing trades in 2026 (`MOMO` -21.2%, `VISN` -20.3%). *(WYFI was closed in Oct 2025 at +5.0% prior to 2026).*
  - **Multi-Currency FX Support**: Dynamically handles Korean Won (`402340.KS`), Japanese Yen (`6626.T`, `285A.T`), and Euro (`ABCA.PA`) converted daily to USD.
  - **Highest operational complexity**: Requires monitoring intraday chat alerts and managing multi-leg options collars (`MU`, `WDC`, `GOOGL`, `IESC`, `FIX`).
