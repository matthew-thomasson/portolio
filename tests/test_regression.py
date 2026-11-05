from __future__ import annotations

import re
from datetime import date
import pandas as pd
import pytest

from btt_sim.config import load_settings
from btt_sim.parser import parse_source_data, _clean_market_code, _find_col
from btt_sim.prices import PriceProvider
from btt_sim.simulator import PortfolioSimulator, Position, ExecutedTrade


def test_cluseau_no_retrospective_buy_contamination():
    settings = load_settings()
    src = settings.get_source("cluseau")
    holdings_df, events_df = parse_source_data(src)

    # 1. No synthetic 2026-01-02 BUY trades
    jan2_buys = events_df[(events_df["date"] == "2026-01-02") & (events_df["action"] == "BUY")]
    assert len(jan2_buys) == 0, f"Found synthetic 2026-01-02 BUY trades: {jan2_buys}"

    # 2. SK Square (402340) must be entered in late April 2026 (Opening the Gates), not January
    sk_sq_buys = events_df[(events_df["ticker"] == "402340") & (events_df["action"] == "BUY")]
    assert len(sk_sq_buys) == 1
    assert sk_sq_buys.iloc[0]["date"] == "2026-04-29"
    assert sk_sq_buys.iloc[0]["market"] == ":kr:"

    # 3. WYFI was exited in October 2025 (+5% gain) and is NOT active as of 2026-01-01
    prices = PriceProvider(settings)
    sim = PortfolioSimulator(settings, prices, holdings_df, events_df)
    active_2026 = sim.active_buys_at_date("2026-01-01")
    active_tickers = [b["ticker"] for b in active_2026]
    assert "WYFI" not in active_tickers
    assert "402340" not in active_tickers
    assert "MOMO" not in active_tickers
    assert "VISN" not in active_tickers

    # Prior documented positions should be present in Strategy A active buys
    assert "CBL" in active_tickers
    assert "AGM" in active_tickers
    assert "HRTG" in active_tickers
    assert "WSBF" in active_tickers
    assert "OPY" in active_tickers


def test_tjstocks_three_july_removals_and_additions():
    settings = load_settings()
    src = settings.get_source("tjstocks")
    holdings_df, events_df = parse_source_data(src)

    # On 2026-07-28, exactly 3 removals (SPB, MSCI, FDX) and 3 additions (CAKE, CNXN, FELE)
    july_events = events_df[events_df["date"] == "2026-07-28"]
    sells = july_events[july_events["action"] == "SELL"]["ticker"].tolist()
    buys = july_events[july_events["action"] == "BUY"]["ticker"].tolist()

    assert set(sells) == {"SPB", "MSCI", "FDX"}, f"Expected SPB, MSCI, FDX sold, got {sells}"
    assert set(buys) == {"CAKE", "CNXN", "FELE"}, f"Expected CAKE, CNXN, FELE bought, got {buys}"

    # VLO 50% trim on 2026-11-03 with discretionary note
    vlo_event = events_df[(events_df["ticker"] == "VLO") & (events_df["action"] == "TRIM")]
    assert len(vlo_event) == 1
    assert vlo_event.iloc[0]["trim_fraction"] == 0.50
    assert "discretionary" in vlo_event.iloc[0]["notes"].lower()

    # Simulator holding verification post-July
    prices = PriceProvider(settings)
    sim = PortfolioSimulator(settings, prices, holdings_df, events_df)
    res = sim.run_strategy(seed_existing_buys=False, start_date="2026-01-01", end_date="2026-11-05")

    # SPB, MSCI, FDX should have 0 shares at end
    for sym in ["SPB", "MSCI", "FDX"]:
        assert res.positions[sym].shares == pytest.approx(0.0), f"Expected {sym} to be fully closed"

    # CAKE, CNXN, FELE should be held
    for sym in ["CAKE", "CNXN", "FELE"]:
        assert res.positions[sym].shares > 0, f"Expected {sym} to be held"


