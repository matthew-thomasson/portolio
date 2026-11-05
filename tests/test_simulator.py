from __future__ import annotations

from datetime import date
import pandas as pd
import pytest

from btt_sim.config import Settings, load_settings
from btt_sim.parser import extract_tickers_from_html
from btt_sim.simulator import PortfolioSimulator, compute_xirr


class FakePriceProvider:
    def __init__(self, table: dict[str, dict[str, float]]) -> None:
        self.table = table

    def get_price(self, symbol: str, dt: str, market: str | None = None, direction: str = "forward", fallback_price: float | None = None) -> float | None:
        s_map = self.table.get(symbol.upper(), {})
        if dt in s_map:
            return s_map[dt]
        keys = sorted(s_map.keys())
        if not keys:
            return fallback_price
        if direction == "forward":
            after = [k for k in keys if k >= dt]
            return s_map[after[0]] if after else s_map[keys[-1]]
        before = [k for k in keys if k <= dt]
        return s_map[before[-1]] if before else s_map[keys[0]]

    def latest_available_date(self, symbol: str = "SPY") -> date:
        return date(2026, 1, 1)


def test_compute_xirr_exact_one_year() -> None:
    cfs = [(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 1250.0)]
    xirr = compute_xirr(cfs)
    assert xirr is not None
    assert xirr == pytest.approx(0.25, rel=1e-2)


def test_extract_substack_ticker_pills() -> None:
    html = (
        '<p>Looking at Synchrony Financial '
        '<span data-component-name="StockTickerToDOM" data-attrs="{&quot;symbol&quot;:&quot;SYF&quot;}"></span> '
        'and NASDAQ: CRDO today.</p>'
    )
    assert extract_tickers_from_html(html) == ["SYF", "CRDO"]


def test_strategy_a_vs_b_and_hold_exclusion(tmp_path) -> None:
    settings = load_settings()
    settings.allocation_mode = "fixed_unit"
    settings.default_unit_usd = 1000.0
    settings.add_unit_usd = 500.0
    settings.trim_fraction = 0.5
    settings.reinvest_sales_cash = True
    holdings_df = pd.DataFrame(
        [
            {"symbol": "AAA", "market": ":us:", "weight": 0.10},
            {"symbol": "BBB", "market": ":us:", "weight": 0.05},
        ]
    )
    # AAA bought 2025-01-01 (still BUY at T0=2025-06-01), BBB downgraded to HOLD before T0, CCC is a fresh BUY after T0
    events_df = pd.DataFrame(
        [
            {"date": "2025-01-10", "ticker": "AAA", "market": ":us:", "action": "BUY", "rating_after": "BUY", "ref_price": 50.0, "target_weight": 0.10, "trim_fraction": None, "notes": "init AAA"},
            {"date": "2025-02-01", "ticker": "BBB", "market": ":us:", "action": "BUY", "rating_after": "BUY", "ref_price": 40.0, "target_weight": 0.05, "trim_fraction": None, "notes": "init BBB"},
            {"date": "2025-05-01", "ticker": "BBB", "market": ":us:", "action": "HOLD", "rating_after": "HOLD", "ref_price": 80.0, "target_weight": 0.05, "trim_fraction": None, "notes": "BBB to HOLD"},
            {"date": "2025-07-01", "ticker": "AAA", "market": ":us:", "action": "SELL", "rating_after": "CLOSED", "ref_price": 150.0, "target_weight": 0.0, "trim_fraction": 1.0, "notes": "close AAA"},
            {"date": "2025-08-01", "ticker": "CCC", "market": ":us:", "action": "BUY", "rating_after": "BUY", "ref_price": 100.0, "target_weight": 0.05, "trim_fraction": None, "notes": "new CCC"},
        ]
    )
    prices = FakePriceProvider(
        {
            "AAA": {"2025-06-01": 100.0, "2025-07-01": 150.0, "2026-01-01": 150.0},
            "BBB": {"2025-06-01": 80.0, "2026-01-01": 90.0},
            "CCC": {"2025-08-01": 100.0, "2026-01-01": 120.0},
            "SPY": {"2025-06-01": 500.0, "2025-07-01": 510.0, "2025-08-01": 520.0, "2026-01-01": 550.0},
        }
    )
    sim = PortfolioSimulator(settings, prices, holdings_df, events_df)

    # Strategy A seeds ONLY AAA on 2025-06-01 ($1,000 @ $100 = 10 shares), skips BBB (HOLD),
    # sells AAA on 2025-07-01 (@ $150 = $1,500 proceeds), and uses $1,000 of that cash to buy CCC on 2025-08-01 (@ $100 -> $1,200 at end)!
    res_a = sim.run_strategy(seed_existing_buys=True, start_date="2025-06-01", end_date="2026-01-01")
    assert res_a.seeded_count == 1
    assert "BBB" not in res_a.positions
    assert res_a.external_cash_invested == pytest.approx(1000.0)
    assert res_a.ending_cash_balance == pytest.approx(500.0)
    assert res_a.ending_equity_value == pytest.approx(1200.0)
    assert res_a.net_profit == pytest.approx(700.0)

    # Strategy B does NOT seed AAA, ignores AAA's SELL on 2025-07-01, and only buys CCC on 2025-08-01 ($1,000 -> $1,200)
    res_b = sim.run_strategy(seed_existing_buys=False, start_date="2025-06-01", end_date="2026-01-01")
    assert res_b.seeded_count == 0
    assert "AAA" not in res_b.positions
    assert res_b.external_cash_invested == pytest.approx(1000.0)
    assert res_b.net_profit == pytest.approx(200.0)
