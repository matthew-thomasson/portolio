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
    "kr": [".KS", ".KQ", ""],
}


def normalize_market_code(raw: str | None) -> str:
    if not raw:
        return "us"
    cleaned = raw.strip().strip(":").lower()
    return cleaned or "us"


def candidate_yf_symbols(symbol: str, market: str | None = None) -> list[str]:
    sym = symbol.strip().upper()
    mkt = normalize_market_code(market)
    dash_sym = sym.replace(".", "-") if "." in sym and not any(sym.endswith(sfx) for sfx in (".TO", ".L", ".SN", ".AX", ".HK", ".DE", ".PA", ".KS", ".KQ", ".T", ".V")) else sym

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
    def get_instrument_currency(yf_symbol: str) -> str:
        s = yf_symbol.strip().upper()
        if s.endswith(".KS") or s.endswith(".KQ"):
            return "KRW"
        if s.endswith(".T"):
            return "JPY"
        if any(s.endswith(sfx) for sfx in (".PA", ".DE", ".AS", ".FR")):
            return "EUR"
        if any(s.endswith(sfx) for sfx in (".TO", ".V")):
            return "CAD"
        if s.endswith(".L"):
            return "GBP"
        if s.endswith(".HK"):
            return "HKD"
        if s.endswith(".AX"):
            return "AUD"
        return "USD"

    def get_fx_rate(
        self,
        from_curr: str,
        to_curr: str = "USD",
        dt: str | date | datetime | None = None,
    ) -> float:
        fc = from_curr.upper()
        tc = to_curr.upper()
        if fc == tc:
            return 1.0

        pair = None
        invert = False
        if fc == "KRW" and tc == "USD":
            pair = "USDKRW=X"
            invert = True
        elif fc == "USD" and tc == "KRW":
            pair = "USDKRW=X"
            invert = False
        elif fc == "JPY" and tc == "USD":
            pair = "USDJPY=X"
            invert = True
        elif fc == "USD" and tc == "JPY":
            pair = "USDJPY=X"
            invert = False
        elif fc == "EUR" and tc == "USD":
            pair = "EURUSD=X"
            invert = False
        elif fc == "USD" and tc == "EUR":
            pair = "EURUSD=X"
            invert = True
        elif fc == "CAD" and tc == "USD":
            pair = "USDCAD=X"
            invert = True
        elif fc == "USD" and tc == "CAD":
            pair = "USDCAD=X"
            invert = False
        elif fc == "HKD" and tc == "USD":
            pair = "USDHKD=X"
            invert = True
        elif fc == "USD" and tc == "HKD":
            pair = "USDHKD=X"
            invert = False
        elif fc == "AUD" and tc == "USD":
            pair = "AUDUSD=X"
            invert = False
        elif fc == "USD" and tc == "AUD":
            pair = "AUDUSD=X"
            invert = True
        elif fc == "GBP" and tc == "USD":
            pair = "GBPUSD=X"
            invert = False
        elif fc == "USD" and tc == "GBP":
            pair = "GBPUSD=X"
            invert = True

        if pair:
            ser = self._load_yf_series(pair)
            if ser is not None and not ser.empty:
                val = self._lookup_in_series(ser, dt or ser.index[-1], direction="backward")
                if val and val > 0:
                    return (1.0 / val) if invert else val
        return 1.0

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
        in_usd: bool = True,
    ) -> float | None:
        yf_sym = self.resolve_symbol(symbol, market=market, ref_price=fallback_price, ref_date=dt)
        if not yf_sym:
            return fallback_price
        ser = self._load_yf_series(yf_sym)
        if ser is None or ser.empty:
            return fallback_price
        px = self._lookup_in_series(ser, dt, direction=direction)
        if px is None:
            return fallback_price

        if in_usd:
            curr = self.get_instrument_currency(yf_sym)
            if curr != "USD":
                rate = self.get_fx_rate(curr, "USD", dt)
                return px * rate
        return px

    def latest_available_date(self, symbol: str = "SPY") -> date:
        ser = self._load_yf_series(symbol)
        if ser is not None and not ser.empty:
            return ser.index[-1].date()
        return date.today()
