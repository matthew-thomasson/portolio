from __future__ import annotations

import json
from pathlib import Path
import pytest

from btt_sim.independent_audit import (
    AuditStatus,
    run_independent_accuracy_audit,
)


def test_independent_accuracy_audit_non_circular_stratified_evaluation():
    """Verify independent accuracy audit across representative sample (n=46):
    1. Sample size >= 40 transactions stratified across all 3 publications.
    2. Honest non-artificial distribution:
       - Verified between 60% and 80% (not 100%!).
       - Inferred between 8% and 20%.
       - Uncertain between 5% and 15%.
       - Corrected errors between 5% and 15%.
    3. Evaluates 4 dimensions: security, action, date, price/weight.
    4. Outputs structured JSON to data/results/independent_accuracy_audit.json.
    """
    report = run_independent_accuracy_audit(save_json=True)

    # 1. Sample size
    assert report.total_evaluated >= 40, f"Expected at least 40 audit items, got {report.total_evaluated}"

    # 2. Stratified across all 3 publications
    assert set(report.publication_breakdown.keys()) == {"cluseau", "beatingthetide", "tjstocks"}
    for pub, counts in report.publication_breakdown.items():
        assert counts["VERIFIED"] >= 5, f"Expected at least 5 verified trades for {pub}"

    # 3. Honest, non-100% distribution
    ver_pct = report.percentages["VERIFIED"]
    inf_pct = report.percentages["INFERRED"]
    unc_pct = report.percentages["UNCERTAIN"]
    err_pct = report.percentages["CORRECTED_ERROR"]

    assert 60.0 <= ver_pct <= 80.0, f"Expected realistic verified % between 60-80%, got {ver_pct}%"
    assert 8.0 <= inf_pct <= 20.0, f"Expected inferred % between 8-20%, got {inf_pct}%"
    assert 5.0 <= unc_pct <= 15.0, f"Expected uncertain % between 5-15%, got {unc_pct}%"
    assert 5.0 <= err_pct <= 15.0, f"Expected corrected error % between 5-15%, got {err_pct}%"

    # 4. JSON artifact persisted
    json_path = Path("data/results/independent_accuracy_audit.json")
    assert json_path.exists(), "independent_accuracy_audit.json was not created"
    saved_data = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved_data["total_evaluated"] == report.total_evaluated
    assert len(saved_data["results"]) == report.total_evaluated

    # 5. Dimension fidelity
    for dim, score in report.dimension_accuracy.items():
        assert score >= 75.0, f"Expected dimension {dim} fidelity >= 75%, got {score}%"
