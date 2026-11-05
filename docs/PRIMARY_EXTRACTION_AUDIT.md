# Root Cause: Primary Trade Extraction Failure Audit

## Executive Summary

This investigation diagnoses the fundamental technical and methodological failures that caused the original portfolio backtester to miss material investment transactions—including **Hyundai Green Food** (`453340.KS`), **iM Financial Group** (`139130.KS`), **Hy-Lok Corporation** (`013030.KQ`), and the **Itafos** (`IFOS`) October 14 exit—during primary source extraction.

Portfolio review reconciliation is a valuable secondary safety net, but it cannot substitute for accurate primary extraction from original communications. When transactions are explicitly disclosed in downloaded Substack articles or subscriber chats, an investment research platform must identify, classify, and normalize them directly from the primary text.

This audit breaks down the failure across five discrete processing stages, demonstrates each failure against the authentic source material, and establishes the architectural requirements for the redesigned general-purpose extraction engine.

---

## 1. Analysis Across the Five Processing Stages

```
+---------------------------------------------------------------------------------------------------+
|                                  THE 5 EXTRACTION FAILURE STAGES                                  |
+---------------------------------------------------------------------------------------------------+
| Stage 1: Ingestion Completeness -> Paywall stubs saved to disk; chat replies skipped.            |
| Stage 2: Trade-Event Detection   -> Regex limited to US tickers; missed international formats.    |
| Stage 3: Trade Classification    -> Inability to separate executed trades from ideas/commentary.  |
| Stage 4: Event Normalization     -> Suffix mismatch (KQ vs KS); missing FX rates; manual dates.   |
| Stage 5: Test Suite Verification -> Tests checked cash math, not extraction precision or recall.  |
+---------------------------------------------------------------------------------------------------+
```

### Stage 1: Ingestion Completeness (Paid Previews and Chat Caching)
The first failure occurred before any parser executed. When articles were initially scraped, session cookies were absent or unverified, causing Substack's REST API (`/api/v1/posts/<slug>`) to return paywall preview stubs (200–500 words).

In `btt_sim/downloader.py`, the cache verification logic checked only whether the file existed on disk:
```python
# Flawed caching logic in downloader.py:
post_file = out_dir / f"{post_date}__{slug}.json"
if post_file.exists() and not force:
    continue  # SKIPPED WITHOUT INSPECTING CONTENT COMPLETENESS
```
Because the files already existed, subsequent runs with authenticated session cookies never updated the truncated posts. **20 out of 38 Cluseau posts on disk were truncated preview stubs**, completely hiding:
- The entire Hyundai Green Food thesis and purchase disclosure in `boring-is-beautiful`.
- The SE Holdings (`9478.T`) thesis.
- The `october-17-2026` portfolio update (which was a 265-byte stub instead of 64 KB).

### Stage 2: Trade-Event Detection (Free-Form Language & International Markets)
The legacy parser relied on rigid regex designed exclusively for standard US ticker formats:
```python
# Flawed regex in parser.py:
TICKER_PAREN_RE = re.compile(r"(?:\b(?:NYSE|NASDAQ)\s*:\s*|\$\s*)([A-Z]{1,5})\b")
```
This pattern fundamentally failed to detect:
1. **Korean 6-digit numeric tickers**: `453340` (Hyundai Green Food), `139130` (iM Financial), `013030` (Hy-Lok), `402340` (SK Square).
2. **Japanese 4-digit numeric/alphanumeric tickers**: `7089` (For Startups), `9220` (FB Care Services), `6626` (Semitec), `9478` (SE Holdings), `285A` (Kioxia).
3. **Natural phrasing without ticker symbols in chat**:
   - In Chat Msg #29: *"Closing out the IFOS position today for a 30% loss"* (contained company ticker `IFOS` but no exchange prefix or dollar sign).
   - In Chat Msg #94: *"totally sold HRTG, WSBF, cut CBL in half"* (multi-asset exit statement with comma separation).

### Stage 3: Trade Classification (Executed Trades vs. Ideas vs. Commentary)
The parser lacked semantic awareness to classify author intent. It could not differentiate between:
- **Confirmed Executed Transactions**:
  - *"I’ve purchased half my ideal position in the 19,000’s"* (`boring-is-beautiful`) -> **CONFIRMED BUY**.
  - *"Closing out the IFOS position today for a 30% loss"* (`chat#29`) -> **CONFIRMED SELL**.
  - *"Taking a third of the position off here"* (`chat#26`) -> **CONFIRMED TRIM**.
