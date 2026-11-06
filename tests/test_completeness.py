from __future__ import annotations

import json
import pandas as pd

from btt_sim.config import load_settings
from btt_sim.ingestion import validate_source_archive
from btt_sim.prices import PriceProvider
from btt_sim.reconciliation import Checkpoint, CheckpointType, ReconciliationEngine, ReconciliationStatus


def test_source_archive_completeness_all_publications():
    """Verify 100% paid post integrity, zero truncated posts, zero 0-byte posts, and paginated chat archives across all 3 publications."""
    settings = load_settings()
    for skey in ("beatingthetide", "tjstocks", "cluseau"):
        src = settings.sources[skey]
        rep = validate_source_archive(src, save_report=False)
        assert rep.is_valid, f"{skey} archive failed validation: {rep.anomalies}"
        assert rep.posts_paywall_truncated_count == 0
        assert rep.posts_empty_or_corrupt_count == 0
        assert rep.posts_total_files > 0
        assert rep.chat_threads_count > 0
        assert rep.chat_replies_total_count > 0


def test_cluseau_korean_basket_true_forensic_chronology():
    """
    Verify authentic Korean basket chronology:
    - `opening-the-gates` (2026-04-29) is a watchlist/overview post and manufactures ZERO confirmed BUYs for 013030.KQ or 139130.KS.
    - `402340.KS` (SK Square) is entered on 2026-04-28 via primary chat (`bought a small position last night at 828000`), trimmed 2026-10-01, exited 2026-11-04.
    - `013030.KQ` (Hy-Lok) and `139130.KS` (iM Financial) are initiated from 2026-05-04 primary chat ownership disclosures with `date_uncertainty` recorded.
    - `453340.KS` (Hyundai Green Food) is initiated on 2026-05-11 from `boring-is-beautiful`.
    """
    settings = load_settings()
    cl = settings.sources["cluseau"]
    df = pd.read_csv(cl.data_dir / "trade_events.csv")

    # 1. Zero confirmed BUYs manufactured from `opening-the-gates`
    otg_buys = df[(df["source_slug"] == "opening-the-gates") & (df["action"] == "BUY")]
    assert len(otg_buys) == 0, f"opening-the-gates is a watchlist post and must not manufacture confirmed BUYs: {otg_buys}"

    # Verify candidate_events.json recorded opening-the-gates ideas as non-confirmed (`proposed` / `retrospective`), never `confirmed` BUY
    cands = json.loads((cl.data_dir / "candidate_events.json").read_text(encoding="utf-8"))
    otg_cands = [c for c in cands if c.get("source_id") == "opening-the-gates"]
    assert len(otg_cands) > 0
    assert all(c.get("execution_status") in ("proposed", "retrospective") for c in otg_cands)

    # 2. SK Square (402340.KS) full lifecycle
    sk = df[df["ticker"] == "402340.KS"].sort_values("date")
    assert not sk.empty
    assert sk.iloc[0]["action"] == "BUY"
    assert sk.iloc[0]["date"] in ("2026-04-28", "2026-04-29")
    assert sk.iloc[0]["discovery_layer"] == "primary_chat"
    assert any(sk["date"] == "2026-10-01") and any(sk["action"] == "SELL")
    assert sk[sk["action"] == "SELL"].iloc[-1]["date"] == "2026-11-04"

    # 3. Hy-Lok (013030.KQ) and iM Financial (139130.KS) May 2026 chat ownership disclosures
    hylok = df[(df["ticker"] == "013030.KQ") & (df["action"] == "BUY")].iloc[0]
    imfin = df[(df["ticker"] == "139130.KS") & (df["action"] == "BUY")].iloc[0]
    assert hylok["date"] >= "2026-05-04"
    assert imfin["date"] >= "2026-05-04"
    assert hylok["discovery_layer"] == "primary_chat"
    assert imfin["discovery_layer"] == "primary_chat"
    assert pd.notna(hylok["date_uncertainty"]) and str(hylok["date_uncertainty"]).strip() != ""
    assert pd.notna(imfin["date_uncertainty"]) and str(imfin["date_uncertainty"]).strip() != ""

    # 4. Hyundai Green Food (453340.KS) May 11 article execution
    hgf = df[(df["ticker"] == "453340.KS") & (df["action"] == "BUY")].iloc[0]
    assert hgf["date"] == "2026-05-11"
    assert hgf["source_slug"] == "boring-is-beautiful"


