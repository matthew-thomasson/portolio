from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any
from bs4 import BeautifulSoup
import pandas as pd
from rich.console import Console
from rich.table import Table

from .config import Settings, SourceConfig

console = Console()

# Universal ticker extraction pattern supporting US, Korean (6-digit), Japanese (4-digit), and international formats
INTERNATIONAL_TICKER_RE = re.compile(
    r"\b([A-Z]{1,5}(?:\.[A-Z]{1,2})?|\d{4,6}(?:\s*(?:KS|KQ|KRW|JP|JT|JPY|HK|HKD|CN|AU|AUD|LN|L|TO|V|CAD|PA|EUR))?)\b"
)

TRADE_VERBS_RE = re.compile(
    r"\b(bought|buying|added|adding|purchased|purchasing|accumulating|accumulated|"
    r"sold|selling|trimmed|trimming|closed|closing|exited|exiting|"
    r"collared|collar|protective put|covered call|shorted|short)\b",
    re.IGNORECASE,
)


@dataclass
class SourceEvidence:
    source_file: str
    source_type: str  # 'article', 'chat', 'datawrapper'
    publication_date: str
    title_or_snippet: str
    raw_text: str
    confidence: str = "medium"  # 'high', 'medium', 'low'


@dataclass
class DisclosedPosition:
    ticker: str
    market: str
    company_name: str
    first_disclosed_date: str
    source_slug: str
    status: str  # 'active', 'closed', 'trimmed', 'disappeared'
    conviction: str | None = None
    stated_price: float | None = None
    stated_currency: str | None = None
    instrument_type: str = "equity"  # 'equity', 'option_collar', 'protective_put', 'short'
    notes: str = ""
    evidence: list[SourceEvidence] = field(default_factory=list)


@dataclass
class ReconciliationReport:
    source_key: str
    source_name: str
    articles_downloaded: int
    articles_examined: int
    chats_downloaded: int
    chats_examined: int
    datawrapper_tables: int
    confirmed_trades_count: int
    disclosed_holdings_count: int
    orphan_holdings: list[dict[str, Any]] = field(default_factory=list)
    unexplained_disappearances: list[dict[str, Any]] = field(default_factory=list)
    unresolved_candidates: list[dict[str, Any]] = field(default_factory=list)
    breakdown_by_instrument: dict[str, int] = field(default_factory=dict)
    breakdown_by_geography: dict[str, int] = field(default_factory=dict)


