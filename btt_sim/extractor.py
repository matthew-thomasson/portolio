from __future__ import annotations

import hashlib
import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional
from bs4 import BeautifulSoup, NavigableString, Tag
import pandas as pd
from pydantic import BaseModel, Field

from .config import Settings, SourceConfig
from .ingestion import discover_publication_authors
from .prices import PriceProvider

EXTRACTOR_VERSION = "3.4.0"

# Financial / accounting / macro / English tokens that must NEVER be mistaken for bare stock tickers
STOPWORD_ACRONYMS: set[str] = {
    "A", "I", "AM", "PM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IF", "IN", "IS", "IT",
    "ME", "MY", "NO", "OF", "OK", "ON", "OR", "SO", "TO", "UP", "US", "WE", "RE", "VS", "EX",
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "ANY", "CAN", "HAD", "HER", "WAS",
    "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW", "MAN", "NEW", "NOW", "OLD",
    "SEE", "TWO", "WAY", "WHO", "BOY", "DID", "ITS", "LET", "PUT", "SAY", "SHE", "TOO", "USE",
    "BUY", "ADD", "CUT", "TOP", "LOW", "BIG", "END", "FAR", "FEW", "GOT", "LOT", "MAY", "NET",
    "OFF", "OWN", "PAY", "PER", "RAN", "RUN", "SAW", "SET", "SIX", "TEN", "TRY", "WIN", "WON",
    "YET", "YES", "WHY", "BIT", "BPS", "CEO", "CFO", "COO", "CTO", "CIO", "CPA", "IPO", "SPO",
    "ETF", "ETN", "ADR", "GDR", "NAV", "AUM", "ROE", "ROA", "ROI", "IRR", "FCF", "DCF", "EPS",
    "DPS", "BV", "TBV", "PE", "PB", "PS", "EV", "TEV", "NII", "NIM", "CET", "LTV", "NPL", "ARR",
    "NRR", "MRR", "TAM", "SAM", "SOM", "CAC", "ARPU", "GMV", "GDP", "CPI", "PPI", "PCE", "PMI",
    "FED", "FOMC", "BOJ", "ECB", "BOE", "BOK", "PBOC", "RBA", "BOC", "IMF", "WTO", "SEC", "FTC",
    "DOJ", "IRS", "FDA", "EPA", "FCC", "FDIC", "OCC", "FINRA", "NYSE", "NASDAQ", "AMEX", "OTC",
    "TSX", "TSXV", "LSE", "KSE", "AIM", "ASX", "HKEX", "KRX", "KOSPI", "KOSDAQ", "TSE", "JPX", "ELI",
    "EUR", "USD", "GBP", "JPY", "KRW", "CAD", "AUD", "HKD", "CNY", "RMB", "SEK", "NOK", "CHF",
    "SGD", "BRL", "MXN", "CLP", "ARS", "INR", "TWD", "YTD", "QTD", "MTD", "WTD", "TTM", "NTM", "LTM",
    "YOY", "QOQ", "MOM", "CAGR", "GAAP", "IFRS", "EBITDA", "EBIT", "NOPAT", "CAPEX", "OPEX",
    "SG", "SGA", "RD", "ROIC", "ROCE", "WACC", "VIX", "SPX", "NDX", "DJI", "RUT", "IWM", "SPY",
    "QQQ", "DIA", "MSCI", "S&P", "LCE", "RFS", "RIN", "LNG", "LPG", "WTI", "API", "GPU", "CPU",
    "TPU", "LLM", "NLP", "AWS", "GCP", "OCI", "SMB", "B2B", "B2C", "SAAS", "PAAS", "IAAS", "OEM",
    "ODM", "EMS", "ERP", "CRM", "HCM", "VCP", "SMA", "EMA", "RSI", "MACD", "VWAP", "ATH", "ATL",
    "HOD", "LOD", "EOD", "AH", "PR", "IR", "QA", "FAQ", "TBD", "TBA", "IMO", "IMHO", "FYI",
    "BTW", "LOL", "LMAO", "OMG", "WTF", "TLDR", "PDF", "CSV", "URL", "HTML", "JSON", "LLC", "INC",
    "CORP", "LTD", "PLC", "SA", "NV", "AG", "SE", "AB", "SPA", "KK", "CO", "LP", "LLP", "HOLD",
    "SELL", "TRIM", "LONG", "SHORT", "CALL", "PUTS", "PUT", "CALLS", "JAN", "FEB", "MAR", "APR",
    "JUN", "JUL", "AUG", "SEP", "SEPT", "OCT", "NOV", "DEC", "MON", "TUE", "WED", "THU", "FRI",
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
    "USA", "UK", "EU", "KR", "JP", "HK", "CA", "AU", "FR", "DE", "PT", "NL", "CL", "IL", "NA",
    "PRO", "CON", "MAX", "MIN", "AVG", "EST", "ACT", "REV", "VOL", "ADV", "FLOAT", "DEBT", "CASH",
    "TAX", "IRA", "ROTH", "HSA", "ISA", "TFSA", "RRSP", "SIPP", "REIT", "BDC", "MLP", "SPAC",
    "BNPL", "HPC", "ATSC", "WAM", "HYP", "JUST", "ONCE", "GSE", "ACA", "CMIC", "NBV", "HBM", "DRAM", "NAND",
    "FFO", "AFFO", "GDDR", "NDFI", "CMBS", "RMBS", "CLO", "MBS", "ABS", "CBK", "MORT", "OAR", "NLV", "IBKR",
    "TSX", "TSXV", "NYSE", "NASDAQ", "AMEX", "LSE", "HKEX", "KRX", "KOSPI", "KOSDAQ", "TYO", "TSE", "XETRA",
    "ASX", "EURONEXT", "OTC", "BCS",
}

# Note: Some real tickers overlap with English/acronym words when explicitly prefixed with $ or in known context
VALID_TICKERS_DESPITE_OVERLAP: set[str] = {
    "ALL", "MSCI", "PAAS", "NET", "U", "T", "C", "V", "X", "COST", "CAR", "EAT", "GAP", "NOW", "ON", "SO", "IT"
}

EXCHANGE_HINT_MAP: dict[str, tuple[str, str, str]] = {
    # hint -> (yf_suffix, market_code, exchange_label)
    "KS": (".KS", ":kr:", "KRX"),
    "KOSPI": (".KS", ":kr:", "KRX"),
    "KQ": (".KQ", ":kr:", "KOSDAQ"),
    "KOSDAQ": (".KQ", ":kr:", "KOSDAQ"),
    "KR": (".KS", ":kr:", "KRX"),
    "JT": (".T", ":jp:", "TSE"),
    "JP": (".T", ":jp:", "TSE"),
    "TSE": (".T", ":jp:", "TSE"),
    "TYO": (".T", ":jp:", "TSE"),
    "T": (".T", ":jp:", "TSE"),
    "HK": (".HK", ":hk:", "HKEX"),
    "HKEX": (".HK", ":hk:", "HKEX"),
    "HKG": (".HK", ":hk:", "HKEX"),
    "AU": (".AX", ":au:", "ASX"),
    "AX": (".AX", ":au:", "ASX"),
    "ASX": (".AX", ":au:", "ASX"),
    "LN": (".L", ":uk:", "LSE"),
    "L": (".L", ":uk:", "LSE"),
    "LSE": (".L", ":uk:", "LSE"),
    "AIM": (".L", ":uk:", "AIM"),
    "IL": (".IL", ":uk:", "LSE-IOB"),
    "LI": (".IL", ":uk:", "LSE-IOB"),
    "IOB": (".IL", ":uk:", "LSE-IOB"),
    "FP": (".PA", ":fr:", "EPA"),
    "PA": (".PA", ":fr:", "EPA"),
    "EPA": (".PA", ":fr:", "EPA"),
    "PL": (".LS", ":pt:", "ELI"),
    "LS": (".LS", ":pt:", "ELI"),
    "ELI": (".LS", ":pt:", "ELI"),
    "DE": (".DE", ":de:", "XETRA"),
    "F": (".F", ":de:", "FWB"),
    "FWB": (".F", ":de:", "FWB"),
    "GR": (".DE", ":de:", "XETRA"),
    "ETR": (".DE", ":de:", "XETRA"),
    "AS": (".AS", ":nl:", "AMS"),
    "NA": (".AS", ":nl:", "AMS"),
    "ST": (".ST", ":se:", "STO"),
    "SS": (".ST", ":se:", "STO"),
    "STO": (".ST", ":se:", "STO"),
    "TO": (".TO", ":ca:", "TSX"),
    "TSX": (".TO", ":ca:", "TSX"),
    "V": (".V", ":ca:", "TSXV"),
    "CVE": (".V", ":ca:", "TSXV"),
    "TSXV": (".V", ":ca:", "TSXV"),
    "STS": (".V", ":ca:", "TSXV"),
    "TSX-V": (".V", ":ca:", "TSXV"),
    "CN": ("", ":cn:", "US-ADR"),
    "KY": ("", ":ky:", "US"),
    "TW": ("", ":tw:", "US-ADR"),
    "CL": ("", ":cl:", "US-ADR"),
    "SN": (".SN", ":cl:", "SN"),
    "BCS": (".SN", ":cl:", "SN"),
    "NL": ("", ":nl:", "US"),
    "US": ("", ":us:", "US"),
    "UW": ("", ":us:", "NASDAQ"),
    "UN": ("", ":us:", "NYSE"),
    "NYSE": ("", ":us:", "NYSE"),
    "NASDAQ": ("", ":us:", "NASDAQ"),
    "AMEX": ("", ":us:", "AMEX"),
    "OTC": ("", ":us:", "OTC"),
}

MONTH_NAMES = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)


@dataclass
class DocBlock:
    index: int
    kind: str  # "heading", "list_item", "paragraph", "table_row"
    tag: str
    section: str
    text: str
    char_offset: int


class ExtractedCandidate(BaseModel):
    event_id: str = ""
    source_id: str
    source_type: Literal["article", "chat_thread", "chat_reply", "chat", "datawrapper", "table"]
    location: str
    char_offset: int = 0
    exact_text: str
    publication_date: str
    effective_date: str
    date_uncertainty: Optional[str] = None
    company_name: Optional[str] = None
    ticker: str
    normalized_ticker: str
    exchange: Optional[str] = None
    market: str = ":us:"
    instrument_type: Literal[
        "equity",
        "preferred",
        "etf",
        "mutual_fund",
        "short",
        "option_call",
        "option_put",
        "option_collar",
        "option_spread",
        "future",
    ] = "equity"
    action: Literal["BUY", "ADD", "TRIM", "SELL", "HOLD", "SHORT", "COVER", "HEDGE"]
    execution_status: Literal["confirmed", "proposed", "retrospective", "uncertain"]
    discovery_layer: Literal[
        "primary_realtime", "primary_article", "primary_chat", "primary_table", "checkpoint_review"
    ] = "primary_article"
    portfolio_book: Literal["primary", "model_etf", "personal_swing"] = "primary"
    stated_price: Optional[float] = None
    stated_currency: Optional[str] = None
    position_sizing: Optional[float] = None
    trim_fraction: Optional[float] = None
    confidence: Literal["high", "medium", "low"] = "high"
    notes: Optional[str] = ""
    unresolved_fields: list[str] = Field(default_factory=list)


def unpack_substack_widgets(body_html: str) -> str:
    """Replace empty Substack CashtagToDOM and StockTickerToDOM spans with explicit visible $TICKER text."""
    if not body_html:
        return ""

    def _replace_widget(match: re.Match[str]) -> str:
        tag_str = match.group(0)
        m_attrs = re.search(r'data-attrs=(["\'])(.*?)\1', tag_str, re.DOTALL)
        if not m_attrs:
            return tag_str
        try:
            attrs = json.loads(html.unescape(m_attrs.group(2)))
            sym = str(attrs.get("symbol") or attrs.get("ticker") or "").strip()
            if sym:
                if not sym.startswith("$"):
                    sym = f"${sym}"
                return f" {sym} "
        except Exception:
            pass
        return tag_str

    unpacked = re.sub(
        r'<span\b[^>]*data-component-name=["\'](?:CashtagToDOM|StockTicker[^"\']*)["\'][^>]*>.*?</span>',
        _replace_widget,
        body_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return unpacked


def preprocess_substack_html(body_html: str) -> tuple[str, list[DocBlock]]:
    """Unpack Substack widgets and parse HTML into section-aware structural blocks with char offsets."""
    unpacked = unpack_substack_widgets(body_html)
    if not unpacked.strip():
        return "", []

    soup = BeautifulSoup(unpacked, "html.parser")
    blocks: list[DocBlock] = []
    current_section = "Intro"
    running_offset = 0
    full_parts: list[str] = []

    # Walk top-level semantic elements without duplicating <p> inside <li>
    for el in soup.find_all(["h1", "h2", "h3", "h4", "li", "p", "tr"]):
        if el.name == "p" and el.find_parent(["li", "td", "th"]) is not None:
            continue
        txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
        if not txt:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            kind = "heading"
            current_section = txt[:120]
        elif el.name == "li":
            kind = "list_item"
        elif el.name == "tr":
            cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)).strip() for c in el.find_all(["th", "td"])]
            txt = " | ".join(c for c in cells if c)
            if not txt:
                continue
            kind = "table_row"
        else:
            kind = "paragraph"

        blk = DocBlock(
            index=len(blocks),
            kind=kind,
            tag=el.name,
            section=current_section,
            text=txt,
            char_offset=running_offset,
        )
        blocks.append(blk)
        full_parts.append(txt)
        running_offset += len(txt) + 1

    return "\n".join(full_parts), blocks


GENERIC_ALIAS_WORDS: set[str] = {
    "the", "and", "for", "with", "from", "into", "over", "under", "after", "before", "since", "while",
    "where", "when", "what", "which", "this", "that", "these", "those", "here", "there", "some", "more",
    "most", "many", "much", "very", "just", "only", "also", "even", "still", "back", "down", "well",
    "small", "large", "mid", "micro", "mega", "cap", "caps", "new", "old", "one", "two", "three", "four",
    "five", "first", "second", "third", "top", "best", "good", "great", "high", "low", "long", "short",
    "real", "pure", "core", "main", "deep", "value", "growth", "cheap", "boring", "flash", "quick",
    "brief", "weekly", "monthly", "annual", "daily", "quarter", "quarterly", "total", "net", "gross",
    "free", "paid", "open", "closed", "closing", "buying", "bought", "selling", "sold", "adding", "added",
    "trimming", "trimmed", "cutting", "reduced", "reducing", "exited", "exiting", "holding", "started", "initiated",
    "current", "existing", "recent", "initial", "final", "full", "half", "other", "another", "next",
    "last", "prior", "future", "global", "international", "national", "american", "united", "general",
    "pacific", "western", "eastern", "northern", "southern", "central", "modern", "standard", "premier",
    "prime", "alpha", "beta", "delta", "plus", "bank", "banks", "banking", "bancorp", "bancshares", "financial",
    "finance", "insurance", "insurers", "specialty", "capital", "asset", "assets", "wealth", "trust", "fund",
    "funds", "etf", "index", "basket", "portfolio", "portfolios", "svif", "usa", "korea", "korean", "japan",
    "japanese", "china", "chinese", "hong", "kong", "europe", "european", "british", "canadian", "australian",
    "argentina", "argentine", "chile", "chilean", "brazil", "brazilian", "taiwan", "taiwanese",
    "energy", "power", "electric", "electrical", "solar", "oil", "gas", "gold", "silver", "lithium", "mining",
    "metals", "steel", "tech", "technology", "technologies", "software", "cloud", "data", "digital", "cyber",
    "systems", "solutions", "services", "network", "networks", "media", "communications", "telecom", "health",
    "healthcare", "medical", "pharma", "pharmaceuticals", "biotech", "biosciences", "therapeutics", "semiconductor",
    "semiconductors", "infrastructure", "facilities", "equipment", "rentals", "food", "foods", "retail", "consumer",
    "brands", "properties", "property", "realty", "reit", "industrial", "industrials", "aerospace", "defense",
    "marine", "shipping", "logistics", "airlines", "motors", "auto", "automotive", "home", "homes", "building",
    "materials", "advanced", "water", "waste", "green", "clean", "blue", "black", "white", "red", "golden", "star",
    "crown", "bridge", "river", "mountain", "valley", "harbor", "bay", "coast", "island", "park", "square",
    "street", "point", "peak", "summit", "horizon", "pioneer", "frontier", "venture", "ventures", "partners",
    "advisors", "advisory", "management", "consulting", "enterprises", "industries", "investments", "investment",
    "trade", "trades", "trading", "stock", "stocks", "share", "shares", "position", "positions", "idea",
    "ideas", "pick", "picks", "update", "updates", "review", "reviews", "alert", "alerts", "report", "reports",
    "analysis", "thesis", "model", "tracker", "summary", "recap", "overview", "intro", "conclusion", "market",
    "markets", "winner", "winners", "loser", "losers", "target", "price", "prices", "margin", "margins", "revenue",
    "earnings", "dividend", "dividends", "preferred", "preferreds", "common", "options", "calls", "puts", "collar",
    "collars", "investor", "investors", "newsletter", "subscribers", "subscriber", "company", "companies", "business",
    "hyundai", "samsung", "lg", "sk", "lotus", "mitsubishi", "sumitomo", "mitsui", "china", "first", "citizens",
    "series", "santiago", "exchange", "class", "common", "ordinary", "sponsored",
    "supply", "chain", "chains", "demand", "services", "service", "systems", "system", "solutions", "network", "networks",
    "thought", "thoughts", "weekly", "monthly", "growing", "extreme", "comparable", "sales", "example", "current", "special", "feature",
}

NON_COMPANY_START_TOKENS: set[str] = {
    "i", "we", "you", "he", "she", "they", "it", "my", "our", "your", "his", "her", "their", "its",
    "the", "a", "an", "and", "or", "but", "so", "yet", "for", "nor", "in", "on", "at", "by", "to",
    "of", "from", "with", "into", "over", "under", "after", "before", "since", "while", "when", "where",
    "why", "how", "what", "which", "who", "if", "as", "than", "then", "here", "there", "this", "that",
    "these", "those", "both", "each", "some", "more", "most", "many", "much", "all", "any", "no", "not",
    "just", "only", "also", "even", "still", "already", "recently", "today", "tonight", "yesterday",
    "buy", "buying", "bought", "sell", "selling", "sold", "add", "adding", "added", "trim", "trimming",
    "trimmed", "close", "closing", "closed", "cut", "cutting", "exit", "exiting", "exited", "hold", "holding",
    "trade", "trades", "weekly", "monthly", "update", "alert", "review", "recap", "note", "notes", "execution",
}