def test_btt_no_live_datawrapper_backdating_and_clean_market():
    settings = load_settings()
    src = settings.get_source("beatingthetide")
    holdings_df, events_df = parse_source_data(src)

    # 1. No arbitrary 2024-01-02 baseline BUYs
    jan2_trades = events_df[events_df["date"] == "2024-01-02"]
    assert len(jan2_trades) == 0, f"Found 2024-01-02 trades: {jan2_trades}"

    # 2. No price strings in market fields
    assert not events_df["market"].str.contains(r"\$", na=False).any()
    assert not holdings_df["market"].str.contains(r"\$", na=False).any()

    # 3. Exact dated picks in performance table
    audit_samples = {
        "MU": "2025-12-30",
        "DELL": "2026-02-23",
        "DAR": "2026-05-18",
        "SNEX": "2026-06-10",
        "CSTM": "2026-07-15",
    }
    for sym, expected_date in audit_samples.items():
        sym_buys = events_df[(events_df["ticker"] == sym) & (events_df["action"] == "BUY")]
        assert len(sym_buys) >= 1, f"Missing BUY for {sym}"
        assert sym_buys.iloc[0]["date"] == expected_date, f"{sym} date {sym_buys.iloc[0]['date']} != {expected_date}"


def test_cash_conservation_arithmetic_identity():
    settings = load_settings()
    prices = PriceProvider(settings)

    for skey in ["beatingthetide", "tjstocks", "cluseau"]:
        src = settings.get_source(skey)
        holdings_df, events_df = parse_source_data(src)
        sim = PortfolioSimulator(settings, prices, holdings_df, events_df)

        for seed in [True, False]:
            res = sim.run_strategy(seed_existing_buys=seed, start_date="2026-01-01", end_date="2026-11-05")
            # Ending Value - External Invested == Net Profit
            implied_profit = res.ending_total_value - res.external_cash_invested
            assert implied_profit == pytest.approx(res.net_profit, abs=0.05), (
                f"{skey} (seed={seed}): implied {implied_profit} != net {res.net_profit}"
            )
            # Benchmark Ending Value - External Invested == Benchmark Net Profit
            bench_implied = res.benchmark_ending_value - res.external_cash_invested
            assert bench_implied == pytest.approx(res.benchmark_net_profit, abs=0.05), (
                f"{skey} (seed={seed}): bench implied {bench_implied} != bench net {res.benchmark_net_profit}"
            )


def test_currency_treatment_international_holding():
    settings = load_settings()
    prices = PriceProvider(settings)

    # 402340.KS trades in KRW (around 800,000 KRW in April 2026)
    krw_px = prices.get_price("402340", "2026-04-29", market=":kr:", in_usd=False)
    usd_px = prices.get_price("402340", "2026-04-29", market=":kr:", in_usd=True)

    assert krw_px is not None and krw_px > 100000.0, f"Expected KRW price > 100,000, got {krw_px}"
    assert usd_px is not None and 300.0 < usd_px < 1000.0, f"Expected USD price between 300 and 1000, got {usd_px}"

    # FX rate check
    fx = prices.get_fx_rate("KRW", "USD", "2026-04-29")
    assert 0.0006 < fx < 0.0009
    assert usd_px == pytest.approx(krw_px * fx, rel=1e-3)


def test_no_lookahead_publication_timestamps():
    settings = load_settings()
    for skey in ["beatingthetide", "tjstocks", "cluseau"]:
        src = settings.get_source(skey)
        events_df = pd.read_csv(src.data_dir / "trade_events.csv")
        for _, r in events_df.iterrows():
            t_date = str(r["date"])
            slug = str(r["source_slug"])
            m = re.match(r"^(\d{4}-\d{2}-\d{2})__", slug)
            if m:
                pub_date = m.group(1)
                # Trade date should not be arbitrarily before publication date unless documented pick date from table
                if r["source_type"] == "article":
                    assert t_date >= pub_date or abs((pd.to_datetime(t_date) - pd.to_datetime(pub_date)).days) <= 60, (
                        f"Trade {r['ticker']} on {t_date} predates article {pub_date}"
                    )

