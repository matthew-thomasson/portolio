# Material backtest findings and repair plan

**Status:** Open — implementation brief for the next coding agent  
**Scope:** Three Substack-derived strategies: Beating The Tide, TJ Stocks / StockTok ETF, and Cluseau.  
**Objective:** Reconstruct defensible, reproducible, point-in-time portfolio performance from the source material already archived here, fix errors that materially affect results, regenerate every dependent analysis, and commit/push the corrected outputs to GitHub.

## Non-negotiable principles

1. **Use evidence, not hindsight.** Each simulated BUY/ADD/TRIM/SELL needs a source document or chat message, its actual publication timestamp, effective trade date and confidence. Do not invent historical purchases to complete a later author's recap.
2. **Do not mistake a live Datawrapper table embedded in an old article for a historical snapshot.** Publication date, download date and the data's effective/as-of date are different concepts.
3. **Separate two legitimate questions:** (a) what a subscriber could actually have traded based on signals available at the time (strict, primary performance report), and (b) a reconstructed author's historic book (secondary, flagged estimates). Never silently combine them.
4. **Correct material distortions first.** Avoid generic rewrites, aesthetic refactoring, broad scraping changes, and speculative work on incomplete derivative details. Preserve existing raw downloads; derive clean events from them.
5. **Do not force a predetermined result.** Corrected returns may be higher or lower than existing reports. Report exclusions and unresolved source gaps rather than manufacturing precision.

## P0 — Incorrect or hindsight-biased trade chronology

### P0.1 Cluseau: synthetic January 2026 buys from future exit recaps

**Evidence**
- `btt_sim/parser.py` contains a Cluseau removal extractor that creates a BUY dated **2026-01-02** whenever a later portfolio review mentions an exit; it assigns high confidence and `:us:` by default.
- `sources/cluseau/data/trade_events.csv` consequently contains synthetic January purchases for SK Square (402340), EVC, CBL, POWL, AGM, HRTG, WSBF, etc., from the **2026-10-05** September review.
- `sources/cluseau/api_posts/2026-10-05__september-2026-portfolio-review.json` says **SK Square was first bought in late April 2026** and **EVC entered in March**. `sources/cluseau/api_posts/2026-06-12__june-2026-portfolio-review.json` describes existing CBL and POWL positions, a CBL reduction and options collars.
- Source archive also includes preceding 2025/2026 posts and `sources/cluseau/chat/chat_threads.json`. Review contemporaneous original posts/chat, not just retrospective summaries.

**Required repair**
- Remove the unconditional synthetic January BUY generation. Never treat the date of a later exit recap as evidence of an earlier exact purchase date or size.
- Extract true dated recommendations/position changes from contemporaneous posts and chats where supportable. If only a retrospective reference exists, preserve it as a historical claim with provenance, not a verified executable signal.
- Map instrument/exchange correctly: e.g., **402340.KS is Korean**, not US. Treat actual options-based exits/hedges as non-equivalent to unhedged stock trades.
- For strict subscriber backtests, include only signals available by the execution date; for reconstructed-book analysis, separately display inferred holdings, date uncertainty and coverage.

**Acceptance:** No synthetic 2026-01-02 Cluseau trade justified solely by a later exit; every included entry is traceable to evidence published no later than the trade date; unreconstructable positions are explicitly excluded or labelled.

### P0.2 TJ Stocks: two July 2026 ETF rebalance sales omitted

**Evidence**
- Original `sources/tjstocks/api_posts/2026-01-14__only-10-stocks-made-the-cut.json` unambiguously states the 10 equally weighted starting constituents.
- Original `sources/tjstocks/api_posts/2026-07-28__stocktok-etf-20.json` explicitly **removes SPB, MSCI and FDX** and **adds CAKE, CNXN and FELE** for ETF 2.0.
- `sources/tjstocks/data/trade_events.csv` records all three additions and **SPB SELL only**. Missing **MSCI SELL** and **FDX SELL**. This changes holdings, required capital, cash flows and returns.
- `sources/tjstocks/api_posts/2026-11-03__stocktok-etf-doubles-the-s-and-p.json` advises **VLO trim or cut**; a 50% trim is an implementation scenario, not an exact mandated quantity.