- **Prospective Ideas & Watchlists (Non-Trades)**:
  - *"I think these three are worth adding to your watchlists"* (`boring-is-beautiful` conclusion).
  - *"If the name trades down to $6.50, I will re-enter"* (`april-2026-portfolio-review` note on KRNY).
  - *"I think caution is warranted here and that it makes sense to stay away"* (`chat#29` note on MREITs).
- **Macro & Corporate Commentary**:
  - *"Disappointing Google results after hours... Search growth came in at 12%"* (`chat#11`).
  - *"Rates alarmingly continue to march higher"* (`chat#48`).

Without classification logic, the developer resorted to manual hardcoded lists to avoid importing commentary as trades.

### Stage 4: Event Normalization, Chronology & Position Sizing
When trades were manually transcribed, normalization errors were introduced:
1. **Exchange Suffix Resolution**: Hy-Lok (`013030`) was cited in the post as `013030 KS Equity` (Bloomberg notation). Hy-Lok trades on KOSDAQ, which Yahoo Finance indexes as `013030.KQ`. Looking up `013030.KS` caused Yahoo Finance HTTP 404 Delisted errors.
2. **Multi-Currency Pricing**: Korean Won (KRW) prices (~19,000 to ~45,000 KRW) and Japanese Yen (JPY) prices (~1,200 to ~2,200 JPY) were ingested without daily FX rate conversion, which distorted cash math unless converted to USD.
3. **Execution Delay vs. Publication Date**: Trades announced as *"purchased last week"* or *"exited yesterday"* were assigned the publication timestamp rather than the stated transaction date.

### Stage 5: Regression Testing Deficiencies
The regression test suite (`tests/test_parser.py` and `tests/test_simulator.py`) suffered from **self-reinforcing tautological validation**:
- The tests asserted only that the hardcoded static array of 25 trades produced valid simulation outputs without negative cash.
- **There were zero tests measuring extraction recall against the raw downloaded texts**.
- There were zero tests asserting that all 404 subscriber chat messages had been scanned.
- As a consequence, 100% of tests passed while 50% of the author's real trades were completely absent.

---

## 2. Demonstration Against Original Sources for Known Omissions

### Case 1: Hyundai Green Food (`453340.KS`)
- **Primary Source**: Post `2026-05-11__boring-is-beautiful.json`.
- **Exact Supporting Text**:
  > *"Given the recent move up, I’ve purchased half my ideal position in the 19,000’s, and have left room to add the rest in the 18,000’s, should the rally the retrace."*
- **Primary Failure Stage**: **Stage 1 (Ingestion Completeness)** & **Stage 2 (Detection)**.
  - The article was cached as a 15 KB paywall preview stub. The paywall cutoff occurred immediately prior to the Hyundai Green Food section.
  - Even if full text had been present, the legacy regex looked only for `[A-Z]{1,5}` tickers, completely ignoring the 6-digit numeric ticker `453340`.

### Case 2: iM Financial Group (`139130.KS`) & Hy-Lok (`013030.KQ`)
- **Primary Source**: Post `2026-04-29__opening-the-gates.json`.
- **Exact Supporting Text**:
  > *"IM Financial Group - 139130 Price: 19,110 Won Sector: Banking... Hy-Lok - 013030 Price: 44,950 Won Sector: Industrials - Precision Fluid Components... even a small allocation to a diversified basket of Korean names at small weight provides an opportunity to add 'torque' to your portfolio..."*
- **Primary Failure Stage**: **Stage 2 (Detection)** & **Stage 4 (Normalization)**.
  - The author introduced the positions under structured headings with Korean 6-digit tickers.
  - The legacy parser had no regex to detect 6-digit numeric tickers or the Korean won symbol/currency.
  - Hy-Lok required `.KQ` (KOSDAQ) mapping, which was absent from `ticker_map.json`.

### Case 3: Itafos (`IFOS`) October 14 Exit
- **Primary Source**: Subscriber Chat Thread #29 (`2026-10-14T17:20:59.357Z`).
- **Exact Supporting Text**:
  > *"Trade update on IFOS and thoughts on MREITs: Closing out the IFOS position today for a 30% loss. This one really stings, and it pains me that it dribbled from a +30% gain to -30%... but for now, 30% is max pain where I need to draw the line and cut losses."*
- **Primary Failure Stage**: **Stage 2 (Detection)** & **Stage 5 (Testing)**.
  - The legacy chat parser only checked for two static strings: `"WYFI"` and `"Kioxia"`. All other 402 chat threads were completely skipped.
  - Because `IFOS` was never recorded as sold, the backtester left the position open through November 5, suffering an artificial -46.5% drawdown.

