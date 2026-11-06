from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd

from .config import Settings, SourceConfig, load_settings
from .extractor import ExtractionEngine, STOPWORD_ACRONYMS, unpack_substack_widgets
from .ingestion import validate_source_archive
from .prices import PriceProvider

PRICE_CLEAN_RE = re.compile(r"[^0-9.\-+]+")
TICKER_PAREN_RE = re.compile(
    r"(?:\b(?:NYSE|NASDAQ|TSX|TSXV|LSE|AMEX|OTC|BMV|BCS)\s*:\s*|\$\s*)([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b"
)
COMMON_PAREN_TICKER = re.compile(r"\((?:[A-Z]{1,5}:)?([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\)")


@dataclass
class TradeEvent:
    date: str
    ticker: str
    market: str
    action: str  # BUY, ADD, HOLD, TRIM, SELL
    rating_after: str  # BUY, HOLD, CLOSED
    ref_price: float | None
    target_weight: float | None
    trim_fraction: float | None
    source_slug: str
    source_type: str  # performance_table, portfolio_table, trade_alert, article, override
    confidence: str  # high, medium, low
    notes: str
    discovery_layer: str = "primary_article"
    date_uncertainty: str = ""


def _parse_float(val: object) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "n/a", "-", "upgrade to paid"):
        return None
    cleaned = PRICE_CLEAN_RE.sub("", s)
    if not cleaned or cleaned in ("-", "+", "."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_pct(val: object) -> float | None:
    num = _parse_float(val)
    if num is None:
        return None
    if "%" in str(val) or abs(num) > 1.0:
        return num / 100.0
    return num


def _find_col(cols: list[str], keywords: list[str], exclude: list[str] | None = None) -> str | None:
    exclude = [e.upper() for e in (exclude or [])]
    upper_map = {c: c.strip().upper() for c in cols}
    for kw in keywords:
        kw_u = kw.upper()
        for orig, up in upper_map.items():
            if up == kw_u:
                return orig
    for kw in keywords:
        kw_u = kw.upper()
        for orig, up in upper_map.items():
            if any(ex in up for ex in exclude):
                continue
            if kw_u in up:
                return orig
    return None


def _clean_market_code(raw: object, fallback: str = ":us:") -> str:
    if raw is None:
        return fallback
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", "-", ""):
        return fallback
    if s.startswith("$") or any(c.isdigit() for c in s):
        return fallback
    clean = s.strip(":").lower()
    if clean in (
        "us", "ca", "uk", "gb", "cl", "au", "hk", "de", "fr", "pt", "eu",
        "mx", "br", "il", "nl", "se", "no", "jp", "kr", "tw", "ky",
    ):
        return f":{clean}:"
    return f":{clean}:" if clean else fallback


def extract_tickers_from_html(body_html: str) -> list[str]:
    """Extract Substack CashtagToDOM, StockTickerToDOM pills, ($TICKER), and (EXCHANGE:TICKER) without acronym pollution."""
    found: list[str] = []
    if not body_html:
        return found

    unpacked = unpack_substack_widgets(body_html)
    soup = BeautifulSoup(unpacked, "html.parser")
    text = soup.get_text(" ", strip=True)

    for m in TICKER_PAREN_RE.finditer(text):
        sym = m.group(1).strip().upper()
        if sym and sym not in STOPWORD_ACRONYMS and sym not in found:
            found.append(sym)

    for m in COMMON_PAREN_TICKER.finditer(text):
        sym = m.group(1).strip().upper()
        if sym and sym not in STOPWORD_ACRONYMS and sym not in found:
            found.append(sym)

    return found


def parse_source_data(
    source: SourceConfig,
    settings: Settings | None = None,
    use_cache: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate source archive and extract normalized portfolio holdings and trade events via ExtractionEngine."""
    cfg = settings or load_settings()
    source.data_dir.mkdir(parents=True, exist_ok=True)

    # Mandatory Step 1: Validate source archive integrity
    validate_source_archive(source, save_report=True)

    # Mandatory Step 2: Run general-purpose primary extraction across Datawrapper, articles, and nested chats
    prices = PriceProvider(cfg)
    engine = ExtractionEngine(settings=cfg, prices=prices)
    candidates, holdings_rows = engine.extract_publication(source, use_cache=use_cache)
    normalized_rows, holdings_rows = engine.build_normalized_ledger(source, candidates, holdings_rows)

    deduped: list[TradeEvent] = [
        TradeEvent(
            date=str(r["date"]),
            ticker=str(r["ticker"]),
            market=_clean_market_code(r.get("market"), fallback=":us:"),
            action=str(r["action"]),
            rating_after=str(r["rating_after"]),
            ref_price=r.get("ref_price"),
            target_weight=r.get("target_weight"),
            trim_fraction=r.get("trim_fraction"),
            source_slug=str(r["source_slug"]),
            source_type=str(r["source_type"]),
            confidence=str(r["confidence"]),
            notes=str(r["notes"]),
            discovery_layer=str(r.get("discovery_layer") or "primary_article"),
            date_uncertainty=str(r.get("date_uncertainty") or ""),
        )
        for r in normalized_rows
    ]

    # Apply explicit manual overrides if present in trade_events_overrides.csv
    overrides_path = source.data_dir / "trade_events_overrides.csv"
    if overrides_path.exists():
        ov_df = pd.read_csv(overrides_path)
        for _, r in ov_df.iterrows():
            sym = str(r.get("ticker", "")).strip().upper()
            dt = str(r.get("date", "")).strip()[:10]
            act = str(r.get("action", "")).strip().upper()
            if not sym or not dt or not act:
                continue
            if act == "IGNORE":
                deduped = [e for e in deduped if not (e.date == dt and e.ticker == sym)]
                continue
            deduped = [e for e in deduped if not (e.date == dt and e.ticker == sym and e.action == act)]
            deduped.append(
                TradeEvent(
                    date=dt,
                    ticker=sym,
                    market=_clean_market_code(r.get("market"), fallback=":us:"),
                    action=act,
                    rating_after=str(r.get("rating_after", "CLOSED" if act == "SELL" else "BUY")).strip().upper(),
                    ref_price=_parse_float(r.get("ref_price")),
                    target_weight=_parse_pct(r.get("target_weight")),
                    trim_fraction=_parse_pct(r.get("trim_fraction")),
                    source_slug="trade_events_overrides.csv",
                    source_type="override",
                    confidence="high",
                    notes=str(r.get("notes", "Manual override")),
                    discovery_layer="primary_realtime",
                    date_uncertainty="",
                )
            )

    deduped.sort(key=lambda e: (e.date, e.ticker))

    unique_holdings: dict[str, dict] = {}
    for h in holdings_rows:
        s = h.get("symbol")
        if s and s not in unique_holdings:
            h["market"] = _clean_market_code(h.get("market"), fallback=":us:")
            unique_holdings[s] = h

    holdings_df = pd.DataFrame(list(unique_holdings.values()))
    events_df = pd.DataFrame([asdict(e) for e in deduped])

    holdings_df.to_csv(source.data_dir / "portfolio_holdings.csv", index=False)
    events_df.to_csv(source.data_dir / "trade_events.csv", index=False)
    prices.save_ticker_map()

    if not overrides_path.exists():
        with overrides_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["date", "ticker", "market", "action", "rating_after", "ref_price", "target_weight", "trim_fraction", "notes"]
            )

    return holdings_df, events_df
