# Universal Analysis Validation & Point-in-Time Checkpoint Reconciliation Report

## Executive Summary

This report establishes the universal quality-control and checkpoint reconciliation framework across the portfolio research platform. Under this framework, **every standard analysis command (`simulate`, `compare`, `trades`, `sweep`) automatically executes independent source coverage checks and point-in-time portfolio reconciliations** before computing or displaying results.

Reconciliation is enforced using three complementary sources of truth:
1. **Original Investment Activity**: Primary Substack articles, subscriber chat threads, and trade alerts establishing executed transactions.
2. **Portfolio Updates & Published Holdings**: Independent monthly/quarterly reviews, model ETF constituent lists, and Datawrapper tables acting as immutable point-in-time checkpoints.
3. **Independent Market Data**: Local-currency historical prices, daily multi-currency foreign exchange rates, and exchange symbol mapping.

---

## 1. Universal Reconciliation Architecture

The platform executes a 10-stage bounded, deterministic reconciliation pipeline:

```
+---------------------------------------------------------------------------------------------------+
|                                  UNIVERSAL RECONCILIATION PIPELINE                                |
+---------------------------------------------------------------------------------------------------+
| 1. Download Guard:         Detects and rejects paywalled preview stubs (< 1,500 bytes or preview). |
| 2. Signal Extraction:      Multi-pattern regex extracts BUY/ADD/TRIM/SELL actions from sources.   |
| 3. Checkpoint Discovery:   Dynamically discovers reviews, constituent lists, and table updates.   |
| 4. Chronological Replay:   Replays verified transactions up to each checkpoint's as-of date.      |
| 5. Holdings Comparison:    Compares disclosed holdings vs. simulated open positions.              |
| 6. Discrepancy Detection:  Identifies missing holdings, unexpected holdings, and weight shifts.  |
| 7. Root-Cause Backtrack:   Follows evidence backwards into prior archives to locate missed events.|
| 8. Evidence Correction:    Applies verified trade events without synthetic backdating.            |
| 9. Downstream Replay:      Replays all affected subsequent checkpoints through the current date.  |
| 10. Audit Record Creation: Saves persistent machine-readable checkpoint_reconciliation.json.      |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Checkpoint Reconciliation: Cluseau

Cluseau operates across quarterly portfolio reviews, research articles, and 404 subscriber chat threads. The engine identified and reconciled **9 distinct checkpoints**:

| Checkpoint ID | As-Of Date | Source Slug | Checkpoint Type | Disclosed Holdings | Reconstructed Status | Key Findings & Discrepancy Investigations |
|---|---|---|---|---|---|---|
| `cluseau-01` | **2026-03-09** | `march-2026-trade-review` | `COMPLETE_SNAPSHOT` | `WDC`, `FIX`, `IESC`, `285A.T`, `CBL`, `POWL`, `EVC` | `RECONCILED_WITH_WARNINGS` | **Baseline & Options Overlay**: Identified `WDC` (Dec 350 puts), `FIX` (Nov 1500 puts), `IESC` (Nov 220 puts), and `285A.T` (Kioxia stub). Classified as pre-2026 baseline holdings with options collars. |
| `cluseau-02` | **2026-04-17** | `april-2026-portfolio-review` | `COMPLETE_SNAPSHOT` | `7089.T`, `9220.T`, `CCV.AX`, `CTT`, `HRTG`, `BMBL` (exit), `MCHB` (exit) | `FULLY_RECONCILED` | **International Small-Caps**: Reconciled Tokyo small-caps (`7089.T`, `9220.T`), ASX micro-cap (`CCV.AX`), Euronext postal stub (`CTT`), and confirmed exits of `BMBL` (+17.1%) and `MCHB` (+23.0%). |
| `cluseau-03` | **2026-04-29** | `opening-the-gates` | `PARTIAL_SNAPSHOT` | `402340.KS`, `139130.KS`, `013030.KQ` | `RECONCILED_WITH_WARNINGS` | **Korea Value Basket Inception**: Disclosed simultaneous initiation of SK Square (`402340.KS`), iM Financial (`139130.KS`), and Hy-Lok (`013030.KQ`). Reconciled against primary pitch. Silence on US holdings correctly treated as non-sale. |
| `cluseau-04` | **2026-05-11** | `boring-is-beautiful` | `TRANSACTION_UPDATE` | `453340.KS` | `FULLY_RECONCILED` | **Hyundai Green Food Purchase**: Author confirmed execution in 19,000s (19,200 KRW). Full body extracted after bypassing paywall caching defect. |
| `cluseau-05` | **2026-06-12** | `june-2026-portfolio-review` | `COMPLETE_SNAPSHOT` | `453340.KS` (-9%), `139130.KS` (-6%), `013030.KQ` (-25%), `CBL` (trim), `VISN` (add), `GMRS` (buy) | `FULLY_RECONCILED` | **Korea Progress & Trims**: Confirmed drawdowns for Korea basket, 1/3 trim on `CBL`, addition to `VISN`, and new position `GMRS`. Reconstructed portfolio matches author disclosure. |
| `cluseau-06` | **2026-09-15** | `september-2026-portfolio-review` | `TRANSACTION_UPDATE` | `CBL` (exit) | `FULLY_RECONCILED` | **CBL Final Exit**: Verified complete liquidation at $53.26 for +114% lifetime gain (+51.3% in 2026). |
| `cluseau-07` | **2026-10-05** | `september-2026-portfolio-review` | `COMPLETE_SNAPSHOT` | High: `453340.KS`; Medium: `139130.KS`; `GDDY`, `6626.T`; Exits: `EVC`, `POWL`, `VISN`, `MOMO`, `ASIC`, `402340.KS` | `RECONCILED_WITH_WARNINGS` | **Hy-Lok Disappearance Warning**: Author promoted Hyundai Green Food to High Conviction and iM Financial to Medium Conviction, but omitted Hy-Lok (`013030.KQ`) without an exit recap. Engine flagged as `UNEXPLAINED_DISAPPEARANCE` warning. |
| `cluseau-08` | **2026-10-14** | `chat#29` | `TRANSACTION_UPDATE` | `IFOS` (exit) | `FULLY_RECONCILED` | **IFOS Chat Exit Discovery**: Author explicitly stated: *"Closing out the IFOS position today for a 30% loss... 30% is max pain where I need to draw the line"*. Engine incorporated `SELL` trade on 2026-10-14, eliminating previous unclosed drag. |
| `cluseau-09` | **2026-10-30** | `chat#4` & `chat#5` | `TRANSACTION_UPDATE` | `GDDY` (exit), `285A.T` (exit) | `FULLY_RECONCILED` | **Final Chat Exits**: Confirmed closing remaining GoDaddy (`GDDY`) at $116 and Kioxia (`285A.T`) following earnings. Reconstructed book has zero unexpected open positions. |

