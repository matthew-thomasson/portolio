from __future__ import annotations

import re

import pandas as pd
import pytest

from btt_sim.config import load_settings
from btt_sim.extractor import STOPWORD_ACRONYMS
from btt_sim.parser import parse_source_data
from btt_sim.prices import PriceProvider
from btt_sim.simulator import PortfolioSimulator


def test_cluseau_no_retrospective_buy_contamination_and_no_acronym_pollution():
    settings = load_settings()
    src = settings.get_source("cluseau")
    holdings_df = pd.read_csv(src.data_dir / "portfolio_holdings.csv")
    events_df = pd.read_csv(src.data_dir / "trade_events.csv")

    # 1. No synthetic 2026-01-02 BUY trades
    jan2_buys = events_df[(events_df["date"] == "2026-01-02") & (events_df["action"] == "BUY")]
    assert len(jan2_buys) == 0, f"Found synthetic 2026-01-02 BUY trades: {jan2_buys}"

    # 2. Zero acronym hallucinations (NIM, LCE, RFS, BOK, TSX, PRO)
    tickers = set(events_df["ticker"].astype(str))
    for bad_tok in ("NIM", "LCE", "RFS", "BOK", "TSX", "TSXV", "NYSE", "NASDAQ"):
        assert bad_tok not in tickers, f"Acronym {bad_tok} polluted Cluseau trade_events.csv"
        assert bad_tok in STOPWORD_ACRONYMS

    # 3. SK Square (402340.KS) entered in late April 2026, not January
    sk_sq_buys = events_df[(events_df["ticker"] == "402340.KS") & (events_df["action"] == "BUY")]
    assert len(sk_sq_buys) in (1, 2)
    assert sk_sq_buys.iloc[0]["date"] in ("2026-04-28", "2026-04-29")
    assert sk_sq_buys.iloc[0]["market"] == ":kr:"
    # Verify October 1 exit and genuine re-entry lifecycle
    sk_sq_sells = events_df[(events_df["ticker"] == "402340.KS") & (events_df["action"] == "SELL")]
    assert any(sk_sq_sells["date"] == "2026-10-01"), "Expected October 1 review exit for SK Square"
    assert sk_sq_sells.iloc[-1]["date"] == "2026-11-04", "Expected final November 4 exit for SK Square"

    # 4. WYFI exited in Oct 2025 and NOT active as of 2026-01-01
    prices = PriceProvider(settings)
    sim = PortfolioSimulator(settings, prices, holdings_df, events_df)
    active_2026 = sim.active_buys_at_date("2026-01-01")
    active_tickers = {b["ticker"] for b in active_2026}
    for not_active in ("WYFI", "402340.KS", "MOMO", "VISN"):
        assert not_active not in active_tickers
    for pre_2026_active in ("CBL", "AGM", "HRTG", "WSBF", "OPY"):
        assert pre_2026_active in active_tickers


def test_tjstocks_complete_stocktok_etf_lifecycle():
    settings = load_settings()
    src = settings.get_source("tjstocks")
    holdings_df = pd.read_csv(src.data_dir / "portfolio_holdings.csv")
    events_df = pd.read_csv(src.data_dir / "trade_events.csv")

    assert len(events_df) == 17, f"Expected 17 validated StockTok ETF events, got {len(events_df)}"

    # On 2026-07-28, exactly 3 removals (SPB, MSCI, FDX) and 3 additions (CAKE, CNXN, FELE)
    july_events = events_df[events_df["date"] == "2026-07-28"]
    sells = set(july_events[july_events["action"] == "SELL"]["ticker"])
    buys = set(july_events[july_events["action"] == "BUY"]["ticker"])
    assert sells == {"SPB", "MSCI", "FDX"}
    assert buys == {"CAKE", "CNXN", "FELE"}

    # VLO 50% discretionary trim on 2026-11-03
    vlo_event = events_df[(events_df["ticker"] == "VLO") & (events_df["action"] == "TRIM")]
    assert len(vlo_event) == 1
    assert vlo_event.iloc[0]["trim_fraction"] == pytest.approx(0.50)

    prices = PriceProvider(settings)
    sim = PortfolioSimulator(settings, prices, holdings_df, events_df)
    res = sim.run_strategy(seed_existing_buys=False, start_date="2026-01-01", end_date="2026-11-05")
    for sym in ("SPB", "MSCI", "FDX"):
        assert res.positions[sym].shares == pytest.approx(0.0)
    for sym in ("CAKE", "CNXN", "FELE", "PRU", "VLO"):
        assert res.positions[sym].shares > 0