def test_cluseau_japanese_banks_gdrs_and_chat_exits():
    """
    Verify international lifecycles in Cluseau:
    - Japanese regional banks (`8399.T`, `7167.T`, `7380.T`): entries, 2026-10-15 50% trims, and 2026-10-22/23 full exits.
    - Disentangled memory instruments: `HY9H.F` (SK Hynix Frankfurt GDR), `SMSD.IL` (Samsung Preferred LSE-IOB), and `285A.T` (Kioxia TSE + 2026-10-30 close).
    - `IFOS.V` (2026-10-14 close), `GDDY` (2026-10-16 1/3 trim & 2026-10-30 close), `MOMO` (2026-09-10 close), `BARAX`, `NRG`, `ABCA.PA`, `6626.T`.
    """
    settings = load_settings()
    cl = settings.sources["cluseau"]
    df = pd.read_csv(cl.data_dir / "trade_events.csv")
    tickers = set(df["ticker"].astype(str))

    for required in ("8399.T", "7167.T", "7380.T", "HY9H.F", "SMSD.IL", "285A.T", "IFOS.V", "GDDY", "MOMO", "BARAX", "NRG", "ABCA.PA", "6626.T"):
        assert required in tickers, f"Missing expected validated security {required} in Cluseau trade_events.csv"

    # Japanese regional banks Oct 15 50% trims & Oct 22/23 exits
    for jbank, exit_dt in (("7167.T", "2026-10-22"), ("7380.T", "2026-10-22"), ("8399.T", "2026-10-23")):
        sub = df[df["ticker"] == jbank]
        assert any((sub["action"] == "TRIM") & (sub["date"] == "2026-10-15"))
        assert any((sub["action"] == "SELL") & (sub["date"] == exit_dt))

    # Kioxia & GoDaddy Oct 30 exits, IFOS Oct 14 exit, MOMO Sept 10 exit
    assert any((df["ticker"] == "285A.T") & (df["action"] == "SELL") & (df["date"] == "2026-10-30"))
    assert any((df["ticker"] == "GDDY") & (df["action"] == "SELL") & (df["date"] == "2026-10-30"))
    assert any((df["ticker"] == "IFOS.V") & (df["action"] == "SELL") & (df["date"] == "2026-10-14"))
    assert any((df["ticker"] == "MOMO") & (df["action"] == "SELL") & (df["date"] == "2026-09-10"))


def test_independent_checkpoint_reconciliation_and_hylok_disappearance():
    """Verify all 3 publications pass independent checkpoint reconciliation with 0 unresolved errors, and Cluseau flags 013030.KQ's silent disappearance."""
    settings = load_settings()
    prices = PriceProvider(settings)
    engine = ReconciliationEngine(settings, prices=prices)

    btt_audit = engine.validate_and_reconcile_source(settings.sources["beatingthetide"], save_outputs=False)
    assert btt_audit.overall_status == ReconciliationStatus.FULLY_RECONCILED
    assert btt_audit.unresolved_errors == 0
    assert btt_audit.checkpoints_evaluated >= 5

    tj_audit = engine.validate_and_reconcile_source(settings.sources["tjstocks"], save_outputs=False)
    assert tj_audit.overall_status == ReconciliationStatus.FULLY_RECONCILED
    assert tj_audit.unresolved_errors == 0
    assert tj_audit.checkpoints_evaluated == 3

    cl_audit = engine.validate_and_reconcile_source(settings.sources["cluseau"], save_outputs=False)
    assert cl_audit.overall_status == ReconciliationStatus.RECONCILED_WITH_WARNINGS
    assert cl_audit.unresolved_errors == 0
    assert any(
        d.ticker == "013030.KQ" and d.discrepancy_type == "UNEXPLAINED_DISAPPEARANCE" and d.severity == "WARNING"
        for d in cl_audit.discrepancies
    ), f"Expected 013030.KQ silent disappearance warning on Oct 5 review, got {cl_audit.discrepancies}"


def test_partial_snapshot_does_not_raise_false_missing_sale_alerts():
    """Verify partial prose snapshots do not raise false UNEXPECTED_IN_SIMULATION errors on unmentioned active holdings."""
    settings = load_settings()
    prices = PriceProvider(settings)
    engine = ReconciliationEngine(settings, prices=prices)
    cl = settings.sources["cluseau"]

    cp = Checkpoint(
        checkpoint_id="partial-check",
        source_key="cluseau",
        date="2026-06-12",
        evaluation_date="2026-06-12",
        title="Partial Prose Review",
        source_file="2026-06-12__june-2026-portfolio-review.json",
        checkpoint_type=CheckpointType.PARTIAL_SNAPSHOT,
        disclosed_positions={"453340.KS": {"status": "active", "name": "Hyundai Green Food", "evidence": "Accumulated"}},
    )
    discs = engine.reconcile_checkpoint(cl, cp)
    assert len(discs) == 0