---

## 3. Checkpoint Reconciliation: Beating The Tide

Beating The Tide communicates portfolio state via weekly/monthly publications featuring embedded Datawrapper tables. The engine identified **11 monthly complete portfolio snapshots**:

| Checkpoint ID | As-Of Date | Checkpoint Title | Checkpoint Type | Snapshot Properties | Status | Reconciled Holdings |
|---|---|---|---|---|---|---|
| `btt-01` | **2026-01-02** | January 2026 Portfolio Snapshot | `COMPLETE_SNAPSHOT` | Baseline table at $T_0$ | `FULLY_RECONCILED` | 13 Seeded positions (`CLS`, `ATI`, `BAC`, `CRDO`, `CSTM`, `DELL`, `MU`, `PARR`, `RYAM`, `VEON`, etc.) |
| `btt-02` | **2026-02-06** | February 2026 Portfolio Review | `COMPLETE_SNAPSHOT` | Monthly Datawrapper snapshot | `FULLY_RECONCILED` | All active holdings matched |
| `btt-03` | **2026-03-06** | March 2026 Portfolio Review | `COMPLETE_SNAPSHOT` | Monthly Datawrapper snapshot | `FULLY_RECONCILED` | All active holdings matched |
| `btt-04` | **2026-04-03** | April 2026 Portfolio Review | `COMPLETE_SNAPSHOT` | Monthly Datawrapper snapshot | `FULLY_RECONCILED` | All active holdings matched |
| `btt-05` | **2026-05-08** | May 2026 Portfolio Review | `COMPLETE_SNAPSHOT` | Monthly Datawrapper snapshot | `FULLY_RECONCILED` | All active holdings matched |
| `btt-06` | **2026-06-05** | June 2026 Portfolio Review | `COMPLETE_SNAPSHOT` | Monthly Datawrapper snapshot | `FULLY_RECONCILED` | All active holdings matched |
| `btt-07` | **2026-07-03** | July 2026 Portfolio Review | `COMPLETE_SNAPSHOT` | Monthly Datawrapper snapshot | `FULLY_RECONCILED` | All active holdings matched |
| `btt-08` | **2026-08-07** | August 2026 Portfolio Review | `COMPLETE_SNAPSHOT` | Monthly Datawrapper snapshot | `FULLY_RECONCILED` | Peak portfolio valuation snapshot (+47.7%) |
| `btt-09` | **2026-09-04** | September 2026 Portfolio Review | `COMPLETE_SNAPSHOT` | Monthly Datawrapper snapshot | `FULLY_RECONCILED` | Reflects cyclicals drawdown |
| `btt-10` | **2026-10-02** | October 2026 Portfolio Review | `COMPLETE_SNAPSHOT` | Monthly Datawrapper snapshot | `FULLY_RECONCILED` | Reconciled against rating adjustments |
| `btt-11` | **2026-11-02** | November 2026 Portfolio Review | `COMPLETE_SNAPSHOT` | Monthly Datawrapper snapshot | `FULLY_RECONCILED` | 100% matched against active ledger |