def test_btt_clean_ledger_no_backdating_and_proper_international_symbols():
    settings = load_settings()
    src = settings.get_source("beatingthetide")
    holdings_df = pd.read_csv(src.data_dir / "portfolio_holdings.csv")
    events_df = pd.read_csv(src.data_dir / "trade_events.csv")

    # 1. No synthetic 2024-01-02 baseline BUYs or price strings in market codes
    assert len(events_df[events_df["date"] == "2024-01-02"]) == 0
    assert not events_df["market"].astype(str).str.contains(r"\$", na=False).any()
    assert not holdings_df["market"].astype(str).str.contains(r"\$", na=False).any()

    # 2. Verify no Supply Chain Services (SCS) acronym hallucination and proper ATI / ILC.SN extraction
    tickers = set(events_df["ticker"].astype(str))
    assert "SCS" not in tickers
    assert "ATI" in tickers
    assert "ILC.SN" in tickers

    # 3. Verify dated picks from Datawrapper / primary articles
    audit_samples = {
        "MU": "2025-12-30",
        "DELL": "2026-02-23",
        "ATI": "2026-04-13",
        "DAR": "2026-05-18",
        "SNEX": "2026-06-10",
        "CSTM": "2026-07-15",
    }
    for sym, expected_date in audit_samples.items():
        sym_buys = events_df[(events_df["ticker"] == sym) & (events_df["action"] == "BUY")]
        assert len(sym_buys) >= 1, f"Missing BUY for {sym}"
        assert sym_buys.iloc[0]["date"] == expected_date


def test_cash_conservation_arithmetic_identity():
    settings = load_settings()
    prices = PriceProvider(settings)

    for skey in ("beatingthetide", "tjstocks", "cluseau"):
        src = settings.get_source(skey)
        holdings_df = pd.read_csv(src.data_dir / "portfolio_holdings.csv")
        events_df = pd.read_csv(src.data_dir / "trade_events.csv")
        sim = PortfolioSimulator(settings, prices, holdings_df, events_df)

        for seed in (True, False):
            res = sim.run_strategy(seed_existing_buys=seed, start_date="2026-01-01", end_date="2026-11-05")
            implied_profit = res.ending_total_value - res.external_cash_invested
            assert implied_profit == pytest.approx(res.net_profit, abs=0.05)
            bench_implied = res.benchmark_ending_value - res.external_cash_invested
            assert bench_implied == pytest.approx(res.benchmark_net_profit, abs=0.05)


def test_multi_currency_fx_conversions_krw_jpy_eur_clp():
    settings = load_settings()
    prices = PriceProvider(settings)

    # KRW (SK Square 402340.KS)
    krw_px = prices.get_price("402340.KS", "2026-04-29", market=":kr:", in_usd=False)
    usd_px = prices.get_price("402340.KS", "2026-04-29", market=":kr:", in_usd=True)
    assert krw_px is not None and krw_px > 100000.0
    assert usd_px is not None and 250.0 < usd_px < 1200.0

    # JPY (Kioxia 285A.T)
    jpy_px = prices.get_price("285A.T", "2026-08-12", market=":jp:", in_usd=False)
    jpy_usd = prices.get_price("285A.T", "2026-08-12", market=":jp:", in_usd=True)
    assert jpy_px is not None and jpy_px > 500.0
    assert jpy_usd is not None and 3.0 < jpy_usd < 150.0

    # EUR (SK Hynix Frankfurt GDR HY9H.F)
    eur_px = prices.get_price("HY9H.F", "2026-08-12", market=":de:", in_usd=False)
    eur_usd = prices.get_price("HY9H.F", "2026-08-12", market=":de:", in_usd=True)
    assert eur_px is not None and eur_px > 50.0
    assert eur_usd is not None and eur_usd > eur_px

    # CLP (Inversiones La Construccion ILC.SN)
    clp_px = prices.get_price("ILC.SN", "2026-09-24", market=":cl:", in_usd=False)
    clp_usd = prices.get_price("ILC.SN", "2026-09-24", market=":cl:", in_usd=True)
    assert clp_px is not None and clp_px > 1000.0
    assert clp_usd is not None and 1.0 < clp_usd < 60.0