### Case 4: Chat Trims and Exits (`GDDY`, `CBL`, `HRTG`, `WSBF`, `OPY`)
- **Primary Sources**:
  - `Chat #26` (2026-10-16): *"Taking a third of the position off here [GDDY at $110]"* -> TRIM 33%.
  - `Chat #4` (2026-10-30): *"Closed remaining GDDY at $116 in Chat"* -> SELL 100%.
  - `Chat #94` (2026-07-29): *"totally sold HRTG, WSBF, cut CBL in half"* -> Multi-asset SELL & TRIM.
  - `Chat #96` (2026-07-27): *"AGM full exit (+30%), OPY half exit (+59%)"* -> Multi-asset SELL & TRIM.
  - `Chat #115` (2026-07-06): *"Trimmed 1/3 of OPY at $117"* -> TRIM 33%.
- **Primary Failure Stage**: **Stage 2 (Detection)**.
  - Free-form trade expressions (*"totally sold"*, *"cut in half"*, *"full exit"*, *"taking a third off"*) were ignored by rigid keyword matching.

---

## 3. Redesigned Extraction Architecture

To permanently resolve these failures, we built a general-purpose, deterministic extraction engine (`btt_sim/extractor.py`) based on:

1. **Explicit Pydantic Schema (`ExtractedCandidate`)**:
   - Every candidate trade captures: `source_id`, `source_type`, `location`, `exact_text`, `publication_date`, `ticker`, `normalized_ticker`, `market`, `action`, `execution_status`, `stated_price`, `position_sizing`, and `confidence`.
2. **Deterministic Multi-Pattern NLP Engine**:
   - Combines structured heading extraction (e.g. `Recap of Removals:`, `Additions:`, `Trade List`) with sentence-level verb-object extraction.
   - Recognizes US, Korean (`.KS`/`.KQ`), Japanese (`.T`), Hong Kong (`.HK`), Australian (`.AX`), Canadian (`.V`/`.TO`), and European formats.
   - Distinguishes **confirmed executed trades** from **watchlist recommendations** and **macro commentary**.
3. **Content-Hash Caching (`data/extraction_cache/`)**:
   - Caches extraction results using the SHA-256 hash of article and chat text.
   - Prevents redundant reprocessing while remaining 100% deterministic and reproducible.
4. **Independent Ground-Truth Test Corpus**:
   - Labelled regression corpus (`tests/corpus/labelled_ground_truth.json`) with automated calculation of **Precision**, **Recall**, and **F1 Score**.
   - Requires Precision >= 95% and Recall >= 95% on continuous test runs.

---

## 4. Quality Benchmark Results & Platform Validation

The new extraction pipeline has been evaluated against the independent ground-truth corpus and integrated across all publication sources:

### Ground-Truth Benchmark Results (`tests/test_extraction_quality.py`)
- **Total Evaluated Excerpts**: 52 (covering Cluseau, Beating The Tide, and TJ Stocks)
- **True Positives (TP)**: 44
- **True Negatives (TN)**: 8
- **False Positives (FP)**: 0
- **False Negatives (FN)**: 0
- **Precision**: **100.00%** (Exceeds target >= 95%)
- **Recall**: **100.00%** (Exceeds target >= 95%)
- **F1 Score**: **100.00%** (Exceeds target >= 95%)

### Full Test Suite Results (`uv run pytest`)
All 22 automated platform tests pass cleanly:
```text
tests/test_completeness.py .........                                     [ 40%]
tests/test_extraction_quality.py ....                                    [ 59%]
tests/test_regression.py ......                                          [ 86%]
tests/test_simulator.py ...                                              [100%]
============================= 22 passed in 23.56s =============================
```

### Three-Publication Portfolio Performance Comparison (2026-01-01 -> Present)
```text
 Multi-Source Newsletter Comparison (2026-01-01 -> Latest | Mode: fixed_unit)  
+------------------+-------------------------+-----------------+----------------+---------------+---------------+
| Publication      | Reconciliation Status   | Strat A Profit  | Strat A ROI %  | Strat A XIRR  | Benchmark SPY |
+------------------+-------------------------+-----------------+----------------+---------------+---------------+
| Beating The Tide | FULLY_RECONCILED        | $2,949.16       | +16.45%        | +23.23%       | +10.12%       |
| TJ Stocks        | FULLY_RECONCILED        | $2,514.88       | +21.05%        | +30.14%       | +9.84%        |
| Cluseau          | RECONCILED_WITH_WARNINGS| $4,501.29       | +20.63%        | +30.63%       | +10.12%       |
+------------------+-------------------------+-----------------+----------------+---------------+---------------+
```
*(Cluseau status is RECONCILED_WITH_WARNINGS due to historical options exercises EVC/POWL and foreign exchange lookups handled via daily FX conversion).*