---

## 4. Checkpoint Reconciliation: TJ Stocks

TJ Stocks manages the rules-based model **StockTok ETF**. The engine identified **3 structural checkpoints**:

| Checkpoint ID | As-Of Date | Checkpoint Title | Checkpoint Type | Disclosed Actions | Status | Reconciled Holdings |
|---|---|---|---|---|---|---|
| `tjstocks-01` | **2026-01-14** | StockTok ETF Launch (Inception) | `COMPLETE_SNAPSHOT` | Initial 10 constituent equal-weighted basket | `FULLY_RECONCILED` | `PRU`, `MTB`, `SPG`, `UBSI`, `TXT`, `HNI`, `SPB`, `FDX`, `MSCI`, `VLO` (100% match) |
| `tjstocks-02` | **2026-07-28** | StockTok ETF 2.0 Rebalance | `COMPLETE_SNAPSHOT` | Sold 3 (`SPB`, `FDX`, `MSCI`); Bought 3 (`CAKE`, `CNXN`, `FELE`); Retained 7 | `FULLY_RECONCILED` | 10 active constituents + 3 closed trades verified with exact execution |
| `tjstocks-03` | **2026-11-03** | Performance Update & VLO Trim | `PARTIAL_SNAPSHOT` | Trimmed `VLO` after >28% gain; validated 2.99x SPY outperformance | `FULLY_RECONCILED` | Reconciled trim fraction and cash reinvestment |

---

## 5. Material Discrepancies Investigated & Resolved

Below is the definitive log of root-cause investigations, failure classifications, and corrective actions:

```
+-------------------------------------------------------------------------------------------------------------------------------+
| TICKER   | CHECKPOINT  | ROOT CAUSE CLASSIFICATION          | DISCLOSED VS. SIMULATED       | CORRECTIVE ACTION APPLIED       |
+-------------------------------------------------------------------------------------------------------------------------------+
| 453340   | 2026-05-11  | INCOMPLETE_DOWNLOAD_OR_PREVIEW     | Stated BUY in 19,000s;        | Ingested full post using paid   |
|          |             |                                    | missing from preview stub.    | session; added 2026-05-11 BUY.  |
+-------------------------------------------------------------------------------------------------------------------------------+
| 139130   | 2026-04-29  | UNSUPPORTED_LANGUAGE / CHAT SKIPPED| Stated BUY at 19,110 KRW;     | Added multi-pattern Korean      |
|          |             |                                    | ignored by manual trade list. | ticker regex; added BUY.        |
+-------------------------------------------------------------------------------------------------------------------------------+
| 013030   | 2026-04-29  | INCORRECT_TICKER_OR_EXCHANGE       | KOSDAQ suffix (.KQ) vs (.KS)  | Mapped 013030 to 013030.KQ;     |
|          |             |                                    | Yahoo Finance 404 delisted.   | added daily KRW FX conversion.  |
+-------------------------------------------------------------------------------------------------------------------------------+
| 013030   | 2026-10-05  | UNEXPLAINED_DISAPPEARANCE          | Disclosed down -25% in June;  | Raised WARNING flag in audit;   |
|          |             |                                    | silently omitted in Oct table.| preserved in ledger without     |
|          |             |                                    |                               | fabricating synthetic exit.     |
+-------------------------------------------------------------------------------------------------------------------------------+
| IFOS     | 2026-10-14  | UNRECORDED_EXIT_OR_TRIM            | Author exited at -30% in chat;| Discovered Chat Msg #29;        |
|          |             |                                    | remained open to -46.5% in sim| added SELL trade on 2026-10-14  |
|          |             |                                    |                               | at C$0.59 / stated -30% loss.   |
+-------------------------------------------------------------------------------------------------------------------------------+
| WDC, FIX,| 2026-03-09  | BASELINE_HOLDING_DOCUMENTED        | Held with protective put      | Logged as baseline holdings with|
| IESC, CTT|             |                                    | collars; lacked 2026 BUY.     | options overlay notes.          |
+-------------------------------------------------------------------------------------------------------------------------------+
```

---

## 6. Updated Recalculated Performance Summary

Following the incorporation of the `IFOS` October 14 chat exit at -30% (closing out the position rather than allowing it to drift to -46.5% on November 5), Cluseau's Strategy A net profit and alpha improved:

### Dollar-Matched Backtest Results (2026-01-01 to 2026-11-05)

| Publication | Strategy | Capital Invested ($) | Net Profit ($) | ROI (%) | Annualized XIRR (%) | Matched SPY XIRR (%) | Alpha vs SPY (%) | Status |
|---|---|---|---|---|---|---|---|---|
| **Beating The Tide** | **Strategy A** | $17,929.76 | +$2,949.16 | **+16.45%** | **+23.23%** | +10.12% | **+13.11%** | `FULLY_RECONCILED` |
| | **Strategy B** | $8,500.00 | +$644.00 | **+7.58%** | **+15.83%** | +7.44% | **+8.39%** | `FULLY_RECONCILED` |
| **TJ Stocks** | **Strategy A** | $12,000.00 | +$2,519.43 | **+21.00%** | **+30.13%** | +9.87% | **+20.25%** | `FULLY_RECONCILED` |
| | **Strategy B** | $12,000.00 | +$2,519.43 | **+21.00%** | **+30.13%** | +9.87% | **+20.25%** | `FULLY_RECONCILED` |
| **Cluseau (Audited)** | **Strategy A** | $21,314.80 | +$4,829.21 | **+22.66%** | **+33.12%** | +10.26% | **+22.86%** | `RECONCILED_WITH_WARNINGS` |
| | **Strategy B** | $11,950.62 | +$1,792.65 | **+15.00%** | **+29.74%** | +8.07% | **+21.67%** | `RECONCILED_WITH_WARNINGS` |

---

## 7. Automated Regression Suite Verification

The automated quality control framework is permanently enforced by **18 passing unit and regression tests** (`uv run pytest`):
- `test_korean_positions_discovered_from_source`: Verifies `013030.KQ`, `453340.KS`, and `139130.KS` discovery from authentic source text.
- `test_checkpoint_discovery_and_reconciliation_all_sources`: Asserts all 23 checkpoints across all 3 publications are discovered and validated.
- `test_ifos_chat_exit_and_unexpected_holding_detection`: Proves that explicitly closed positions that remain open in simulation trigger `UNEXPECTED_IN_SIMULATION` critical alerts.
- `test_partial_review_does_not_create_false_missing_sale_alerts`: Asserts partial snapshots do not misclassify unmentioned holdings as sales.
- `test_complete_snapshot_detects_unexplained_omissions`: Proves that complete review tables flag unrecapped omissions as `UNEXPLAINED_DISAPPEARANCE` warnings.
- `test_multi_currency_fx_and_instrument_types`: Verifies currency conversion and ticker suffixes.
- `test_no_hindsight_synthetic_trades`: Enforces point-in-time trade dates without lookahead bias.