def test_targeted_accuracy_hardening_transaction_attribution():
    """Harden extraction and lifecycle accuracy across the 5 verified defect cases:
    1. NECB / OPBK: 'adding to OPBK and monitoring NECB' assigns ADD to OPBK only, NO BUY/ADD to NECB.
    2. SE Holdings / PFF: Volume commentary on Sehi does NOT produce spurious PFF trades.
    3. HY9H / Kioxia: SK Hynix Frankfurt buy on 2025-11-24 does NOT create a fake Kioxia 285A.T buy.
    4. CUBI / OPBK: Multi-security pricing assigns 73 to CUBI and 14 to OPBK distinctly.
    5. SK Square: Reconstructs genuine re-entry lifecycle (April entry, Oct 1 exit, Oct 30 re-entry, Nov 4 exit).
    """
    settings = load_settings()
    src = settings.get_source("cluseau")
    events_df = pd.read_csv(src.data_dir / "trade_events.csv")

    # 1. NECB / OPBK
    # On 2025-10-15, chat reply: "I've been adding to OPBK and just monitoring NECB"
    necb_events = events_df[(events_df["ticker"] == "NECB") & (events_df["date"] == "2025-10-15")]
    assert len(necb_events) == 0, f"Expected no trade for NECB on 2025-10-15, got: {necb_events}"
    opbk_oct15 = events_df[(events_df["ticker"] == "OPBK") & (events_df["date"] == "2025-10-15")]
    assert len(opbk_oct15) >= 1
    assert opbk_oct15.iloc[0]["action"] in ("BUY", "ADD")

    # 2. SE Holdings / PFF
    # Verify PFF (iShares Preferred & Income Securities ETF) never hallucinated in Cluseau ledger
    pff_events = events_df[events_df["ticker"] == "PFF"]
    assert len(pff_events) == 0, f"Spurious PFF trades found: {pff_events}"

    # 3. HY9H / Kioxia
    # 2025-11-24 SK Hynix GDR purchase should not generate any 285A.T trade
    kioxia_nov24 = events_df[(events_df["ticker"] == "285A.T") & (events_df["date"] == "2025-11-24")]
    assert len(kioxia_nov24) == 0, f"Hallucinated Kioxia purchase on 2025-11-24: {kioxia_nov24}"

    # 4. CUBI / OPBK
    # "picked up some CUBI at 73 and OPBK at 14"
    cubi_buy = events_df[(events_df["ticker"] == "CUBI") & (events_df["date"] == "2026-01-23")]
    assert not cubi_buy.empty
    assert cubi_buy.iloc[0]["ref_price"] == pytest.approx(73.0)

    opbk_buy = events_df[(events_df["ticker"] == "OPBK") & (events_df["date"] == "2026-01-23")]
    assert not opbk_buy.empty
    assert opbk_buy.iloc[0]["ref_price"] == pytest.approx(14.0)

    # 5. SK Square complete lifecycle
    sk_events = events_df[events_df["ticker"] == "402340.KS"].sort_values("date")
    actions = list(zip(sk_events["date"], sk_events["action"]))
    assert ("2026-10-01", "SELL") in actions, f"Missing 2026-10-01 review exit: {actions}"
    assert ("2026-11-04", "SELL") in actions, f"Missing 2026-11-04 re-entry SELL: {actions}"
    assert any(d >= "2026-10-02" and a in ("BUY", "ADD") for d, a in actions), f"Missing October re-entry: {actions}"

