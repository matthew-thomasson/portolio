from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd
from rich.console import Console

from .config import Settings, SourceConfig

console = Console()

PCT_CLEAN_RE = re.compile(r"[^0-9.\-+]+")
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
    confidence: str  # high, medium, review
    notes: str


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
    """Return percentage as decimal fraction (e.g. '11.17%' -> 0.1117)."""
    num = _parse_float(val)
    if num is None:
        return None
    if "%" in str(val) or abs(num) > 1.0:
        return num / 100.0
    return num


def _find_col(cols: list[str], keywords: list[str], exclude: list[str] | None = None) -> str | None:
    exclude = [e.upper() for e in (exclude or [])]
    upper_map = {c: c.strip().upper() for c in cols}
    # 1. Exact match
    for kw in keywords:
        kw_u = kw.upper()
        for orig, up in upper_map.items():
            if up == kw_u:
                return orig
    # 2. Substring match, respecting exclusions
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
    if clean in ("us", "ca", "uk", "gb", "cl", "au", "hk", "de", "fr", "mx", "br", "il", "nl", "se", "no", "jp", "kr", "tw", "ky"):
        return f":{clean}:"
    return f":{clean}:" if clean else fallback


def extract_tickers_from_html(body_html: str) -> list[str]:
    """Extract Substack StockTicker pills, ($TICKER) and (EXCHANGE:TICKER)."""
    found: list[str] = []
    if not body_html:
        return found

    soup = BeautifulSoup(body_html, "html.parser")
    for el in soup.find_all(attrs={"data-component-name": re.compile(r"StockTicker", re.I)}):
        raw_attrs = el.get("data-attrs")
        if raw_attrs:
            try:
                attrs = json.loads(html.unescape(str(raw_attrs)))
                sym = (attrs.get("symbol") or attrs.get("ticker") or "").strip().upper()
                if sym and sym not in found:
                    found.append(sym)
            except Exception:
                pass

    text = soup.get_text(" ", strip=True)
    for m in TICKER_PAREN_RE.finditer(text):
        sym = m.group(1).strip().upper()
        if sym and sym not in ("USD", "EUR", "CAD", "GBP", "CEO", "CFO", "IPO", "DCF", "EPS", "FCF", "YTD", "TTM", "ETF") and sym not in found:
            found.append(sym)

    for m in COMMON_PAREN_TICKER.finditer(text):
        sym = m.group(1).strip().upper()
        if sym and sym not in ("USD", "EUR", "CAD", "GBP", "CEO", "CFO", "IPO", "DCF", "EPS", "FCF", "YTD", "TTM", "ETF") and sym not in found:
            found.append(sym)

    return found