**Required repair**
- Parse and record all July constituents and deletions from the actual post; ensure ETF 1.0 and ETF 2.0 are coherent point-in-time baskets.
- Explicitly define two possible approaches if necessary: *follow the July rebalance* vs *retain original January positions where author acknowledges tax considerations*. Do not accidentally mix them.
- Label discretionary 2026-11-03 VLO `TRIM or CUT` as an assumption/scenario; do not portray 50% as an observed author fill.

**Acceptance:** Post-July rebalance-following scenario holds none of SPB/MSCI/FDX and contains the three additions, unless a later dated buy is evidenced; event ledger, invested cash, benchmark and positions reconcile.

### P0.3 Beating The Tide: dynamically updated tables and invented historical holdings

**Evidence**
- `sources/beatingthetide/datawrapper/2025-01-11__svif-usa-portfolio__IOJBk.csv` and `2025-11-29__global-portfolio-free__8zf5q.csv` contain investments/thesis links from **2026** (e.g., CSTM, DAR, SNEX). They are likely live Datawrapper contents downloaded after the posts were originally published, **not point-in-time holdings as of the filename dates**.
- `btt_sim/parser.py` defaults undated baseline holdings to **2024-01-02**, producing artificial old BUYs and overlapping portfolio positions.
- `sources/beatingthetide/datawrapper/2025-01-12__historical-performance__adNaZ.csv` has explicit Date of Pick, Status and Close Date. Examples: MU 30-Dec-2025, DELL 23-Feb-2026, SNEX 10-Jun-2026, CSTM 15-Jul-2026.
- `sources/beatingthetide/data/trade_events.csv` includes invalid market strings such as `$42.92` from the **Market price** column. That is a parser column-selection issue, not evidence of bad source data.

**Required repair**
- Separate the continuously updated holdings tables (useful for *current* positions/weights) from historical dated performance tables and point-in-time article/alert data. Do not backdate current holdings.
- Prioritize dated pick/exit records and contemporaneous alerts. Correct column mapping and normalize market codes. Resolve duplicate snapshots by source and effective date without losing legitimate additional trades.
- Keep provenance and record unknown original entries as unknown, not 2024-01-02. Ensure historical entry/exit dates can be reconstructed without looking ahead.

**Acceptance:** No arbitrary baseline date for undated live holdings; no price strings in market fields; no false double-buy from two overlapping portfolio table snapshots; audit sample MU/DELL/SNEX/CSTM to exact dated sources.

## P1 — Correct performance accounting (material to the ranking)

### P1.1 SPY benchmark cash-flow and returns reconciliation

**Evidence:** `btt_sim/simulator.py`, particularly `fund_purchase`, `receive_sale`, benchmark shares/cash, and the separate calculation of net profit, ROI and XIRR. The implementation attempts dollar-matched comparison but matches sale *proceeds* to benchmark liquidation in a way that can desynchronise portfolio and benchmark exposures and withdrawals.

**Required repair**
- Define and document a consistent cash-flow convention for both investments and benchmark: external contributions/withdrawals, proceeds retained as cash vs distributed, internal reinvestment, and terminal value. **Reconcile both ledgers arithmetically on every event.**
- Show capital invested, realised/unrealised P&L, remaining cash, terminal value, ROI, time-weighted return (where reliable) and XIRR clearly. An annualized XIRR is **not** a YTD ROI and should not be subtracted from an unmatched statistic.
- Keep benchmark SPY on the identical dated external funding schedule with a defensible treatment of cash and sales. Compare like for like, and test outcomes with no sales, partial sales, full exits, reinvestment and withdrawals.