def _clean_company_alias(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"^(?:long|short|buy|buying|sell|selling|closing|closed|new position:?|position increase:?|reduce|cut|added|remove)\s+", "", s)
    s = re.sub(r"^\d+[\.\)]\s*", "", s)
    s = re.sub(
        r"\b(?:inc\.?|corp\.?|corporation|ltd\.?|limited|plc|holdings?|group|co\.?|company|sa|nv|ag|se|ab|adr|ads|equity|common|stock|shares)\b",
        " ",
        s,
    )
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class SecurityResolver:
    """General-purpose international ticker normalizer and dynamic company-to-ticker co-reference resolver."""

    def __init__(self, prices: Optional[PriceProvider] = None) -> None:
        self.prices = prices
        # alias -> (normalized_ticker, market, exchange, display_name)
        self.alias_map: dict[str, tuple[str, str, str, str]] = {}
        # raw_base_symbol -> (normalized_ticker, market, exchange, display_name)
        self.known_symbols: dict[str, tuple[str, str, str, str]] = {}

    def normalize_symbol(
        self,
        raw_symbol: str,
        hint: Optional[str] = None,
        context_text: str = "",
    ) -> tuple[str, str, str]:
        """Normalize raw ticker + optional exchange/context hint into (normalized_yf_ticker, market_code, exchange)."""
        sym = raw_symbol.strip().lstrip("$").upper()
        sym = re.sub(r"[,;:!?]+$", "", sym)
        hint_u = (hint or "").strip().strip(":").upper()

        # Already carries explicit exchange suffix (e.g. 453340.KS, 013030.KQ, 285A.T, IFOS.V, CCV.AX, ABCA.PA, CTT.LS)
        for sfx, (yf_sfx, mkt, exch) in [
            (".KS", (".KS", ":kr:", "KRX")),
            (".KQ", (".KQ", ":kr:", "KOSDAQ")),
            (".T", (".T", ":jp:", "TSE")),
            (".HK", (".HK", ":hk:", "HKEX")),
            (".AX", (".AX", ":au:", "ASX")),
            (".L", (".L", ":uk:", "LSE")),
            (".IL", (".IL", ":uk:", "LSE-IOB")),
            (".PA", (".PA", ":fr:", "EPA")),
            (".LS", (".LS", ":pt:", "ELI")),
            (".DE", (".DE", ":de:", "XETRA")),
            (".F", (".F", ":de:", "FWB")),
            (".AS", (".AS", ":nl:", "AMS")),
            (".ST", (".ST", ":se:", "STO")),
            (".TO", (".TO", ":ca:", "TSX")),
            (".V", (".V", ":ca:", "TSXV")),
            (".SN", (".SN", ":cl:", "SN")),
        ]:
            if sym.endswith(sfx):
                base = sym[: -len(sfx)]
                if sfx == ".HK" and base.isdigit():
                    base = base.zfill(4)
                norm = f"{base}{yf_sfx}"
                if sfx in (".KS", ".KQ") and self.prices is not None:
                    resolved = self.prices.resolve_symbol(norm, market="kr")
                    if resolved in (f"{base}.KS", f"{base}.KQ"):
                        norm = resolved
                        exch = "KOSDAQ" if norm.endswith(".KQ") else "KRX"
                return norm, mkt, exch

        # Prefix or suffix colon exchange notation (e.g. LSE:CGEO, TSXV:IFOS, 8399:TYO, 3600:HKG)
        if ":" in sym:
            pfx, rest = sym.split(":", 1)
            if pfx in EXCHANGE_HINT_MAP and rest:
                sym = rest.strip()
                hint_u = pfx
            elif rest in EXCHANGE_HINT_MAP and pfx:
                sym = pfx.strip()
                hint_u = rest

        # Check explicit exchange hint
        if hint_u in EXCHANGE_HINT_MAP:
            yf_sfx, mkt, exch = EXCHANGE_HINT_MAP[hint_u]
            # Asian numeric exchanges (.KS, .KQ, .T, .HK) only apply suffixes to domestic numeric/TSE codes;
            # alphabetic symbols with country flags (e.g. KB with :kr:) are US-listed ADRs.
            if yf_sfx in (".KS", ".KQ") and not (sym.isdigit() and len(sym) == 6):
                return sym, mkt, "US-ADR"
            if yf_sfx == ".HK" and not sym.isdigit():
                return sym, mkt, "US-ADR"
            if yf_sfx == ".T" and not (sym.isdigit() or re.fullmatch(r"\d{3}[A-Z]", sym)):
                return sym, mkt, "US-ADR"
            if mkt == ":hk:" and sym.isdigit():
                sym = sym.zfill(4)
            norm = f"{sym}{yf_sfx}" if yf_sfx else sym
            if mkt == ":kr:" and sym.isdigit() and len(sym) == 6 and hint_u in ("KR", "KS") and self.prices is not None:
                resolved = self.prices.resolve_symbol(sym, market="kr")
                if resolved and resolved.endswith((".KS", ".KQ")):
                    return resolved, ":kr:", ("KOSDAQ" if resolved.endswith(".KQ") else "KRX")
            if mkt == ":ca:" and self.prices is not None and hint_u in ("CA", "TO", "TSX", "V", "TSXV", "CN"):
                resolved = self.prices.resolve_symbol(sym, market="ca")
                if resolved and resolved.endswith((".V", ".TO", "")):
                    return resolved, ":ca:", ("TSXV" if resolved.endswith(".V") else ("TSX" if resolved.endswith(".TO") else "US"))
            if mkt == ":cl:" and self.prices is not None and hint_u == "CL":
                resolved = self.prices.resolve_symbol(sym, market="cl")
                if resolved and resolved.endswith(".SN"):
                    return resolved, ":cl:", "SN"
            return norm, mkt, exch

        ctx_low = context_text.lower()
        if not raw_symbol.strip().startswith("$") and re.search(r"\bclp\b", ctx_low) and sym.isalpha():
            return f"{sym}.SN", ":cl:", "SN"

        # Check previously learned symbol in publication corpus
        if sym in self.known_symbols:
            n_sym, n_mkt, n_exch, _ = self.known_symbols[sym]
            return n_sym, n_mkt, n_exch

        # Alphanumeric Frankfurt GDR code (e.g. HY9H on Frankfurt Stock Exchange in EUR)
        if re.fullmatch(r"[A-Z]{2}\d[A-Z]", sym) and not re.fullmatch(r"(?:GDDR|DDR\d|B2B\d|S1\w+)", sym):
            if any(w in ctx_low for w in ("euro", "euros", "eur", "frankfurt", "fwb", "german", "gdr")) or (
                self.prices is not None and self.prices.resolve_symbol(f"{sym}.F", market="de")
            ):
                return f"{sym}.F", ":de:", "FWB"

        # 6-digit numeric -> Korean listing (.KS or .KQ verified via PriceProvider when available)
        if re.fullmatch(r"\d{6}", sym):
            if "kosdaq" in ctx_low or " kq" in ctx_low:
                return f"{sym}.KQ", ":kr:", "KOSDAQ"
            if self.prices is not None:
                resolved = self.prices.resolve_symbol(sym, market="kr")
                if resolved and resolved.endswith((".KS", ".KQ")):
                    return resolved, ":kr:", ("KOSDAQ" if resolved.endswith(".KQ") else "KRX")
            return f"{sym}.KS", ":kr:", "KRX"

        # 4-digit numeric or 3-digit+letter Japanese TSE code (e.g. 7089, 6626, 8399, 285A — excluding units like 400G, 800G, 401K, 100M, 100B)
        if re.fullmatch(r"\d{3}[A-Z]", sym) and not re.fullmatch(r"\d{3}[GKMBX]", sym):
            return f"{sym}.T", ":jp:", "TSE"
        if re.fullmatch(r"\d{4}", sym):
            if any(w in ctx_low for w in ("hk", "hong kong", "hkd", "hk$")):
                return f"{sym.zfill(4)}.HK", ":hk:", "HKEX"
            return f"{sym}.T", ":jp:", "TSE"

        # Contextual country cues for alphabetic international tickers
        if any(w in ctx_low for w in ("portugal", "lisbon", "correios", "correrios")):
            return f"{sym}.LS", ":pt:", "ELI"
        if any(w in ctx_low for w in ("tsxv", "tsx-v", "venture exchange")):
            return f"{sym}.V", ":ca:", "TSXV"
        if self.prices is not None and sym in self.prices.ticker_map:
            mapped = self.prices.ticker_map[sym]
            if mapped != sym:
                return self.normalize_symbol(mapped)

        return sym, ":us:", "US"

    def register_binding(
        self,
        company_name: str,
        raw_symbol: str,
        hint: Optional[str] = None,
        context_text: str = "",
    ) -> tuple[str, str, str]:
        norm_sym, mkt, exch = self.normalize_symbol(raw_symbol, hint=hint, context_text=context_text)
        base_sym = raw_symbol.strip().lstrip("$").upper().split(".")[0]
        clean_disp = re.sub(r"\s+", " ", company_name).strip(" -–—:,.()[]")
        if (
            base_sym in STOPWORD_ACRONYMS
            and base_sym not in VALID_TICKERS_DESPITE_OVERLAP
            and not raw_symbol.strip().startswith("$")
        ):
            return norm_sym, mkt, exch
        if base_sym and (base_sym not in STOPWORD_ACRONYMS or base_sym in VALID_TICKERS_DESPITE_OVERLAP):
            prev = self.known_symbols.get(base_sym)
            if prev is None or (prev[1] == ":us:" and mkt != ":us:"):
                self.known_symbols[base_sym] = (norm_sym, mkt, exch, clean_disp or norm_sym)
        self.known_symbols[norm_sym] = (norm_sym, mkt, exch, clean_disp or norm_sym)

        # Reject sentence fragments pretending to be company names
        raw_words = re.findall(r"[A-Za-z0-9&\'’-]+", clean_disp)
        if not raw_words or raw_words[0].lower() in NON_COMPANY_START_TOKENS:
            return norm_sym, mkt, exch
        if clean_disp.upper() == base_sym:
            return norm_sym, mkt, exch

        alias = _clean_company_alias(clean_disp)
        tokens = alias.split() if alias else []
        if tokens and tokens[0] not in NON_COMPANY_START_TOKENS:
            is_valid_full = False
            if len(tokens) == 1:
                if (
                    len(tokens[0]) >= 5
                    and tokens[0] not in GENERIC_ALIAS_WORDS
                    and tokens[0].upper() not in STOPWORD_ACRONYMS
                    and not tokens[0].isdigit()
                ):
                    is_valid_full = True
            elif 2 <= len(tokens) <= 5:
                non_generic = [t for t in tokens if t not in GENERIC_ALIAS_WORDS and not t.isdigit()]
                if non_generic or (
                    (raw_symbol.strip().startswith("$") or bool(hint) or base_sym.isdigit())
                    and len(alias) >= 6
                    and all(w[0].isupper() or w.lower() in ("of", "the", "&", "and", "de", "la") for w in raw_words if w)
                ):
                    if not any(t in ("newsletter", "subscribe", "subscribers", "tracker", "watchlist", "portfolio") for t in tokens):
                        is_valid_full = True

            if is_valid_full:
                self.alias_map[alias] = (norm_sym, mkt, exch, clean_disp)
                # Register distinctive non-generic proper-noun single word only on concise company names (<=3 tokens)
                if len(tokens) <= 3:
                    for tok in tokens:
                        if (
                            len(tok) >= 6
                            and tok not in GENERIC_ALIAS_WORDS
                            and tok not in NON_COMPANY_START_TOKENS
                            and tok.upper() not in STOPWORD_ACRONYMS
                            and not tok.isdigit()
                        ):
                            self.alias_map.setdefault(tok, (norm_sym, mkt, exch, clean_disp))
                            break
        return norm_sym, mkt, exch

    @staticmethod
    def _is_valid_4digit_stock_code(code: str, window_text: str, has_explicit_hint: bool) -> bool:
        if not re.fullmatch(r"\d{4}", code):
            return True
        val = int(code)
        if 1900 <= val <= 2040 and not has_explicit_hint:
            return False
        if has_explicit_hint:
            return True
        return bool(
            re.search(
                r"(?:\b(?:japan|japanese|yen|jpy|tokyo|tse|jt|jp|hk|hong\s+kong|hkd|nikkei|keiretsu)\b|¥)",
                window_text,
                re.IGNORECASE,
            )
        )

    def learn_from_text(self, text: str) -> None:
        """Scan document or chat text to learn explicit Company <-> Ticker bindings."""
        if not text:
            return

        # Pattern 1: Proper Company Name ($TICKER) / [ $TICKER ] / (453340 KS) / (LSE: CGEO) / (8399:TYO) / (HY9H)
        p1 = re.compile(
            r"\b([A-Z][A-Za-z0-9&.\'’-]+(?:\s+(?:of|the|de|la|&|[A-Z][A-Za-z0-9&.\'’-]+)){0,5})\s*"
            r"[\(\[]\s*(?:([A-Z]{2,6}(?:-[A-Z])?)\s*:\s*)?(\$?[A-Z]{1,5}(?:\.[A-Z]{1,2})?|[A-Z]{2}\d[A-Z]|\d{4,6}|\d{3}[A-Z])(?:\s+and\s+[A-Z0-9/]+)?"
            r"(?:\s*(?::|\s+)\s*(KS|KQ|JT|JP|TYO|TSE|HK|HKG|HKEX|AU|AX|LN|LSE|LI|IL|FP|EPA|PL|LS|DE|GR|F|FWB|ST|TO|V|SN|BCS|US))?(?:\s+Equity)?\s*[\)\]]"
        )
        for m in p1.finditer(text):
            cname, pfx_exch, raw_sym, sfx_exch = m.group(1), m.group(2), m.group(3), m.group(4)
            # Check if colon notation was TICKER:EXCHANGE (e.g. IFOS:TSX, AMG:AMS) rather than EXCHANGE:TICKER (e.g. LSE:CGEO)
            if pfx_exch and not sfx_exch:
                pfx_u = pfx_exch.upper()
                raw_u = raw_sym.upper()
                if (raw_u in EXCHANGE_HINT_MAP and pfx_u not in EXCHANGE_HINT_MAP) or (
                    raw_u in ("TSX", "TSXV", "AMS", "TYO", "TSE", "LSE", "EPA", "ELI", "XETRA", "FWB", "STO", "ASX", "KRX", "KOSDAQ", "HKEX")
                ):
                    raw_sym, pfx_exch = pfx_exch, raw_sym
            sym_clean = raw_sym.lstrip("$").upper()
            has_hint = bool(pfx_exch or sfx_exch)
            win = text[max(0, m.start() - 200): min(len(text), m.end() + 200)]
            if len(sym_clean) == 4 and sym_clean.isdigit() and not self._is_valid_4digit_stock_code(sym_clean, win, has_hint):
                continue
            if len(sym_clean) == 6 and sym_clean.isdigit() and not has_hint and not re.search(
                r"\b(?:korea|korean|kospi|kosdaq|krx|won|krw|ks|kq)\b", win, re.I
            ):
                continue
            if (
                sym_clean in STOPWORD_ACRONYMS
                and sym_clean not in VALID_TICKERS_DESPITE_OVERLAP
                and not raw_sym.startswith("$")
                and not has_hint
            ):
                continue
            if sym_clean in VALID_TICKERS_DESPITE_OVERLAP and len(sym_clean) == 1 and not raw_sym.startswith("$") and not has_hint:
                continue
            self.register_binding(cname, raw_sym, hint=(pfx_exch or sfx_exch), context_text=win)

        # Pattern 2: Company Name, $TICKER or Company Name - $TICKER (Substack unpacked cashtags)
        p2 = re.compile(
            r"\b([A-Z][A-Za-z0-9&.\'’-]+(?:\s+(?:of|the|&|[A-Z][A-Za-z0-9&.\'’-]+)){0,4})\s*[,-]\s*\$([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b"
        )
        for m in p2.finditer(text):
            self.register_binding(m.group(1), f"${m.group(2)}", context_text=m.group(0))

        # Pattern 3: Ticker + Exchange (Company Name) OR 285A (Kioxia) OR TICKER (Proper Multi-Word Company Name)
        p3 = re.compile(
            r"\b([A-Z]{2,5}|\d{4,6}|\d{3}[A-Z])(?:\s+(KS|KQ|JT|JP|TYO|HK|HKG|AU|LN|LI|FP|PL|LS|US))?(?:\s+Equity)?\s*"
            r"\(\s*([A-Z][A-Za-z0-9&.\'’-]+(?:\s+(?:of|the|&|[A-Z][A-Za-z0-9&.\'’-]+)){0,5})\s*\)"
        )
        for m in p3.finditer(text):
            raw_sym, ex_hint, cname = m.group(1), m.group(2), m.group(3)
            # If parenthetical content is a ticker/exchange code (e.g. MC FP, 453340 KS), this is Company (TICKER), not TICKER (Company)
            if re.match(
                r"^[A-Z0-9.]{1,6}(?:\s*:\s*|\s+)(?:KS|KQ|JT|JP|TYO|TSE|HK|HKG|HKEX|AU|AX|LN|LSE|LI|IL|FP|EPA|PL|LS|DE|GR|F|FWB|ST|TO|V|SN|BCS|US)$",
                cname.strip(),
            ):
                continue
            # Single-word parenthetical after alphabetic ticker requires exchange hint to avoid "EPS (Consensus)"
            if " " not in cname.strip() and raw_sym.isalpha() and not ex_hint:
                continue
            if raw_sym in STOPWORD_ACRONYMS and not ex_hint:
                continue
            win = text[max(0, m.start() - 160): min(len(text), m.end() + 160)]
            if len(raw_sym) == 4 and raw_sym.isdigit() and not self._is_valid_4digit_stock_code(raw_sym, win, bool(ex_hint)):
                continue
            if len(raw_sym) == 6 and raw_sym.isdigit() and not ex_hint and not re.search(
                r"\b(?:korea|korean|kospi|kosdaq|krx|won|krw|ks|kq)\b", win, re.I
            ):
                continue
            self.register_binding(cname, raw_sym, hint=ex_hint, context_text=win)

        # Pattern 4: Company Name - 8399 / Company Name, 453340 (explicit numeric international listing)
        p4 = re.compile(
            r"\b([A-Z][A-Za-z0-9&.\'’-]+(?:\s+(?:of|the|[A-Z][A-Za-z0-9&.\'’-]+)){0,4})\s*(?:[-–—]|,)\s*(\d{4}|\d{6}|\d{3}[ACDEFHIJLNOPQRSTUVWY])\b"
        )
        for m in p4.finditer(text):
            cname = m.group(1).strip()
            code = m.group(2).strip()
            win = text[max(0, m.start() - 200): min(len(text), m.end() + 200)]
            if len(code) == 4 and code.isdigit() and not self._is_valid_4digit_stock_code(code, win, False):
                continue
            if len(code) == 6 and code.isdigit() and not re.search(
                r"\b(?:korea|korean|kospi|kosdaq|krx|won|krw|ks|kq)\b", win, re.I
            ):
                continue
            self.register_binding(cname, code, context_text=win)

    def find_securities_in_clause(self, clause: str, fallback_context: str = "") -> list[tuple[str, str, str, str]]:
        """Extract ordered list of (normalized_ticker, market, exchange, company_name) mentioned in a clause."""
        found: list[tuple[str, str, str, str]] = []
        seen_norms: set[str] = set()
        bound_company_words: set[str] = set()

        def _add(norm: str, mkt: str, exch: str, cname: str) -> None:
            if norm not in seen_norms:
                seen_norms.add(norm)
                found.append((norm, mkt, exch, cname))

        # 1. Explicit $CASHTAG mentions (highest precision)
        for m in re.finditer(r"\$([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b", clause):
            raw = m.group(1)
            if raw.isdigit():
                continue
            norm, mkt, exch = self.normalize_symbol(raw, context_text=clause)
            cname = self.known_symbols.get(norm, (norm, mkt, exch, norm))[3]
            _add(norm, mkt, exch, cname)

        # 2. Explicit international ticker + exchange code: e.g. 402340 KS, 7089 JT, ABCA FP, CCV AU, 013030.KQ, 285A.T, IFOS.V, 8399:TYO
        for m in re.finditer(
            r"\b(\d{6}|\d{4}|\d{3}[A-Z]|[A-Z]{2}\d[A-Z]|[A-Z]{2,5})\.(KS|KQ|T|HK|AX|L|IL|PA|LS|DE|F|AS|ST|TO|V)\b",
            clause,
        ):
            norm, mkt, exch = self.normalize_symbol(f"{m.group(1)}.{m.group(2)}", context_text=clause)
            cname = self.known_symbols.get(norm, (norm, mkt, exch, norm))[3]
            _add(norm, mkt, exch, cname)

        for m in re.finditer(
            r"\b(\d{6}|\d{4}|\d{3}[A-Z]|[A-Z]{2}\d[A-Z]|[A-Z]{2,5})(?:\s*:\s*|\s+)(KS|KQ|JT|JP|TYO|TSE|HK|HKG|HKEX|AU|AX|LN|LSE|LI|IL|FP|EPA|PL|LS|F|FWB|STO|TSXV)(?:\s+Equity)?\b",
            clause,
        ):
            raw_s, ex_h = m.group(1), m.group(2)
            if raw_s in STOPWORD_ACRONYMS and not raw_s.isdigit():
                continue
            norm, mkt, exch = self.normalize_symbol(raw_s, hint=ex_h, context_text=clause)
            cname = self.known_symbols.get(norm, (norm, mkt, exch, norm))[3]
            _add(norm, mkt, exch, cname)

        # 3. Parenthetical or bracketed tickers: Company (TICKER) / Company [TICKER] / Company - 8399
        for m in re.finditer(
            r"([A-Z][A-Za-z0-9&.\'’-]+(?:\s+(?:of|the|&|[A-Z][A-Za-z0-9&.\'’-]+)){0,3})\s*[\(\[]\s*(?:([A-Z]{2,6})\s*:\s*)?(\$?[A-Z]{1,5}(?:\.[A-Z]{1,2})?|[A-Z]{2}\d[A-Z]|\d{4,6}|\d{3}[A-Z])(?:\s+and\s+[A-Z0-9/]+)?(?:\s*(?::|\s+)\s*(KS|KQ|JT|JP|TYO|HK|HKG|AU|LN|LI|FP|PL|LS|F|US))?\s*[\)\]]",
            clause,
        ):
            cname_raw, pfx_h, raw_s, sfx_h = m.group(1).strip(), m.group(2), m.group(3), m.group(4)
            sym_clean = raw_s.lstrip("$").upper()
            has_h = bool(pfx_h or sfx_h)
            if len(sym_clean) == 4 and sym_clean.isdigit() and not self._is_valid_4digit_stock_code(sym_clean, f"{clause} {fallback_context}", has_h):
                continue
            if len(sym_clean) == 6 and sym_clean.isdigit() and not has_h and sym_clean not in self.known_symbols and not re.search(
                r"\b(?:korea|korean|kospi|kosdaq|krx|won|krw|ks|kq)\b", f"{clause} {fallback_context}", re.I
            ):
                continue
            if (
                sym_clean in STOPWORD_ACRONYMS
                and sym_clean not in VALID_TICKERS_DESPITE_OVERLAP
                and not has_h
                and sym_clean not in self.known_symbols
            ):
                continue
            norm, mkt, exch = self.register_binding(cname_raw, raw_s, hint=(pfx_h or sfx_h), context_text=clause)
            for cw in re.findall(r"\b[A-Z]{2,5}\b", cname_raw):
                if cw != sym_clean:
                    bound_company_words.add(cw)
            _add(norm, mkt, exch, cname_raw)

        # 4. Bare 6-digit Korean codes, 3-digit+letter TSE codes (285A), GDR codes (HY9H), or 4-digit Japanese codes in JP/HK context
        for m in re.finditer(r"(?<![$,\d])\b(\d{6})\b(?![,\d])", clause):
            code = m.group(1)
            left = clause[max(0, m.start() - 15): m.start()].lower()
            if re.search(r"\b(?:at|around|near|below|above|over|under|won|krw|clp|ars)\s*$", left):
                continue
            if code not in self.known_symbols and not re.search(
                r"\b(?:korea|korean|kospi|kosdaq|krx|won|krw|ks|kq)\b", f"{clause} {fallback_context}", re.I
            ):
                continue
            norm, mkt, exch = self.normalize_symbol(code, context_text=clause)
            cname = self.known_symbols.get(norm, (norm, mkt, exch, norm))[3]
            _add(norm, mkt, exch, cname)

        for m in re.finditer(r"\b(\d{3}[ACDEFHIJLNOPQRSTUVWY]|[A-Z]{2}\d[A-Z])\b", clause):
            code = m.group(1)
            if code in self.known_symbols or re.fullmatch(r"\d{3}[ACDEFHIJLNOPQRSTUVWY]", code):
                norm, mkt, exch = self.normalize_symbol(code, context_text=f"{clause} {fallback_context}")
                if norm.endswith((".T", ".F", ".DE")) or code in self.known_symbols:
                    cname = self.known_symbols.get(norm, (norm, mkt, exch, norm))[3]
                    _add(norm, mkt, exch, cname)

        for m in re.finditer(r"(?<![$,.\d])\b(\d{4})\b(?![,.\d])", clause):
            code = m.group(1)
            left = clause[max(0, m.start() - 12): m.start()].lower()
            right = clause[m.end(): min(len(clause), m.end() + 12)].lower()
            if re.search(r"\b(?:in|since|from|by|year|fy|q[1-4]|at|around|near|below|above|clp|usd|eur)\s*$", left):
                continue
            if re.match(r"^\s*(?:earnings|consensus|estimate|guidance|revenue|ebitda|eps|m\b|b\b|k\b|%)", right):
                continue
            if code in self.known_symbols and self._is_valid_4digit_stock_code(code, f"{clause} {fallback_context}", True):
                # Require either Japanese/HK context OR explicit bank/basket list context if bare 4-digit
                if self._is_valid_4digit_stock_code(code, f"{clause} {fallback_context}", False) or re.search(
                    r"\b(?:banks?|basket|holdings?|8399|7167|7380|9478|3600)\b", clause, re.I
                ):
                    norm, mkt, exch = self.normalize_symbol(code, context_text=f"{clause} {fallback_context}")
                    cname = self.known_symbols.get(norm, (norm, mkt, exch, norm))[3]
                    _add(norm, mkt, exch, cname)
            elif re.search(r"\b[A-Z][A-Za-z]{2,}\s*(?:[-–—]\s*)?$", clause[max(0, m.start() - 25): m.start()]) and self._is_valid_4digit_stock_code(
                code, f"{clause} {fallback_context}", False
            ):
                norm, mkt, exch = self.normalize_symbol(code, context_text=f"{clause} {fallback_context}")
                cname = self.known_symbols.get(norm, (norm, mkt, exch, norm))[3]
                _add(norm, mkt, exch, cname)

        # 5. Preferred stock tickers (e.g. ACGLN, DCOMP, AGM-PG, AGM.PR.G, AGM-A, GNL-B)
        for m in re.finditer(r"\b([A-Z]{2,4}(?:-[A-Z]{1,2}|\.PR\.[A-Z]))\b", clause):
            raw_p = m.group(1)
            if not raw_p.startswith(("SQM-", "PRE-", "SUB-", "NON-", "MID-", "LOW-", "TOP-", "PRO-", "BUY-", "ONE-", "TWO-")):
                _add(raw_p, ":us:", "US", raw_p)

        # 6. Uppercase bare tickers in clause (either known in corpus OR directly adjacent to explicit trade action)
        for m in re.finditer(r"\b([A-Z]{2,5})\b", clause):
            tok = m.group(1)
            if tok in bound_company_words:
                continue
            if tok in self.known_symbols:
                if tok in (
                    "ALL", "ON", "IT", "NOW", "SO", "BE", "DO", "GO", "OR", "UP", "US", "COST", "EAT", "GAP",
                    "NET", "NEXT", "BEST", "OPEN", "REAL", "PLUS", "FAST", "PLAY", "WORK", "LOVE", "LIFE",
                    "TIME", "WELL", "CASH", "GOLD", "MIND", "AR", "ATZ", "FIX", "FB",
                ):
                    left = clause[max(0, m.start() - 28): m.start()]
                    right = clause[m.end(): min(len(clause), m.end() + 22)]
                    if not (
                        re.search(r"(?i:\b(?:buy|buying|bought|add\s+to|adding\s+to|added\s+to|sell|selling|sold|close|closing|closed|trim|trimming|trimmed|cut|cutting)\s+(?:the\s+)?)$", left)
                        or re.match(r"^\s+(?:position|shares|stock|at\s+\$?\d)", right, re.I)
                    ):
                        continue
                norm, mkt, exch, cname = self.known_symbols[tok]
                _add(norm, mkt, exch, cname)
            elif tok not in STOPWORD_ACRONYMS and tok.lower() not in GENERIC_ALIAS_WORDS:
                left = clause[max(0, m.start() - 48): m.start()]
                right = clause[m.end(): min(len(clause), m.end() + 30)]
                # Skip if tok is immediately followed by a titleword (e.g. ABC Arbitrage) or parenthetical ticker (e.g. LVMH (MC FP))
                if re.match(r"^\s+[A-Z][a-z]{2,}", right) or re.match(r"^\s*[\(\[]\s*(?:[A-Z0-9.]{1,6}(?:\s*:\s*|\s+)[A-Z]{2,4}|\$?[A-Z0-9.]{1,6})\s*[)\]]", right):
                    continue
                if (
                    re.search(
                        r"(?:^\s*|(?i:\b(?:trade\s+update\s+on|trade\s+alert\s+on|buy|buying|bought|am\s+long|long|add\s+to|adding\s+to|added\s+(?:to|a\s+little\s+more|some\s+more|more|a\s+bit\s+of)|picked\s+up|setup\s+for|allocated\s+\d+(?:\.\d+)?%\s+.*?\bto|initiated(?:\s+(?:a\s+)?(?:new\s+|smaller\s+|small\s+|starter\s+)?(?:position|short)\s+in)?|opened\s+(?:a\s+)?(?:new\s+|small\s+|starter\s+)?position\s+in|started\s+a\s+position\s+in|sell|selling|sold|close|closing(?:\s+out)?|closed(?:\s+out)?|sale\s+of|(?:trim|trimming|trimmed)(?:\s+(?:\d+(?:\.\d+)?%|\d+/\d+|half|a\s+third|a\s+quarter)\s+of)?|cut|cutting|stopped\s+out\s+of|exited|short|shorted|shorting|smaller\s+short\s+in|(?:puts?|calls?|collar)\s+on)\s+(?:some\s+|more\s+|the\s+|a\s+bit\s+of\s+)?)(?:[A-Z]{2,5}\s+(?:and|&|,)\s+)*)$",
                        left,
                    )
                    or re.match(r"^\s+(?:[-–—]\s*(?:Closing|Full\s+exit|Half\s+exit)|position\b|hit\s+stops?|stop\s+hit|was\s+stopped\s+out|has\s+been\s+cut|in\s+(?:the\s+)?(?:SVIF|USA|Canada|Portfolio))\b", right)
                ):
                    norm, mkt, exch = self.normalize_symbol(tok, context_text=clause)
                    _add(norm, mkt, exch, norm)

        # 7. Learned company name aliases (longest match first so "Hyundai Green Food" beats "Hyundai")
        clause_clean = f" {_clean_company_alias(clause)} "
        if len(clause_clean) > 3:
            for alias in sorted(self.alias_map.keys(), key=len, reverse=True):
                if len(alias) < 4:
                    continue
                if f" {alias} " in clause_clean:
                    norm, mkt, exch, cname = self.alias_map[alias]
                    _add(norm, mkt, exch, cname)

        # 8. Anaphoric fallback ("both", "all three", "in each", "purchased half my ideal position", "taking a third of the position off")
        if not found and fallback_context:
            low_c = clause.lower()
            if re.search(
                r"\b(?:small\s+positions?\s+in\s+both|both\s+positions|all\s+three|adding\s+to\s+all\s+of\s+them|position\s+in\s+each|"
                r"half\s+my\s+ideal\s+position|third\s+of\s+the\s+position|last\s+of\s+my\s+position|closing\s+(?:out\s+)?my\s+position|"
                r"closed\s+my\s+position|initiated\s+my\s+position|sized\s+my\s+position|add\s+to\s+my\s+position|"
                r"added\s+(?:a\s+bit|several\s+hundred\s+shares|some\s+more)\s+(?:here|today|last\s+night)|"
                r"bought\s+a\s+bit\s+last\s+night|picked\s+up\s+some\s+more\s+last\s+night|closed\s+tonight)\b",
                low_c,
            ):
                ctx_secs = self.find_securities_in_clause(fallback_context, fallback_context="")
                if re.search(r"\bboth\b", low_c):
                    found.extend(ctx_secs[:2])
                elif re.search(r"\b(?:all\s+three|all\s+of\s+them|in\s+each)\b", low_c):
                    found.extend(ctx_secs[:3])
                elif ctx_secs:
                    found.append(ctx_secs[-1])

        return found