def parse_source_data(source: SourceConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse Datawrapper CSVs and API post JSONs for a specific source."""
    source.data_dir.mkdir(parents=True, exist_ok=True)

    holdings_rows: list[dict] = []
    events: list[TradeEvent] = []
    known_tickers: dict[str, str] = {}  # ticker -> market

    # 1. Inspect Datawrapper CSVs (if present)
    dw_files = sorted(source.datawrapper_dir.glob("*.csv")) if source.datawrapper_dir.exists() else []

    portfolio_csvs = [f for f in dw_files if any(k in f.name for k in ("svif-usa-portfolio", "portfolio", "global-portfolio"))]
    watchlist_csvs = [f for f in dw_files if "watchlist" in f.name]
    perf_csvs = [f for f in dw_files if any(k in f.name for k in ("stock-picks-performance", "performance"))]

    watchlist_ratings: dict[str, str] = {}
    for wcsv in watchlist_csvs:
        df = pd.read_csv(wcsv)
        cols = list(df.columns)
        sym_col = _find_col(cols, ["SYMBOL", "TICKER", "STOCK"])
        rat_col = _find_col(cols, ["RECO.", "RECO", "RECOMMENDATION", "RATING", "STATUS", "STANCE", "VERDICT"])
        if sym_col and rat_col:
            for _, r in df.iterrows():
                sym = str(r.get(sym_col, "")).strip().upper()
                rat = str(r.get(rat_col, "")).strip().upper()
                if sym and sym != "NAN" and "UPGRADE TO PAID" not in sym:
                    if "BUY" in rat:
                        watchlist_ratings[sym] = "BUY"
                    elif "HOLD" in rat:
                        watchlist_ratings[sym] = "HOLD"

    seen_holding_syms: set[str] = set()
    for pcsv in portfolio_csvs:
        df = pd.read_csv(pcsv)
        cols = list(df.columns)
        sym_col = _find_col(cols, ["SYMBOL", "TICKER"]) or _find_col(cols, ["STOCKS", "STOCK"])
        name_col = _find_col(cols, ["STOCKS", "COMPANY", "NAME"])
        mkt_col = _find_col(cols, ["COUNTRY", "MARKET", "EXCHANGE"], exclude=["PRICE", "COST", "RETURN", "TOTAL"])
        wt_col = _find_col(cols, ["WEIGHT", "ALLOCATION", "% OF PORTFOLIO"])
        cost_col = _find_col(cols, ["COST", "AVG COST", "BUY PRICE", "ENTRY"])
        px_col = _find_col(cols, ["PRICE", "CURRENT PRICE", "LAST"])
        rat_col = _find_col(cols, ["RECO.", "RECO", "RECOMMENDATION", "RATING", "STATUS", "STANCE", "ACTION"])
        dt_col = _find_col(cols, ["DATE", "BUY DATE", "ENTRY DATE", "OPENED"])

        if not sym_col:
            continue

        for _, r in df.iterrows():
            sym = str(r.get(sym_col, "")).strip().upper()
            if not sym or sym in ("NAN", "CASH", "TOTAL") or "UPGRADE TO PAID" in sym:
                continue
            if sym in seen_holding_syms:
                continue
            seen_holding_syms.add(sym)

            mkt = _clean_market_code(r.get(mkt_col), fallback=":us:") if mkt_col else ":us:"
            wt = _parse_pct(r.get(wt_col)) if wt_col else None
            cost = _parse_float(r.get(cost_col)) if cost_col else None
            px = _parse_float(r.get(px_col)) if px_col else None
            raw_rat = str(r.get(rat_col, "")).strip().upper() if rat_col else watchlist_ratings.get(sym, "")
            rating = "BUY" if "BUY" in raw_rat else ("HOLD" if "HOLD" in raw_rat else (raw_rat if raw_rat and raw_rat != "NAN" else "BUY"))
            entry_dt = str(r.get(dt_col, "")).strip()[:10] if dt_col else ""

            known_tickers[sym] = mkt
            holdings_rows.append(
                {
                    "symbol": sym,
                    "name": str(r.get(name_col, sym)).strip() if name_col else sym,
                    "market": mkt,
                    "weight": wt,
                    "cost_basis": cost,
                    "latest_price": px,
                    "current_rating": rating,
                    "entry_date": entry_dt if re.match(r"^\d{4}-\d{2}-\d{2}$", entry_dt) else "",
                    "source_file": pcsv.name,
                }
            )

    # 2. Parse Stock Picks Performance CSVs
    for fcsv in perf_csvs:
        df = pd.read_csv(fcsv)
        cols = list(df.columns)
        sym_col = _find_col(cols, ["SYMBOL", "TICKER", "STOCK"])
        dt_col = _find_col(cols, ["DATE OF PICK", "DATE", "PICK DATE", "BUY DATE", "ENTRY DATE", "PUBLISHED"])
        close_dt_col = _find_col(cols, ["CLOSE DATE", "SELL DATE", "EXIT DATE", "CLOSED"])
        mkt_col = _find_col(cols, ["MARKET", "EXCHANGE", "COUNTRY"], exclude=["PRICE", "COST", "RETURN", "TOTAL"])
        cost_col = _find_col(cols, ["BUY PRICE", "ENTRY PRICE", "PICK PRICE", "COST", "PRICE AT PICK"])
        exit_px_col = _find_col(cols, ["MARKET PRICE", "SELL PRICE", "EXIT PRICE", "CLOSE PRICE"])

        if not sym_col:
            continue
        for _, r in df.iterrows():
            sym = str(r.get(sym_col, "")).strip().upper()
            if not sym or sym == "NAN" or "UPGRADE TO PAID" in sym:
                continue
            mkt = _clean_market_code(r.get(mkt_col), fallback=known_tickers.get(sym, ":us:")) if mkt_col else known_tickers.get(sym, ":us:")
            known_tickers[sym] = mkt
            raw_dt = str(r.get(dt_col, "")).strip() if dt_col else ""
            parsed_dt = pd.to_datetime(raw_dt, errors="coerce")
            if pd.notna(parsed_dt):
                dt_str = parsed_dt.strftime("%Y-%m-%d")
                cost = _parse_float(r.get(cost_col)) if cost_col else None
                events.append(
                    TradeEvent(
                        date=dt_str,
                        ticker=sym,
                        market=mkt,
                        action="BUY",
                        rating_after="BUY",
                        ref_price=cost,
                        target_weight=None,
                        trim_fraction=None,
                        source_slug=fcsv.name,
                        source_type="performance_table",
                        confidence="high",
                        notes=f"Initial pick from {fcsv.name}",
                    )
                )
            if close_dt_col:
                raw_cdt = str(r.get(close_dt_col, "")).strip()
                parsed_cdt = pd.to_datetime(raw_cdt, errors="coerce")
                if pd.notna(parsed_cdt):
                    exit_px = _parse_float(r.get(exit_px_col)) if exit_px_col else None
                    events.append(
                        TradeEvent(
                            date=parsed_cdt.strftime("%Y-%m-%d"),
                            ticker=sym,
                            market=mkt,
                            action="SELL",
                            rating_after="CLOSED",
                            ref_price=exit_px,
                            target_weight=0.0,
                            trim_fraction=1.0,
                            source_slug=fcsv.name,
                            source_type="performance_table",
                            confidence="high",
                            notes=f"Closed pick from {fcsv.name}",
                        )
                    )

    # 3. Parse Substack API post JSONs (trade alerts, portfolio reviews, articles)
    api_files = sorted(source.api_posts_dir.glob("*.json")) if source.api_posts_dir.exists() else []
    for jpath in api_files:
        data = json.loads(jpath.read_text(encoding="utf-8"))
        slug = data.get("slug") or ""
        pdate = (data.get("post_date") or "")[:10]
        if not pdate or pdate.startswith("0000"):
            continue

        title = data.get("title") or ""
        subtitle = data.get("subtitle") or ""
        body_html = data.get("body_html") or ""
        tags = [str(t.get("slug") or t.get("name") or "").lower() for t in (data.get("postTags") or [])]

        tickers_in_post = extract_tickers_from_html(body_html)
        title_upper = f" {title.upper()} {slug.upper().replace('-', ' ')} "
        for ksym in list(known_tickers.keys()):
            if len(ksym) >= 2 and re.search(rf"\b{re.escape(ksym)}\b", title_upper):
                if ksym not in tickers_in_post:
                    tickers_in_post.insert(0, ksym)

        headline = f"{title} | {subtitle}".lower()
        soup = BeautifulSoup(body_html, "html.parser")
        soup_text = soup.get_text(" ", strip=True)

        is_trade_alert = any(k in slug or k in headline for k in ("trade-alert", "trade alert", "trades", "flash-buy", "picking-up"))
        is_post_mortem_or_sale = (
            any(kw in slug for kw in ("post-mortem", "closing-", "-stock-sale", "stock-sale", "why-i-sold-my-"))
            or re.search(r"\b(?:why\s+i\s+sold|closing\s+(?:my\s+)?position\s+in|saying\s+goodbye\s+to|stock\s+sale)\b", headline)
        )

        # Detect explicit actions
        action: str | None = None
        rating_after: str | None = None
        confidence = "medium"

        if re.search(r"\bhold\s+to\s+buy\b|\bupgrad(?:e|ing)\s+to\s+buy\b", headline):
            action, rating_after, confidence = "BUY", "BUY", "high"
        elif re.search(r"\bbuy\s+to\s+hold\b|\bmov(?:e|ing)\s+(?:it\s+)?to\s+hold\b|\bdowngrad(?:e|ing)\s+to\s+hold\b", headline):
            action, rating_after, confidence = "HOLD", "HOLD", "high"
        elif is_post_mortem_or_sale and not is_trade_alert:
            action, rating_after, confidence = "SELL", "CLOSED", "high"
        elif re.search(r"\bso\s+i\s+added\b|\badded\s+to\s+the\s+position\b", headline):
            action, rating_after, confidence = "ADD", "BUY", "high"
        elif re.search(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+(?:stock\s+)?pick\b", headline) and "update" not in headline:
            action, rating_after, confidence = "BUY", "BUY", "high"
        elif re.search(r"\bi['’]m\s+buying\b|\bbuy\s+rating\b|\bnew\s+addition\s+to\s+portfolio\b|\bone\s+addition\s+to\b|\bflash\s+buy\b|\bbuying\s+\d+\s+stocks\b", headline) and "not buying" not in headline:
            action, rating_after, confidence = "BUY", "BUY", "high"

        if is_trade_alert:
            sentences = re.split(r"(?<=[.!?])\s+|\n+", f"{title}. {subtitle}. {soup_text}")
            matched_in_alert = False
            for sent in sentences:
                sl = sent.lower()
                if "sold off" in sl or "market sold" in sl or "ounce sold" in sl or "got sold" in sl:
                    continue
                for sym in list(known_tickers.keys()) + tickers_in_post:
                    if len(sym) < 2 or sym in ("ETF", "VIX", "SPY", "QQQ"):
                        continue
                    if re.search(rf"\b{re.escape(sym)}\b", sent):
                        s_act = None
                        sym_idx = sent.find(sym)
                        left_window = sent[max(0, sym_idx - 40):sym_idx].lower()
                        right_window = sent[sym_idx:min(len(sent), sym_idx + 40)].lower()
                        surround = left_window + " " + right_window

                        if re.search(r"\b(?:close|closed|closing|sold|selling|exit|exited|exiting)\b", surround):
                            s_act, s_rat = "SELL", "CLOSED"
                        elif re.search(r"\b(?:trim|trimmed|trimming|reduce|reduced|reducing)\b", surround):
                            s_act, s_rat = "TRIM", "HOLD"
                        elif re.search(r"\b(?:add|added|adding|increased|increasing)\b", surround):
                            s_act, s_rat = "ADD", "BUY"
                        elif re.search(r"\b(?:buy|bought|buying|initiated|initiating|opened|opening|new position|flash buy)\b", surround):
                            s_act, s_rat = "BUY", "BUY"

                        if s_act:
                            matched_in_alert = True
                            events.append(
                                TradeEvent(
                                    date=pdate,
                                    ticker=sym,
                                    market=known_tickers.get(sym, ":us:"),
                                    action=s_act,
                                    rating_after=s_rat,
                                    ref_price=None,
                                    target_weight=None,
                                    trim_fraction=None,
                                    source_slug=slug,
                                    source_type="trade_alert",
                                    confidence="high",
                                    notes=sent[:180],
                                )
                            )
        elif action and tickers_in_post:
            primary_sym = tickers_in_post[0]
            if primary_sym not in ("ETF", "VIX", "SPY"):
                events.append(
                    TradeEvent(
                        date=pdate,
                        ticker=primary_sym,
                        market=known_tickers.get(primary_sym, ":us:"),
                        action=action,
                        rating_after=rating_after or "BUY",
                        ref_price=None,
                        target_weight=None,
                        trim_fraction=1.0 if action == "SELL" else None,
                        source_slug=slug,
                        source_type="article",
                        confidence=confidence,
                        notes=title[:180],
                    )
                )

    # Source-specific enhancements for TJ Stocks and Cluseau
    if source.key == "tjstocks":
        tj_initial_etf = [
            ("PRU", "Prudential Financial"),
            ("MTB", "M&T Bank"),
            ("SPG", "Simon Property Group"),
            ("UBSI", "United Bankshares"),
            ("TXT", "Textron Inc"),
            ("HNI", "HNI Corporation"),
            ("SPB", "Spectrum Brands Holdings"),
            ("FDX", "FedEx Corporation"),
            ("MSCI", "MSCI Inc"),
            ("VLO", "Valero Energy Corporation"),
        ]
        for sym, name in tj_initial_etf:
            events.append(
                TradeEvent(
                    date="2026-01-14",
                    ticker=sym,
                    market=":us:",
                    action="BUY",
                    rating_after="BUY",
                    ref_price=None,
                    target_weight=0.10,
                    trim_fraction=None,
                    source_slug="only-10-stocks-made-the-cut",
                    source_type="portfolio_table",
                    confidence="high",
                    notes=f"StockTok ETF 1.0 Initial Holding: {name}",
                )
            )
            holdings_rows.append(
                {
                    "symbol": sym,
                    "market": ":us:",
                    "company_name": name,
                    "cost_basis": None,
                    "entry_date": "2026-01-14",
                    "current_rating": "BUY",
                    "weight": 0.10,
                    "source_file": "only-10-stocks-made-the-cut",
                }
            )

        # StockTok ETF 2.0 Rebalance on 2026-07-28
        # Removals: SPB, MSCI, FDX (all 3 sold)
        for cut_sym, cut_name in [
            ("SPB", "Spectrum Brands Holdings"),
            ("MSCI", "MSCI Inc"),
            ("FDX", "FedEx Corporation"),
        ]:
            events.append(
                TradeEvent(
                    date="2026-07-28",
                    ticker=cut_sym,
                    market=":us:",
                    action="SELL",
                    rating_after="CLOSED",
                    ref_price=None,
                    target_weight=0.0,
                    trim_fraction=1.0,
                    source_slug="stocktok-etf-20",
                    source_type="article",
                    confidence="high",
                    notes=f"StockTok ETF 2.0 Removal: Cut {cut_name} ({cut_sym})",
                )
            )

        # Additions: CAKE, CNXN, FELE
        for sym, name in [
            ("CAKE", "Cheesecake Factory"),
            ("CNXN", "PC Connection"),
            ("FELE", "Franklin Electric"),
        ]:
            events.append(
                TradeEvent(
                    date="2026-07-28",
                    ticker=sym,
                    market=":us:",
                    action="BUY",
                    rating_after="BUY",
                    ref_price=None,
                    target_weight=0.10,
                    trim_fraction=None,
                    source_slug="stocktok-etf-20",
                    source_type="article",
                    confidence="high",
                    notes=f"StockTok ETF 2.0 New Addition: {name}",
                )
            )
            holdings_rows.append(
                {
                    "symbol": sym,
                    "market": ":us:",
                    "company_name": name,
                    "cost_basis": None,
                    "entry_date": "2026-07-28",
                    "current_rating": "BUY",
                    "weight": 0.10,
                    "source_file": "stocktok-etf-20",
                }
            )

        # 2026-11-03: Valero discretionary trim scenario
        events.append(
            TradeEvent(
                date="2026-11-03",
                ticker="VLO",
                market=":us:",
                action="TRIM",
                rating_after="HOLD",
                ref_price=None,
                target_weight=0.05,
                trim_fraction=0.50,
                source_slug="stocktok-etf-doubles-the-s-and-p",
                source_type="article",
                confidence="medium",
                notes="Valero Energy Corporation - Discretionary 50% trim assumption based on author advice 'Trim or Cut' (+28% gain)",
            )
        )

    elif source.key == "cluseau":
        # Documented baseline recommendations prior to 2026-01-01 (for Strategy A seeding)
        cluseau_prior_holdings = [
            ("CBL", "CBL Properties", ":us:", "2024-11-20", "its-just-more-fun-the-second-time", "BUY", 0.08),
            ("AGM", "Farmer Mac", ":us:", "2025-08-14", "juicing-the-market-one-repurchase", "BUY", 0.08),
            ("WSBF", "Waterstone Financial", ":us:", "2025-08-29", "shifting-into-rates-down", "BUY", 0.08),
            ("HRTG", "Heritage Insurance Holdings", ":us:", "2025-10-08", "30-days-to-november", "BUY", 0.08),
            ("OPY", "Oppenheimer Holdings", ":us:", "2025-07-17", "betting-on-capital-markets-with-a", "BUY", 0.08),
            ("ASIC", "Ategrity Specialty Insurance", ":us:", "2025-11-25", "snacking-on-banking-and-insurance", "BUY", 0.08),
            ("POWL", "Powell Industries", ":us:", "2025-10-15", "capital-markets-ai-and-rare-earths", "BUY", 0.08),
            ("MCHB", "Mechanics Bancorp", ":us:", "2025-09-10", "dividends-discounts-diamonds-in-the", "BUY", 0.05),
            ("KRNY", "Kearny Financial", ":us:", "2025-08-29", "shifting-into-rates-down", "BUY", 0.05),
        ]
        for sym, name, mkt, edt, slug, rat, wt in cluseau_prior_holdings:
            events.append(
                TradeEvent(
                    date=edt,
                    ticker=sym,
                    market=mkt,
                    action="BUY",
                    rating_after=rat,
                    ref_price=None,
                    target_weight=wt,
                    trim_fraction=None,
                    source_slug=slug,
                    source_type="article",
                    confidence="high",
                    notes=f"Cluseau documented pick: {name} ({sym})",
                )
            )
            holdings_rows.append(
                {
                    "symbol": sym,
                    "market": mkt,
                    "company_name": name,
                    "cost_basis": None,
                    "entry_date": edt,
                    "current_rating": rat,
                    "weight": wt,
                    "source_file": slug,
                }
            )

        # 2026-02-03: Bumble (BMBL)
        events.append(
            TradeEvent(
                date="2026-02-03",
                ticker="BMBL",
                market=":us:",
                action="BUY",
                rating_after="BUY",
                ref_price=None,
                target_weight=0.04,
                trim_fraction=None,
                source_slug="february-3-2026",
                source_type="article",
                confidence="high",
                notes="Bumble (BMBL) initiated in February 2026",
            )
        )
        # 2026-03-09: Entravision Communications (EVC)
        events.append(
            TradeEvent(
                date="2026-03-09",
                ticker="EVC",
                market=":us:",
                action="BUY",
                rating_after="BUY",
                ref_price=None,
                target_weight=0.06,
                trim_fraction=None,
                source_slug="march-2026-trade-review",
                source_type="article",
                confidence="high",
                notes="Entravision Communications (EVC) initiated in March 2026 review",
            )
        )
        # 2026-03-24: BMBL exit reported in April review
        events.append(
            TradeEvent(
                date="2026-03-24",
                ticker="BMBL",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=4.03,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="april-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Closed BMBL on March 24, 2026 (+17.07% return)",
            )
        )
        # 2026-04-10: MCHB and KRNY exits reported in April review
        events.append(
            TradeEvent(
                date="2026-04-10",
                ticker="MCHB",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="april-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Closed MCHB on April 10, 2026 (+22.98% return)",
            )
        )
        events.append(
            TradeEvent(
                date="2026-04-10",
                ticker="KRNY",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="april-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Closed KRNY on April 10, 2026 (+25.80% return)",
            )
        )
        # 2026-04-17: April Portfolio Review: Hello Group (MOMO) addition and Heritage (HRTG) addition
        events.append(
            TradeEvent(
                date="2026-04-17",
                ticker="MOMO",
                market=":us:",
                action="BUY",
                rating_after="BUY",
                ref_price=None,
                target_weight=0.06,
                trim_fraction=None,
                source_slug="april-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Hello Group (MOMO US) added in April 2026 Portfolio Review",
            )
        )
        events.append(
            TradeEvent(
                date="2026-04-17",
                ticker="HRTG",
                market=":us:",
                action="ADD",
                rating_after="BUY",
                ref_price=None,
                target_weight=0.08,
                trim_fraction=None,
                source_slug="april-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Added to Heritage Insurance (HRTG) position in April review",
            )
        )
        # 2026-04-29: SK Square (402340.KS) added upon IBKR Korean equities launch
        events.append(
            TradeEvent(
                date="2026-04-29",
                ticker="402340",
                market=":kr:",
                action="BUY",
                rating_after="BUY",
                ref_price=None,
                target_weight=0.08,
                trim_fraction=None,
                source_slug="opening-the-gates",
                source_type="article",
                confidence="high",
                notes="SK Square (402340.KS) initiated in 'Opening the Gates' post",
            )
        )
        # 2026-05-26: Vistance Networks (VISN)
        events.append(
            TradeEvent(
                date="2026-05-26",
                ticker="VISN",
                market=":us:",
                action="BUY",
                rating_after="BUY",
                ref_price=None,
                target_weight=0.05,
                trim_fraction=None,
                source_slug="go-stub-yourself",
                source_type="article",
                confidence="high",
                notes="Vistance Networks (VISN) initiated in 'Go Stub Yourself'",
            )
        )
        # 2026-06-12: June Portfolio Review: CBL trim, VISN add, GMRS buy
        events.append(
            TradeEvent(
                date="2026-06-12",
                ticker="CBL",
                market=":us:",
                action="TRIM",
                rating_after="HOLD",
                ref_price=None,
                target_weight=0.04,
                trim_fraction=0.333333,
                source_slug="june-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Reduce CBL & Associates (CBL) in June review",
            )
        )
        events.append(
            TradeEvent(
                date="2026-06-12",
                ticker="VISN",
                market=":us:",
                action="ADD",
                rating_after="BUY",
                ref_price=None,
                target_weight=0.08,
                trim_fraction=None,
                source_slug="june-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Position Increase: Vistance Networks (VISN) in June review",
            )
        )
        events.append(
            TradeEvent(
                date="2026-06-12",
                ticker="GMRS",
                market=":us:",
                action="BUY",
                rating_after="BUY",
                ref_price=None,
                target_weight=0.05,
                trim_fraction=None,
                source_slug="june-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="New Position: GMR Solutions (GMRS) in June review",
            )
        )
        # 2026-07-02: GMRS exit
        events.append(
            TradeEvent(
                date="2026-07-02",
                ticker="GMRS",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="september-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Exited GMRS on July 2 (+10% return)",
            )
        )
        # 2026-07-06: OPY 1/3 trim in Chat
        events.append(
            TradeEvent(
                date="2026-07-06",
                ticker="OPY",
                market=":us:",
                action="TRIM",
                rating_after="HOLD",
                ref_price=117.0,
                target_weight=0.05,
                trim_fraction=0.333333,
                source_slug="chat",
                source_type="trade_alert",
                confidence="high",
                notes="Trimmed 1/3 of OPY at $117 in Chat (msg 115)",
            )
        )
        # 2026-07-27: AGM full exit, OPY half trim in Chat
        events.append(
            TradeEvent(
                date="2026-07-27",
                ticker="AGM",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="chat",
                source_type="trade_alert",
                confidence="high",
                notes="AGM full exit (+30%) in Chat (msg 96)",
            )
        )
        events.append(
            TradeEvent(
                date="2026-07-27",
                ticker="OPY",
                market=":us:",
                action="TRIM",
                rating_after="HOLD",
                ref_price=None,
                target_weight=0.025,
                trim_fraction=0.50,
                source_slug="chat",
                source_type="trade_alert",
                confidence="high",
                notes="OPY half exit (+59%) in Chat (msg 96)",
            )
        )
        # 2026-07-29: HRTG full exit, WSBF full exit, CBL cut half, OPY cut half in Chat
        events.append(
            TradeEvent(
                date="2026-07-29",
                ticker="HRTG",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="chat",
                source_type="trade_alert",
                confidence="high",
                notes="Totally sold HRTG in Chat (msg 94)",
            )
        )
        events.append(
            TradeEvent(
                date="2026-07-29",
                ticker="WSBF",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="chat",
                source_type="trade_alert",
                confidence="high",
                notes="Totally sold WSBF in Chat (msg 94)",
            )
        )
        events.append(
            TradeEvent(
                date="2026-07-29",
                ticker="CBL",
                market=":us:",
                action="TRIM",
                rating_after="HOLD",
                ref_price=None,
                target_weight=0.02,
                trim_fraction=0.50,
                source_slug="chat",
                source_type="trade_alert",
                confidence="high",
                notes="Cut CBL by half in Chat (msg 94)",
            )
        )
        # 2026-08-06: VISN exit
        events.append(
            TradeEvent(
                date="2026-08-06",
                ticker="VISN",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="september-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Exited VISN on August 6 (-20% return)",
            )
        )
        # 2026-08-21: EVC and POWL exits via options collar
        events.append(
            TradeEvent(
                date="2026-08-21",
                ticker="EVC",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="september-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Exited EVC August 21 via options (+171% claimed return)",
            )
        )
        events.append(
            TradeEvent(
                date="2026-08-21",
                ticker="POWL",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="september-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Exited POWL August 21 via options (+136% claimed return)",
            )
        )
        # 2026-09-03: Buying the Buyback additions: ABCA.PA, 6626.T, 244920.KS
        # 2026-09-10: MOMO exit in Chat
        events.append(
            TradeEvent(
                date="2026-09-10",
                ticker="MOMO",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="chat",
                source_type="trade_alert",
                confidence="high",
                notes="Closed MOMO for -15% in Chat (msg 60)",
            )
        )
        # 2026-09-15: CBL final exit
        events.append(
            TradeEvent(
                date="2026-09-15",
                ticker="CBL",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="september-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Final CBL exit (+114% return) on September 15",
            )
        )
        # 2026-09-21: GDDY addition in Chat / Review
        events.append(
            TradeEvent(
                date="2026-09-21",
                ticker="GDDY",
                market=":us:",
                action="BUY",
                rating_after="BUY",
                ref_price=None,
                target_weight=0.06,
                trim_fraction=None,
                source_slug="september-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="GoDaddy (GDDY) added on September 21",
            )
        )
        # 2026-09-28: ASIC exit
        events.append(
            TradeEvent(
                date="2026-09-28",
                ticker="ASIC",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="september-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Exited ASIC on September 28 (+39% return)",
            )
        )
        # 2026-10-01: SK Square exit
        events.append(
            TradeEvent(
                date="2026-10-01",
                ticker="402340",
                market=":kr:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=None,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="september-2026-portfolio-review",
                source_type="article",
                confidence="high",
                notes="Exited SK Square (402340.KS) on October 1 (+44% return)",
            )
        )
        # 2026-10-16: GDDY trim 1/3 in Chat
        events.append(
            TradeEvent(
                date="2026-10-16",
                ticker="GDDY",
                market=":us:",
                action="TRIM",
                rating_after="HOLD",
                ref_price=110.0,
                target_weight=0.04,
                trim_fraction=0.333333,
                source_slug="chat",
                source_type="trade_alert",
                confidence="high",
                notes="Trimmed 1/3 GDDY at $110 in Chat (msg 26)",
            )
        )
        # 2026-10-30: GDDY final close in Chat
        events.append(
            TradeEvent(
                date="2026-10-30",
                ticker="GDDY",
                market=":us:",
                action="SELL",
                rating_after="CLOSED",
                ref_price=116.0,
                target_weight=0.0,
                trim_fraction=1.0,
                source_slug="chat",
                source_type="trade_alert",
                confidence="high",
                notes="Closed remaining GDDY at $116 in Chat (msg 4)",
            )
        )

        # Chat alerts audit
        chat_path = source.base_dir / "chat" / "chat_threads.json"
        if chat_path.exists():
            try:
                chat_data = json.loads(chat_path.read_text(encoding="utf-8"))
                for item in chat_data:
                    post = item.get("communityPost", {})
                    dt = (post.get("created_at") or "")[:10]
                    body = post.get("body", "")
                    if not body:
                        continue
                    # WYFI 2025 trades: bought Oct 1, sold Oct 9
                    if "adding a speculative position in White Fiber WYFI" in body:
                        events.append(
                            TradeEvent(
                                date=dt,
                                ticker="WYFI",
                                market=":us:",
                                action="BUY",
                                rating_after="BUY",
                                ref_price=31.0,
                                target_weight=0.03,
                                trim_fraction=None,
                                source_slug="chat",
                                source_type="trade_alert",
                                confidence="high",
                                notes="Adding speculative position in White Fiber WYFI at $31",
                            )
                        )
                    if "Closing out WYFI (Whitefiber) here at 33" in body:
                        events.append(
                            TradeEvent(
                                date=dt,
                                ticker="WYFI",
                                market=":us:",
                                action="SELL",
                                rating_after="CLOSED",
                                ref_price=33.0,
                                target_weight=0.0,
                                trim_fraction=1.0,
                                source_slug="chat",
                                source_type="trade_alert",
                                confidence="high",
                                notes="Closing WYFI at $33 for a 5% gain",
                            )
                        )
                    if "Trade Update on Kioxia (Closed)" in body:
                        events.append(
                            TradeEvent(
                                date=dt,
                                ticker="285A.T",
                                market=":jp:",
                                action="SELL",
                                rating_after="CLOSED",
                                ref_price=None,
                                target_weight=0.0,
                                trim_fraction=1.0,
                                source_slug="chat",
                                source_type="trade_alert",
                                confidence="high",
                                notes="Trade Update on Kioxia (Closed)",
                            )
                        )
            except Exception as e:
                console.print(f"[yellow]Warning parsing chat events: {e}[/yellow]")

    # 4. Deduplicate
    priority = {"override": 0, "performance_table": 1, "trade_alert": 2, "article": 3, "portfolio_table": 4}
    events.sort(key=lambda e: (e.date, e.ticker, priority.get(e.source_type, 9)))
    deduped: list[TradeEvent] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for ev in events:
        key = (ev.date, ev.ticker, ev.action)
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(ev)

    # Do not invent arbitrary historical dates (e.g. 2024-01-02) for undated holdings.
    # Only create a baseline TradeEvent if an explicit, documented entry_date is known!
    tickers_with_buy = {e.ticker for e in deduped if e.action == "BUY"}
    for h in holdings_rows:
        sym = h["symbol"]
        edt = h.get("entry_date") or ""
        if sym not in tickers_with_buy and edt and re.match(r"^\d{4}-\d{2}-\d{2}$", edt):
            tickers_with_buy.add(sym)
            deduped.append(
                TradeEvent(
                    date=edt,
                    ticker=sym,
                    market=h["market"],
                    action="BUY",
                    rating_after=h.get("current_rating") or "BUY",
                    ref_price=h.get("cost_basis"),
                    target_weight=h.get("weight"),
                    trim_fraction=None,
                    source_slug=h.get("source_file", "portfolio_table"),
                    source_type="portfolio_table",
                    confidence="medium",
                    notes="Baseline holding with documented entry date",
                )
            )

    # 5. Overrides
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
                    market=str(r.get("market", known_tickers.get(sym, ":us:"))).strip(),
                    action=act,
                    rating_after=str(r.get("rating_after", "CLOSED" if act == "SELL" else "BUY")).strip().upper(),
                    ref_price=_parse_float(r.get("ref_price")),
                    target_weight=_parse_pct(r.get("target_weight")),
                    trim_fraction=_parse_pct(r.get("trim_fraction")),
                    source_slug="trade_events_overrides.csv",
                    source_type="override",
                    confidence="high",
                    notes=str(r.get("notes", "Manual override")),
                )
            )

    deduped.sort(key=lambda e: (e.date, e.ticker))

    # Deduplicate holdings_rows by symbol
    unique_holdings: dict[str, dict] = {}
    for h in holdings_rows:
        s = h.get("symbol")
        if s and s not in unique_holdings:
            unique_holdings[s] = h
    holdings_df = pd.DataFrame(list(unique_holdings.values()))
    events_df = pd.DataFrame([asdict(e) for e in deduped])

    holdings_df.to_csv(source.data_dir / "portfolio_holdings.csv", index=False)
    events_df.to_csv(source.data_dir / "trade_events.csv", index=False)

    if not overrides_path.exists():
        with overrides_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["date", "ticker", "market", "action", "rating_after", "ref_price", "target_weight", "trim_fraction", "notes"]
            )

    return holdings_df, events_df
