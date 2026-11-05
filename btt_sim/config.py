from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SOURCE_DEFAULTS = {
    "beatingthetide": {
        "url": "https://www.beatingthetide.com/",
        "cookie_name": "connect.sid",
        "display_name": "Beating The Tide",
    },
    "tjstocks": {
        "url": "https://tjstocks.substack.com/",
        "cookie_name": "substack.sid",
        "display_name": "TJ Stocks",
    },
    "cluseau": {
        "url": "https://www.cluseau.com/",
        "cookie_name": "substack.sid",
        "display_name": "Cluseau",
    },
}


@dataclass
class SourceConfig:
    key: str
    display_name: str
    url: str
    cookie_name: str
    cookie_val: str

    @property
    def base_dir(self) -> Path:
        # Keep beatingthetide root for backwards compatibility or within sources/
        return PROJECT_ROOT / "sources" / self.key

    @property
    def archive_dir(self) -> Path:
        return self.base_dir / "archive"

    @property
    def api_posts_dir(self) -> Path:
        return self.base_dir / "api_posts"

    @property
    def datawrapper_dir(self) -> Path:
        return self.base_dir / "datawrapper"

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def results_dir(self) -> Path:
        return self.data_dir / "results"


@dataclass
class Settings:
    sources: dict[str, SourceConfig]
    allocation_mode: str = "fixed_unit"
    default_unit_usd: float = 1000.0
    add_unit_usd: float = 500.0
    trim_fraction: float = 1.0 / 3.0
    benchmark_ticker: str = "SPY"
    reinvest_sales_cash: bool = True

    @property
    def sbstck_bin(self) -> Path:
        return PROJECT_ROOT / "bin" / "sbstck-dl.exe"

    @property
    def shared_price_cache_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "price_cache"

    @property
    def price_cache_dir(self) -> Path:
        return self.shared_price_cache_dir

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    def get_source(self, key: str) -> SourceConfig:
        clean = key.lower().replace("-", "").replace("_", "")
        for k, src in self.sources.items():
            if k.lower() == clean:
                return src
        raise ValueError(f"Unknown source '{key}'. Available: {list(self.sources.keys())}")


def load_settings(env_path: Path | None = None) -> Settings:
    load_dotenv(env_path or (PROJECT_ROOT / ".env"), override=True)

    # Legacy fallback cookie
    legacy_cookie = os.getenv("SUBSTACK_COOKIE_VAL", "").strip()

    sources: dict[str, SourceConfig] = {}
    for skey, sdef in SOURCE_DEFAULTS.items():
        prefix = skey.upper()
        url = os.getenv(f"{prefix}_URL", sdef["url"]).strip()
        cname = os.getenv(f"{prefix}_COOKIE_NAME", sdef["cookie_name"]).strip()
        cval = os.getenv(f"{prefix}_COOKIE_VAL", "").strip() or (legacy_cookie if skey in ("beatingthetide", "cluseau") else "")
        sources[skey] = SourceConfig(
            key=skey,
            display_name=sdef["display_name"],
            url=url,
            cookie_name=cname,
            cookie_val=cval,
        )

    return Settings(
        sources=sources,
        allocation_mode=os.getenv("ALLOCATION_MODE", "fixed_unit").strip().lower(),
        default_unit_usd=float(os.getenv("DEFAULT_UNIT_USD", "1000.0")),
        add_unit_usd=float(os.getenv("ADD_UNIT_USD", "500.0")),
        trim_fraction=float(os.getenv("TRIM_FRACTION", "0.333333")),
        benchmark_ticker=os.getenv("BENCHMARK_TICKER", "SPY").strip().upper(),
        reinvest_sales_cash=os.getenv("REINVEST_SALES_CASH", "true").strip().lower() in ("1", "true", "yes", "y"),
    )