class ExtractionEngine:
    """General-purpose Layer A primary extraction pipeline across articles, tables, and nested chat threads."""

    def __init__(
        self,
        settings: Settings,
        prices: Optional[PriceProvider] = None,
        cache_dir: Optional[Path] = None,
    ) -> None:
        self.settings = settings
        self.prices = prices or PriceProvider(settings)
        self.cache_dir = cache_dir or (settings.data_dir / "extraction_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.resolver = SecurityResolver(prices=self.prices)
        self.known_shorts: set[str] = set()
        self.llm_enabled = os.getenv("BTT_ENABLE_LLM_EXTRACTION", "0").strip() in ("1", "true", "yes")

    @staticmethod
    def _hash_content(text: str) -> str:
        return hashlib.sha256(f"{EXTRACTOR_VERSION}::{text}".encode("utf-8")).hexdigest()

    def _normalize_ticker_market(self, symbol: str, hint: Optional[str] = None, context: str = "") -> tuple[str, str]:
        """Compatibility helper returning (normalized_ticker, market_code)."""
        norm, mkt, _ = self.resolver.normalize_symbol(symbol, hint=hint, context_text=context)
        # Keep backwards-compatible ':eu:' alias only when caller specifically expects FP -> :fr:/:eu:
        return norm, mkt

    @staticmethod
    def _parse_verbal_date(raw_date: str, default_year: str = "2026") -> Optional[str]:
        s = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", raw_date.strip())
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
        if not re.search(r"\b\d{4}\b", s):
            s_with_yr = f"{s}, {default_year}"
        else:
            s_with_yr = s
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%m/%d/%Y", "%m/%d"):
            try:
                if fmt == "%m/%d":
                    dt = datetime.strptime(f"{s}/{default_year}", "%m/%d/%Y")
                else:
                    dt = datetime.strptime(s_with_yr, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        parsed = pd.to_datetime(s_with_yr, errors="coerce")
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")
        return None

    @staticmethod
    def _extract_price_and_currency(text: str, market: str = ":us:") -> tuple[Optional[float], Optional[str]]:
        # Explicit $ price (avoid $5k / $10M / $30 Billion position or market cap amounts)
        m_usd = re.search(
            r"(?:\bat\b|\baround\b|\bnear\b|@)\s*\$\s*([0-9]{1,5}(?:,[0-9]{3})*(?:\.[0-9]{1,4})?)\b(?!\s*(?:k|m|b|t|thousand|million|billion|trillion|%))",
            text,
            re.IGNORECASE,
        )
        if m_usd:
            return float(m_usd.group(1).replace(",", "")), "USD"

        # Korean Won / Japanese Yen / Euro / numeric "at 828000" / "at 858k" / "in the 19,000's" / "at 12,420"
        m_k = re.search(r"\bat\s+([0-9]{2,4}(?:\.[0-9]+)?)\s*k\b", text, re.IGNORECASE)
        if m_k and market == ":kr:":
            return float(m_k.group(1)) * 1000.0, "KRW"

        m_range = re.search(r"\bin\s+the\s+([0-9]{1,3}(?:,[0-9]{3})+)[’\']?s\b", text, re.IGNORECASE)
        if m_range:
            val = float(m_range.group(1).replace(",", ""))
            curr = "KRW" if market == ":kr:" else ("JPY" if market == ":jp:" else None)
            return val, curr

        m_at_num = re.search(
            r"\bat\s+([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{2,7}(?:\.[0-9]{1,2})?)\b(?!\s*(?:%|bps|x|times|shares|million|billion))",
            text,
            re.IGNORECASE,
        )
        if m_at_num:
            val = float(m_at_num.group(1).replace(",", ""))
            curr = {"kr": "KRW", "jp": "JPY", "uk": "GBP", "fr": "EUR", "pt": "EUR", "ca": "CAD", "au": "AUD", "hk": "HKD"}.get(
                market.strip(":"), "USD"
            )
            return val, curr

        return None, None

    @staticmethod
    def _extract_sizing_and_trim(text: str) -> tuple[Optional[float], Optional[float]]:
        low = text.lower()
        sizing: Optional[float] = None
        trim_frac: Optional[float] = None

        # Weight transition: "from 11% -> 8.5%" or "from 3.95% -> 5.95%"
        m_trans = re.search(r"from\s+(\d+(?:\.\d+)?)\s*%\s*(?:->|to|→)\s*(\d+(?:\.\d+)?)\s*%", low)
        if m_trans:
            w_old = float(m_trans.group(1)) / 100.0
            w_new = float(m_trans.group(2)) / 100.0
            sizing = w_new
            if w_old > w_new > 0:
                trim_frac = round((w_old - w_new) / w_old, 4)
            return sizing, trim_frac

        # Basis points: "25 bps", "50bps"
        m_bps = re.search(r"\b(\d+(?:\.\d+)?)\s*bps\b", low)
        if m_bps:
            sizing = float(m_bps.group(1)) / 10000.0

        # Percentage weight: "0.25% buy", "at 0.25%", "3.5% weight", "3.5% of the portfolio", "half a percent"
        if sizing is None:
            if "half a percent" in low:
                sizing = 0.005
            else:
                m_wt = re.search(
                    r"\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:weight|position|allocation|buy|starter|of\s+(?:the\s+)?portfolio)",
                    low,
                )
                if not m_wt:
                    m_wt = re.search(r"(?:at|around|roughly)\s+(\d{1,2}(?:\.\d+)?)\s*%(?!\s*(?:gain|loss|return|up|down|yield))", low)
                if m_wt:
                    val = float(m_wt.group(1))
                    if 0 < val <= 35.0:
                        sizing = val / 100.0

        # Explicit fractional trims
        m_pct_trim = re.search(r"\b(?:trimmed|trimming|cut|cutting)\s+(\d{1,2}(?:\.\d+)?)\s*%", low)
        if m_pct_trim and 0 < float(m_pct_trim.group(1)) < 100:
            trim_frac = round(float(m_pct_trim.group(1)) / 100.0, 4)
        elif any(p in low for p in ("in half", "cut 50%", "50% trim", "half exit", "half of my position", "half the position", "trimmed half")):
            trim_frac = 0.50
        elif any(p in low for p in ("two thirds", "2/3")):
            trim_frac = 2.0 / 3.0
        elif any(p in low for p in ("a third", "1/3", "one third")):
            trim_frac = 1.0 / 3.0
        elif any(p in low for p in ("a quarter", "1/4", "25% of")):
            trim_frac = 0.25

        return sizing, trim_frac

    def _detect_instrument_type(self, text: str, symbol: str) -> Literal[
        "equity", "preferred", "etf", "mutual_fund", "short", "option_call", "option_put", "option_collar", "option_spread", "future"
    ]:
        low = text.lower()
        # Option / collar / spread patterns
        if re.search(r"\b(?:collar|collared|collaring|re-collar)\b", low):
            return "option_collar"
        if re.search(r"\b(?:butterfly|put\s+spread|call\s+spread|straddle|strangle|box\s+spreads?)\b", low):
            return "option_spread"
        if re.search(
            r"\b(?:\d+\s+strike\s+puts?|protective\s+puts?|bought\s+(?:a\s+|some\s+)?puts?|sold\s+.*?\s+puts?|"
            r"closing\s+(?:out\s+)?(?:the\s+)?(?:\d+\s+puts?|protection)|put\s+options?\s+for\s+income|"
            r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d+\s+puts?|\b\d+\s+puts\b)\b",
            low,
        ):
            return "option_put"
        if re.search(
            r"\b(?:\d+\s+strike\s+calls?|covered\s+calls?|short\s+calls?|bought\s+(?:a\s+|some\s+)?calls?|"
            r"selling\s+[a-z0-9]+\s+calls|\d+[’\']?s\s+and\s+\d+[’\']?s\s+calls|\bleaps\b|"
            r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d+[’\']?s?\s+calls?)\b",
            low,
        ):
            return "option_call"

        # Short sale / short basket detection (including publication-tracked active short positions unless explicitly going long)
        if re.search(
            r"\b(?:short\s+[A-Z]|shorting\b|shorted\b|short\s+position|short\s+basket|initiation\s+of\s+a\s+short|"
            r"added\s+to\s+(?:my\s+|the\s+)?.*?\s*short|initiated\s+a\s+short|remain\s+short|am\s+also\s+short|"
            r"smaller\s+short\s+in)\b",
            text,
            re.IGNORECASE,
        ):
            self.known_shorts.add(symbol)
            return "short"

        if symbol in self.known_shorts and not re.search(r"\b(?:went\s+long|go\s+long|long\s+position)\b", low):
            return "short"

        # Preferred shares
        if re.search(r"\bpreferred(?:s|\s+shares|\s+stock)?\b", low) or re.match(r"^[A-Z]{2,4}(?:-[A-Z]{1,2}|\.PR\.[A-Z])$", symbol) or symbol in ("ACGLN", "DCOMP", "MBINL"):
            return "preferred"

        # Mutual funds (5-letter ending in X like BARAX)
        if len(symbol) == 5 and symbol.endswith("X") and "." not in symbol and any(w in low for w in ("fund", "nav", "mutual", "arbitrage")):
            return "mutual_fund"

        return "equity"

    @staticmethod
    def _split_into_atomic_clauses(text: str) -> list[str]:
        """Split compound multi-trade paragraphs/messages into atomic clauses while preserving entity context."""
        if not text:
            return []
        # Extract inline parenthetical trade updates like:
        # "... and SE Holdings And Incubations barreling back towards 500 (picked up some more last night, earnings next week)"
        # by rewriting "Entity ... (picked up ...)" into a separate sentence with the immediately preceding clause tail!
        expanded_lines: list[str] = []
        raw_lines = re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z0-9\"'“‘\[-])", text)
        paren_trade_re = re.compile(
            r"([^,;()]+?)\s*\(([^()]*\b(?:picked\s+up|i\s+bought|bought\s+more|added\s+to|i\s+trimmed|i\s+sold|i\s+closed)\b[^()]*)\)",
            re.IGNORECASE,
        )
        for rl in raw_lines:
            rl = rl.strip()
            if not rl:
                continue
            m_pt = paren_trade_re.search(rl)
            if m_pt:
                lead_entity = m_pt.group(1).strip()
                aside = m_pt.group(2).strip()
                cleaned_main = (rl[: m_pt.start(2) - 1] + rl[m_pt.end(2) + 1 :]).strip()
                if cleaned_main:
                    expanded_lines.append(cleaned_main)
                expanded_lines.append(f"{lead_entity}: {aside}")
            else:
                expanded_lines.append(rl)

        clauses: list[str] = []
        for line in expanded_lines:
            # Handle multi-entity header alerts like:
            # "Trade Update on Kioxia (Closed) and GoDaddy (Closing Later Today):"
            m_dual_hdr = re.match(
                r"^Trade\s+Update\s+on\s+([A-Za-z0-9\s.&'-]+?)\s*\((Closed|Closing[^)]*)\)\s+and\s+([A-Za-z0-9\s.&'-]+?)\s*\((Closed|Closing[^)]*)\)",
                line,
                re.IGNORECASE,
            )
            if m_dual_hdr:
                clauses.append(f"Trade Update on {m_dual_hdr.group(1).strip()} ({m_dual_hdr.group(2).strip()})")
                clauses.append(f"Trade Update on {m_dual_hdr.group(3).strip()} ({m_dual_hdr.group(4).strip()})")
                continue

            # Split compound coordinate & contrast trade clauses:
            # - "Closed SYF at 52% gain and trimmed a bit more DELL"
            # - "Buy DXPE and close NTGR" / "Closing IAG Position, Initiating NGD Position"
            # - "significantly reducing CBL and initating smaller positions in..."
            # - "added a bit to HRTG, the stock trades wildly... peers like HCI..."
            sub_parts = re.split(
                r"(?:,\s*but\s+|,\s*(?=the\s+(?:stock|only|company)\b)|,\s*|\s+and\s+|\s+to\s+(?=make\s+room\s+for\b)|\s*;\s*|\s+[-–—]\s+(?=tonight\s+i\b))(?=(?:(?:i|we)\s+(?:am|are|have|will\s+be|bought|added|trimmed|closed|sold|cut)\b|the\s+(?:stock|only)\b|totally\s+|am\s+also\s+(?:looking|short)\b|continue\s+to\s+remain|[A-Z][a-z]+\s+will\s+continue\s+|redeploying\b|make\s+room\s+for\b|put\s+the\s+proceeds\s+into\b|initiat(?:e|ing|ed)\b|initating\b|(?:buy|bought|buying|add|added|adding|increased|increasing|picked\s+up|start|started|starting|trimmed|trimming|cut|cutting|reduce|reduced|reducing|close|closed|closing|sell|sold|selling|exit|exited|exiting|shorted|shorting))\b)",
                line,
                flags=re.IGNORECASE,
            )
            for sp in sub_parts:
                sp_clean = sp.strip(" ,;-")
                if sp_clean:
                    clauses.append(sp_clean)
        return clauses

    def classify_clause(
        self,
        clause: str,
        pub_date: str,
        source_id: str = "inline",
        source_type: Literal["article", "chat_thread", "chat_reply", "chat", "datawrapper", "table"] = "article",
        location: str = "body",
        char_offset: int = 0,
        fallback_context: str = "",
        section_heading: str = "",
        include_non_confirmed: bool = False,
    ) -> list[ExtractedCandidate]:
        """Core production clause classifier shared by archive extraction AND benchmark tests."""
        raw = clause.strip()
        if not raw or len(raw) < 3:
            return []
        low = raw.lower()
        pub_day = pub_date[:10] if len(pub_date) >= 10 else "2026-01-01"
        default_yr = pub_day[:4] if re.match(r"^\d{4}", pub_day) else "2026"

        # Pre-scan explicit short basket mentions so short tickers are remembered across the publication
        if re.search(r"\b(?:remain\s+short|am\s+also\s+short|short\s+basket|smaller\s+short\s+in)\b", low):
            for s_norm, _, _, _ in self.resolver.find_securities_in_clause(raw):
                self.known_shorts.add(s_norm)

        # 0. Reject subscriber questions or pure interrogatives unless explicit "Trade Update ... (Closed)"
        if "?" in raw and not re.search(r"\b(?:trade\s+update|trade\s+alert|just\s+bought|i\s+sold|closing\s+out)\b", low):
            return []
        if low.startswith(("do you think", "what is your", "hi ", "hello ", "hey ", "dear ", "matt,", "george,", "tim,")):
            if not re.search(r"\b(?:trade\s+alert|april\s+trade|i\s+closed|so\s+i\s+closed|closing\s+opfi)\b", low):
                return []

        # Reject third-party / corporate business ops / M&A / software features / reader hypotheticals
        if re.search(
            r"\b(?:insider\s+was\s+selling|ceo\s+was\s+buying|founder\s+is\s+(?:currently\s+)?selling|widow.*selling|"
            r"who\s+purchased\s+shares\s+on\s+the\s+open\s+market|private\s+equity\s+firm\s+that\s+bought|"
            r"third-party\s+resellers\s+selling|bought\s+a\s+(?:second\s+)?large\s+piece\s+of\s+land|bought\s+a\s+plane\s+ticket|"
            r"bought\s+my\s+first\s+graphics\s+card|university\s+dorm|"
            r"repurchasing\s+[\d,]+\s+shares|share\s+repurchases|market\s+sold\s+off|stocks?\s+sold\s+off|"
            r"shutting\s+down\s+the\s+equity\s+strategy|taconic\s+capital|"
            r"dip\s+buyers|retail\s+investors|if\s+a\s+friend\s+of\s+yours|if\s+i\s+(?:buy|want\s+to\s+buy)\s+[a-z]+\b|let[’\']s\s+say\s+it\s+is\s+trading|"
            r"you\s+could\s+buy|if\s+you\s+(?:buy|want|own|have\s+fewer|haven[’\']t)|better\s+off\s+(?:just\s+)?buying|"
            r"a\s+lot\s+of\s+people\s+(?:just\s+)?buy|wouldn[’\']t\s+fault\s+you|should\s+have\s+(?:just\s+)?bought|"
            r"margin\s+added\s+to|charge\s+added\s+to|deal\s+added\s+more|value-added\s+services|"
            r"added\s+(?:a\s+|the\s+)?[a-z0-9\s-]{1,35}\b(?:function|feature|spread|metric|tab|tool|chart)\s+(?:on|to)\b|rankedstocks|"
            r"added\s+(?:more\s+than\s+)?\d+\s+(?:beds|stores|jobs|projects|mw|gw|units)|added\s+several\s+jobs|"
            r"(?:closing|shrinking)\s+(?:or\s+shrinking\s+)?(?:expensive\s+)?(?:onshore\s+)?(?:sites|stores|plants|branches|offices)|"
            r"value\s+cut\s+in\s+half\s+overnight|"
            r"added\s+to\s+(?:the\s+)?(?:nasdaq|s&p|russell|index|benchmark)|pff[’\']s\s+benchmark|"
            r"added\s+a\s+(?:living\s+)?watchlist|added\s+the\s+portfolio\s+performance|adding\s+to\s+the\s+fund\s+over\s+time|"
            r"contribution.*?\badded\s+\d+\s*bps|buying\s+[a-z0-9\s]+\s+in\s+202\d\s+lets\b|"
            r"received\s+the\s+shares\s+as\s+an\s+exchange|year\s+closed\s+with|closed\s+\d+\s+new\s+client|"
            r"closed\s+in\s+\d+\s+months|closing\s+the\s+(?:discount|gap)|closed\s+the\s+(?:hbm\s+|valuation\s+)?gap|"
            r"market\s+closed\s+the\s+gap|closed\s+the\s+book\s+on\s+a\s+loan|"
            r"picked\s+up\s+(?:steam|momentum|pace|the\s+slack|the\s+orphaned|atsc)|chatter\s+picked\s+up|growth.*?\bpicked\s+up|"
            r"adding\s+more\s+postpaid|adding\s+customers|"
            r"trimming\s+(?:some\s+)?(?:low-margin|domestic\s+revenue|expenses|costs|headcount)|"
            r"candidate\s+for\s+trimming|once\s+a\s+month,\s+i\s+will\s+send)\b",
            low,
        ):
            return []

        # Strip negative-contrast clauses cleanly:
        # - Leading "Rather than slash..., tonight I cut..." -> keep main clause after dash/comma
        # - Trailing "bought X rather than Y" / "... to my AI Infrastructure Basket - IES, ..." -> keep main clause before contrast/basket list
        if re.match(r"^(?:rather\s+than|instead\s+of)\b", low):
            parts_lead = re.split(r"(?:\s+[-–—]\s+|,\s*(?=(?:i|we|tonight|today)\b))", raw, maxsplit=1, flags=re.IGNORECASE)
            raw = parts_lead[1].strip() if len(parts_lead) > 1 else ""
        else:
            raw = re.split(
                r"\b(?:rather\s+than|instead\s+of|as\s+opposed\s+to|looking\s+forward\s+to|and\s+just\s+monitoring|"
                r"with\s+(?:some\s+of\s+)?the\s+proceeds\s+from)\b"
                r"|\s+to\s+my\s+[A-Za-z0-9\s]+\s+Basket\s*[-–—:]",
                raw,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
        low = raw.lower()
        if not raw:
            return []

        # 1. Structured Review Recaps: Removals ("1. CBL Properties (CBL) +114% - Exited September 15" / "MCHB US (Merchants Bancorp) - Total Return -5% - Closed April 10")
        m_rev_rem1 = re.match(
            r"^(?:(?:\d+\.|\*|-)\s*)?(Short\s+)?([A-Za-z0-9\s&.,\'’-]+?)\s*\(([A-Z0-9/,\sand.-]+)\)\s*(?:[+-]?\d+(?:\.\d+)?%)?\s*[-–—]\s*(?:Exited|Closed)\s+([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)(?:\s+[Vv]ia\s+([A-Za-z\s]+))?",
            raw,
            re.IGNORECASE,
        )
        if m_rev_rem1:
            is_short = bool(m_rev_rem1.group(1))
            cname = m_rev_rem1.group(2).strip()
            sym_tokens = m_rev_rem1.group(3).strip().split()
            raw_sym = sym_tokens[0].split("/")[0]
            hint = sym_tokens[1] if len(sym_tokens) > 1 and sym_tokens[1].upper() in EXCHANGE_HINT_MAP else None
            eff_dt = self._parse_verbal_date(m_rev_rem1.group(4), default_year=default_yr) or pub_day
            via = (m_rev_rem1.group(5) or "").lower()
            norm_sym, mkt, exch = self.resolver.register_binding(cname, raw_sym, hint=hint, context_text=raw)
            if is_short:
                self.known_shorts.add(norm_sym)
            inst = "short" if is_short else ("option_collar" if "option" in via else "equity")
            return [
                ExtractedCandidate(
                    source_id=source_id,
                    source_type=source_type,
                    location=location,
                    char_offset=char_offset,
                    exact_text=raw,
                    publication_date=pub_day,
                    effective_date=eff_dt,
                    company_name=cname,
                    ticker=raw_sym,
                    normalized_ticker=norm_sym,
                    exchange=exch,
                    market=mkt,
                    instrument_type=inst,
                    action="COVER" if is_short else "SELL",
                    execution_status="confirmed",
                    discovery_layer="checkpoint_review",
                    trim_fraction=1.0,
                    confidence="high",
                    notes=f"Review removal disclosure ({raw[:120]})",
                )
            ]

        m_rev_rem2 = re.match(
            r"^(?:(?:\d+\.|\*|-)\s*)?([A-Z0-9]{1,6})\s+([A-Z]{2})\s*\(([^)]+)\)\s*[-–—]\s*Total\s+Return\s*(?:[+-]?\d+(?:\.\d+)?%)?\s*[-–—]\s*(?:Closed|Exited)\s+([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)",
            raw,
            re.IGNORECASE,
        )
        if m_rev_rem2:
            raw_sym, mkt_code, cname, raw_dt = (
                m_rev_rem2.group(1).upper(),
                m_rev_rem2.group(2).upper(),
                m_rev_rem2.group(3).strip(),
                m_rev_rem2.group(4).strip(),
            )
            eff_dt = self._parse_verbal_date(raw_dt, default_year=default_yr) or pub_day
            norm_sym, mkt, exch = self.resolver.register_binding(cname, raw_sym, hint=mkt_code, context_text=raw)
            return [
                ExtractedCandidate(
                    source_id=source_id,
                    source_type=source_type,
                    location=location,
                    char_offset=char_offset,
                    exact_text=raw,
                    publication_date=pub_day,
                    effective_date=eff_dt,
                    company_name=cname,
                    ticker=raw_sym,
                    normalized_ticker=norm_sym,
                    exchange=exch,
                    market=mkt,
                    instrument_type="equity",
                    action="SELL",
                    execution_status="confirmed",
                    discovery_layer="checkpoint_review",
                    trim_fraction=1.0,
                    confidence="high",
                    notes=f"Review closed trade recap ({raw[:120]})",
                )
            ]

        # 2. Structured Review Recaps: Additions ("1. GoDaddy (GDDY US) - Added September 21" / "Short JPMorgan (JPM US) - Added September 28")
        m_rev_add = re.match(
            r"^(?:(?:\d+\.|\*|-)\s*)?(Short\s+)?([A-Za-z0-9\s&.,\'’-]+?)\s*\(([A-Z0-9/,\sand.-]+)\)\s*[-–—]\s*Added\s+([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)",
            raw,
            re.IGNORECASE,
        )
        if m_rev_add:
            is_short = bool(m_rev_add.group(1))
            cname = m_rev_add.group(2).strip()
            sym_tokens = m_rev_add.group(3).strip().split()
            raw_sym = sym_tokens[0].split("/")[0]
            hint = sym_tokens[1] if len(sym_tokens) > 1 and sym_tokens[1].upper() in EXCHANGE_HINT_MAP else None
            eff_dt = self._parse_verbal_date(m_rev_add.group(4), default_year=default_yr) or pub_day
            norm_sym, mkt, exch = self.resolver.register_binding(cname, raw_sym, hint=hint, context_text=raw)
            if is_short:
                self.known_shorts.add(norm_sym)
            return [
                ExtractedCandidate(
                    source_id=source_id,
                    source_type=source_type,
                    location=location,
                    char_offset=char_offset,
                    exact_text=raw,
                    publication_date=pub_day,
                    effective_date=eff_dt,
                    company_name=cname,
                    ticker=raw_sym,
                    normalized_ticker=norm_sym,
                    exchange=exch,
                    market=mkt,
                    instrument_type="short" if is_short else self._detect_instrument_type(raw, norm_sym),
                    action="SHORT" if is_short else "BUY",
                    execution_status="confirmed",
                    discovery_layer="checkpoint_review",
                    confidence="high",
                    notes=f"Review addition disclosure ({raw[:120]})",
                )
            ]

        # 3. Direct structured commands / headings: "BUY SYM (Company)", "POWL - Closing Powell Position", "Trade Update - Name (SYM) Closing Out"
        m_sec_hdr = re.match(
            r"^([A-Z]{2,5})\s*[-–—]\s*(Closing|Full\s+exit|Half\s+exit)\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if m_sec_hdr:
            raw_sym = m_sec_hdr.group(1).upper()
            kind_h = m_sec_hdr.group(2).lower()
            rest_h = m_sec_hdr.group(3)
            norm_sym, mkt, exch = self.resolver.normalize_symbol(raw_sym, context_text=raw)
            inst_h = self._detect_instrument_type(raw, norm_sym)
            act_h: Literal["SELL", "TRIM", "HEDGE", "COVER"] = (
                "HEDGE"
                if inst_h.startswith("option")
                else ("COVER" if inst_h == "short" else ("TRIM" if "half" in kind_h else "SELL"))
            )
            return [
                ExtractedCandidate(
                    source_id=source_id,
                    source_type=source_type,
                    location=location,
                    char_offset=char_offset,
                    exact_text=raw,
                    publication_date=pub_day,
                    effective_date=pub_day,
                    company_name=self.resolver.known_symbols.get(norm_sym, (norm_sym, mkt, exch, rest_h[:40]))[3],
                    ticker=raw_sym,
                    normalized_ticker=norm_sym,
                    exchange=exch,
                    market=mkt,
                    instrument_type=inst_h,
                    action=act_h,
                    execution_status="confirmed",
                    discovery_layer="primary_chat" if "chat" in source_type else "primary_article",
                    trim_fraction=1.0 if act_h == "SELL" else (self._extract_sizing_and_trim(raw)[1] or (0.50 if act_h == "TRIM" else None)),
                    confidence="high",
                    notes=raw[:140],
                )
            ]

        m_direct = re.match(r"^(?i:BUY|SELL|TRIM)\s+(\$[A-Za-z0-9.]{1,8}|[A-Z0-9.]{2,8})\b(?:\s*\(([^)]+)\))?", raw)
        if m_direct:
            act_u = raw.split()[0].upper()
            raw_sym = m_direct.group(1).lstrip("$").upper()
            if raw_sym not in STOPWORD_ACRONYMS and raw_sym.lower() not in GENERIC_ALIAS_WORDS:
                cname = (m_direct.group(2) or raw_sym).strip()
                norm_sym, mkt, exch = self.resolver.register_binding(cname, raw_sym, context_text=raw)
                return [
                    ExtractedCandidate(
                        source_id=source_id,
                        source_type=source_type,
                        location=location,
                        char_offset=char_offset,
                        exact_text=raw,
                        publication_date=pub_day,
                        effective_date=pub_day,
                        company_name=cname,
                        ticker=raw_sym,
                        normalized_ticker=norm_sym,
                        exchange=exch,
                        market=mkt,
                        instrument_type="equity",
                        action=act_u,  # type: ignore[arg-type]
                        execution_status="confirmed",
                        discovery_layer="primary_article",
                        confidence="high",
                        notes=raw[:140],
                    )
                ]

        m_long_hd = re.match(
            r"^(?:Idea\s*\d*\s*:\s*)?(Long|Short)\s+([A-Z0-9]{1,6})\s+(KS|KQ|JT|JP|AU|AX|US|LN|LSE|FP|PL|LS|HK)(?:\s+Equity)?(?:\s*\(([^)]+)\))?",
            raw,
            re.IGNORECASE,
        )
        if m_long_hd:
            side = m_long_hd.group(1).upper()
            raw_sym = m_long_hd.group(2).upper()
            hint = m_long_hd.group(3).upper()
            cname = (m_long_hd.group(4) or raw_sym).strip()
            norm_sym, mkt, exch = self.resolver.register_binding(cname, raw_sym, hint=hint, context_text=raw)
            is_short = side == "SHORT"
            if is_short:
                self.known_shorts.add(norm_sym)
            return [
                ExtractedCandidate(
                    source_id=source_id,
                    source_type=source_type,
                    location=location,
                    char_offset=char_offset,
                    exact_text=raw,
                    publication_date=pub_day,
                    effective_date=pub_day,
                    company_name=cname,
                    ticker=raw_sym,
                    normalized_ticker=norm_sym,
                    exchange=exch,
                    market=mkt,
                    instrument_type="short" if is_short else "equity",
                    action="SHORT" if is_short else "BUY",
                    execution_status="confirmed",
                    discovery_layer="primary_article",
                    confidence="high",
                    notes=raw[:140],
                )
            ]

        m_ann = re.match(
            r"^(New\s+Position|Position\s+Increase|Reduce|Trim|Closing|Trade\s+Exit\s+in|Trade\s+Update\s*[-–—:]\s*.*?\bClosing\s+Out)\s*:?\s*([A-Za-z0-9\s&.,\'’-]*?)\s*(?:(\d{6}|\d{4})\s*(KS|KQ|JT|JP)?|\(([A-Z0-9.]+)(?:\s+([A-Z]{2}))?\)|\b([A-Z]{2,5})\b)?",
            raw,
            re.IGNORECASE,
        )
        if m_ann and m_ann.group(1):
            kind_l = m_ann.group(1).lower()
            secs_ann = self.resolver.find_securities_in_clause(raw)
            if secs_ann:
                norm_sym, mkt, exch, cname = secs_ann[0]
                act_map: Literal["BUY", "ADD", "TRIM", "SELL"] = (
                    "BUY"
                    if "new" in kind_l
                    else ("ADD" if "increase" in kind_l else ("SELL" if ("closing" in kind_l or "exit" in kind_l) else "TRIM"))
                )
                _sz, _tr = self._extract_sizing_and_trim(raw)
                _px, _curr = self._extract_price_and_currency(raw, market=mkt)
                return [
                    ExtractedCandidate(
                        source_id=source_id,
                        source_type=source_type,
                        location=location,
                        char_offset=char_offset,
                        exact_text=raw,
                        publication_date=pub_day,
                        effective_date=pub_day,
                        company_name=cname,
                        ticker=norm_sym.split(".")[0] if mkt == ":us:" else norm_sym,
                        normalized_ticker=norm_sym,
                        exchange=exch,
                        market=mkt,
                        instrument_type=self._detect_instrument_type(raw, norm_sym),
                        action=act_map,
                        execution_status="confirmed",
                        discovery_layer="primary_chat" if "chat" in source_type else "primary_article",
                        stated_price=_px,
                        stated_currency=_curr,
                        position_sizing=_sz,
                        trim_fraction=1.0 if act_map == "SELL" else (_tr or (0.50 if act_map == "TRIM" else None)),
                        confidence="high",
                        notes=raw[:140],
                    )
                ]

        # 4. Negations, Desires, Watchlists & Conditional Non-Executions (MUST run BEFORE confirmed execution patterns!)
        has_negated_trade = bool(
            re.search(
                r"\b(?:not|never|didn[’\']t|did\s+not|don[’\']t|do\s+not|won[’\']t|will\s+not|wouldn[’\']t|would\s+not|"
                r"can[’\']t|cannot|haven[’\']t|have\s+not|hasn[’\']t|no\s+intention\s+of|not\s+(?:as\s+|really\s+)?(?:enthusiastic\s+about|looking\s+to)|"
                r"just\s+holding,\s*not|aside\s+from\s+(?:significantly\s+)?(?:reducing|trimming))\b"
                r"[^.!?;]{0,55}?\b(?:buy|buying|bought|add|adding|added|trim|trimming|trimmed|sell|selling|sold|close|closing|closed|exit|exiting|initiat(?:e|ing))\b",
                low,
            )
        )
        # Exception: "didn't touch any of my positions today aside from trimming HRTG" -> trimming HRTG IS executed!
        if "aside from trimming" in low or "other than trimming" in low or "other than adding" in low:
            has_negated_trade = False

        if has_negated_trade:
            if not include_non_confirmed:
                return []
            secs = self.resolver.find_securities_in_clause(raw, fallback_context=fallback_context)
            return [
                ExtractedCandidate(
                    source_id=source_id,
                    source_type=source_type,
                    location=location,
                    char_offset=char_offset,
                    exact_text=raw,
                    publication_date=pub_day,
                    effective_date=pub_day,
                    company_name=cname,
                    ticker=norm.split(".")[0],
                    normalized_ticker=norm,
                    exchange=exch,
                    market=mkt,
                    instrument_type="equity",
                    action="HOLD",
                    execution_status="retrospective",
                    discovery_layer="primary_chat" if "chat" in source_type else "primary_article",
                    confidence="medium",
                    notes="Negated non-execution statement",
                )
                for norm, mkt, exch, cname in secs
            ]

        is_proposed = bool(
            re.search(
                r"\b(?:on\s+(?:my|the|your)\s+watch\s*list|worth\s+adding\s+to\s+your\s+watch\s*lists?|on\s+(?:my|the)\s+radar|"
                r"worth\s+a\s+look|worth\s+considering|caught\s+my\s+eye|caution\s+is\s+warranted|"
                r"i\s+want\s+to\s+(?:buy|add|own)|would\s+(?:absolutely\s+)?love\s+to\s+(?:buy|add)|"
                r"will\s+probably\s+buy|would\s+probably\s+(?:buy|wait)|getting\s+close\s+to\s+buying|going\s+to\s+wait|"
                r"what\s+would\s+make\s+me\s+buy|long\s+before\s+i\s+trim|if\s+i\s+(?:had\s+no|didn[’\']t)|"
                r"waiting\s+for\s+.*?(?:earnings|report|pullback|clarity)\s+(?:first\s+)?before\s+(?:adding|buying)|"
                r"if\s+.*?(?:declines?|drops?|falls?|pulls?\s+back|holds?|is\s+within).*?(?:i\s+will|expect\s+me\s+to|would)\s+(?:consider\s+)?(?:buy|re-enter|add|closing|selling|cutting)|"
                r"i\s+will\s+consider\s+(?:closing|selling|buying|adding|trimming)|"
                r"stop\s+limit\s+buy\s+order|buy\s+limit\s+order\s+set|alerts?\s+set\s+for\s+to\s+buy|orders?\s+to\s+add\s+at|"
                r"seeking\s+to\s+add|looking\s+to\s+(?:buy|add)\b|slowly\s+adding\s+.*?\bbelow\s+\d|"
                r"plan\s+to\s+buy\s+at|potentially\s*…?\s*get\s+cut|anything\s+below\s+\$?\d+(?:\.\d+)?\s*,?\s*i\s+(?:am\s+cutting|will\s+cut|will\s+sell))\b",
                low,
            )
        )
        has_present_ownership = bool(
            re.search(r"^(?:i\s+have\s+)?small\s+positions?\s+in\b|\bso\s+far\s+i\s+have\b|\bi[’\']ve\s+purchased\b|\bi\s+bought\b|\bjust\s+bought\b", low)
        )
        if is_proposed and not has_present_ownership:
            if not include_non_confirmed:
                return []
            secs = self.resolver.find_securities_in_clause(raw, fallback_context=fallback_context)
            return [
                ExtractedCandidate(
                    source_id=source_id,
                    source_type=source_type,
                    location=location,
                    char_offset=char_offset,
                    exact_text=raw,
                    publication_date=pub_day,
                    effective_date=pub_day,
                    company_name=cname,
                    ticker=norm.split(".")[0],
                    normalized_ticker=norm,
                    exchange=exch,
                    market=mkt,
                    instrument_type=self._detect_instrument_type(raw, norm),
                    action="BUY",
                    execution_status="proposed",
                    discovery_layer="primary_chat" if "chat" in source_type else "primary_article",
                    confidence="medium",
                    notes="Watchlist / conditional / unexecuted idea",
                )
                for norm, mkt, exch, cname in secs
            ]

        # 5. Retrospective historical recaps & passive commentary ("since I added X", "Why I bought at $10", "In January I closed X", "still holding")
        is_retrospective = bool(
            re.search(
                r"\b(?:haven[’\']t\s+(?:sold|touched)|i\s+am\s+not\s+selling|won[’\']t\s+(?:really\s+)?touch\s+it|"
                r"continue\s+to\s+remain\s+in\s+the\s+portfolio|remains\s+in\s+the\s+portfolio|sitting\s+tight|"
                r"since\s+(?:i|we)\s+(?:first\s+)?(?:added|bought|picked|closed|exited|initiated)|"
                r"from\s+(?:when|where)\s+(?:i|we)\s+(?:added|bought)|before\s+i\s+bought|than\s+when\s+i\s+bought|"
                r"than\s+the\s+one\s+i\s+bought|when\s+i\s+(?:bought\s+it\s+last\s+year|launched\s+this\s+newsletter|started\s+this\s+newsletter)|"
                r"when\s+it\s+was\s+clearly\s+undervalued|and\s+it[’\']?s\s+(?:already\s+)?up\s+\+?\d+%|and\s+it\s+is\s+already\s+\+?\d+%\s+up|"
                r"let[’\']s\s+rewind\s+to|(?:a\s+year|a\s+few\s+years|months)\s+ago,\s*i\s+(?:bought|trimmed|added|closed)|"
                r"(?:in|back\s+in|early\s+in|mid-)\s*20(?:0\d|1\d|2[0-4])\b|"
                r"\b(?:bought|added)\b[^.!?;]{0,45}\b(?:last\s+year|last\s+spring|last\s+summer|last\s+fall|in\s+202[0-4])\b|"
                r"in\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+202\d)?\s*,?\s*i\s+(?:bought|added|closed|sold)|"
                r"last\s+(?:week|spring|year)[,\s]+i\s+(?:shared|added|bought|closed)|"
                r"on\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?,\s*i\s+sent\s+a\s+trad(?:e|ing)\s+alert|"
                r"why\s+i\s+bought\b|resolved\s+to\s+flip\s+what\s+we\s+picked\s+up|"
                r"as\s+a\s+recap,\s+over\s+the\s+past\s+\d+\s+weeks|sold\s+a\s+portion\s+of\s+what\s+i\s+added\s+past|"
                r"one\s+of\s+the\s+reasons\s+i\s+sold|bought\s+in\s+because\b|bought\s+[^.!?;]{1,35}?\bbecause\b|"
                r"^for\s+example,\s*i\s+(?:picked\s+up|bought|added))\b",
                low,
            )
        )
        # Also detect explicit historical purchase date in prose (>21 days prior to publication_date), e.g. "I added X on 6 August 2025" in a June 2026 post
        if not is_retrospective and re.search(r"\b(?:i|we)\s+(?:added|bought|purchased|closed|sold)\b", low):
            m_hist_dt = re.search(
                r"\b(?:on|in)\s+(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+202\d|"
                r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+(?:\d{1,2},\s*)?202\d)\b",
                low,
            )
            if m_hist_dt:
                parsed_hist = self._parse_verbal_date(m_hist_dt.group(1), default_year=default_yr)
                if parsed_hist and abs((pd.Timestamp(pub_day) - pd.Timestamp(parsed_hist)).days) > 21:
                    is_retrospective = True
        if is_retrospective:
            if not include_non_confirmed:
                return []
            secs = self.resolver.find_securities_in_clause(raw, fallback_context=fallback_context)
            return [
                ExtractedCandidate(
                    source_id=source_id,
                    source_type=source_type,
                    location=location,
                    char_offset=char_offset,
                    exact_text=raw,
                    publication_date=pub_day,
                    effective_date=pub_day,
                    company_name=cname,
                    ticker=norm.split(".")[0],
                    normalized_ticker=norm,
                    exchange=exch,
                    market=mkt,
                    instrument_type="equity",
                    action="HOLD",
                    execution_status="retrospective",
                    discovery_layer="primary_chat" if "chat" in source_type else "primary_article",
                    confidence="medium",
                    notes="Retrospective reference or passive holding commentary",
                )
                for norm, mkt, exch, cname in secs
            ]

        # 6. First-person / active portfolio execution detection (SELL, TRIM, ADD, BUY, SHORT, HEDGE)
        act: Optional[Literal["BUY", "ADD", "TRIM", "SELL", "HOLD", "SHORT", "COVER", "HEDGE"]] = None
        date_uncert: Optional[str] = None

        # 6a. Full Exits (SELL) — test against `raw` using (?i:...) on verbs so [A-Z] ticker classes remain case-sensitive!
        if re.search(
            r"(?:(?i:\b(?:closing\s+out|closed\s+out|i\s+(?:have\s+|just\s+)?closed|so\s+i\s+closed|closed\s+(?:my\s+|the\s+|remaining\s+)|"
            r"closing\s+(?:my\s+|the\s+|remaining\s+|some\s+positions\s+now)|trade\s+update\s+on\s+.*?\((?:closed|closing[^)]*)\)|"
            r"pulling\s+the\s+plug|^(?:[-*•]\s*)?sale\s+of\s+[a-z0-9]|painful\s+to\s+cut\s+[a-z0-9]|let\s+go\s+of\s+the\s+last\s+portion|"
            r"let\s+the\s+position\s+be\s+[\"“]?put\s+away|plan\s+on\s+getting\s+rid\s+of\s+the\s+position\s+today|"
            r"sold\s+my\s+final\s+shares|full\s+exit|fully\s+cut|totally\s+sold|sold\s+(?:the\s+(?:last|final|rest)\s+of|out\s+of|my\s+entire)|"
            r"i\s+am\s+selling|got\s+stopped\s+out|was\s+stopped\s+out|stopped\s+out\s+of|hit\s+stops?\b.*?\bsold|stop\s+hit|"
            r"it\s+is\s+being\s+cut|has\s+(?:also\s+)?been\s+cut|i[’\']ve\s+cut\s+it|i\s+am\s+cutting|"
            r"i[’\']ll\s+(?:also\s+)?be\s+closing\s+out))(?:\b|(?<=\)))|"
            r"\b(?i:closing|closed|close|selling|cutting)\s+(?:here\s+|out\s+)?(?:\$[A-Z]{1,5}|[A-Z]{2,5})\b)",
            raw,
        ):
            if re.search(r"\b(?:in\s+half|50%|half\s+exit|half\s+of|1/3|a\s+third|2/3|two\s+thirds|a\s+quarter|trimmed|reducing)\b", low):
                act = "TRIM"
            else:
                act = "SELL"

        # 6b. Partial Sales (TRIM)
        elif re.search(
            r"(?:(?i:\b(?:i\s+(?:am\s+|have\s+been\s+|heavily\s+)?trimming|i\s+(?:heavily\s+)?trimmed|trimmed\s+(?:a\s+bit|a\s+good\s+chunk|another\s+portion|\d|1/3|half|some)|"
            r"(?:trim|trimming|trimmed)\s+(?:\d+(?:\.\d+)?%|half|a\s+third|a\s+quarter|some|part)\s+of|"
            r"aside\s+from\s+(?:significantly\s+)?(?:trimming|reducing)|other\s+than\s+trimming|"
            r"taking\s+(?:a\s+third|half|some)\s+of\s+the\s+position\s+off|took\s+some\s+profit\s+on|"
            r"took\s+(?:some|half|a\s+third)\s+off|cut\s+(?:50%|in\s+half|half)|cut\s+.*?\bpositions?\s+in\s+half|cut\s+[A-Za-z0-9]+\s+in\s+half|half\s+exit|"
            r"paring\s+back|reduced\s+(?:my\s+)?position))(?:\b|(?<=%))|"
            r"\b(?i:trimmed|trimming|reducing)\s+(?:a\s+bit\s+more\s+)?(?:\$[A-Z]{1,5}|[A-Z]{2,5})\b)",
            raw,
        ):
            act = "TRIM"

        # 6c. Position Additions (ADD)
        elif re.search(
            r"(?:(?i:\b(?:i\s+(?:have\s+|carefully\s+|also\s+)?added|added\s+(?:some|more|a\s+little\s+more|a\s+bit|a\s+lot\s+more|\d+(?:\.\d+)?\s*bps|several\s+hundred\s+shares|to\s+(?:my|the|that))\b|"
            r"put\s+the\s+proceeds\s+into|i\s+add\s+to\s+my\s+position|"
            r"i\s+(?:am|will\s+be)\s+adding\s+to|adding\s+to\s+(?:my|the)\b|i[’\']ve\s+been\s+(?:steadily\s+|heavily\s+)?adding\s+to|"
            r"have\s+been\s+(?:steadily\s+|heavily\s+)?adding\s+to|steadily\s+adding\s+to|quickly\s+adding\s+to|buying\s+more\b|bought\s+more\b))\b|"
            r"\b(?i:increased|added\s+to|adding\s+to)\s+(?:\$[A-Z]{1,5}|[A-Z]{2,5})\b)",
            raw,
        ):
            act = "ADD"

        # 6d. New Position Purchases / Confirmed Active Ownership Disclosures (BUY)
        elif re.search(
            r"(?:(?i:\b(?:just\s+bought|i\s+bought|bought\s+(?:a\s+bit|some|a\s+little|shares|a\s+starter|a\s+small)|i[’\']ve\s+purchased|"
            r"purchased\s+(?:half\s+my\s+ideal\s+position|shares|a\s+position)|"
            r"opened\s+a\s+(?:new\s+|small\s+|starter\s+)?position|started\s+a\s+(?:new\s*,?\s*|small\s+|speculative\s+|starter\s+)?position|"
            r"initiat(?:ed|ing)\s+(?:a\s+(?:new\s+|smaller\s+|small\s+|starter\s+)?(?:position\s+in\s+)?|smaller\s+positions?\s+in\s+|my\s+position\s+in\s+|my\s+)?|"
            r"sized\s+my\s+position\s+(?:small\s+)?at\s+\d+(?:\.\d+)?%|have\s+allocated\s+\d+(?:\.\d+)?%\s+of\s+my\s+portfolio\s+to|"
            r"redeploying\s+most\s+of\s+that\s+capital\s+to|make\s+room\s+for|initiating\s+[A-Za-z0-9\s]+?\s*\(|initiating\s+[A-Za-z0-9]+\s+position|"
            r"put\s+on\s+a\s+(?:\d+(?:\.\d+)?%\s+)?position|i\s+picked\s+up|picked\s+up\s+(?:some|more|both|[A-Z][A-Za-z0-9&.\'’-]+)|"
            r"small\s+\d+(?:\.\d+)?%\s+buy\s+in|dip\s+buying\s+[A-Z]{2,5}|"
            r"april\s+trade\s+is\s+\d+(?:\.\d+)?%\s+of\s+the\s+portfolio\s+in|"
            r"^(?:i\s+have\s+)?small\s+positions?\s+in\s+(?:both|[a-z0-9])|so\s+far\s+i\s+have\b.*?\bbuilding\s+the\s+positions?|"
            r"i[’\']ve\s+owned\b.*?\bfor\s+a\s+while|highest\s+conviction\s+position\s+is\b|aths?\s+today\s+in\s+the\s+portfolio))(?:\b|(?<=\())|"
            r"\b(?i:buy|buying|bought)\s+(?:\$[A-Z]{1,5}|[A-Z][A-Za-z0-9&.\'’-]+(?:\s+[A-Z][A-Za-z0-9&.\'’-]+){0,3}\s*\()|"
            r"\b(?i:i\s+am\s+long)\s+(?:\$[A-Z]{1,5}|[A-Z]{2,5})\b|"
            r"\b(?i:the\s+pick\s+is|it\s+is)\s+(?:\$[A-Z]{1,5}|[A-Z]{2,5})\b)",
            raw,
        ):
            act = "BUY"
            if re.search(
                r"^(?:i\s+have\s+)?small\s+positions?\s+in\b|\bso\s+far\s+i\s+have\b|\bi[’\']ve\s+owned\b.*?\bfor\s+a\s+while|\bhighest\s+conviction\s+position\s+is\b|\baths?\s+today\s+in\s+the\s+portfolio\b",
                low,
            ):
                date_uncert = f"disclosed_owned_by_{pub_day}_accumulated_prior_days"

        # 6e. Article "Position" / "Conclusion" section explicit long disclosure ("I own shares of X", "I am long X at a 2% weight")
        elif any(k in section_heading.lower() for k in ("position", "conclusion", "disclosure", "summary")) and re.search(
            r"\b(?:i\s+own\b|i\s+am\s+long\b|i\s+hold\s+a\s+.*?\s*position\s+in|allocated\s+\d+(?:\.\d+)?%\s+to)\b",
            low,
        ):
            act = "BUY"

        # 6f. Explicit Short / Option Collar / Protective Put Executions (excluded from long equity simulation)
        elif re.search(
            r"(?i:\b(?:i\s+am\s+(?:also\s+)?short\b|shorted\b|shorting\b|smaller\s+short\s+in\b|initiated\s+a\s+(?:smaller\s+)?short\s+in\b|"
            r"(?:bought|put\s+on|added)\s+[^.!?;]{0,40}?\b(?:protective\s+puts?|options?\s+collar|collar|puts?|calls?)\s+on\b))",
            raw,
        ):
            act = "SHORT" if "short" in low else "HEDGE"

        if act is None:
            return []

        secs = self.resolver.find_securities_in_clause(raw, fallback_context=fallback_context)
        if not secs:
            return []

        sizing, trim_f = self._extract_sizing_and_trim(raw)
        if act == "SELL":
            trim_f = 1.0

        results: list[ExtractedCandidate] = []
        for norm, mkt, exch, cname in secs:
            inst = self._detect_instrument_type(raw, norm)
            final_act = act
            if inst == "short":
                final_act = "COVER" if act in ("SELL", "TRIM") else "SHORT"
            elif inst in ("option_call", "option_put", "option_collar", "option_spread"):
                final_act = "HEDGE"

            px, curr = self._extract_price_and_currency(raw, market=mkt)
            unresolved: list[str] = []
            if date_uncert:
                unresolved.append("exact_initial_fill_date")

            eff_dt = pub_day
            if re.search(r"\b(?:last\s+night|yesterday)\b", low):
                try:
                    eff_dt = (pd.Timestamp(pub_day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                    if mkt == ":kr:" and eff_dt < "2026-04-28":
                        eff_dt = "2026-04-28"
                except Exception:
                    eff_dt = pub_day

            results.append(
                ExtractedCandidate(
                    source_id=source_id,
                    source_type=source_type,
                    location=location,
                    char_offset=char_offset,
                    exact_text=raw,
                    publication_date=pub_day,
                    effective_date=eff_dt,
                    date_uncertainty=date_uncert,
                    company_name=cname,
                    ticker=norm.split(".")[0] if mkt == ":us:" else norm,
                    normalized_ticker=norm,
                    exchange=exch,
                    market=mkt,
                    instrument_type=inst,
                    action=final_act,
                    execution_status="confirmed",
                    discovery_layer="primary_chat" if "chat" in source_type else "primary_article",
                    stated_price=px,
                    stated_currency=curr,
                    position_sizing=sizing,
                    trim_fraction=trim_f,
                    confidence="high" if not date_uncert else "medium",
                    notes=raw[:180],
                    unresolved_fields=unresolved,
                )
            )
        return results

    def classify_statement(self, text: str, source_publication: str = "cluseau", pub_date: str = "2026-05-01") -> Optional[ExtractedCandidate]:
        """Single-statement entrypoint delegating directly to the production clause pipeline."""
        self.resolver.learn_from_text(text)
        for clause in self._split_into_atomic_clauses(text):
            cands = self.classify_clause(
                clause=clause,
                pub_date=pub_date,
                source_id=f"{source_publication}:statement",
                source_type="article",
                location="statement",
                fallback_context=text,
            )
            confirmed = [c for c in cands if c.execution_status == "confirmed"]
            if confirmed:
                return confirmed[0]
        return None

    def extract_from_chat(
        self,
        chat_threads: list[dict[str, Any]],
        chat_replies: Optional[dict[str, list[dict[str, Any]]]] = None,
        author_ids: Optional[set[int]] = None,
        author_handles: Optional[set[str]] = None,
    ) -> list[ExtractedCandidate]:
        """Extract trade candidates from chat threads and nested replies using author verification and paragraph-local conversational context."""
        replies_map = chat_replies or {}
        for item in chat_threads:
            cp = item.get("communityPost") or item
            body = str(cp.get("body") or "")
            if body:
                self.resolver.learn_from_text(body)
        for _tid, clist in replies_map.items():
            for c_wrap in clist:
                c_obj = c_wrap.get("comment") if isinstance(c_wrap.get("comment"), dict) else c_wrap
                c_body = str(c_obj.get("body") or "")
                if c_body:
                    self.resolver.learn_from_text(c_body)

        def _is_author(user_obj: dict[str, Any], uid_val: Any, role_val: Any) -> bool:
            if not author_ids and not author_handles:
                if not user_obj and uid_val is None:
                    return True
            if str(role_val or "").lower() in ("admin", "owner", "author", "contributor"):
                return True
            if uid_val is not None and author_ids:
                try:
                    if int(uid_val) in author_ids:
                        return True
                except (TypeError, ValueError):
                    pass
            h = str(user_obj.get("handle") or "").strip().lower()
            if h and author_handles and h in author_handles:
                return True
            return False

        candidates: list[ExtractedCandidate] = []

        ordered_threads = sorted(
            enumerate(chat_threads),
            key=lambda pair: str(((pair[1].get("communityPost") or pair[1]).get("created_at")) or ""),
        )

        for orig_idx, item in ordered_threads:
            cp = item.get("communityPost") or item
            tid = str(cp.get("id") or f"idx_{orig_idx}")
            created = str(cp.get("created_at") or "2026-01-01")
            pub_day = created[:10]
            body = str(cp.get("body") or "").strip()
            user = cp.get("user") or item.get("user") or {}
            uid = user.get("id") or cp.get("user_id")
            role = cp.get("pub_role") or item.get("pubRole") or user.get("pubRole")

            if body and _is_author(user, uid, role):
                paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
                header_para = paragraphs[0] if paragraphs else ""
                c_global = 0
                for p_idx, para in enumerate(paragraphs):
                    p_clauses = self._split_into_atomic_clauses(para)
                    for local_i, cl in enumerate(p_clauses):
                        # Paragraph-local preceding sentences first, then thread header paragraph
                        prev_in_para = " ".join(p_clauses[max(0, local_i - 2): local_i])
                        fb_ctx = prev_in_para if prev_in_para else (paragraphs[p_idx - 1] if p_idx > 0 else header_para)
                        cands = self.classify_clause(
                            clause=cl,
                            pub_date=pub_day,
                            source_id=f"chat:{tid[:8]}",
                            source_type="chat_thread",
                            location=f"thread:{tid}:clause:{c_global}",
                            char_offset=body.find(cl[:20]) if len(cl) >= 20 else 0,
                            fallback_context=fb_ctx,
                            include_non_confirmed=True,
                        )
                        candidates.extend(cands)
                        c_global += 1

            thread_comments = replies_map.get(tid, [])
            if not thread_comments:
                continue

            by_comment_id: dict[str, str] = {}
            recent_messages: list[str] = [body[:300]] if body else []

            for c_wrap in thread_comments:
                c_obj = c_wrap.get("comment") if isinstance(c_wrap.get("comment"), dict) else c_wrap
                c_user = c_wrap.get("user") if isinstance(c_wrap.get("user"), dict) else (c_obj.get("user") or {})
                c_id = str(c_obj.get("id") or "")
                c_uid = c_user.get("id") or c_obj.get("user_id")
                raw_proles = c_wrap.get("pub_roles")
                fallback_role = (
                    next(iter(raw_proles.values()), None)
                    if isinstance(raw_proles, dict)
                    else (raw_proles[0] if isinstance(raw_proles, list) and raw_proles else None)
                )
                c_role = c_obj.get("user_pub_role") or fallback_role
                c_created = str(c_obj.get("created_at") or created)
                c_day = c_created[:10]
                c_body = str(c_obj.get("body") or "").strip()
                parent_id = str(c_obj.get("parent_id") or c_obj.get("quote_id") or "")

                if c_id and c_body:
                    by_comment_id[c_id] = c_body

                if not c_body:
                    continue

                if _is_author(c_user, c_uid, c_role):
                    conv_ctx = ""
                    if parent_id and parent_id in by_comment_id:
                        conv_ctx = by_comment_id[parent_id]
                    elif recent_messages:
                        conv_ctx = " | ".join(recent_messages[-2:])
                    if body and body[:240] not in conv_ctx:
                        conv_ctx = f"{conv_ctx} | {body[:240]}".strip(" |")

                    c_clauses = self._split_into_atomic_clauses(c_body)
                    for c_i, cl in enumerate(c_clauses):
                        prev_local = " ".join(c_clauses[:c_i])
                        fb_reply = f"{prev_local} | {conv_ctx}".strip(" |")
                        cands = self.classify_clause(
                            clause=cl,
                            pub_date=c_day,
                            source_id=f"chat:{tid[:8]}:reply:{c_id[:8]}",
                            source_type="chat_reply",
                            location=f"thread:{tid}:reply:{c_id}:clause:{c_i}",
                            char_offset=0,
                            fallback_context=fb_reply,
                            include_non_confirmed=True,
                        )
                        candidates.extend(cands)

                recent_messages.append(c_body)

        return candidates

    def extract_from_article(self, post_data: dict[str, Any]) -> list[ExtractedCandidate]:
        """Extract candidates from a single Substack API post JSON (handling HTML widgets, sections, model ETF lists, and prose)."""
        slug = str(post_data.get("slug") or "unknown")
        pub_day = str(post_data.get("post_date") or "")[:10]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", pub_day):
            return []

        title = str(post_data.get("title") or "").strip()
        subtitle = str(post_data.get("subtitle") or "").strip()
        body_html = str(post_data.get("body_html") or "")
        if not body_html.strip():
            return []

        plain_text, blocks = preprocess_substack_html(body_html)
        full_doc_text = f"{title}\n{subtitle}\n{plain_text}"
        self.resolver.learn_from_text(full_doc_text)

        candidates: list[ExtractedCandidate] = []
        title_low = f"{title} {subtitle}".lower()

        # Skip pure marketing / promotional landing pages ("Best Stock Investing Newsletters", "% off")
        if re.search(r"\b(?:best\s+stock\s+investing\s+newsletters?|real-time\s+buy/sell\s+alerts\s+in\s+my\s+portfolio)\b", plain_text.lower()) and (
            "newsletter" in slug or "off" in slug
        ):
            return []

        # A. Detect structured Model ETF / Equal-Weight Basket posts (e.g. StockTok ETF 1.0, 2.0, Status Review)
        is_model_etf_post = bool(
            re.search(r"\betf\b", title_low)
            and any(
                phrase in plain_text.lower()
                for phrase in (
                    "10 stocks i would assemble",
                    "build this etf",
                    "equally weighted",
                    "stocks that are staying, removed and added",
                    "all 10 stocks in the",
                )
            )
        )
        if is_model_etf_post:
            m_baskets = self._extract_model_basket_blocks(slug, pub_day, title, blocks)
            candidates.extend(m_baskets)
            if m_baskets:
                return candidates

        # B. Detect headline-level single-stock trade articles (e.g. BTT monthly stock picks, post-mortems, upgrades/downgrades)
        headline_cands = self._extract_headline_driven_article(slug, pub_day, title, subtitle, blocks)
        candidates.extend(headline_cands)

        # C. Block-by-block structural & prose extraction
        is_review_doc = bool("review" in title_low or "review" in slug.lower() or "portfolio" in slug.lower())
        is_exit_postmortem_doc = bool(
            any(k in slug for k in ("position-close", "post-mortem", "closing-position", "why-i-sold", "why-im-closing", "-stock-sale", "-sold-thesis"))
            and "rotating-out" not in slug
            and "redeploy" not in slug
        )
        in_new_positions_intro = False
        active_recap_mode: Optional[str] = None
        current_idea_ticker: Optional[tuple[str, str, str, str]] = None
        recent_block_secs: list[tuple[str, str, str, str]] = []

        for blk in blocks:
            btxt = blk.text.strip()
            blow = btxt.lower()

            if "here are the new positions" in blow or "new additions to the portfolio" in blow:
                in_new_positions_intro = True

            if blk.kind == "heading":
                if re.search(r"\b(?:additions|recap\s+of\s+additions)\b", blow):
                    active_recap_mode = "additions"
                elif re.search(r"\b(?:removals|recap\s+of\s+removals|closed\s+positions)\b", blow):
                    active_recap_mode = "removals"
                elif re.search(r"\b(?:existing\s+portfolio|current\s+holdings|conclusion|macro)\b", blow):
                    active_recap_mode = None
                    in_new_positions_intro = False

                sec_in_hd = self.resolver.find_securities_in_clause(btxt)
                if sec_in_hd:
                    current_idea_ticker = sec_in_hd[0]
                    recent_block_secs = list(sec_in_hd)

                for h_cl in self._split_into_atomic_clauses(btxt):
                    hd_cands = self.classify_clause(
                        clause=h_cl,
                        pub_date=pub_day,
                        source_id=slug,
                        source_type="article",
                        location=f"heading:{blk.index}@char:{blk.char_offset}",
                        char_offset=blk.char_offset,
                        section_heading=blk.section,
                        include_non_confirmed=True,
                    )
                    for hc in hd_cands:
                        if h_cl.lower().startswith("long ") and not in_new_positions_intro and "review" not in title_low:
                            hc.execution_status = "proposed"
                        if is_exit_postmortem_doc and hc.action in ("BUY", "ADD"):
                            hc.execution_status = "retrospective"
                        if is_review_doc:
                            hc.discovery_layer = "checkpoint_review"
                        if is_model_etf_post:
                            hc.portfolio_book = "model_etf"
                        candidates.append(hc)
                continue

            secs_in_blk = self.resolver.find_securities_in_clause(btxt)
            fallback_ctx = ""
            if recent_block_secs:
                fallback_ctx = ", ".join(f"{s[3]} ({s[0]})" for s in recent_block_secs[:3])
            elif current_idea_ticker:
                fallback_ctx = f"{current_idea_ticker[3]} (${current_idea_ticker[0]})"

            b_clauses = self._split_into_atomic_clauses(btxt)
            for c_i, cl in enumerate(b_clauses):
                prev_cl = " ".join(b_clauses[:c_i])
                local_fb = f"{prev_cl} | {fallback_ctx}".strip(" |")
                cl_cands = self.classify_clause(
                    clause=cl,
                    pub_date=pub_day,
                    source_id=slug,
                    source_type="article",
                    location=f"{blk.kind}:{blk.index}:c{c_i}@char:{blk.char_offset}",
                    char_offset=blk.char_offset,
                    fallback_context=local_fb,
                    section_heading=blk.section if not active_recap_mode else active_recap_mode,
                    include_non_confirmed=True,
                )
                for cc in cl_cands:
                    if is_exit_postmortem_doc and cc.action in ("BUY", "ADD"):
                        cc.execution_status = "retrospective"
                    if is_review_doc:
                        cc.discovery_layer = "checkpoint_review"
                    if is_model_etf_post:
                        cc.portfolio_book = "model_etf"
                    candidates.append(cc)

            if secs_in_blk:
                recent_block_secs = secs_in_blk

        # D. Dedicated single-company research write-ups stating explicit ownership (ONLY when no transaction was found above)
        has_confirmed_for_doc = any(c.execution_status == "confirmed" for c in candidates)
        if not has_confirmed_for_doc:
            candidates.extend(self._extract_thesis_position_disclosures(slug, pub_day, title, subtitle, blocks))

        return candidates

    def _extract_model_basket_blocks(
        self,
        slug: str,
        pub_day: str,
        title: str,
        blocks: list[DocBlock],
    ) -> list[ExtractedCandidate]:
        """General structural parser for Model ETF / Equal-Weight Basket construction, rebalance, and review posts."""
        out: list[ExtractedCandidate] = []
        full_low = "\n".join(b.text.lower() for b in blocks)
        is_rebalance = "staying, removed and added" in full_low or "(remove)" in full_low

        if is_rebalance:
            mode = "initial_list"
            removed_syms: set[str] = set()
            kept_syms: set[str] = set()
            for blk in blocks:
                txt = blk.text.strip()
                low = txt.lower()
                if low in ("remove", "removed", "removals") or "stocks removed" in low or "removed stocks" in low:
                    mode = "remove_section"
                    continue
                if low in ("added", "additions", "new additions", "add") or "stocks added" in low or low.startswith("new additions"):
                    mode = "added_section"
                    continue
                if blk.kind not in ("list_item", "heading"):
                    if "here are the new" in low or "3 new stocks" in low or ("replacing" in low and "added" in low):
                        mode = "added_section"
                    continue

                secs = self.resolver.find_securities_in_clause(txt)
                if not secs:
                    continue
                norm, mkt, exch, cname = secs[0]
                if "(remove)" in low or mode == "remove_section":
                    removed_syms.add(norm)
                    out.append(
                        ExtractedCandidate(
                            source_id=slug,
                            source_type="article",
                            location=f"list_item:{blk.index}@char:{blk.char_offset}",
                            char_offset=blk.char_offset,
                            exact_text=txt,
                            publication_date=pub_day,
                            effective_date=pub_day,
                            company_name=cname,
                            ticker=norm,
                            normalized_ticker=norm,
                            exchange=exch,
                            market=mkt,
                            instrument_type="equity",
                            action="SELL",
                            execution_status="confirmed",
                            discovery_layer="primary_article",
                            portfolio_book="model_etf",
                            position_sizing=0.0,
                            trim_fraction=1.0,
                            confidence="high",
                            notes=f"{title} Rebalance Removal: {cname} ({norm})",
                        )
                    )
                elif mode == "initial_list":
                    kept_syms.add(norm)
                elif mode == "added_section" and norm not in kept_syms and norm not in removed_syms:
                    kept_syms.add(norm)
                    out.append(
                        ExtractedCandidate(
                            source_id=slug,
                            source_type="article",
                            location=f"list_item:{blk.index}@char:{blk.char_offset}",
                            char_offset=blk.char_offset,
                            exact_text=txt,
                            publication_date=pub_day,
                            effective_date=pub_day,
                            company_name=cname,
                            ticker=norm,
                            normalized_ticker=norm,
                            exchange=exch,
                            market=mkt,
                            instrument_type="equity",
                            action="BUY",
                            execution_status="confirmed",
                            discovery_layer="primary_article",
                            portfolio_book="model_etf",
                            position_sizing=0.10,
                            confidence="high",
                            notes=f"{title} New Addition: {cname} ({norm})",
                        )
                    )
            return out

        # Check for Holding Action Review list ("Company, $SYM - Trim or cut" / "- Hold" / "- Hold/Buy")
        status_items: list[tuple[DocBlock, tuple[str, str, str, str], str]] = []
        for blk in blocks:
            if blk.kind != "list_item":
                continue
            m_st = re.search(r"[-–—]\s*(trim\s+or\s+cut|hold/buy|buy/hold|hold|trim|cut|sell)\s*$", blk.text.strip(), re.I)
            if m_st:
                secs = self.resolver.find_securities_in_clause(blk.text)
                if secs:
                    status_items.append((blk, secs[0], m_st.group(1).lower()))

        if len(status_items) >= 5:
            for blk, (norm, mkt, exch, cname), st_str in status_items:
                if "trim or cut" in st_str or st_str == "trim":
                    out.append(
                        ExtractedCandidate(
                            source_id=slug,
                            source_type="article",
                            location=f"list_item:{blk.index}@char:{blk.char_offset}",
                            char_offset=blk.char_offset,
                            exact_text=blk.text,
                            publication_date=pub_day,
                            effective_date=pub_day,
                            company_name=cname,
                            ticker=norm,
                            normalized_ticker=norm,
                            exchange=exch,
                            market=mkt,
                            instrument_type="equity",
                            action="TRIM",
                            execution_status="confirmed",
                            discovery_layer="primary_article",
                            portfolio_book="model_etf",
                            position_sizing=0.05,
                            trim_fraction=0.50,
                            confidence="medium",
                            notes=f"{cname} - Discretionary 50% trim based on model update '{st_str}'",
                        )
                    )
                elif st_str in ("cut", "sell"):
                    out.append(
                        ExtractedCandidate(
                            source_id=slug,
                            source_type="article",
                            location=f"list_item:{blk.index}@char:{blk.char_offset}",
                            char_offset=blk.char_offset,
                            exact_text=blk.text,
                            publication_date=pub_day,
                            effective_date=pub_day,
                            company_name=cname,
                            ticker=norm,
                            normalized_ticker=norm,
                            exchange=exch,
                            market=mkt,
                            instrument_type="equity",
                            action="SELL",
                            execution_status="confirmed",
                            discovery_layer="primary_article",
                            portfolio_book="model_etf",
                            position_sizing=0.0,
                            trim_fraction=1.0,
                            confidence="high",
                            notes=f"{cname} - Model removal '{st_str}'",
                        )
                    )
                else:
                    out.append(
                        ExtractedCandidate(
                            source_id=slug,
                            source_type="article",
                            location=f"list_item:{blk.index}@char:{blk.char_offset}",
                            char_offset=blk.char_offset,
                            exact_text=blk.text,
                            publication_date=pub_day,
                            effective_date=pub_day,
                            company_name=cname,
                            ticker=norm,
                            normalized_ticker=norm,
                            exchange=exch,
                            market=mkt,
                            instrument_type="equity",
                            action="HOLD",
                            execution_status="retrospective",
                            discovery_layer="checkpoint_review",
                            portfolio_book="model_etf",
                            position_sizing=0.10,
                            confidence="high",
                            notes=f"{cname} - Retained in model portfolio ({st_str})",
                        )
                    )
            return out

        # Otherwise: Model Basket Inception (collect list_items or headings with $TICKER or parenthetical (TICKER))
        is_inception = (
            "i would assemble" in full_low
            or "build this etf" in full_low
            or "initial 10" in full_low
            or "launching" in full_low
            or title.strip().lower() == "stocktok etf"
        )
        if not is_inception:
            return []

        li_securities: list[tuple[DocBlock, tuple[str, str, str, str]]] = []
        seen_init: set[str] = set()
        for blk in blocks:
            if blk.kind in ("list_item", "heading") and ("$" in blk.text or re.search(r"\([A-Z]{1,5}\)", blk.text)):
                secs = self.resolver.find_securities_in_clause(blk.text)
                if secs and secs[0][0] not in seen_init:
                    seen_init.add(secs[0][0])
                    li_securities.append((blk, secs[0]))

        if len(li_securities) >= 2:
            wt = round(1.0 / len(li_securities), 4)
            for blk, (norm, mkt, exch, cname) in li_securities:
                out.append(
                    ExtractedCandidate(
                        source_id=slug,
                        source_type="article",
                        location=f"list_item:{blk.index}@char:{blk.char_offset}",
                        char_offset=blk.char_offset,
                        exact_text=blk.text,
                        publication_date=pub_day,
                        effective_date=pub_day,
                        company_name=cname,
                        ticker=norm,
                        normalized_ticker=norm,
                        exchange=exch,
                        market=mkt,
                        instrument_type="equity",
                        action="BUY",
                        execution_status="confirmed",
                        discovery_layer="primary_table",
                        portfolio_book="model_etf",
                        position_sizing=wt,
                        confidence="high",
                        notes=f"{title} Initial Holding: {cname} ({norm})",
                    )
                )
        return out

    def _extract_headline_driven_article(
        self,
        slug: str,
        pub_day: str,
        title: str,
        subtitle: str,
        blocks: list[DocBlock],
    ) -> list[ExtractedCandidate]:
        """Extract explicit headline-declared single-stock buys, sales, upgrades, and downgrades."""
        headline = f"{title} | {subtitle}"
        hlow = headline.lower()

        act: Optional[Literal["BUY", "ADD", "HOLD", "SELL"]] = None
        if re.search(r"\bhold\s+to\s+buy\b|\bupgrad(?:e|ing)\s+to\s+buy\b", hlow):
            act = "BUY"
        elif re.search(r"\bbuy\s+to\s+hold\b|\bdowngrad(?:e|ing)\s+to\s+hold\b|\bmov(?:e|ing)\s+(?:it\s+)?to\s+hold\b", hlow):
            act = "HOLD"
        elif (
            (
                re.search(r"\b(?:why\s+i\s+sold|why\s+i[’\']m\s+closing|closing\s+trade|closing\s+position|stock\s+sale|post-mortem)\b", hlow)
                or any(k in slug for k in ("closing-position-", "closing-trade-", "-stock-sale", "why-i-sold-my-"))
            )
            and not title.lower().startswith("weekly")
            and "when-sell-stock" not in slug
            and "reinforces-discipline" not in slug
        ):
            act = "SELL"
        elif re.search(r"\b(?:new\s+addition\s+to\s+portfolio|one\s+addition\s+to)\b", hlow):
            act = "BUY"
        elif re.search(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+(?:202\d\s+)?(?:stock\s+)?pick\b", hlow) and "update" not in hlow and "is up" not in hlow:
            act = "BUY"
        elif re.search(r"\bbuy\s+\$\d+\s+target\b|\blithium\s+buy\b", hlow):
            act = "BUY"

        if not act:
            return []

        secs = self.resolver.find_securities_in_clause(headline)
        if not secs:
            opening_text = " ".join(b.text for b in blocks[:8])
            for m in re.finditer(r"\$([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b", opening_text):
                sym = m.group(1)
                if sym not in STOPWORD_ACRONYMS or sym in VALID_TICKERS_DESPITE_OVERLAP:
                    norm, mkt, exch = self.resolver.normalize_symbol(sym, context_text=opening_text)
                    cname = self.resolver.known_symbols.get(norm, (norm, mkt, exch, norm))[3]
                    secs.append((norm, mkt, exch, cname))
                    break
        if not secs:
            for tok in slug.upper().split("-"):
                if len(tok) >= 2 and tok in self.resolver.known_symbols and tok not in STOPWORD_ACRONYMS:
                    secs.append(self.resolver.known_symbols[tok])
                    break

        if not secs:
            return []

        norm, mkt, exch, cname = secs[0]
        return [
            ExtractedCandidate(
                source_id=slug,
                source_type="article",
                location="headline@char:0",
                char_offset=0,
                exact_text=headline[:200],
                publication_date=pub_day,
                effective_date=pub_day,
                company_name=cname,
                ticker=norm.split(".")[0] if mkt == ":us:" else norm,
                normalized_ticker=norm,
                exchange=exch,
                market=mkt,
                instrument_type="equity",
                action=act,
                execution_status="confirmed",
                discovery_layer="primary_article",
                trim_fraction=1.0 if act == "SELL" else None,
                confidence="high",
                notes=title[:180],
            )
        ]

    def _extract_thesis_position_disclosures(
        self,
        slug: str,
        pub_day: str,
        title: str,
        subtitle: str,
        blocks: list[DocBlock],
    ) -> list[ExtractedCandidate]:
        """Check single-company research write-ups for explicit first-person ownership disclosures."""
        out: list[ExtractedCandidate] = []
        # Skip weekly philosophy / macro essays that aren't company thesis write-ups
        if title.lower().startswith("weekly") or "guide" in slug or "watchlist" in slug or "lessons" in slug:
            return []

        tail_text = "\n".join(b.text.lower() for b in blocks[-4:])
        if "worth adding to your watchlists" in tail_text or "on my watchlist" in tail_text:
            return []

        ownership_re = re.compile(
            r"\b(?:i\s+(?:currently\s+)?own\s+(?:about\s+)?[\d,]*\s*(?:shares\s+of\b|\$?[A-Z])|"
            r"my\s+(?:current\s+)?position\s+in\s+[A-Z]|"
            r"i\s+have\s+a\s+(?:small\s+|starter\s+|core\s+|full\s+)?position\s+in\b|"
            r"i[’\']ve\s+been\s+buying\s+starter\s+positions)\b",
            re.IGNORECASE,
        )

        title_secs = self.resolver.find_securities_in_clause(f"{title} {subtitle}")
        for blk in blocks:
            if not ownership_re.search(blk.text):
                continue
            blow = blk.text.lower()
            if any(neg in blow for neg in ("haven't", "have not", "do not own", "don't own", "if you own")):
                continue
            secs_here = self.resolver.find_securities_in_clause(blk.text) or title_secs[:1]
            for norm, mkt, exch, cname in secs_here[:2]:
                inst = self._detect_instrument_type(blk.text, norm)
                out.append(
                    ExtractedCandidate(
                        source_id=slug,
                        source_type="article",
                        location=f"thesis:{blk.index}@char:{blk.char_offset}",
                        char_offset=blk.char_offset,
                        exact_text=blk.text[:240],
                        publication_date=pub_day,
                        effective_date=pub_day,
                        company_name=cname,
                        ticker=norm.split(".")[0] if mkt == ":us:" else norm,
                        normalized_ticker=norm,
                        exchange=exch,
                        market=mkt,
                        instrument_type=inst,
                        action="SHORT" if inst == "short" else ("HEDGE" if inst.startswith("option") else "BUY"),
                        execution_status="confirmed",
                        discovery_layer="primary_article",
                        confidence="high",
                        notes=f"[Ownership disclosure] {title}: {blk.text[:120]}",
                    )
                )
        return out

    def extract_from_datawrapper(self, source: SourceConfig) -> tuple[list[ExtractedCandidate], list[dict[str, Any]]]:
        """Extract dated primary pick & exit transactions and reference portfolio metadata from Datawrapper CSVs."""
        candidates: list[ExtractedCandidate] = []
        holdings_rows: list[dict[str, Any]] = []
        if not source.datawrapper_dir.exists():
            return candidates, holdings_rows

        dw_files = sorted(source.datawrapper_dir.glob("*.csv"))

        def _find_col(cols: list[str], kws: list[str], excl: Optional[list[str]] = None) -> Optional[str]:
            ex = [e.upper() for e in (excl or [])]
            umap = {c: c.strip().upper() for c in cols}
            for kw in kws:
                for orig, up in umap.items():
                    if up == kw.upper():
                        return orig
            for kw in kws:
                for orig, up in umap.items():
                    if not any(e in up for e in ex) and kw.upper() in up:
                        return orig
            return None

        def _parse_num(v: object) -> Optional[float]:
            if v is None:
                return None
            s = re.sub(r"[^0-9.\-+]+", "", str(v).strip())
            if not s or s in ("-", "+", "."):
                return None
            try:
                return float(s)
            except ValueError:
                return None

        # 1. Portfolio holdings CSVs (for weights, markets, known tickers — NEVER manufacturing undated BUYs)
        seen_holding_syms: set[str] = set()
        for fcsv in dw_files:
            if not any(k in fcsv.name for k in ("portfolio", "watchlist")):
                continue
            try:
                df = pd.read_csv(fcsv)
            except Exception:
                continue
            cols = list(df.columns)
            sym_col = _find_col(cols, ["SYMBOL", "TICKER"])
            name_col = _find_col(cols, ["STOCKS", "STOCK", "COMPANY", "NAME"])
            mkt_col = _find_col(cols, ["COUNTRY", "MARKET", "EXCHANGE"], excl=["PRICE", "COST", "RETURN", "TOTAL"])
            wt_col = _find_col(cols, ["WEIGHT", "ALLOCATION"])
            cost_col = _find_col(cols, ["COST", "AVG COST", "BUY PRICE"])
            px_col = _find_col(cols, ["PRICE", "CURRENT $"])
            rat_col = _find_col(cols, ["RECO.", "RECO", "RATING", "STATUS"])
            if not sym_col:
                continue

            is_portfolio_file = "portfolio" in fcsv.name
            for _, r in df.iterrows():
                raw_sym = str(r.get(sym_col, "")).strip().upper()
                if not raw_sym or raw_sym in ("NAN", "CASH", "TOTAL") or "UPGRADE" in raw_sym:
                    continue
                raw_mkt = str(r.get(mkt_col, ":us:")).strip() if mkt_col else ":us:"
                mkt_hint = raw_mkt.strip(":").upper() if raw_mkt and not raw_mkt.startswith("$") else "US"
                cname = str(r.get(name_col, raw_sym)).strip() if name_col else raw_sym
                if "UPGRADE TO PAID" in cname.upper() or cname.lower() == "nan":
                    cname = raw_sym
                norm_sym, mkt, _exch = self.resolver.register_binding(cname, raw_sym, hint=mkt_hint)
                # Preserve exact country tag from BTT CSV (e.g. :ky:, :tw:, :nl:, :fr:, :ca:, :kr:)
                clean_mkt = f":{raw_mkt.strip(':').lower()}:" if raw_mkt and re.match(r"^:?[a-zA-Z]{2}:?$", raw_mkt) else mkt

                if is_portfolio_file and norm_sym not in seen_holding_syms:
                    seen_holding_syms.add(norm_sym)
                    wt_raw = _parse_num(r.get(wt_col)) if wt_col else None
                    wt = (wt_raw / 100.0) if (wt_raw is not None and ("%" in str(r.get(wt_col, "")) or wt_raw > 1.0)) else wt_raw
                    rat_str = str(r.get(rat_col, "BUY")).strip().upper() if rat_col else "BUY"
                    rating = "HOLD" if "HOLD" in rat_str else "BUY"
                    holdings_rows.append(
                        {
                            "symbol": norm_sym,
                            "name": cname,
                            "market": clean_mkt,
                            "weight": wt,
                            "cost_basis": _parse_num(r.get(cost_col)) if cost_col else None,
                            "latest_price": _parse_num(r.get(px_col)) if px_col else None,
                            "current_rating": rating,
                            "entry_date": "",
                            "source_file": fcsv.name,
                        }
                    )

        # 2. Dated Pick Performance CSVs (Date of Pick -> BUY, Close Date -> SELL)
        seen_table_events: set[tuple[str, str, str]] = set()
        for fcsv in dw_files:
            try:
                df = pd.read_csv(fcsv)
            except Exception:
                continue
            cols = list(df.columns)
            dt_col = _find_col(cols, ["DATE OF PICK", "PICK DATE", "BUY DATE", "ENTRY DATE"])
            sym_col = _find_col(cols, ["SYMBOL", "TICKER"])
            if not (dt_col and sym_col):
                continue
            close_col = _find_col(cols, ["CLOSE DATE", "SELL DATE", "EXIT DATE"])
            cost_col = _find_col(cols, ["COST", "BUY PRICE", "ENTRY PRICE"])
            px_col = _find_col(cols, ["MARKET PRICE", "SELL PRICE", "CLOSE PRICE"])
            name_col = _find_col(cols, ["STOCK", "COMPANY", "NAME"])

            for r_idx, r in df.iterrows():
                raw_sym = str(r.get(sym_col, "")).strip().upper()
                if not raw_sym or raw_sym == "NAN" or "UPGRADE" in raw_sym:
                    continue
                cname = str(r.get(name_col, raw_sym)).strip() if name_col else raw_sym
                if "UPGRADE TO PAID" in cname.upper() or cname.lower() == "nan":
                    cname = raw_sym
                norm_sym, mkt, exch = self.resolver.normalize_symbol(raw_sym)
                # Use portfolio holdings market if known
                for h in holdings_rows:
                    if h["symbol"] == norm_sym:
                        mkt = h["market"]
                        break

                p_dt = pd.to_datetime(str(r.get(dt_col, "")).strip(), errors="coerce")
                if pd.notna(p_dt):
                    d_str = p_dt.strftime("%Y-%m-%d")
                    key_b = (d_str, norm_sym, "BUY")
                    if key_b not in seen_table_events:
                        seen_table_events.add(key_b)
                        candidates.append(
                            ExtractedCandidate(
                                source_id=fcsv.name,
                                source_type="datawrapper",
                                location=f"row:{r_idx}",
                                exact_text=f"{d_str} BUY {norm_sym} @ {r.get(cost_col, '')}",
                                publication_date=d_str,
                                effective_date=d_str,
                                company_name=cname,
                                ticker=raw_sym,
                                normalized_ticker=norm_sym,
                                exchange=exch,
                                market=mkt,
                                instrument_type="equity",
                                action="BUY",
                                execution_status="confirmed",
                                discovery_layer="primary_table",
                                stated_price=_parse_num(r.get(cost_col)) if cost_col else None,
                                stated_currency="USD",
                                confidence="high",
                                notes=f"Dated pick from {fcsv.name}",
                            )
                        )

                if close_col:
                    c_dt = pd.to_datetime(str(r.get(close_col, "")).strip(), errors="coerce")
                    if pd.notna(c_dt):
                        cd_str = c_dt.strftime("%Y-%m-%d")
                        key_s = (cd_str, norm_sym, "SELL")
                        if key_s not in seen_table_events:
                            seen_table_events.add(key_s)
                            candidates.append(
                                ExtractedCandidate(
                                    source_id=fcsv.name,
                                    source_type="datawrapper",
                                    location=f"row:{r_idx}:close",
                                    exact_text=f"{cd_str} CLOSE {norm_sym} @ {r.get(px_col, '')}",
                                    publication_date=cd_str,
                                    effective_date=cd_str,
                                    company_name=cname,
                                    ticker=raw_sym,
                                    normalized_ticker=norm_sym,
                                    exchange=exch,
                                    market=mkt,
                                    instrument_type="equity",
                                    action="SELL",
                                    execution_status="confirmed",
                                    discovery_layer="primary_table",
                                    stated_price=_parse_num(r.get(px_col)) if px_col else None,
                                    stated_currency="USD",
                                    trim_fraction=1.0,
                                    confidence="high",
                                    notes=f"Closed pick from {fcsv.name}",
                                )
                            )

        return candidates, holdings_rows

    def extract_publication(self, source: SourceConfig, use_cache: bool = True) -> tuple[list[ExtractedCandidate], list[dict[str, Any]]]:
        """Run complete multi-pass primary extraction across all Datawrapper tables, API articles, and nested chats."""
        source.data_dir.mkdir(parents=True, exist_ok=True)
        cache_path = source.data_dir / "extraction_cache.json"
        cache_data: dict[str, list[dict[str, Any]]] = {}
        if use_cache and cache_path.exists():
            try:
                loaded = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and loaded.get("_version") == EXTRACTOR_VERSION:
                    cache_data = loaded.get("items", {})
            except Exception:
                cache_data = {}

        author_ids, author_handles = discover_publication_authors(source)

        # Pass 1: Datawrapper tables + Corpus-wide entity binding scan across all posts & chats
        dw_cands, holdings_rows = self.extract_from_datawrapper(source)

        post_records: list[tuple[Path, dict[str, Any]]] = []
        if source.api_posts_dir.exists():
            for jpath in sorted(source.api_posts_dir.glob("*.json")):
                if jpath.stat().st_size == 0:
                    continue
                try:
                    pdata = json.loads(jpath.read_text(encoding="utf-8"))
                    if isinstance(pdata, dict):
                        post_records.append((jpath, pdata))
                        unpacked = unpack_substack_widgets(str(pdata.get("body_html") or ""))
                        plain = BeautifulSoup(unpacked, "html.parser").get_text(" ", strip=True)
                        self.resolver.learn_from_text(f"{pdata.get('title') or ''} {pdata.get('subtitle') or ''} {plain}")
                except Exception:
                    continue

        threads_list: list[dict[str, Any]] = []
        tpath = source.chat_dir / "chat_threads.json"
        if not tpath.exists() and (source.base_dir / "chat_threads.json").exists():
            tpath = source.base_dir / "chat_threads.json"
        if tpath.exists() and tpath.stat().st_size > 0:
            try:
                threads_list = json.loads(tpath.read_text(encoding="utf-8"))
            except Exception:
                threads_list = []

        replies_map: dict[str, list[dict[str, Any]]] = {}
        rpath = source.chat_dir / "chat_replies.json"
        if rpath.exists() and rpath.stat().st_size > 0:
            try:
                replies_map = json.loads(rpath.read_text(encoding="utf-8"))
            except Exception:
                replies_map = {}

        # Pass 2: Extract from every article (with SHA-256 content-hash caching)
        all_candidates: list[ExtractedCandidate] = list(dw_cands)
        new_cache_items: dict[str, list[dict[str, Any]]] = {}

        for jpath, pdata in post_records:
            raw_key_str = f"{pdata.get('slug')}|{pdata.get('post_date')}|{pdata.get('title')}|{pdata.get('body_html')}"
            chash = self._hash_content(raw_key_str)
            if use_cache and chash in cache_data:
                art_cands = [ExtractedCandidate(**d) for d in cache_data[chash]]
            else:
                art_cands = self.extract_from_article(pdata)
            new_cache_items[chash] = [c.model_dump() for c in art_cands]
            all_candidates.extend(art_cands)

        # Pass 3: Extract from chat threads & nested replies (cached by combined hash)
        if threads_list:
            chat_hash = self._hash_content(
                f"chats::{len(threads_list)}::{sum(len(v) for v in replies_map.values())}::"
                + json.dumps([((t.get('communityPost') or t).get('id'), (t.get('communityPost') or t).get('comment_count')) for t in threads_list[:25]])
            )
            if use_cache and chat_hash in cache_data:
                chat_cands = [ExtractedCandidate(**d) for d in cache_data[chat_hash]]
            else:
                chat_cands = self.extract_from_chat(
                    threads_list,
                    chat_replies=replies_map,
                    author_ids=author_ids,
                    author_handles=author_handles,
                )
            new_cache_items[chat_hash] = [c.model_dump() for c in chat_cands]
            all_candidates.extend(chat_cands)

        # Assign deterministic event_ids
        has_model_etf = any(c.portfolio_book == "model_etf" and c.execution_status == "confirmed" for c in all_candidates)
        for idx, cand in enumerate(all_candidates):
            if has_model_etf and cand.portfolio_book == "primary":
                cand.portfolio_book = "personal_swing"
            if not cand.event_id:
                cand.event_id = f"{source.key}-{idx+1:04d}-{cand.effective_date}-{cand.normalized_ticker}-{cand.action}"

        # Save cache & complete candidate ledger
        cache_path.write_text(
            json.dumps({"_version": EXTRACTOR_VERSION, "items": new_cache_items}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        cand_out = source.data_dir / "candidate_events.json"
        cand_out.write_text(
            json.dumps([c.model_dump() for c in all_candidates], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Save non-equity confirmed events (shorts, options, collars) separately
        non_eq = [
            c.model_dump()
            for c in all_candidates
            if c.execution_status == "confirmed"
            and c.instrument_type in ("short", "option_call", "option_put", "option_collar", "option_spread", "future")
        ]
        pd.DataFrame(non_eq).to_csv(source.data_dir / "non_equity_events.csv", index=False)

        return all_candidates, holdings_rows

    def build_normalized_ledger(
        self,
        source: SourceConfig,
        candidates: list[ExtractedCandidate],
        holdings_rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Normalize confirmed long cash security candidates into chronological, deduplicated trade events."""
        has_model_etf = any(c.portfolio_book == "model_etf" and c.execution_status == "confirmed" for c in candidates)
        target_book = "model_etf" if has_model_etf else "primary"

        valid_long_types = {"equity", "preferred", "etf", "mutual_fund"}
        valid_actions = {"BUY", "ADD", "TRIM", "SELL", "HOLD"}

        confirmed_long = [
            c
            for c in candidates
            if c.execution_status == "confirmed"
            and c.portfolio_book == target_book
            and c.instrument_type in valid_long_types
            and c.action in valid_actions
            # Exclude retrospective HOLDs emitted purely for model checkpoint tracking
            and not (c.action == "HOLD" and c.discovery_layer == "checkpoint_review")
        ]

        # Priority: primary_table > primary_article > primary_realtime > primary_chat > checkpoint_review
        layer_priority = {
            "primary_table": 0,
            "primary_article": 1,
            "primary_realtime": 2,
            "primary_chat": 2,
            "checkpoint_review": 3,
        }
        confirmed_long.sort(
            key=lambda c: (
                c.effective_date,
                layer_priority.get(c.discovery_layer, 9),
                c.normalized_ticker,
            )
        )

        # Deduplicate same-day same-ticker same-action AND suppress checkpoint_review restatements
        # when an earlier primary_table / primary_chat / primary_article event already captured the trade!
        deduped_cands: list[ExtractedCandidate] = []
        seen_exact: set[tuple[str, str, str]] = set()
        primary_history_by_sym: dict[str, list[tuple[str, str]]] = {}

        # Pre-index primary (Layer A) events by symbol
        for c in confirmed_long:
            if c.discovery_layer != "checkpoint_review":
                primary_history_by_sym.setdefault(c.normalized_ticker, []).append((c.effective_date, c.action))

        for c in confirmed_long:
            sym = c.normalized_ticker
            dt = c.effective_date
            act = c.action

            # If this is a retrospective review recap (e.g. "Added Sept 21" or "Exited Aug 21"),
            # skip if a primary Layer A buy/sell already exists within ±14 days (or any prior open BUY for review BUY)
            if c.discovery_layer == "checkpoint_review":
                prim_list = primary_history_by_sym.get(sym, [])
                already_captured = False
                for p_dt, p_act in prim_list:
                    day_diff = abs((pd.Timestamp(dt) - pd.Timestamp(p_dt)).days)
                    if act in ("BUY", "ADD") and p_act in ("BUY", "ADD") and (day_diff <= 20 or p_dt <= dt):
                        already_captured = True
                        break
                    if act == "SELL" and p_act == "SELL" and day_diff <= 14:
                        already_captured = True
                        break
                if already_captured:
                    continue

                if act == "SELL":
                    has_later_primary_sell = any(
                        p_dt > dt and p_act == "SELL" for (p_dt, p_act) in prim_list
                    )
                    if has_later_primary_sell:
                        c.action = "TRIM"
                        c.trim_fraction = 0.50
                        act = "TRIM"

            # Suppress duplicate article BUY/SELL restatement when Datawrapper primary_table or chat alert already recorded the trade within ±14 days
            if c.discovery_layer == "primary_article" and act == "BUY":
                has_table_buy = any(
                    c2.normalized_ticker == sym
                    and c2.action == "BUY"
                    and c2.discovery_layer in ("primary_table", "primary_chat")
                    and abs((pd.Timestamp(dt) - pd.Timestamp(c2.effective_date)).days) <= 14
                    and c2 is not c
                    for c2 in confirmed_long
                )
                if has_table_buy and c.source_type == "article":
                    # Keep if no primary_table exists and chat was AFTER article; drop if table or earlier/same-day chat exists
                    has_authoritative = any(
                        c2.normalized_ticker == sym
                        and c2.action == "BUY"
                        and (
                            c2.discovery_layer == "primary_table"
                            or (c2.discovery_layer == "primary_chat" and c2.effective_date < dt)
                        )
                        and abs((pd.Timestamp(dt) - pd.Timestamp(c2.effective_date)).days) <= 14
                        for c2 in confirmed_long
                    )
                    if has_authoritative:
                        continue

            if c.discovery_layer == "primary_article" and act == "SELL":
                prior_sells = [
                    d for (d, a) in primary_history_by_sym.get(sym, [])
                    if a == "SELL" and d < dt and 0 < (pd.Timestamp(dt) - pd.Timestamp(d)).days <= 14
                ]
                if prior_sells:
                    continue

            key = (dt, sym, act)
            if key in seen_exact:
                continue
            seen_exact.add(key)
            deduped_cands.append(c)

        # Stateful chronological normalization:
        # - Suppress static ownership restatements ("I own X", "small positions in...") if X is already open
        # - Convert initial ADD on an unheld non-legacy position into BUY (preserving accumulation note)
        # - Drop orphan SELL/TRIM if ticker was neither held nor a documented pre-2025 legacy holding
        legacy_holding_syms = {h["symbol"] for h in holdings_rows}
        open_state: set[str] = set()
        normalized_rows: list[dict[str, Any]] = []

        for c in deduped_cands:
            sym = c.normalized_ticker
            act = c.action
            note = c.notes or ""

            is_static_ownership = bool(
                (c.date_uncertainty and c.date_uncertainty.startswith("disclosed_owned_by_"))
                or note.startswith("[Ownership disclosure]")
            )
            if act == "BUY" and is_static_ownership and (sym in open_state or sym in legacy_holding_syms):
                continue

            if c.date_uncertainty:
                note = f"[{c.date_uncertainty}] {note}".strip()

            if act == "ADD" and sym not in open_state and sym not in legacy_holding_syms:
                act = "BUY"
                note = f"[Initiated via accumulation disclosure] {note}".strip()
            elif act == "BUY" and sym in open_state:
                act = "ADD"
                note = f"[Accumulation addition] {note}".strip()

            if act in ("SELL", "TRIM") and sym not in open_state and sym not in legacy_holding_syms:
                # Unopened legacy/swing exit before archive window: keep only if from primary_table with explicit entry, else skip from cash simulation
                continue

            if act in ("BUY", "ADD"):
                open_state.add(sym)
                rating_after = "BUY"
            elif act == "HOLD":
                rating_after = "HOLD"
            elif act == "TRIM":
                rating_after = "HOLD"
            elif act == "SELL":
                open_state.discard(sym)
                rating_after = "CLOSED"
            else:
                rating_after = "BUY"

            src_type_label = (
                "performance_table"
                if c.source_type == "datawrapper"
                else ("trade_alert" if "chat" in c.source_type else ("portfolio_table" if c.discovery_layer == "primary_table" else "article"))
            )

            normalized_rows.append(
                {
                    "date": c.effective_date,
                    "ticker": sym,
                    "market": c.market,
                    "action": act,
                    "rating_after": rating_after,
                    "ref_price": c.stated_price,
                    "target_weight": c.position_sizing,
                    "trim_fraction": c.trim_fraction,
                    "source_slug": c.source_id,
                    "source_type": src_type_label,
                    "confidence": c.confidence,
                    "discovery_layer": c.discovery_layer,
                    "date_uncertainty": c.date_uncertainty or "",
                    "notes": note[:240],
                }
            )

            # Ensure holdings_rows has metadata for every traded symbol
            if not any(h.get("symbol") == sym for h in holdings_rows):
                holdings_rows.append(
                    {
                        "symbol": sym,
                        "name": c.company_name or sym,
                        "market": c.market,
                        "weight": c.position_sizing,
                        "cost_basis": c.stated_price,
                        "latest_price": None,
                        "current_rating": rating_after if rating_after != "CLOSED" else "CLOSED",
                        "entry_date": c.effective_date if act == "BUY" else "",
                        "source_file": c.source_id,
                    }
                )

        return normalized_rows, holdings_rows
