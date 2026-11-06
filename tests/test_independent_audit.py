from __future__ import annotations

import json
from pathlib import Path
import pytest

from btt_sim.config import load_settings
from btt_sim.extractor import ExtractionEngine
from btt_sim.independent_audit import (
    AuditSampleRecord,
    AuditStatus,
    SourceDocumentArchive,
    evaluate_transaction_evidence,
    run_independent_accuracy_audit,
)


def test_independent_accuracy_audit_retrieves_genuine_archived_records():
    """Verify that the independent audit evaluates real production records against authentic archived source files:
    1. Sample size >= 40 real production transactions stratified across Cluseau, Beating The Tide, and TJ Stocks.
    2. 100% of audited samples retrieve an authentic archived source file on disk with non-empty content.
    3. Results and metrics are calculated dynamically from actual evidence evaluations (no hardcoded/predetermined labels).
    4. Evaluates all 4 dimensions independently: security attribution, action execution, date exactness, and price/sizing.
    5. Persists complete audit output to data/results/independent_accuracy_audit.json.
    """
    report = run_independent_accuracy_audit(save_json=True)

    # 1. Sample size and coverage
    assert report.total_audited >= 40, f"Expected at least 40 audited records, got {report.total_audited}"
    assert set(report.publication_breakdown.keys()) == {"cluseau", "beatingthetide", "tjstocks"}

    # 2. Genuine source retrieval verification
    for item in report.results:
        doc_path = item.get("document_path")
        assert doc_path is not None, f"Sample {item['sample_id']} has no document path"
        assert Path(doc_path).exists(), f"Source file does not exist on disk: {doc_path}"
        assert item.get("evidence_excerpt"), f"Sample {item['sample_id']} has empty evidence excerpt"

    # 3. Dynamic metrics check (non-zero counts and real dimension evaluations)
    assert report.counts["VERIFIED"] > 0
    assert report.counts["INFERRED"] > 0
    assert report.dimension_accuracy["security_attribution"] > 90.0
    assert report.dimension_accuracy["action_classification"] > 85.0
    assert report.dimension_accuracy["date_exactness"] > 60.0
    assert report.dimension_accuracy["price_sizing_support"] > 90.0

    # 4. JSON artifact verification
    json_path = Path("data/results/independent_accuracy_audit.json")
    assert json_path.exists(), "independent_accuracy_audit.json was not created"
    saved_data = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved_data["total_audited"] == report.total_audited
    assert len(saved_data["results"]) == report.total_audited