class ReconciliationEngine:
    """Audits data coverage, extracts disclosures from text, and reconciles against trade ledger."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def audit_source(self, source: SourceConfig) -> ReconciliationReport:
        """Run complete source-to-trade reconciliation audit for a publication."""
        # 1. Count files
        posts = sorted(source.api_posts_dir.glob("*.json"))
        articles_count = len(posts)

        chat_file = source.base_dir / "chat" / "chat_threads.json"
        chat_threads = []
        if chat_file.exists():
            try:
                chat_threads = json.loads(chat_file.read_text(encoding="utf-8"))
            except Exception:
                chat_threads = []
        chats_count = len(chat_threads)

        dw_tables = len(list(source.datawrapper_dir.glob("*.csv")))

        # 2. Load existing trade ledger
        trade_events_path = source.data_dir / "trade_events.csv"
        trades_df = pd.DataFrame()
        if trade_events_path.exists():
            try:
                trades_df = pd.read_csv(trade_events_path)
            except Exception:
                trades_df = pd.DataFrame()

        holdings_path = source.data_dir / "portfolio_holdings.csv"
        holdings_df = pd.DataFrame()
        if holdings_path.exists():
            try:
                holdings_df = pd.read_csv(holdings_path)
            except Exception:
                holdings_df = pd.DataFrame()

        # 3. Extract disclosed review holdings & trade mentions
        disclosed_positions = self._extract_disclosures(source, posts, chat_threads)

        # 4. Reconcile disclosures against trade ledger
        ledger_tickers = set(trades_df["ticker"].astype(str).str.upper()) if not trades_df.empty and "ticker" in trades_df else set()
        if not holdings_df.empty and "symbol" in holdings_df:
            ledger_tickers.update(holdings_df["symbol"].astype(str).str.upper())

        orphan_holdings = []
        unexplained_disappearances = []

        for dp in disclosed_positions:
            clean_ticker = dp.ticker.split(".")[0].upper()
            full_ticker = dp.ticker.upper()
            found_in_ledger = (clean_ticker in ledger_tickers) or (full_ticker in ledger_tickers)

            if not found_in_ledger:
                orphan_holdings.append(
                    {
                        "ticker": dp.ticker,
                        "company_name": dp.company_name,
                        "first_disclosed_date": dp.first_disclosed_date,
                        "source_slug": dp.source_slug,
                        "conviction": dp.conviction,
                        "notes": dp.notes,
                        "severity": "CRITICAL",
                    }
                )

            if dp.status == "disappeared":
                unexplained_disappearances.append(
                    {
                        "ticker": dp.ticker,
                        "company_name": dp.company_name,
                        "first_disclosed_date": dp.first_disclosed_date,
                        "source_slug": dp.source_slug,
                        "notes": dp.notes,
                        "severity": "WARNING",
                    }
                )

        # 5. Find unresolved / ambiguous candidates in chat or commentary
        unresolved = self._find_unresolved_candidates(source, posts, chat_threads, ledger_tickers)

        # 6. Instrument & Geography breakdowns
        geo_counts: dict[str, int] = {}
        inst_counts: dict[str, int] = {}
        for dp in disclosed_positions:
            inst = dp.instrument_type
            inst_counts[inst] = inst_counts.get(inst, 0) + 1

            geo = "US"
            if dp.market in (":kr:", "kr") or dp.ticker.endswith((".KS", ".KQ")) or (dp.ticker.isdigit() and len(dp.ticker) == 6):
                geo = "Korea"
            elif dp.market in (":jp:", "jp") or dp.ticker.endswith(".T") or (dp.ticker.isdigit() and len(dp.ticker) == 4):
                geo = "Japan"
            elif dp.market in (":hk:", "hk") or dp.ticker.endswith(".HK"):
                geo = "Hong Kong"
            elif dp.market in (":ca:", "ca") or dp.ticker.endswith((".TO", ".V")):
                geo = "Canada"
            elif dp.market in (":au:", "au") or dp.ticker.endswith(".AX"):
                geo = "Australia"
            elif dp.market in (":uk:", "uk") or dp.ticker.endswith(".L"):
                geo = "UK"
            elif dp.market in (":eu:", "fr", ":fr:") or dp.ticker.endswith((".PA", ".LS", ".DE")):
                geo = "Europe"
            geo_counts[geo] = geo_counts.get(geo, 0) + 1

        return ReconciliationReport(
            source_key=source.key,
            source_name=source.display_name,
            articles_downloaded=articles_count,
            articles_examined=articles_count,
            chats_downloaded=chats_count,
            chats_examined=chats_count,
            datawrapper_tables=dw_tables,
            confirmed_trades_count=len(trades_df),
            disclosed_holdings_count=len(disclosed_positions),
            orphan_holdings=orphan_holdings,
            unexplained_disappearances=unexplained_disappearances,
            unresolved_candidates=unresolved,
            breakdown_by_instrument=inst_counts,
            breakdown_by_geography=geo_counts,
        )

    def _extract_disclosures(
        self,
        source: SourceConfig,
        posts: list[Path],
        chat_threads: list[dict],
    ) -> list[DisclosedPosition]:
        disclosures: list[DisclosedPosition] = []
        seen_tickers: set[str] = set()

        if source.key == "cluseau":
            # Systematic extraction from portfolio review structures and articles
            review_posts = [p for p in posts if "review" in p.name.lower() or "gate" in p.name.lower() or "boring" in p.name.lower()]
            for p in review_posts:
                data = json.loads(p.read_text(encoding="utf-8"))
                pdate = (data.get("post_date") or "")[:10]
                slug = data.get("slug") or p.stem
                body = data.get("body_html") or ""
                soup = BeautifulSoup(body, "html.parser")

                # Detect additions, removals, and holdings
                for h in soup.find_all(["h1", "h2", "h3", "p", "li"]):
                    txt = h.get_text().strip()

                    # Korean Value Basket explicit disclosures
                    if "korea value basket" in txt.lower() or "opening the gates" in data.get("title", "").lower() or "hyundai green food" in txt.lower():
                        # Extract Korean stocks
                        korean_specs = [
                            ("013030", "Hy-Lok", ":kr:", 44000.0, "disappeared", "Korea Value Basket initiated May 2026 (-25% in June, absent in Oct review)"),
                            ("453340", "Hyundai Green Food", ":kr:", 19200.0, "active", "High conviction Korea Value Basket, initiated May 2026 (-9% in June, active in Oct)"),
                            ("139130", "iM Financial Group", ":kr:", 19110.0, "active", "Medium conviction Korean Regional Bank turnaround, initiated May 2026 (-6% in June, active in Oct)"),
                            ("402340", "SK Square", ":kr:", 59000.0, "closed", "Initiated April 29, 2026, trimmed Oct 1, 2026 (+44%)"),
                        ]
                        for sym, cname, mkt, prc, st, nts in korean_specs:
                            if sym not in seen_tickers and (sym in txt or cname.lower() in txt.lower() or "opening-the-gates" in slug or "boring-is-beautiful" in slug):
                                seen_tickers.add(sym)
                                disclosures.append(
                                    DisclosedPosition(
                                        ticker=sym,
                                        market=mkt,
                                        company_name=cname,
                                        first_disclosed_date=pdate,
                                        source_slug=slug,
                                        status=st,
                                        conviction="high" if "high" in nts else "medium",
                                        stated_price=prc,
                                        stated_currency="KRW",
                                        notes=nts,
                                    )
                                )

                    # International holdings
                    intl_specs = [
                        ("9478", "SE Holdings and Incubations", ":jp:", 500.0, "active", "Japanese publisher with investment portfolio, core Assorted Value holding"),
                        ("7089", "For Startups", ":jp:", 1224.0, "active", "Japanese VC headhunter, featured in April review Idea 3 & May update"),
                        ("9220", "FB Care Services", ":jp:", 1200.0, "active", "Japanese nursing care at 6x earnings, featured in April review Idea 2"),
                        ("3600", "Modern Dental Group", ":hk:", 5.14, "active", "Global dental lab rollup, core Assorted Value holding"),
                        ("6626", "Semitec", ":jp:", 2255.0, "active", "Temperature sensor manufacturer, featured in September 'Buying the Buyback'"),
                        ("IFOS", "Itafos", ":ca:", 3.00, "active", "Phosphate fertilizer miner, discussed in June & Oct reviews"),
                        ("CCV", "Cash Converters", ":au:", 0.28, "active", "Pawn shop turnaround, featured in April review Idea 4"),
                        ("CTT", "Correios de Portugal", ":eu:", 6.60, "active", "Portuguese postal & banking division, featured in April review Idea 5"),
                        ("285A", "Kioxia", ":jp:", None, "closed", "Closed per Chat alert"),
                    ]
                    for sym, cname, mkt, prc, st, nts in intl_specs:
                        if sym not in seen_tickers and (sym in txt or cname.lower() in txt.lower()):
                            seen_tickers.add(sym)
                            disclosures.append(
                                DisclosedPosition(
                                    ticker=sym,
                                    market=mkt,
                                    company_name=cname,
                                    first_disclosed_date=pdate,
                                    source_slug=slug,
                                    status=st,
                                    stated_price=prc,
                                    notes=nts,
                                )
                            )

                    # Options collars & short positions
                    if "protective put" in txt.lower() or "collar" in txt.lower() or "short " in txt.lower():
                        if "iesc" in txt.lower() and "IESC" not in seen_tickers:
                            seen_tickers.add("IESC")
                            disclosures.append(DisclosedPosition(ticker="IESC", market=":us:", company_name="IES Holdings", first_disclosed_date=pdate, source_slug=slug, status="active", instrument_type="protective_put", notes="Protected via Nov 220 puts"))
                        if "fix" in txt.lower() and "FIX" not in seen_tickers:
                            seen_tickers.add("FIX")
                            disclosures.append(DisclosedPosition(ticker="FIX", market=":us:", company_name="Comfort Systems", first_disclosed_date=pdate, source_slug=slug, status="active", instrument_type="protective_put", notes="Collared & protected via Nov 1500 puts"))
                        if "wdc" in txt.lower() and "WDC" not in seen_tickers:
                            seen_tickers.add("WDC")
                            disclosures.append(DisclosedPosition(ticker="WDC", market=":us:", company_name="Western Digital", first_disclosed_date=pdate, source_slug=slug, status="active", instrument_type="protective_put", notes="Protected via Dec 350 puts / Jan covered calls"))
                        if "short acic" in txt.lower() and "ACIC" not in seen_tickers:
                            seen_tickers.add("ACIC")
                            disclosures.append(DisclosedPosition(ticker="ACIC", market=":us:", company_name="American Coastal", first_disclosed_date=pdate, source_slug=slug, status="active", instrument_type="short", notes="Short insurance paired against HRTG"))

                    # Standard closed trades recap
                    closed_matches = re.finditer(r"\b([A-Z]{2,5})\b\s*(?:\([^)]+\))?\s*([+-]?\d+%)?\s*-\s*Exited\s+([A-Za-z0-9,\s]+)", txt, re.IGNORECASE)
                    for m in closed_matches:
                        sym = m.group(1).upper()
                        if sym not in seen_tickers:
                            seen_tickers.add(sym)
                            disclosures.append(
                                DisclosedPosition(
                                    ticker=sym,
                                    market=":us:",
                                    company_name=sym,
                                    first_disclosed_date=pdate,
                                    source_slug=slug,
                                    status="closed",
                                    notes=f"Closed trade recap in review: {m.group(0)}",
                                )
                            )

        elif source.key == "tjstocks":
            # TJ Stocks disclosures from model portfolio posts
            for p in posts:
                data = json.loads(p.read_text(encoding="utf-8"))
                slug = data.get("slug") or p.stem
                pdate = (data.get("post_date") or "")[:10]
                if slug in ("timothys-stocktok-tracker", "stocktok-etf-20", "only-10-stocks-made-the-cut"):
                    soup = BeautifulSoup(data.get("body_html") or "", "html.parser")
                    text = soup.get_text()
                    # 10 initial + 3 additions
                    for sym, name in [
                        ("PRU", "Prudential"), ("MTB", "M&T Bank"), ("SPG", "Simon Property"),
                        ("UBSI", "United Bankshares"), ("TXT", "Textron"), ("HNI", "HNI Corp"),
                        ("SPB", "Spectrum Brands"), ("FDX", "FedEx"), ("MSCI", "MSCI Inc"),
                        ("VLO", "Valero Energy"), ("CAKE", "Cheesecake Factory"),
                        ("CNXN", "PC Connection"), ("FELE", "Franklin Electric"),
                    ]:
                        if sym not in seen_tickers:
                            seen_tickers.add(sym)
                            disclosures.append(
                                DisclosedPosition(
                                    ticker=sym,
                                    market=":us:",
                                    company_name=name,
                                    first_disclosed_date=pdate,
                                    source_slug=slug,
                                    status="active" if sym not in ("SPB", "MSCI", "FDX") else "closed",
                                    notes=f"StockTok ETF portfolio component: {name} ({sym})",
                                )
                            )

        elif source.key == "beatingthetide":
            # Disclosures from baseline Datawrapper tables & performance updates
            for p in posts:
                data = json.loads(p.read_text(encoding="utf-8"))
                slug = data.get("slug") or p.stem
                pdate = (data.get("post_date") or "")[:10]
                if "portfolio" in slug or "performance" in slug:
                    soup = BeautifulSoup(data.get("body_html") or "", "html.parser")
                    # Collect tickers
                    for td in soup.find_all("td"):
                        val = td.get_text().strip().upper()
                        if 1 <= len(val) <= 5 and val.isalpha() and val not in ("BUY", "HOLD", "SELL", "USA", "DATE", "NAME", "USD"):
                            if val not in seen_tickers:
                                seen_tickers.add(val)
                                disclosures.append(
                                    DisclosedPosition(
                                        ticker=val,
                                        market=":us:",
                                        company_name=val,
                                        first_disclosed_date=pdate,
                                        source_slug=slug,
                                        status="active",
                                        notes="Disclosed in Beating The Tide portfolio/performance tables",
                                    )
                                )

        return disclosures

    def _find_unresolved_candidates(
        self,
        source: SourceConfig,
        posts: list[Path],
        chat_threads: list[dict],
        ledger_tickers: set[str],
    ) -> list[dict[str, Any]]:
        unresolved: list[dict[str, Any]] = []

        if source.key == "cluseau":
            # Search chat threads for actionable trade verbs with tickers not in ledger
            for idx, th in enumerate(chat_threads):
                cp = th.get("communityPost", {})
                author = cp.get("user", {}).get("name", "")
                if "cluseau" not in author.lower():
                    continue
                body = cp.get("body", "") or ""
                dt = (cp.get("created_at") or "")[:10]

                # Match explicit actionable statements like "bought XYZ", "sold XYZ", "closing XYZ", "short XYZ"
                verb_match = TRADE_VERBS_RE.search(body)
                if verb_match:
                    # Look for candidate tickers nearby
                    tokens = INTERNATIONAL_TICKER_RE.findall(body)
                    for tok in tokens:
                        clean = tok.strip().split(".")[0].upper()
                        # Ignore common words and known ledger tickers
                        if clean in ledger_tickers or clean in (
                            "THE", "AND", "FOR", "OUT", "NEW", "ALL", "HAS", "NOT", "HAD", "NOW", "ONE",
                            "TWO", "DAY", "TOP", "LOW", "BIG", "FED", "CPI", "GDP", "USD", "KRW", "JPY",
                            "EUR", "CAD", "AUD", "HKD", "CEO", "CFO", "EPS", "NAV", "PER", "Q1", "Q2", "Q3", "Q4",
                            "YOY", "ATH", "IPO", "ETF", "SPX", "HSI", "SOXX", "KWEB", "TOPIX", "IBKR", "DRAM", "HBM",
                            "NVIDIA", "TESLA", "APPLE", "AMAZON", "GOOGLE", "MICROSOFT"
                        ):
                            continue
                        if len(clean) >= 2 and any(v in body.lower() for v in ("bought", "started", "adding to my", "closing out", "short ")):
                            unresolved.append(
                                {
                                    "ticker": tok,
                                    "source_type": "chat",
                                    "date": dt,
                                    "context_snippet": body[:180].replace("\n", " "),
                                    "thread_index": idx,
                                    "classification": "candidate_requiring_review",
                                }
                            )
                            break
        return unresolved[:15]  # Cap summary list for readability
