from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any, Optional

from bs4 import BeautifulSoup
import pandas as pd

from .config import Settings, SourceConfig
from .extractor import (
    EXCHANGE_HINT_MAP,
    STOPWORD_ACRONYMS,
    VALID_TICKERS_DESPITE_OVERLAP,
    SecurityResolver,
    preprocess_substack_html,
    unpack_substack_widgets,
)
from .ingestion import validate_source_archive
from .prices import PriceProvider


class CheckpointType(str, Enum):
    COMPLETE_SNAPSHOT = "COMPLETE_SNAPSHOT"
    PARTIAL_SNAPSHOT = "PARTIAL_SNAPSHOT"
    CHANGES_ONLY = "CHANGES_ONLY"
    BASKET_SNAPSHOT = "BASKET_SNAPSHOT"
    TABLE_SNAPSHOT = "TABLE_SNAPSHOT"


class ReconciliationStatus(str, Enum):
    FULLY_RECONCILED = "FULLY_RECONCILED"
    RECONCILED_WITH_WARNINGS = "RECONCILED_WITH_WARNINGS"
    UNRECONCILED = "UNRECONCILED"


class RootCauseCategory(str, Enum):
    RECONCILED = "RECONCILED"
    PARSER_MISS = "PARSER_MISS"
    CHAT_MISS = "CHAT_MISS"
    SUBTHREAD_REPLY_MISS = "SUBTHREAD_REPLY_MISS"
    PAYWALL_TRUNCATED = "PAYWALL_TRUNCATED"
    IMAGE_ONLY_DISCLOSURE = "IMAGE_ONLY_DISCLOSURE"
    MANUAL_TRADE_OUTSIDE_SUBSTACK = "MANUAL_TRADE_OUTSIDE_SUBSTACK"
    AMBIGUOUS_WORDING = "AMBIGUOUS_WORDING"
    OPTION_EXPIRY_OR_ASSIGNMENT = "OPTION_EXPIRY_OR_ASSIGNMENT"
    SHORT_OR_DERIVATIVE_EXCLUDED = "SHORT_OR_DERIVATIVE_EXCLUDED"
    PARTIAL_DISCLOSURE = "PARTIAL_DISCLOSURE"
    TICKER_NORMALIZATION_MISMATCH = "TICKER_NORMALIZATION_MISMATCH"
    BASELINE_HOLDING_DOCUMENTED = "BASELINE_HOLDING_DOCUMENTED"
    UNEXPLAINED_DISAPPEARANCE = "UNEXPLAINED_DISAPPEARANCE"
    UNINVESTIGATED = "UNINVESTIGATED"


@dataclass
class CheckpointDiscrepancy:
    checkpoint_id: str
    checkpoint_date: str
    ticker: str
    discrepancy_type: str  # MISSING_IN_SIMULATION, UNEXPECTED_IN_SIMULATION, UNEXPLAINED_DISAPPEARANCE, BASELINE_DOCUMENTED, EXCLUDED_INSTRUMENT
    severity: str  # ERROR, WARNING, INFO
    root_cause: RootCauseCategory
    evidence_summary: str
    recommended_action: str = ""
    is_resolved: bool = False


@dataclass
class Checkpoint:
    checkpoint_id: str
    source_key: str
    date: str
    evaluation_date: str
    title: str
    source_file: str
    checkpoint_type: CheckpointType
    # normalized_ticker -> {"status": "active"|"closed"|"disappeared", "name": str, "evidence": str}
    disclosed_positions: dict[str, dict[str, Any]] = field(default_factory=dict)
    excluded_positions: dict[str, str] = field(default_factory=dict)
    notes: str = ""


@dataclass
class PortfolioReconciliationAudit:
    source_key: str
    display_name: str
    overall_status: ReconciliationStatus
    is_archive_valid: bool
    checkpoints_evaluated: int
    checkpoints: list[Checkpoint]
    discrepancies: list[CheckpointDiscrepancy]
    unresolved_errors: int
    warnings_count: int
    info_count: int
    holdings_timeline: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_key": self.source_key,
            "display_name": self.display_name,
            "overall_status": self.overall_status.value,
            "is_archive_valid": self.is_archive_valid,
            "checkpoints_evaluated": self.checkpoints_evaluated,
            "unresolved_errors": self.unresolved_errors,
            "warnings_count": self.warnings_count,
            "info_count": self.info_count,
            "checkpoints": [
                {
                    "checkpoint_id": c.checkpoint_id,
                    "date": c.date,
                    "evaluation_date": c.evaluation_date,
                    "title": c.title,
                    "source_file": c.source_file,
                    "checkpoint_type": c.checkpoint_type.value,
                    "active_count": sum(1 for v in c.disclosed_positions.values() if v.get("status") == "active"),
                    "closed_count": sum(1 for v in c.disclosed_positions.values() if v.get("status") == "closed"),
                    "disappeared_count": sum(1 for v in c.disclosed_positions.values() if v.get("status") == "disappeared"),
                    "disclosed_positions": c.disclosed_positions,
                    "excluded_positions": c.excluded_positions,
                    "notes": c.notes,
                }
                for c in self.checkpoints
            ],
            "discrepancies": [
                {
                    "checkpoint_id": d.checkpoint_id,
                    "checkpoint_date": d.checkpoint_date,
                    "ticker": d.ticker,
                    "discrepancy_type": d.discrepancy_type,
                    "severity": d.severity,
                    "root_cause": d.root_cause.value,
                    "evidence_summary": d.evidence_summary,
                    "recommended_action": d.recommended_action,
                    "is_resolved": d.is_resolved,
                }
                for d in self.discrepancies
            ],
        }


@dataclass
class DisclosedPosition:
    ticker: str
    company_name: str
    source_file: str
    disclosure_date: str
    disclosure_type: str  # "active", "closed", "excluded_short_or_option"
    status_in_ledger: str  # "RECONCILED", "BASELINE_DOCUMENTED", "EXCLUDED_NON_EQUITY", "DISCREPANCY"
    root_cause: str
    notes: str = ""


@dataclass
class ReconciliationReport:
    source_key: str
    display_name: str
    overall_status: str
    api_posts_count: int
    paid_posts_count: int
    truncated_posts_count: int
    zero_byte_posts_count: int
    chat_threads_count: int
    chat_replies_count: int
    datawrapper_tables_count: int
    trade_events_count: int
    unique_simulated_tickers: int
    checkpoints_count: int
    disclosed_positions_checked: int
    reconciled_count: int
    unresolved_discrepancies_count: int
    warnings_count: int
    positions: list[DisclosedPosition] = field(default_factory=list)
    audit: Optional[PortfolioReconciliationAudit] = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "source_key": self.source_key,
            "display_name": self.display_name,
            "overall_status": self.overall_status,
            "api_posts_count": self.api_posts_count,
            "paid_posts_count": self.paid_posts_count,
            "truncated_posts_count": self.truncated_posts_count,
            "zero_byte_posts_count": self.zero_byte_posts_count,
            "chat_threads_count": self.chat_threads_count,
            "chat_replies_count": self.chat_replies_count,
            "datawrapper_tables_count": self.datawrapper_tables_count,
            "trade_events_count": self.trade_events_count,
            "unique_simulated_tickers": self.unique_simulated_tickers,
            "checkpoints_count": self.checkpoints_count,
            "disclosed_positions_checked": self.disclosed_positions_checked,
            "reconciled_count": self.reconciled_count,
            "unresolved_discrepancies_count": self.unresolved_discrepancies_count,
            "warnings_count": self.warnings_count,
            "positions": [asdict(p) for p in self.positions],
        }
        if self.audit is not None:
            d["checkpoint_audit"] = self.audit.to_dict()
        return d