def test_independent_accuracy_audit_detects_deliberate_corruptions():
    """Verify that the independent evaluation detects deliberately corrupted transactions:
    - Corrupted ticker -> fails security attribution, classified as ERROR.
    - Corrupted action -> fails action execution, classified as ERROR.
    - Corrupted date -> fails date exactness, classified as INFERRED or unverified date.
    - Corrupted price -> fails price/sizing support, classified as ERROR.
    """
    archive = SourceDocumentArchive()

    # 1. Baseline genuine record (CUBI at 73 in Cluseau chat)
    clean_rec = AuditSampleRecord(
        sample_id="CORRUPT-TEST",
        publication="cluseau",
        date="2026-01-23",
        ticker="CUBI",
        action="ADD",
        ref_price=73.0,
        target_weight=None,
        trim_fraction=None,
        source_type="trade_alert",
        source_slug="chat:ca8c6edb:reply:848c72ad",
        ledger_notes="picked up some CUBI at 73 and OPBK at 14",
    )
    doc = archive.retrieve("cluseau", "trade_alert", clean_rec.source_slug)
    assert doc["found"], "Could not retrieve CUBI chat source"

    clean_status, clean_dim, _, _ = evaluate_transaction_evidence(clean_rec, doc)
    assert clean_status == AuditStatus.VERIFIED
    assert clean_dim.security_supported is True
    assert clean_dim.action_supported is True
    assert clean_dim.date_supported is True
    assert clean_dim.price_sizing_supported is True

    # 2. Corrupt ticker: replace CUBI with AAPL (not in source text)
    corrupt_tk = AuditSampleRecord(
        sample_id="CORRUPT-TK",
        publication=clean_rec.publication,
        date=clean_rec.date,
        ticker="AAPL",
        action=clean_rec.action,
        ref_price=clean_rec.ref_price,
        target_weight=clean_rec.target_weight,
        trim_fraction=clean_rec.trim_fraction,
        source_type=clean_rec.source_type,
        source_slug=clean_rec.source_slug,
        ledger_notes=clean_rec.ledger_notes,
    )
    st_tk, dim_tk, _, _ = evaluate_transaction_evidence(corrupt_tk, doc)
    assert dim_tk.security_supported is False
    assert st_tk == AuditStatus.ERROR, f"Expected ERROR for fake ticker AAPL, got {st_tk}"

    # 3. Corrupt action: replace ADD with SELL on a buy thesis/alert
    corrupt_act = AuditSampleRecord(
        sample_id="CORRUPT-ACT",
        publication=clean_rec.publication,
        date=clean_rec.date,
        ticker=clean_rec.ticker,
        action="SELL",
        ref_price=clean_rec.ref_price,
        target_weight=clean_rec.target_weight,
        trim_fraction=clean_rec.trim_fraction,
        source_type=clean_rec.source_type,
        source_slug=clean_rec.source_slug,
        ledger_notes=clean_rec.ledger_notes,
    )
    st_act, dim_act, _, _ = evaluate_transaction_evidence(corrupt_act, doc)
    assert dim_act.action_supported is False
    assert st_act == AuditStatus.ERROR, f"Expected ERROR for contradictory SELL action, got {st_act}"

    # 4. Corrupt date: move date to 2023-01-01
    corrupt_dt = AuditSampleRecord(
        sample_id="CORRUPT-DT",
        publication=clean_rec.publication,
        date="2023-01-01",
        ticker=clean_rec.ticker,
        action=clean_rec.action,
        ref_price=clean_rec.ref_price,
        target_weight=clean_rec.target_weight,
        trim_fraction=clean_rec.trim_fraction,
        source_type=clean_rec.source_type,
        source_slug=clean_rec.source_slug,
        ledger_notes=clean_rec.ledger_notes,
    )
    st_dt, dim_dt, _, _ = evaluate_transaction_evidence(corrupt_dt, doc)
    assert dim_dt.date_supported is False
    assert st_dt in (AuditStatus.INFERRED, AuditStatus.UNCERTAIN), f"Expected non-VERIFIED for corrupted date, got {st_dt}"

    # 5. Corrupt price: replace 73.0 with 999.0
    corrupt_px = AuditSampleRecord(
        sample_id="CORRUPT-PX",
        publication=clean_rec.publication,
        date=clean_rec.date,
        ticker=clean_rec.ticker,
        action=clean_rec.action,
        ref_price=999.0,
        target_weight=clean_rec.target_weight,
        trim_fraction=clean_rec.trim_fraction,
        source_type=clean_rec.source_type,
        source_slug=clean_rec.source_slug,
        ledger_notes=clean_rec.ledger_notes,
    )
    st_px, dim_px, _, _ = evaluate_transaction_evidence(corrupt_px, doc)
    assert dim_px.price_sizing_supported is False
    assert st_px == AuditStatus.ERROR, f"Expected ERROR for contradictory price, got {st_px}"


def test_tmobile_spurious_mobile_extraction_prevented():
    """Regression test: verify that discussing a 'mobile banking application' in the
    SUPV Argentina deep dive does NOT register TMUS as a buy trade candidate.
    """
    settings = load_settings()
    engine = ExtractionEngine(settings)
    post_file = Path("sources/beatingthetide/api_posts/2025-01-21__argentina-investment-alert-supv-ypf.json")
    assert post_file.exists(), f"Missing post file: {post_file}"
    post_data = json.loads(post_file.read_text(encoding="utf-8"))

    # Register T-Mobile binding
    engine.resolver.register_binding("T-Mobile", "TMUS")
    assert "mobile" not in engine.resolver.alias_map, "'mobile' must not be registered as a standalone alias for TMUS"

    candidates = engine.extract_from_article(post_data)
    extracted_tickers = {c.normalized_ticker for c in candidates}
    assert "TMUS" not in extracted_tickers, f"Spurious TMUS extracted from mobile banking context: {candidates}"