**Acceptance:** Cash conservation identities hold, no duplicated/vanished money, and hand-calculated miniature portfolios match implementation; benchmark results are reproducible and clearly labeled.

### P1.2 Market data and instrument assumptions that actually affect results

- Verify adjusted-price behavior for dividends and splits before changing it; do not assume dividends were omitted. Avoid double counting.
- Audit actual **non-USD instruments** used in results (market codes, exchange ticker, price currency, USD conversion on each trade/valuation date). Do not treat a KRW quote as USD. Fix material errors; document unresolved conversion issues.
- Options, collars, shorts: **do not fabricate premiums, contract sizes or fills**. If insufficient source data, exclude from strict replicable-stock ledger or model a transparently labelled stock-only proxy, distinct from author's option-enhanced claims.
- State a consistent trade fill convention (e.g., next tradable close after a published post, not the previous close) and evaluate obvious same-day/lookahead issues. State realistic assumptions for unavailable intraday alert timing, transaction costs and spreads; don't build an overcomplicated derivatives engine without evidence.

**Acceptance:** Price provenance, unit/currency and execution timing are testable; no stock-only gain is relabelled as option P&L; no unsupported claimed performance precision.

## P2 — Regenerate and synchronize analysis after fixes

Complete this **in the same repair workflow** rather than changing only the parser.

1. Inspect all source docs and trade event extraction logic, make a short source-to-event audit/coverage report and record key unresolved uncertainties. Prioritize *material* missing signals; avoid attempting to hand-parse every irrelevant article.
2. Write/extend regression tests covering: Cluseau retrospective BUY contamination; TJ three July removals and additions; BTT live Datawrapper backdating/duplication and malformed market; no-lookahead publication timestamps; benchmark cash-flow conservation; currency treatment for a material international holding.
3. Rebuild normalized event datasets and holdings; rerun the existing CLI backtests for **all three publications**, both Strategy A and B as meaningful, from **2026-01-01** to the latest common observed market date. Clearly distinguish verified-signal results from reconstructed-author results. Preserve parameter settings and valuation as-of dates.
4. Recompute ALL dependent summaries and risk statistics: invested capital, net/realised/unrealised return, benchmark return/XIRR, win/loss counts, profit factor, concentration, largest gains/losses, and a meaningful drawdown measure where price history permits. **Do not carry forward old numerical claims** without verification.
5. Update `README.md`, `docs/PERFORMANCE_COMPARISON.md`, `docs/RISK_ANALYSIS.md`, `docs/AUTHOR_RECONCILIATION.md`, `docs/TRADE_HISTORY.md`, source-specific READMEs/trade histories and `data/results/` as applicable. Replace misleading absolutes such as "independently verified" where the evidence is partial. Fix any source links written as local `file:///C:/...` links when touching related docs.
6. Run full tests and consistency checks against source event files and report totals; disclose any missing market quotes or unmatched source trades, plus their likely impact on results.
7. **Commit and push all code, tests, derived data and updated documentation to this GitHub repository.** Prefer a focused branch/PR if available, otherwise coordinate with the repository's existing workflow. Verify the resulting remote commit and give a concise summary of corrected headline metrics, differences vs old results, tests, remaining material limitations and commit/PR URL.

## Definition of done

- The published ranking is reproducible from archived source evidence **without trades planted using future reviews**.
- Every material rebalance and exit that is explicit in the archived source is reflected in the right strategy.
- Cash flows/FX/price units/benchmark and return calculations reconcile.
- The three portfolio analyses and all headline numbers agree across README, reports and generated CSVs.
- Relevant tests pass; revised artefacts exist in the remote GitHub repo (not just the agent's working tree).
- Clearly state any uncertainty that cannot be repaired from the available downloads. Do not mask missing evidence with assumptions.

## Out of scope

Cosmetic cleanup, wholesale architecture rewrites, unrelated new data providers, attempting exact replication of option trades without sufficient fills, and unverified assertions about author performance. Repair the material correctness issues first.
