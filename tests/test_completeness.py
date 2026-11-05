from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import pytest

from btt_sim.config import load_settings
from btt_sim.prices import PriceProvider
from btt_sim.reconciliation import ReconciliationEngine, DisclosedPosition


def test_korean_positions_discovered_from_source():
    """Verify that the 3 missing Korean positions are discovered from authentic source evidence."""
    settings = load_settings()
    cluseau_src = settings.sources["cluseau"]
    trades_path = cluseau_src.data_dir / "trade_events.csv"
    assert trades_path.exists(), "trade_events.csv must exist for Cluseau"

    df = pd.read_csv(trades_path)
    tickers = set(df["ticker"].astype(str))

    # All three Korean positions must be present
    assert "013030" in tickers, "Hy-Lok (013030) must be present in Cluseau trades"
    assert "453340" in tickers, "Hyundai Green Food (453340) must be present in Cluseau trades"
    assert "139130" in tickers, "iM Financial Group (139130) must be present in Cluseau trades"

    # Verify authentic source citations
    hylok = df[df["ticker"] == "013030"].iloc[0]
    hyundai = df[df["ticker"] == "453340"].iloc[0]
    im_fin = df[df["ticker"] == "139130"].iloc[0]

    assert hylok["source_slug"] in ("opening-the-gates", "june-2026-portfolio-review")
    assert hyundai["source_slug"] == "boring-is-beautiful"
    assert im_fin["source_slug"] == "opening-the-gates"

    # Verify point-in-time entry dates (May / late April 2026, NOT backdated to Jan 1)
    assert hylok["date"] >= "2026-04-29"
    assert hyundai["date"] == "2026-05-11"
    assert im_fin["date"] == "2026-04-29"


def test_reconciliation_flags_orphan_holdings_without_hardcoding():
    """Verify that any security disclosed in a review without a prior entry trade is flagged dynamically."""
    settings = load_settings()
    engine = ReconciliationEngine(settings)
    cluseau_src = settings.sources["cluseau"]

    report = engine.audit_source(cluseau_src)
    assert report.articles_examined > 0
    assert report.chats_examined > 0

    # Ensure engine flags orphan holdings and reports them
    orphan_tickers = [oh["ticker"] for oh in report.orphan_holdings]
    # Options overlay hedges (IESC, FIX, WDC) are held without standard equity BUY entries
    assert any(sym in orphan_tickers for sym in ("IESC", "FIX", "WDC")), (
        f"Expected options hedges in orphan holdings, got: {orphan_tickers}"
    )


def test_unexplained_disappearance_detection():
    """Verify that a position present in a June review that vanishes without an exit is flagged."""
    settings = load_settings()
    engine = ReconciliationEngine(settings)
    cluseau_src = settings.sources["cluseau"]

    report = engine.audit_source(cluseau_src)
    disappeared_tickers = [ud["ticker"] for ud in report.unexplained_disappearances]
    assert "013030" in disappeared_tickers, (
        "Hy-Lok (013030) entered in May and mentioned in June review must be flagged as an unexplained disappearance"
    )


def test_multi_currency_fx_and_instrument_types():
    """Verify that Korean, Japanese, and international tickers are converted properly to USD."""
    settings = load_settings()
    pp = PriceProvider(settings)

    # Korean stock on KOSDAQ
    p_krw = pp.get_price("013030.KS", "2026-05-04", in_usd=False)
    p_usd = pp.get_price("013030.KS", "2026-05-04", in_usd=True)
    assert p_krw is not None and p_krw > 10000.0, "Hy-Lok price in KRW should be ~44,000"
    assert p_usd is not None and 20.0 < p_usd < 45.0, f"Hy-Lok USD price should be ~$31, got {p_usd}"

    # Japanese stock on Tokyo Exchange
    p_jpy = pp.get_price("9478.T", "2026-01-02", in_usd=False)
    p_jpy_usd = pp.get_price("9478.T", "2026-01-02", in_usd=True)
    assert p_jpy is not None and p_jpy > 100.0, "SE Holdings price in JPY should be ~394"
    assert p_jpy_usd is not None and 1.5 < p_jpy_usd < 4.0, f"SE Holdings USD price should be ~$2.50, got {p_jpy_usd}"


def test_no_hindsight_synthetic_trades():
    """Verify that no synthetic BUYs were manufactured at Jan 1 from later review exit recaps."""
    settings = load_settings()
    cluseau_src = settings.sources["cluseau"]
    trades_path = cluseau_src.data_dir / "trade_events.csv"
    df = pd.read_csv(trades_path)

    # SK Square was entered April 29, 2026, NOT on 2026-01-02
    sk_buys = df[(df["ticker"].isin(["402340", "402340.KS"])) & (df["action"] == "BUY")]
    for _, r in sk_buys.iterrows():
        assert r["date"] >= "2026-04-29", f"SK Square BUY cannot be before April 29, found {r['date']}"

    # MOMO was entered April 17, 2026, NOT on 2026-01-02
    momo_buys = df[(df["ticker"] == "MOMO") & (df["action"] == "BUY")]
    for _, r in momo_buys.iterrows():
        assert r["date"] >= "2026-04-17", f"MOMO BUY cannot be before April 17, found {r['date']}"