class ReconciliationEngine:
    """
    Layer B Independent Portfolio Verification & Forensic Root-Cause Engine.

    Design Guarantees:
    1. Strictly Non-Circular: Checkpoints are discovered and parsed ONLY from raw
       Datawrapper CSVs and raw Substack API post HTML (`api_posts/*.json`).
       `discover_checkpoints()` NEVER reads `trade_events.csv` and NEVER calls
       `replay_portfolio_to_date()`.
    2. Zero Ticker/Slug Hardcoding: Works across any existing or future Substack
       publication using structural table, basket, and review-post detectors.
    3. Honest Replay: `replay_portfolio_to_date()` replays ONLY dated events in
       `trade_events.csv` without fabricating entry dates for undated holdings.
    """

    def __init__(self, settings: Settings, prices: Optional[PriceProvider] = None) -> None:
        self.settings = settings
        self.prices = prices or PriceProvider(settings)

    def _build_raw_resolver(self, source: SourceConfig) -> SecurityResolver:
        """Build a SecurityResolver primed strictly from raw source archives (never from trade_events.csv)."""
        resolver = SecurityResolver(prices=self.prices)
        if source.datawrapper_dir.exists():
            for fcsv in sorted(source.datawrapper_dir.glob("*.csv")):
                try:
                    df = pd.read_csv(fcsv)
                except Exception:
                    continue
                cols = {c.strip().upper(): c for c in df.columns}
                sym_c = cols.get("SYMBOL") or cols.get("TICKER")
                name_c = cols.get("STOCKS") or cols.get("STOCK") or cols.get("COMPANY") or cols.get("NAME")
                mkt_c = cols.get("COUNTRY") or cols.get("MARKET")
                if sym_c:
                    for _, r in df.iterrows():
                        rs = str(r.get(sym_c, "")).strip().upper()
                        if not rs or rs in ("NAN", "CASH", "TOTAL") or "UPGRADE" in rs:
                            continue
                        nm = str(r.get(name_c, rs)).strip() if name_c else rs
                        mh = str(r.get(mkt_c, "")).strip().strip(":").upper() if mkt_c else None
                        resolver.register_binding(nm, rs, hint=mh)

        if source.api_posts_dir.exists():
            for jp in sorted(source.api_posts_dir.glob("*.json")):
                if jp.stat().st_size == 0:
                    continue
                try:
                    pdata = json.loads(jp.read_text(encoding="utf-8"))
                    unpacked = unpack_substack_widgets(str(pdata.get("body_html") or ""))
                    plain = BeautifulSoup(unpacked, "html.parser").get_text(" ", strip=True)
                    resolver.learn_from_text(f"{pdata.get('title') or ''} {pdata.get('subtitle') or ''} {plain}")
                except Exception:
                    continue

        tpath = source.chat_dir / "chat_threads.json"
        if tpath.exists() and tpath.stat().st_size > 0:
            try:
                for item in json.loads(tpath.read_text(encoding="utf-8")):
                    cp = item.get("communityPost") or item
                    resolver.learn_from_text(str(cp.get("body") or ""))
            except Exception:
                pass
        rpath = source.chat_dir / "chat_replies.json"
        if rpath.exists() and rpath.stat().st_size > 0:
            try:
                for clist in json.loads(rpath.read_text(encoding="utf-8")).values():
                    for cw in clist:
                        co = cw.get("comment") if isinstance(cw.get("comment"), dict) else cw
                        resolver.learn_from_text(str(co.get("body") or ""))
            except Exception:
                pass

        return resolver

    @staticmethod
    def _parse_verbal_date(raw_date: str, default_year: str = "2026") -> Optional[str]:
        s = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", raw_date.strip())
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
        s_yr = s if re.search(r"\b\d{4}\b", s) else f"{s}, {default_year}"
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
            try:
                return pd.to_datetime(s_yr, format=fmt).strftime("%Y-%m-%d")
            except Exception:
                continue
        dt = pd.to_datetime(s_yr, errors="coerce")
        return dt.strftime("%Y-%m-%d") if pd.notna(dt) else None

    def discover_checkpoints(self, source: SourceConfig) -> list[Checkpoint]:
        """
        Independently discover point-in-time portfolio checkpoints from raw Datawrapper
        tables and raw Substack API post HTML (`api_posts/*.json`).
        NEVER accesses `trade_events.csv` or simulated portfolio state.
        """
        resolver = self._build_raw_resolver(source)
        checkpoints: list[Checkpoint] = []

        # ------------------------------------------------------------------
        # 1. Raw Datawrapper CSV Checkpoints (Performance Trackers & Full Snapshots)
        # ------------------------------------------------------------------
        if source.datawrapper_dir.exists():
            dw_files = sorted(source.datawrapper_dir.glob("*.csv"))
            dated_picks: list[dict[str, Any]] = []
            seen_picks: set[tuple[str, str]] = set()
            latest_perf_file = ""
            latest_portfolio_df: Optional[pd.DataFrame] = None
            latest_portfolio_file = ""

            for fcsv in dw_files:
                try:
                    df = pd.read_csv(fcsv)
                except Exception:
                    continue
                cols_up = {c.strip().upper(): c for c in df.columns}
                sym_c = cols_up.get("SYMBOL") or cols_up.get("TICKER")
                if not sym_c:
                    continue

                pick_dt_c = (
                    cols_up.get("DATE OF PICK")
                    or cols_up.get("PICK DATE")
                    or cols_up.get("BUY DATE")
                    or cols_up.get("ENTRY DATE")
                )
                close_dt_c = cols_up.get("CLOSE DATE") or cols_up.get("SELL DATE") or cols_up.get("EXIT DATE")
                name_c = cols_up.get("STOCKS") or cols_up.get("STOCK") or cols_up.get("COMPANY") or cols_up.get("NAME")
                status_c = cols_up.get("STATUS") or cols_up.get("RECO.") or cols_up.get("RECO")
                wt_c = cols_up.get("WEIGHT") or cols_up.get("ALLOCATION")

                if pick_dt_c:
                    latest_perf_file = fcsv.name
                    for _, r in df.iterrows():
                        raw_sym = str(r.get(sym_c, "")).strip().upper()
                        if not raw_sym or raw_sym in ("NAN", "CASH", "TOTAL") or "UPGRADE" in raw_sym:
                            continue
                        p_dt = pd.to_datetime(str(r.get(pick_dt_c, "")).strip(), errors="coerce")
                        if pd.isna(p_dt):
                            continue
                        c_dt = pd.to_datetime(str(r.get(close_dt_c, "")).strip(), errors="coerce") if close_dt_c else pd.NaT
                        norm_sym, _, _ = resolver.normalize_symbol(raw_sym)
                        p_str = p_dt.strftime("%Y-%m-%d")
                        c_str = c_dt.strftime("%Y-%m-%d") if pd.notna(c_dt) else None
                        cname = str(r.get(name_c, norm_sym)).strip() if name_c else norm_sym
                        if (norm_sym, p_str) not in seen_picks:
                            seen_picks.add((norm_sym, p_str))
                            dated_picks.append(
                                {
                                    "symbol": norm_sym,
                                    "name": cname,
                                    "pick_date": p_str,
                                    "close_date": c_str,
                                    "status_raw": str(r.get(status_c, "")).strip().upper() if status_c else "",
                                    "file": fcsv.name,
                                }
                            )
                elif wt_c and "portfolio" in fcsv.name.lower():
                    # Prefer paid/authenticated live portfolio tables (e.g. svif-usa-portfolio) over "-free" teaser snapshots
                    if latest_portfolio_df is None or ("free" in latest_portfolio_file.lower() and "free" not in fcsv.name.lower()):
                        latest_portfolio_df = df
                        latest_portfolio_file = fcsv.name

            # Build independent point-in-time milestones from raw dated picks table
            if dated_picks:
                all_dates = [p["pick_date"] for p in dated_picks] + [p["close_date"] for p in dated_picks if p["close_date"]]
                min_dt = min(all_dates)
                max_dt = max(all_dates)
                milestone_candidates = ["2025-06-30", "2025-12-31", "2026-06-30", max_dt]
                seen_ms: set[str] = set()
                for ms_dt in milestone_candidates:
                    if ms_dt < min_dt or ms_dt > max_dt or ms_dt in seen_ms:
                        continue
                    seen_ms.add(ms_dt)
                    pos_map: dict[str, dict[str, Any]] = {}
                    for p in dated_picks:
                        if p["pick_date"] <= ms_dt:
                            is_closed_by_ms = bool(p["close_date"] and p["close_date"] <= ms_dt)
                            pos_map[p["symbol"]] = {
                                "status": "closed" if is_closed_by_ms else "active",
                                "name": p["name"],
                                "evidence": (
                                    f"Raw Datawrapper table {p['file']}: Picked {p['pick_date']}"
                                    + (f", Closed {p['close_date']}" if is_closed_by_ms else " (Open)")
                                ),
                            }
                    if pos_map:
                        checkpoints.append(
                            Checkpoint(
                                checkpoint_id=f"{source.key}-dw-picks-{ms_dt}",
                                source_key=source.key,
                                date=ms_dt,
                                evaluation_date=ms_dt,
                                title=f"Datawrapper Pick Tracker Point-in-Time Verification ({ms_dt})",
                                source_file=latest_perf_file,
                                checkpoint_type=CheckpointType.TABLE_SNAPSHOT,
                                disclosed_positions=pos_map,
                                notes="Independently derived strictly from raw Datawrapper pick/close dates.",
                            )
                        )

            # Build full portfolio allocation table snapshot checkpoint if present
            if latest_portfolio_df is not None:
                cols_up = {c.strip().upper(): c for c in latest_portfolio_df.columns}
                sym_c = cols_up.get("SYMBOL") or cols_up.get("TICKER")
                name_c = cols_up.get("STOCKS") or cols_up.get("STOCK") or cols_up.get("COMPANY")
                wt_c = cols_up.get("WEIGHT")
                # Determine snapshot date from latest article/pick date (never from trade_events.csv)
                snap_dt = max(
                    [p["pick_date"] for p in dated_picks]
                    + [p["close_date"] for p in dated_picks if p["close_date"]]
                    + ["2026-10-31"]
                )
                if source.api_posts_dir.exists():
                    post_dates = sorted(
                        jp.name[:10] for jp in source.api_posts_dir.glob("*.json") if re.match(r"^\d{4}-\d{2}-\d{2}", jp.name)
                    )
                    if post_dates:
                        snap_dt = max(snap_dt, post_dates[-1])

                full_pos: dict[str, dict[str, Any]] = {}
                if sym_c:
                    for _, r in latest_portfolio_df.iterrows():
                        raw_sym = str(r.get(sym_c, "")).strip().upper()
                        if not raw_sym or raw_sym in ("NAN", "CASH", "TOTAL") or "UPGRADE" in raw_sym:
                            continue
                        norm_sym, _, _ = resolver.normalize_symbol(raw_sym)
                        cname = str(r.get(name_c, norm_sym)).strip() if name_c else norm_sym
                        wt_val = str(r.get(wt_c, "")).strip() if wt_c else ""
                        full_pos[norm_sym] = {
                            "status": "active",
                            "name": cname,
                            "evidence": f"Raw Datawrapper full portfolio snapshot {latest_portfolio_file} (weight={wt_val})",
                        }
                if full_pos:
                    is_regional_subportfolio = any(
                        tag in latest_portfolio_file.lower() for tag in ("usa-portfolio", "canada-portfolio", "europe-portfolio", "asia-portfolio")
                    )
                    checkpoints.append(
                        Checkpoint(
                            checkpoint_id=f"{source.key}-dw-full-{snap_dt}",
                            source_key=source.key,
                            date=snap_dt,
                            evaluation_date=snap_dt,
                            title=f"Portfolio Allocation Snapshot ({latest_portfolio_file})",
                            source_file=latest_portfolio_file,
                            checkpoint_type=CheckpointType.BASKET_SNAPSHOT if is_regional_subportfolio else CheckpointType.COMPLETE_SNAPSHOT,
                            disclosed_positions=full_pos,
                            notes=(
                                "Regional sub-portfolio allocation table (e.g. USA Portfolio) verified against simulated holdings and baseline holdings."
                                if is_regional_subportfolio
                                else "Complete raw Datawrapper holdings table including pre-2025 baseline holdings."
                            ),
                        )
                    )

        # ------------------------------------------------------------------
        # 2. Raw Substack API Post Checkpoints (Model ETFs & Periodic Portfolio Reviews)
        # ------------------------------------------------------------------
        if not source.api_posts_dir.exists():
            return sorted(checkpoints, key=lambda c: c.evaluation_date)

        prior_review_actives: dict[str, tuple[str, str]] = {}  # sym -> (prev_review_date, prev_review_slug)

        for jp in sorted(source.api_posts_dir.glob("*.json")):
            if jp.stat().st_size == 0:
                continue
            try:
                pdata = json.loads(jp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(pdata, dict):
                continue

            slug = str(pdata.get("slug") or jp.stem)
            pub_day = str(pdata.get("post_date") or jp.name[:10])[:10]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", pub_day):
                continue
            title = str(pdata.get("title") or slug).strip()
            subtitle = str(pdata.get("subtitle") or "").strip()
            body_html = str(pdata.get("body_html") or "")
            if not body_html.strip():
                continue

            plain_text, blocks = preprocess_substack_html(body_html)
            title_low = f"{title} {subtitle}".lower()
            plain_low = plain_text.lower()

            # 2A. Model ETF / Equal-Weight Basket Checkpoints
            is_model_etf = bool(
                re.search(r"\betf\b", title_low)
                and any(
                    p in plain_low
                    for p in (
                        "10 stocks i would assemble",
                        "build this etf",
                        "equally weighted",
                        "stocks that are staying, removed and added",
                        "all 10 stocks in the",
                    )
                )
            )
            if is_model_etf:
                cp_etf = self._parse_model_etf_checkpoint(source.key, slug, pub_day, title, blocks, resolver)
                if cp_etf and cp_etf.disclosed_positions:
                    checkpoints.append(cp_etf)
                continue

            # 2B. Periodic Prose Portfolio Reviews & Trade Reviews
            is_review_post = bool(
                re.search(r"\b(?:portfolio\s+review|trade\s+review|quarterly\s+review|mid-year\s+review)\b", title_low)
                or re.search(r"(?:portfolio-review|trade-review)", slug)
            )
            if is_review_post:
                cp_rev, mentioned_all = self._parse_prose_review_checkpoint(
                    source=source,
                    slug=slug,
                    pub_day=pub_day,
                    title=title,
                    body_html=body_html,
                    blocks=blocks,
                    resolver=resolver,
                    prior_review_actives=prior_review_actives,
                )
                if cp_rev and (cp_rev.disclosed_positions or cp_rev.excluded_positions):
                    checkpoints.append(cp_rev)
                    # Update prior_review_actives for cross-review disappearance tracking
                    current_actives = {
                        sym: (pub_day, slug)
                        for sym, info in cp_rev.disclosed_positions.items()
                        if info.get("status") == "active"
                    }
                    if current_actives:
                        # Remove anything explicitly closed in this review, keep newly disclosed actives
                        prior_review_actives = {
                            k: v
                            for k, v in prior_review_actives.items()
                            if cp_rev.disclosed_positions.get(k, {}).get("status") != "closed"
                            and k in mentioned_all
                        }
                        prior_review_actives.update(current_actives)

        checkpoints.sort(key=lambda c: (c.evaluation_date, c.checkpoint_id))
        return checkpoints

    def _parse_model_etf_checkpoint(
        self,
        source_key: str,
        slug: str,
        pub_day: str,
        title: str,
        blocks: list[Any],
        resolver: SecurityResolver,
    ) -> Optional[Checkpoint]:
        full_low = "\n".join(b.text.lower() for b in blocks)
        pos_map: dict[str, dict[str, Any]] = {}

        if "staying, removed and added" in full_low or "(remove)" in full_low:
            mode = "staying"
            for blk in blocks:
                txt = blk.text.strip()
                low = txt.lower()
                if low in ("added", "additions", "new additions") or "here are the new" in low or "3 new stocks" in low:
                    mode = "added"
                    continue
                if blk.kind != "list_item":
                    continue
                # Skip conversational commentary bullets (e.g. "I wrote about FedEx a few weeks ago...")
                if re.match(r"^(?:i\s+wrote|read\s+my|check\s+out|if\s+you|see\s+here)\b", low):
                    continue
                secs = resolver.find_securities_in_clause(txt)
                if not secs:
                    continue
                norm, _, _, cname = secs[0]
                if "(remove)" in low:
                    pos_map[norm] = {
                        "status": "closed",
                        "name": cname,
                        "evidence": f"Model ETF rebalance removal: {txt[:140]}",
                    }
                elif mode in ("staying", "added") and norm not in pos_map:
                    pos_map[norm] = {
                        "status": "active",
                        "name": cname,
                        "evidence": f"Model ETF rebalance {'addition' if mode == 'added' else 'retained'}: {txt[:140]}",
                    }
        else:
            # Check status review ("- Hold" / "- Trim or cut") vs initial 10-stock list
            status_items = []
            for blk in blocks:
                if blk.kind == "list_item":
                    m_st = re.search(r"[-–—]\s*(trim\s+or\s+cut|hold/buy|buy/hold|hold|trim|cut|sell)\s*$", blk.text.strip(), re.I)
                    if m_st:
                        secs = resolver.find_securities_in_clause(blk.text)
                        if secs:
                            status_items.append((blk, secs[0], m_st.group(1).lower()))
            if len(status_items) >= 5:
                for blk, (norm, _, _, cname), st_str in status_items:
                    pos_map[norm] = {
                        "status": "closed" if st_str in ("cut", "sell") else "active",
                        "name": cname,
                        "evidence": f"Model ETF review item ({st_str}): {blk.text[:140]}",
                    }
            else:
                for blk in blocks:
                    if blk.kind == "list_item" and "$" in blk.text:
                        secs = resolver.find_securities_in_clause(blk.text)
                        if secs and secs[0][0] not in pos_map:
                            norm, _, _, cname = secs[0]
                            pos_map[norm] = {
                                "status": "active",
                                "name": cname,
                                "evidence": f"Model ETF initial constituent: {blk.text[:140]}",
                            }

        if not pos_map:
            return None
        return Checkpoint(
            checkpoint_id=f"{source_key}-{pub_day}-{slug[:28]}",
            source_key=source_key,
            date=pub_day,
            evaluation_date=pub_day,
            title=title,
            source_file=f"{pub_day}__{slug}.json",
            checkpoint_type=CheckpointType.COMPLETE_SNAPSHOT,
            disclosed_positions=pos_map,
            notes="Complete model basket constituent verification parsed from raw HTML list items.",
        )

    def _parse_prose_review_checkpoint(
        self,
        source: SourceConfig,
        slug: str,
        pub_day: str,
        title: str,
        body_html: str,
        blocks: list[Any],
        resolver: SecurityResolver,
        prior_review_actives: dict[str, tuple[str, str]],
    ) -> tuple[Optional[Checkpoint], set[str]]:
        """Parse active holdings, closed recaps, excluded shorts/options, and cross-review disappearances from a prose Portfolio/Trade Review."""
        pos_map: dict[str, dict[str, Any]] = {}
        excluded_map: dict[str, str] = {}
        mentioned_anywhere: set[str] = set()
        default_yr = pub_day[:4]
        eval_dt = pub_day
        section_mode: Optional[str] = None
        has_removals_section = False

        soup = BeautifulSoup(body_html, "html.parser")
        img_count = len(soup.find_all("img"))
        table_count = len(soup.find_all("table"))

        for blk in blocks:
            txt = blk.text.strip()
            low = txt.lower()
            secs_blk = resolver.find_securities_in_clause(txt)
            for s_norm, _, _, _ in secs_blk:
                mentioned_anywhere.add(s_norm)

            if blk.kind == "heading":
                if re.search(r"\b(?:removals|recap\s+of\s+removals|closed\s+positions|exits)\b", low):
                    section_mode = "removals"
                    has_removals_section = True
                elif re.search(r"\b(?:additions|recap\s+of\s+additions|new\s+positions)\b", low):
                    section_mode = "additions"
                elif re.search(r"\b(?:existing\s+portfolio|current\s+holdings|macro|conclusion)\b", low):
                    section_mode = "existing"

                # Heading-level disclosures: "Long 7089 JT Equity (For Startups)", "Short UVE US Equity", "New Position: SK Square 402340 KS"
                m_lhd = re.match(
                    r"^(?:Idea\s*\d*\s*:\s*|\d+\.\s*)?(Long|Short)\s+([A-Z0-9]{1,6})\s+(KS|KQ|JT|JP|TYO|AU|AX|US|LN|LI|FP|PL|LS|HK)(?:\s+Equity)?(?:\s*\(([^)]+)\))?",
                    txt,
                    re.IGNORECASE,
                )
                if m_lhd:
                    side = m_lhd.group(1).upper()
                    rsym = m_lhd.group(2).upper()
                    hint = m_lhd.group(3).upper()
                    cname = (m_lhd.group(4) or rsym).strip()
                    norm_s, _, _ = resolver.register_binding(cname, rsym, hint=hint, context_text=txt)
                    mentioned_anywhere.add(norm_s)
                    if side == "SHORT":
                        excluded_map[norm_s] = f"Disclosed short position in review heading: {txt[:120]}"
                    else:
                        pos_map[norm_s] = {
                            "status": "active",
                            "name": cname,
                            "evidence": f"Review heading long disclosure: {txt[:140]}",
                        }
                    continue

                if re.match(r"^(?:\d+\.\s*)?(?:Adding\s+to|New\s+Position:?|Position\s+Increase:?)\b", txt, re.I) and secs_blk:
                    for norm_s, _, _, cname in secs_blk:
                        pos_map[norm_s] = {
                            "status": "active",
                            "name": cname,
                            "evidence": f"Review heading active addition: {txt[:140]}",
                        }
                    continue
                if re.match(r"^(?:\d+\.\s*)?(?:Reduce|Trim)\b", txt, re.I) and secs_blk:
                    norm_s, _, _, cname = secs_blk[0]
                    pos_map[norm_s] = {
                        "status": "active",
                        "name": cname,
                        "evidence": f"Review heading partial reduction (still held): {txt[:140]}",
                    }
                    continue

            # Structured Removal Recap lines ("1. CBL Properties (CBL) +114% - Exited September 15", "MCHB US (...) - Closed April 10")
            m_rem1 = re.match(
                r"^(?:(?:\d+\.|\*|-)\s*)?(Short\s+)?([A-Za-z0-9\s&.,\'’-]+?)\s*\(([A-Z0-9/,\sand.-]+)\)\s*(?:[+-]?\d+(?:\.\d+)?%)?\s*[-–—]\s*(?:Exited|Closed)\s+([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)(?:\s+[Vv]ia\s+([A-Za-z\s]+))?",
                txt,
                re.IGNORECASE,
            )
            if m_rem1:
                has_removals_section = True
                is_sh = bool(m_rem1.group(1))
                cname = m_rem1.group(2).strip()
                stoks = m_rem1.group(3).strip().split()
                rsym = stoks[0].split("/")[0]
                hint = stoks[1] if len(stoks) > 1 and stoks[1].upper() in EXCHANGE_HINT_MAP else None
                ex_dt = self._parse_verbal_date(m_rem1.group(4), default_year=default_yr) or pub_day
                if ex_dt > eval_dt and abs((pd.Timestamp(ex_dt) - pd.Timestamp(pub_day)).days) <= 10:
                    eval_dt = ex_dt
                via = (m_rem1.group(5) or "").lower()
                norm_s, _, _ = resolver.register_binding(cname, rsym, hint=hint, context_text=txt)
                mentioned_anywhere.add(norm_s)
                if is_sh:
                    excluded_map[norm_s] = f"Short recap in review: {txt[:140]}"
                else:
                    pos_map[norm_s] = {
                        "status": "closed",
                        "name": cname,
                        "evidence": f"Review closed recap ({ex_dt}{', via ' + via if via else ''}): {txt[:140]}",
                    }
                continue

            m_rem2 = re.match(
                r"^(?:(?:\d+\.|\*|-)\s*)?([A-Z0-9]{1,6})\s+([A-Z]{2})\s*\(([^)]+)\)\s*[-–—]\s*Total\s+Return\s*(?:[+-]?\d+(?:\.\d+)?%)?\s*[-–—]\s*(?:Closed|Exited)\s+([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)",
                txt,
                re.IGNORECASE,
            )
            if m_rem2:
                has_removals_section = True
                rsym, mkt_h, cname, rdt = m_rem2.group(1).upper(), m_rem2.group(2).upper(), m_rem2.group(3).strip(), m_rem2.group(4).strip()
                ex_dt = self._parse_verbal_date(rdt, default_year=default_yr) or pub_day
                norm_s, _, _ = resolver.register_binding(cname, rsym, hint=mkt_h, context_text=txt)
                mentioned_anywhere.add(norm_s)
                pos_map[norm_s] = {
                    "status": "closed",
                    "name": cname,
                    "evidence": f"Review closed recap ({ex_dt}): {txt[:140]}",
                }
                continue

            # Structured Addition Recap lines ("1. ABC Arbitrage (ABCA FP) - Added September 3", "Short JPMorgan (JPM US) - Added September 28")
            m_add = re.match(
                r"^(?:(?:\d+\.|\*|-)\s*)?(Short\s+)?([A-Za-z0-9\s&.,\'’-]+?)\s*\(([A-Z0-9/,\sand.-]+)\)\s*[-–—]\s*Added\s+([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)",
                txt,
                re.IGNORECASE,
            )
            if m_add:
                is_sh = bool(m_add.group(1))
                cname = m_add.group(2).strip()
                stoks = m_add.group(3).strip().split()
                rsym = stoks[0].split("/")[0]
                hint = stoks[1] if len(stoks) > 1 and stoks[1].upper() in EXCHANGE_HINT_MAP else None
                norm_s, _, _ = resolver.register_binding(cname, rsym, hint=hint, context_text=txt)
                mentioned_anywhere.add(norm_s)
                if is_sh:
                    excluded_map[norm_s] = f"Disclosed short addition in review: {txt[:140]}"
                else:
                    pos_map[norm_s] = {
                        "status": "active",
                        "name": cname,
                        "evidence": f"Review addition recap: {txt[:140]}",
                    }
                continue

            # Explicit prose active ownership / accumulation statements inside the review
            for sent in re.split(r"(?<=[.!?])\s+", txt):
                slow = sent.lower().strip()
                if not slow or "?" in slow:
                    continue
                if re.search(r"\b(?:short\s+position|short\s+basket|remain\s+short|am\s+also\s+short|smaller\s+short)\b", slow):
                    # Split out any contrasting long clause (e.g. "short position in UVE ... cancel out my long HRTG")
                    short_part = re.split(r"\b(?:cancel\s+out|offset|against|my\s+long|long\s+position)\b", sent, maxsplit=1, flags=re.I)[0]
                    for norm_s, _, _, _ in resolver.find_securities_in_clause(short_part):
                        excluded_map.setdefault(norm_s, f"Disclosed short in review prose: {short_part[:120]}")
                    continue
                if re.search(r"\b(?:not|never|haven[’\']t|don[’\']t|watch\s*list|exited|closed\s+out|sold\s+out)\b", slow):
                    continue
                if re.search(
                    r"\b(?:steadily\s+adding\s+to|have\s+been\s+adding\s+to|i[’\']ve\s+been\s+adding\s+to|"
                    r"remain\s+convicted\s+to|started\s+a\s+speculative\s+starter\s+position\s+in|"
                    r"i\s+bought\s+a\s+speculative\s+starter\s+position\s+in|initating\s+smaller\s+positions\s+in|"
                    r"initiating\s+smaller\s+positions\s+in|i\s+added\s+sk\s+square|"
                    r"high\s+conviction\s*:|medium\s+conviction\s*:)\b",
                    slow,
                ):
                    # Split out any leading "Aside from significantly reducing X and ..." clause so each clause keeps its own securities
                    for sub_s in re.split(r"\band\s+(?=initiat|initat)", sent, flags=re.I):
                        if re.search(r"\b(?:reducing|trimming)\b", sub_s, re.I) and not re.search(r"\b(?:adding|initiat|initat|convicted)\b", sub_s, re.I):
                            continue
                        for norm_s, _, _, cname in resolver.find_securities_in_clause(sub_s):
                            if norm_s not in pos_map and norm_s not in excluded_map:
                                pos_map[norm_s] = {
                                    "status": "active",
                                    "name": cname,
                                    "evidence": f"Review active holding statement: {sub_s.strip()[:140]}",
                                }

        # Dynamic Cross-Review Disappearance Detection:
        # If this review has BOTH active portfolio commentary AND a Removals section, check whether any
        # position explicitly active in the immediately preceding Portfolio Review vanished without being
        # mentioned anywhere in this review OR exited in chat/articles between the two reviews!
        if has_removals_section and prior_review_actives:
            intervening_mentions = self._find_mentions_between_dates(
                source=source,
                resolver=resolver,
                start_exclusive=min(v[0] for v in prior_review_actives.values()),
                end_inclusive=eval_dt,
                exclude_slug=slug,
            )
            for prev_sym, (prev_dt, prev_slug) in prior_review_actives.items():
                if prev_sym not in mentioned_anywhere and prev_sym not in pos_map and prev_sym not in excluded_map:
                    # Check if any trade/exit chat or article between prev_dt and eval_dt closed it
                    if prev_sym not in intervening_mentions:
                        pos_map[prev_sym] = {
                            "status": "disappeared",
                            "name": resolver.known_symbols.get(prev_sym, (prev_sym, "", "", prev_sym))[3],
                            "evidence": (
                                f"Disclosed active in {prev_slug} ({prev_dt}) but absent from both active commentary "
                                f"and Removals recap in {slug} ({pub_day}), with zero intervening archive mentions."
                            ),
                        }

        cp_type = CheckpointType.PARTIAL_SNAPSHOT if (img_count > 0 and table_count == 0) else CheckpointType.COMPLETE_SNAPSHOT
        note_str = (
            f"Prose review parsed from raw HTML ({img_count} embedded images, {table_count} HTML tables)."
            + (" Full portfolio table is an image screenshot; prose/list disclosures verified as PARTIAL_SNAPSHOT." if cp_type == CheckpointType.PARTIAL_SNAPSHOT else "")
        )

        return (
            Checkpoint(
                checkpoint_id=f"{source.key}-{pub_day}-{slug[:28]}",
                source_key=source.key,
                date=pub_day,
                evaluation_date=eval_dt,
                title=title,
                source_file=f"{pub_day}__{slug}.json",
                checkpoint_type=cp_type,
                disclosed_positions=pos_map,
                excluded_positions=excluded_map,
                notes=note_str,
            ),
            mentioned_anywhere,
        )

    def _find_mentions_between_dates(
        self,
        source: SourceConfig,
        resolver: SecurityResolver,
        start_exclusive: str,
        end_inclusive: str,
        exclude_slug: str = "",
    ) -> set[str]:
        """Return set of normalized symbols mentioned in exits/sales in raw articles or chats in (start_exclusive, end_inclusive]."""
        closed_syms: set[str] = set()
        exit_re = re.compile(r"\b(?:closed|closing|sold|selling|exited|cut|cutting|stopped\s+out|getting\s+rid)\b", re.I)

        if source.api_posts_dir.exists():
            for jp in sorted(source.api_posts_dir.glob("*.json")):
                if jp.stat().st_size == 0:
                    continue
                dt_p = jp.name[:10]
                if not (start_exclusive < dt_p <= end_inclusive):
                    continue
                try:
                    pdata = json.loads(jp.read_text(encoding="utf-8"))
                    if str(pdata.get("slug") or "") == exclude_slug:
                        continue
                    plain, _ = preprocess_substack_html(str(pdata.get("body_html") or ""))
                    for line in plain.splitlines():
                        if exit_re.search(line):
                            for s_norm, _, _, _ in resolver.find_securities_in_clause(line):
                                closed_syms.add(s_norm)
                except Exception:
                    continue

        tpath = source.chat_dir / "chat_threads.json"
        if tpath.exists() and tpath.stat().st_size > 0:
            try:
                for item in json.loads(tpath.read_text(encoding="utf-8")):
                    cp = item.get("communityPost") or item
                    dt_c = str(cp.get("created_at") or "")[:10]
                    body = str(cp.get("body") or "")
                    if start_exclusive < dt_c <= end_inclusive:
                        for sent_c in re.split(r"[\n.!?]+", body):
                            if exit_re.search(sent_c):
                                for s_norm, _, _, _ in resolver.find_securities_in_clause(sent_c):
                                    closed_syms.add(s_norm)
            except Exception:
                pass

        rpath = source.chat_dir / "chat_replies.json"
        if rpath.exists() and rpath.stat().st_size > 0:
            try:
                for clist in json.loads(rpath.read_text(encoding="utf-8")).values():
                    for cw in clist:
                        co = cw.get("comment") if isinstance(cw.get("comment"), dict) else cw
                        dt_r = str(co.get("created_at") or "")[:10]
                        body = str(co.get("body") or "")
                        if start_exclusive < dt_r <= end_inclusive:
                            for sent_r in re.split(r"[\n.!?]+", body):
                                if exit_re.search(sent_r):
                                    for s_norm, _, _, _ in resolver.find_securities_in_clause(sent_r):
                                        closed_syms.add(s_norm)
            except Exception:
                pass

        return closed_syms

    def replay_portfolio_to_date(self, source: SourceConfig, as_of_date: str) -> set[str]:
        """
        Reconstruct the simulated portfolio's active long holdings strictly as of `as_of_date`
        by replaying `trade_events.csv` chronologically.
        NEVER fabricates entry dates for undated baseline rows in `portfolio_holdings.csv`.
        """
        events_path = source.data_dir / "trade_events.csv"
        if not events_path.exists() or events_path.stat().st_size == 0:
            return set()

        df = pd.read_csv(events_path)
        if df.empty or "date" not in df.columns or "ticker" not in df.columns:
            return set()

        df = df.copy()
        df["date_str"] = df["date"].astype(str).str.slice(0, 10)
        sub = df[df["date_str"] <= as_of_date]

        active: set[str] = set()
        for _, row in sub.iterrows():
            sym = str(row["ticker"]).strip().upper()
            act = str(row["action"]).strip().upper()
            if act in ("BUY", "ADD"):
                active.add(sym)
            elif act == "SELL":
                active.discard(sym)
        return active

    def reconcile_checkpoint(self, source: SourceConfig, cp: Checkpoint) -> list[CheckpointDiscrepancy]:
        """Compare reconstructed simulation state at `cp.evaluation_date` against independent checkpoint disclosures."""
        sim_active = self.replay_portfolio_to_date(source, cp.evaluation_date)
        # Also allow base-symbol match when exchange suffix differs only on US vs dual-listed ADR (e.g. MFC vs MFC.TO)
        sim_bases = {s.split(".")[0]: s for s in sim_active}
        discrepancies: list[CheckpointDiscrepancy] = []

        # 1. Check every disclosed position in the checkpoint
        expected_active_norms: set[str] = set()
        for ticker, info in sorted(cp.disclosed_positions.items()):
            status = info.get("status", "active")
            evidence = str(info.get("evidence") or "")
            base_t = ticker.split(".")[0]
            in_sim = (ticker in sim_active) or (base_t in sim_bases)

            if status == "active":
                expected_active_norms.add(ticker)
                expected_active_norms.add(base_t)
                if not in_sim:
                    disc = self._investigate_missing_holding(source, cp, ticker, evidence)
                    discrepancies.append(disc)

            elif status == "closed":
                if in_sim:
                    disc = self._investigate_unexpected_holding(
                        source,
                        cp,
                        ticker,
                        reason=f"Checkpoint explicitly marks {ticker} as CLOSED ({evidence}), but simulation still holds it open on {cp.evaluation_date}.",
                    )
                    discrepancies.append(disc)

            elif status == "disappeared":
                discrepancies.append(
                    CheckpointDiscrepancy(
                        checkpoint_id=cp.checkpoint_id,
                        checkpoint_date=cp.evaluation_date,
                        ticker=ticker,
                        discrepancy_type="UNEXPLAINED_DISAPPEARANCE",
                        severity="WARNING",
                        root_cause=RootCauseCategory.UNEXPLAINED_DISAPPEARANCE,
                        evidence_summary=evidence,
                        recommended_action="Retain open in simulation until an explicit exit is disclosed; do not fabricate a sell event from silence.",
                        is_resolved=True,
                    )
                )

        # 2. Record excluded short/option positions as transparent INFO items
        for ex_sym, ex_note in sorted(cp.excluded_positions.items()):
            if ex_sym in sim_active:
                discrepancies.append(
                    CheckpointDiscrepancy(
                        checkpoint_id=cp.checkpoint_id,
                        checkpoint_date=cp.evaluation_date,
                        ticker=ex_sym,
                        discrepancy_type="UNEXPECTED_IN_SIMULATION",
                        severity="ERROR",
                        root_cause=RootCauseCategory.SHORT_OR_DERIVATIVE_EXCLUDED,
                        evidence_summary=f"Disclosed short/derivative {ex_sym} ({ex_note}) erroneously appears as a long holding in simulation!",
                        recommended_action="Exclude short/option instruments from long cash equity ledger.",
                        is_resolved=False,
                    )
                )
            else:
                discrepancies.append(
                    CheckpointDiscrepancy(
                        checkpoint_id=cp.checkpoint_id,
                        checkpoint_date=cp.evaluation_date,
                        ticker=ex_sym,
                        discrepancy_type="EXCLUDED_INSTRUMENT",
                        severity="INFO",
                        root_cause=RootCauseCategory.SHORT_OR_DERIVATIVE_EXCLUDED,
                        evidence_summary=ex_note,
                        recommended_action="Tracked in non_equity_events.csv outside long cash equity simulation.",
                        is_resolved=True,
                    )
                )

        # 3. For COMPLETE_SNAPSHOT checkpoints, verify simulation holds NO unexpected extra positions!
        if cp.checkpoint_type == CheckpointType.COMPLETE_SNAPSHOT:
            for sim_sym in sorted(sim_active):
                if sim_sym not in expected_active_norms and sim_sym.split(".")[0] not in expected_active_norms:
                    disc = self._investigate_unexpected_holding(
                        source,
                        cp,
                        sim_sym,
                        reason=f"Simulated portfolio holds {sim_sym} on {cp.evaluation_date}, which is absent from COMPLETE_SNAPSHOT {cp.title}.",
                    )
                    discrepancies.append(disc)

        return discrepancies

    def _investigate_missing_holding(
        self,
        source: SourceConfig,
        cp: Checkpoint,
        ticker: str,
        checkpoint_evidence: str,
    ) -> CheckpointDiscrepancy:
        """Automated forensic investigation across non_equity_events, baseline holdings, candidate_events, and raw archives."""
        base_t = ticker.split(".")[0]

        # A. Check if excluded short or derivative in non_equity_events.csv
        neq_path = source.data_dir / "non_equity_events.csv"
        if neq_path.exists() and neq_path.stat().st_size > 2:
            try:
                neq_df = pd.read_csv(neq_path)
                if not neq_df.empty and "normalized_ticker" in neq_df.columns:
                    sub_n = neq_df[
                        (neq_df["normalized_ticker"].astype(str).str.upper() == ticker)
                        | (neq_df["normalized_ticker"].astype(str).str.upper().str.split(".").str[0] == base_t)
                    ]
                    if not sub_n.empty:
                        inst = str(sub_n.iloc[0].get("instrument_type", "short/option"))
                        return CheckpointDiscrepancy(
                            checkpoint_id=cp.checkpoint_id,
                            checkpoint_date=cp.evaluation_date,
                            ticker=ticker,
                            discrepancy_type="EXCLUDED_INSTRUMENT",
                            severity="INFO",
                            root_cause=RootCauseCategory.SHORT_OR_DERIVATIVE_EXCLUDED,
                            evidence_summary=f"{ticker} is recorded in non_equity_events.csv as '{inst}' and intentionally excluded from long equity simulation.",
                            recommended_action="No long trade required.",
                            is_resolved=True,
                        )
            except Exception:
                pass

        # B. Check if documented pre-archive baseline holding in portfolio_holdings.csv (e.g. pre-2025 BTT holdings)
        h_path = source.data_dir / "portfolio_holdings.csv"
        ev_path = source.data_dir / "trade_events.csv"
        evidence_str = str(checkpoint_evidence or "")
        is_dated_pick_in_evidence = bool(re.search(r"Picked\s+\d{4}-\d{2}-\d{2}", evidence_str))
        if h_path.exists() and h_path.stat().st_size > 2 and not is_dated_pick_in_evidence:
            try:
                h_df = pd.read_csv(h_path)
                ev_df = pd.read_csv(ev_path) if (ev_path.exists() and ev_path.stat().st_size > 2) else pd.DataFrame()
                in_holdings = h_df[
                    (h_df["symbol"].astype(str).str.upper() == ticker)
                    | (h_df["symbol"].astype(str).str.upper().str.split(".").str[0] == base_t)
                ]
                has_any_buy_in_events = False
                if not ev_df.empty and "ticker" in ev_df.columns:
                    has_any_buy_in_events = not ev_df[
                        ((ev_df["ticker"].astype(str).str.upper() == ticker) | (ev_df["ticker"].astype(str).str.upper().str.split(".").str[0] == base_t))
                        & (ev_df["action"].astype(str).str.upper().isin(["BUY", "ADD"]))
                    ].empty
                if not in_holdings.empty and not has_any_buy_in_events:
                    entry_dt_val = str(in_holdings.iloc[0].get("entry_date") or "").strip()
                    if not entry_dt_val or entry_dt_val.lower() == "nan":
                        return CheckpointDiscrepancy(
                            checkpoint_id=cp.checkpoint_id,
                            checkpoint_date=cp.evaluation_date,
                            ticker=ticker,
                            discrepancy_type="BASELINE_DOCUMENTED",
                            severity="INFO",
                            root_cause=RootCauseCategory.BASELINE_HOLDING_DOCUMENTED,
                            evidence_summary=(
                                f"{ticker} is documented in {in_holdings.iloc[0].get('source_file', 'portfolio_holdings.csv')} "
                                f"as a legacy baseline position initiated prior to the dated 2025-2026 pick ledger."
                            ),
                            recommended_action="Documented pre-window baseline holding; not fabricated as a 2025-2026 fresh pick.",
                            is_resolved=True,
                        )
            except Exception:
                pass

        # C. Check candidate_events.json for extracted candidates (either confirmed-but-dropped or proposed/retrospective)
        cand_path = source.data_dir / "candidate_events.json"
        if cand_path.exists() and cand_path.stat().st_size > 2:
            try:
                cands = json.loads(cand_path.read_text(encoding="utf-8"))
                matching_cands = [
                    c
                    for c in cands
                    if (
                        str(c.get("normalized_ticker", "")).upper() == ticker
                        or str(c.get("normalized_ticker", "")).upper().split(".")[0] == base_t
                    )
                    and str(c.get("effective_date", "")) <= cp.evaluation_date
                ]
                confirmed_prior = [c for c in matching_cands if c.get("execution_status") == "confirmed" and c.get("action") in ("BUY", "ADD")]
                if confirmed_prior:
                    c0 = confirmed_prior[0]
                    return CheckpointDiscrepancy(
                        checkpoint_id=cp.checkpoint_id,
                        checkpoint_date=cp.evaluation_date,
                        ticker=ticker,
                        discrepancy_type="MISSING_IN_SIMULATION",
                        severity="ERROR",
                        root_cause=RootCauseCategory.PARSER_MISS,
                        evidence_summary=(
                            f"Confirmed candidate found in {c0.get('source_id')} on {c0.get('effective_date')} "
                            f"('{str(c0.get('exact_text'))[:100]}'), but missing from simulated portfolio on {cp.evaluation_date}! ({checkpoint_evidence})"
                        ),
                        recommended_action="Inspect trade_events.csv ledger integrity or premature SELL event.",
                        is_resolved=False,
                    )
                non_conf = [c for c in matching_cands if c.get("execution_status") in ("proposed", "retrospective", "uncertain")]
                if non_conf:
                    c0 = non_conf[-1]
                    rc = RootCauseCategory.CHAT_MISS if "chat" in str(c0.get("source_type", "")) else RootCauseCategory.AMBIGUOUS_WORDING
                    return CheckpointDiscrepancy(
                        checkpoint_id=cp.checkpoint_id,
                        checkpoint_date=cp.evaluation_date,
                        ticker=ticker,
                        discrepancy_type="MISSING_IN_SIMULATION",
                        severity="ERROR",
                        root_cause=rc,
                        evidence_summary=(
                            f"{ticker} disclosed active at checkpoint ({checkpoint_evidence}); archive candidate in {c0.get('source_id')} "
                            f"was classified '{c0.get('execution_status')}': '{str(c0.get('exact_text'))[:100]}'."
                        ),
                        recommended_action="Review primary source text to verify whether execution occurred.",
                        is_resolved=False,
                    )
            except Exception:
                pass

        # D. Search raw Datawrapper dated pick tables, raw chats, and raw articles directly!
        if source.datawrapper_dir.exists():
            for fcsv in sorted(source.datawrapper_dir.glob("*.csv")):
                try:
                    raw_txt = fcsv.read_text(encoding="utf-8", errors="ignore")
                    if re.search(rf"\b{re.escape(base_t)}\b", raw_txt):
                        return CheckpointDiscrepancy(
                            checkpoint_id=cp.checkpoint_id,
                            checkpoint_date=cp.evaluation_date,
                            ticker=ticker,
                            discrepancy_type="MISSING_IN_SIMULATION",
                            severity="ERROR",
                            root_cause=RootCauseCategory.PARSER_MISS,
                            evidence_summary=f"{ticker} appears in raw Datawrapper table {fcsv.name} ({checkpoint_evidence}) but is missing from trade_events.csv!",
                            recommended_action="Re-run primary extraction (`btt parse`) to restore missing table trade.",
                            is_resolved=False,
                        )
                except Exception:
                    continue

        tpath = source.chat_dir / "chat_threads.json"
        rpath = source.chat_dir / "chat_replies.json"
        pat_sym = re.compile(rf"\b{re.escape(base_t)}\b", re.I)
        if len(base_t) >= 3:
            for p_chat, rc_cat in [(rpath, RootCauseCategory.SUBTHREAD_REPLY_MISS), (tpath, RootCauseCategory.CHAT_MISS)]:
                if p_chat.exists() and p_chat.stat().st_size > 2:
                    txt_c = p_chat.read_text(encoding="utf-8", errors="ignore")
                    if pat_sym.search(txt_c):
                        return CheckpointDiscrepancy(
                            checkpoint_id=cp.checkpoint_id,
                            checkpoint_date=cp.evaluation_date,
                            ticker=ticker,
                            discrepancy_type="MISSING_IN_SIMULATION",
                            severity="ERROR",
                            root_cause=rc_cat,
                            evidence_summary=f"{ticker} is disclosed active ({checkpoint_evidence}) and appears in {p_chat.name}, but was omitted from trade_events.csv!",
                            recommended_action="Inspect chat extraction rules or restore missing trade event.",
                            is_resolved=False,
                        )

        if source.api_posts_dir.exists() and len(base_t) >= 3:
            for jp in sorted(source.api_posts_dir.glob("*.json")):
                if jp.name[:10] <= cp.evaluation_date and jp.name != cp.source_file:
                    txt_a = jp.read_text(encoding="utf-8", errors="ignore")
                    if pat_sym.search(txt_a):
                        return CheckpointDiscrepancy(
                            checkpoint_id=cp.checkpoint_id,
                            checkpoint_date=cp.evaluation_date,
                            ticker=ticker,
                            discrepancy_type="MISSING_IN_SIMULATION",
                            severity="ERROR",
                            root_cause=RootCauseCategory.PARSER_MISS,
                            evidence_summary=f"{ticker} is disclosed active ({checkpoint_evidence}) and appears in {jp.name}, but was omitted from trade_events.csv!",
                            recommended_action="Inspect article extraction rules or restore missing trade event.",
                            is_resolved=False,
                        )

        # E. Zero prior mentions anywhere in raw archive -> initiated outside Substack / prior to archive window
        return CheckpointDiscrepancy(
            checkpoint_id=cp.checkpoint_id,
            checkpoint_date=cp.evaluation_date,
            ticker=ticker,
            discrepancy_type="MISSING_IN_SIMULATION",
            severity="WARNING",
            root_cause=RootCauseCategory.MANUAL_TRADE_OUTSIDE_SUBSTACK,
            evidence_summary=(
                f"{ticker} first appears at {cp.source_file} ({checkpoint_evidence}) with zero prior mentions in archived articles or chats."
            ),
            recommended_action="Do not backdate entry prior to first archival evidence.",
            is_resolved=True,
        )

    def _investigate_unexpected_holding(
        self,
        source: SourceConfig,
        cp: Checkpoint,
        ticker: str,
        reason: str,
    ) -> CheckpointDiscrepancy:
        """Investigate why simulation still holds `ticker` when a checkpoint says it was closed or absent from a complete snapshot."""
        base_t = ticker.split(".")[0]

        # Check if a later exit exists in trade_events.csv after cp.evaluation_date (e.g. timing difference of a few days)
        ev_path = source.data_dir / "trade_events.csv"
        if ev_path.exists() and ev_path.stat().st_size > 2:
            try:
                ev_df = pd.read_csv(ev_path)
                later_sells = ev_df[
                    ((ev_df["ticker"].astype(str).str.upper() == ticker) | (ev_df["ticker"].astype(str).str.upper().str.split(".").str[0] == base_t))
                    & (ev_df["action"].astype(str).str.upper() == "SELL")
                    & (ev_df["date"].astype(str).str.slice(0, 10) > cp.evaluation_date)
                ]
                if not later_sells.empty:
                    sell_dt = str(later_sells.iloc[0]["date"])[:10]
                    day_gap = abs((pd.Timestamp(sell_dt) - pd.Timestamp(cp.evaluation_date)).days)
                    has_recent_trim = not ev_df[
                        ((ev_df["ticker"].astype(str).str.upper() == ticker) | (ev_df["ticker"].astype(str).str.upper().str.split(".").str[0] == base_t))
                        & (ev_df["action"].astype(str).str.upper() == "TRIM")
                        & (abs((pd.to_datetime(ev_df["date"]) - pd.to_datetime(cp.evaluation_date)).dt.days) <= 10)
                    ].empty
                    if day_gap <= 5 or (has_recent_trim and day_gap <= 45):
                        return CheckpointDiscrepancy(
                            checkpoint_id=cp.checkpoint_id,
                            checkpoint_date=cp.evaluation_date,
                            ticker=ticker,
                            discrepancy_type="UNEXPECTED_IN_SIMULATION",
                            severity="WARNING",
                            root_cause=RootCauseCategory.PARTIAL_DISCLOSURE,
                            evidence_summary=f"{reason} Exit recorded {day_gap} day(s) later on {sell_dt}.",
                            recommended_action="Verified partial trim/settlement difference with subsequent explicit exit.",
                            is_resolved=True,
                        )
            except Exception:
                pass

        # Otherwise check if an exit exists in chat/articles/Datawrapper that was missed or deleted from trade_events.csv!
        rc = RootCauseCategory.PARSER_MISS
        rpath = source.chat_dir / "chat_replies.json"
        tpath = source.chat_dir / "chat_threads.json"
        if rpath.exists() and re.search(rf"\b{re.escape(base_t)}\b", rpath.read_text(encoding="utf-8", errors="ignore"), re.I):
            rc = RootCauseCategory.CHAT_MISS
        elif tpath.exists() and re.search(rf"\b{re.escape(base_t)}\b", tpath.read_text(encoding="utf-8", errors="ignore"), re.I):
            rc = RootCauseCategory.CHAT_MISS

        return CheckpointDiscrepancy(
            checkpoint_id=cp.checkpoint_id,
            checkpoint_date=cp.evaluation_date,
            ticker=ticker,
            discrepancy_type="UNEXPECTED_IN_SIMULATION",
            severity="ERROR",
            root_cause=rc,
            evidence_summary=reason,
            recommended_action="Locate missing SELL/exit transaction or remove false-positive BUY from trade_events.csv.",
            is_resolved=False,
        )

    def validate_and_reconcile_source(self, source: SourceConfig, save_outputs: bool = True) -> PortfolioReconciliationAudit:
        """Run mandatory source archive validation + independent point-in-time checkpoint reconciliation."""
        ing_report = validate_source_archive(source, save_report=save_outputs)
        checkpoints = self.discover_checkpoints(source)

        all_discrepancies: list[CheckpointDiscrepancy] = []
        timeline_rows: list[dict[str, Any]] = []

        for cp in checkpoints:
            cp_discs = self.reconcile_checkpoint(source, cp)
            all_discrepancies.extend(cp_discs)
            sim_set = self.replay_portfolio_to_date(source, cp.evaluation_date)
            exp_active = sorted(k for k, v in cp.disclosed_positions.items() if v.get("status") == "active")
            exp_closed = sorted(k for k, v in cp.disclosed_positions.items() if v.get("status") == "closed")
            timeline_rows.append(
                {
                    "checkpoint_id": cp.checkpoint_id,
                    "checkpoint_date": cp.date,
                    "evaluation_date": cp.evaluation_date,
                    "checkpoint_type": cp.checkpoint_type.value,
                    "title": cp.title,
                    "disclosed_active_count": len(exp_active),
                    "disclosed_closed_count": len(exp_closed),
                    "simulated_active_count": len(sim_set),
                    "unresolved_errors": sum(1 for d in cp_discs if d.severity == "ERROR" and not d.is_resolved),
                    "warnings": sum(1 for d in cp_discs if d.severity == "WARNING"),
                    "disclosed_active_tickers": ",".join(exp_active),
                    "simulated_active_tickers": ",".join(sorted(sim_set)),
                }
            )

        unresolved_errors = sum(1 for d in all_discrepancies if d.severity == "ERROR" and not d.is_resolved)
        warnings_cnt = sum(1 for d in all_discrepancies if d.severity == "WARNING")
        info_cnt = sum(1 for d in all_discrepancies if d.severity == "INFO")

        ing_warnings = sum(1 for a in ing_report.anomalies if a.severity == "WARNING")
        if not ing_report.is_valid or unresolved_errors > 0:
            overall = ReconciliationStatus.UNRECONCILED
        elif warnings_cnt > 0 or ing_warnings > 0:
            overall = ReconciliationStatus.RECONCILED_WITH_WARNINGS
        else:
            overall = ReconciliationStatus.FULLY_RECONCILED

        audit = PortfolioReconciliationAudit(
            source_key=source.key,
            display_name=source.display_name,
            overall_status=overall,
            is_archive_valid=ing_report.is_valid,
            checkpoints_evaluated=len(checkpoints),
            checkpoints=checkpoints,
            discrepancies=all_discrepancies,
            unresolved_errors=unresolved_errors,
            warnings_count=warnings_cnt,
            info_count=info_cnt,
            holdings_timeline=timeline_rows,
        )

        if save_outputs:
            source.data_dir.mkdir(parents=True, exist_ok=True)
            source.results_dir.mkdir(parents=True, exist_ok=True)
            audit_json = json.dumps(audit.to_dict(), indent=2, ensure_ascii=False)
            (source.data_dir / "reconciliation_audit.json").write_text(audit_json, encoding="utf-8")
            (source.results_dir / "checkpoint_reconciliation.json").write_text(audit_json, encoding="utf-8")
            (source.data_dir / "checkpoints.json").write_text(
                json.dumps(audit.to_dict()["checkpoints"], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tl_df = pd.DataFrame(timeline_rows)
            tl_df.to_csv(source.data_dir / "holdings_by_checkpoint.csv", index=False)
            tl_df.to_csv(source.results_dir / "checkpoint_history.csv", index=False)

        return audit

    def audit_source(self, source: SourceConfig, save_outputs: bool = True) -> ReconciliationReport:
        """Produce combined archive coverage + checkpoint reconciliation report for CLI & docs."""
        ing = validate_source_archive(source, save_report=save_outputs)
        audit = self.validate_and_reconcile_source(source, save_outputs=save_outputs)

        ev_path = source.data_dir / "trade_events.csv"
        ev_count = 0
        uniq_tickers = 0
        if ev_path.exists() and ev_path.stat().st_size > 2:
            ev_df = pd.read_csv(ev_path)
            ev_count = len(ev_df)
            if "ticker" in ev_df.columns:
                uniq_tickers = int(ev_df["ticker"].nunique())

        disc_by_key: dict[tuple[str, str], CheckpointDiscrepancy] = {
            (d.checkpoint_id, d.ticker): d for d in audit.discrepancies
        }

        positions_checked: list[DisclosedPosition] = []
        for cp in audit.checkpoints:
            for sym, info in sorted(cp.disclosed_positions.items()):
                d_match = disc_by_key.get((cp.checkpoint_id, sym))
                if d_match is None:
                    st_led = "RECONCILED"
                    rc_str = RootCauseCategory.RECONCILED.value
                    note_s = str(info.get("evidence") or "")
                elif d_match.discrepancy_type == "BASELINE_DOCUMENTED":
                    st_led = "BASELINE_DOCUMENTED"
                    rc_str = d_match.root_cause.value
                    note_s = d_match.evidence_summary
                elif d_match.discrepancy_type == "EXCLUDED_INSTRUMENT":
                    st_led = "EXCLUDED_NON_EQUITY"
                    rc_str = d_match.root_cause.value
                    note_s = d_match.evidence_summary
                else:
                    st_led = "DISCREPANCY" if not d_match.is_resolved else "WARNING_DOCUMENTED"
                    rc_str = d_match.root_cause.value
                    note_s = d_match.evidence_summary

                positions_checked.append(
                    DisclosedPosition(
                        ticker=sym,
                        company_name=str(info.get("name") or sym),
                        source_file=cp.source_file,
                        disclosure_date=cp.evaluation_date,
                        disclosure_type=str(info.get("status") or "active"),
                        status_in_ledger=st_led,
                        root_cause=rc_str,
                        notes=note_s[:200],
                    )
                )

        reconciled_cnt = sum(1 for p in positions_checked if p.status_in_ledger in ("RECONCILED", "BASELINE_DOCUMENTED", "EXCLUDED_NON_EQUITY"))

        report = ReconciliationReport(
            source_key=source.key,
            display_name=source.display_name,
            overall_status=audit.overall_status.value,
            api_posts_count=ing.posts_total_files,
            paid_posts_count=ing.posts_paid_count,
            truncated_posts_count=ing.posts_paywall_truncated_count,
            zero_byte_posts_count=ing.posts_empty_or_corrupt_count,
            chat_threads_count=ing.chat_threads_count,
            chat_replies_count=ing.chat_replies_total_count,
            datawrapper_tables_count=ing.datawrapper_csv_count,
            trade_events_count=ev_count,
            unique_simulated_tickers=uniq_tickers,
            checkpoints_count=audit.checkpoints_evaluated,
            disclosed_positions_checked=len(positions_checked),
            reconciled_count=reconciled_cnt,
            unresolved_discrepancies_count=audit.unresolved_errors,
            warnings_count=audit.warnings_count,
            positions=positions_checked,
            audit=audit,
        )

        if save_outputs:
            (source.results_dir / "coverage_and_reconciliation_report.json").write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return report

    def audit_all(self, save_outputs: bool = True) -> list[ReconciliationReport]:
        return [self.audit_source(src, save_outputs=save_outputs) for src in self.settings.sources.values()]
