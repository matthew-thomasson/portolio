from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd
import yfinance as yf

from .config import Settings

MARKET_SUFFIX_CANDIDATES: dict[str, list[str]] = {
    "us": [""],
    "ca": [".TO", "", ".V"],
    "uk": [".L", ""],
    "gb": [".L", ""],
    "cl": ["", ".SN"],
    "au": [".AX", ""],
    "hk": [".HK", ""],
    "de": [".DE", ""],
    "fr": [".PA", ""],
    "mx": [".MX", ""],
    "br": ["", ".SA"],
    "il": ["", ".TA"],
    "nl": [".AS", ""],
    "se": [".ST", ""],
    "no": [".OL", ""],
    "jp": [".T", ""],
    "kr": ["", ".KS"],
}


def normalize_market_code(raw: str | None) -> str:
    if not raw:
        return "us"
    cleaned = raw.strip().strip(":").lower()
    return cleaned or "us"


def candidate_yf_symbols(symbol: str, market: str | None = None) -> list[str]:
    sym = symbol.strip().upper()
    mkt = normalize_market_code(market)
    dash_sym = sym.replace(".", "-") if "." in sym and not any(sym.endswith(sfx) for sfx in (".TO", ".L", ".SN", ".AX", ".HK", ".DE", ".PA")) else sym

    bases = [dash_sym] if dash_sym == sym else [dash_sym, sym]
    suffixes = MARKET_SUFFIX_CANDIDATES.get(mkt, [""])
    out: list[str] = []
    for sfx in suffixes:
        for b in bases:
            cand = f"{b}{sfx}" if sfx and not b.endswith(sfx) else b
            if cand not in out:
                out.append(cand)
    if dash_sym not in out:
        out.append(dash_sym)
    return out


class PriceProvider:
    """Downloads, caches, and resolves daily historical close prices via yfinance."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache_dir = settings.price_cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.map_path = settings.data_dir / "ticker_map.json"
        self.ticker_map: dict[str, str] = {}
        if self.map_path.exists():
            try:
                self.ticker_map = json.loads(self.map_path.read_text(encoding="utf-8"))
            except Exception:
                self.ticker_map = {}
        self._memory: dict[str, pd.Series] = {}

    def save_ticker_map(self) -> None:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.map_path.write_text(json.dumps(self.ticker_map, indent=2, sort_keys=True), encoding="utf-8")

    def _cache_file(self, yf_symbol: str) -> Path:
        safe = yf_symbol.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe}.csv"

    def _load_yf_series(self, yf_symbol: str, start: str = "2020-01-01") -> pd.Series | None:
        if yf_symbol in self._memory:
            return self._memory[yf_symbol]

        cfile = self._cache_file(yf_symbol)
        if cfile.exists():
            df = pd.read_csv(cfile, parse_dates=["Date"], index_col="Date")
            if not df.empty and "Close" in df.columns:
                ser = df["Close"].dropna().sort_index()
                ser.index = pd.to_datetime(ser.index).tz_localize(None).normalize()
                self._memory[yf_symbol] = ser
                return ser

        try:
            end_dt = (date.today() + timedelta(days=5)).isoformat()
            hist = yf.Ticker(yf_symbol).history(start=start, end=end_dt, auto_adjust=True)
            if hist is None or hist.empty or "Close" not in hist.columns:
                return None
            ser = hist["Close"].dropna().copy()
            ser.index = pd.to_datetime(ser.index).tz_localize(None).normalize()
            ser = ser[~ser.index.duplicated(keep="last")].sort_index()
            if ser.empty:
                return None
            out_df = pd.DataFrame({"Date": ser.index, "Close": ser.values})
            out_df.to_csv(cfile, index=False)
            self._memory[yf_symbol] = ser
            return ser
        except Exception:
            return None

    def resolve_symbol(
        self,
        symbol: str,
        market: str | None = None,
        ref_price: float | None = None,
        ref_date: str | date | None = None,
    ) -> str | None:
        key = symbol.strip().upper()
        if key in self.ticker_map:
            return self.ticker_map[key]

        cands = candidate_yf_symbols(key, market)
        loaded: list[tuple[str, pd.Series]] = []
        for cand in cands:
            ser = self._load_yf_series(cand)
            if ser is not None and not ser.empty:
                loaded.append((cand, ser))

        if not loaded:
            return None

        if len(loaded) == 1 or ref_price is None or ref_price <= 0:
            chosen = loaded[0][0]
            self.ticker_map[key] = chosen
            return chosen

        # Pick candidate whose price on ref_date (or latest) is closest in relative terms to ref_price
        best_sym = loaded[0][0]
        best_err = float("inf")
        for cand, ser in loaded:
            px = self._lookup_in_series(ser, ref_date) if ref_date else float(ser.iloc[-1])
            if px and px > 0:
                rel_err = abs(px - ref_price) / ref_price
                if rel_err < best_err:
                    best_err = rel_err
                    best_sym = cand

        self.ticker_map[key] = best_sym
        return best_sym

    @staticmethod
    def _lookup_in_series(
        ser: pd.Series,
        dt: str | date | datetime,
        direction: str = "forward",
    ) -> float | None:
        if ser.empty:
            return None
        ts = pd.Timestamp(dt).tz_localize(None).normalize()
        if ts in ser.index:
            return float(ser.loc[ts])
        if direction == "forward":
            after = ser.loc[ser.index >= ts]
            if not after.empty:
                return float(after.iloc[0])
            return float(ser.iloc[-1])
        else:
            before = ser.loc[ser.index <= ts]
            if not before.empty:
                return float(before.iloc[-1])
            return float(ser.iloc[0])

    def get_price(
        self,
        symbol: str,
        dt: str | date | datetime,
        market: str | None = None,
        direction: str = "forward",
        fallback_price: float | None = None,
    ) -> float | None:
        yf_sym = self.resolve_symbol(symbol, market=market, ref_price=fallback_price, ref_date=dt)
        if not yf_sym:
            return fallback_price
        ser = self._load_yf_series(yf_sym)
        if ser is None or ser.empty:
            return fallback_price
        px = self._lookup_in_series(ser, dt, direction=direction)
        return px if px is not None else fallback_price

    def latest_available_date(self, symbol: str = "SPY") -> date:
        ser = self._load_yf_series(symbol)
        if ser is not None and not ser.empty:
            return ser.index[-1].date()
        return date.today()
