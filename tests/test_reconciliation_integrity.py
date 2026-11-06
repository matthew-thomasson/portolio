from __future__ import annotations

import ast
import dataclasses
import inspect
import shutil
import textwrap
from pathlib import Path

import pandas as pd

from btt_sim.config import SourceConfig, load_settings
from btt_sim import extractor, parser, reconciliation
from btt_sim.prices import PriceProvider
from btt_sim.reconciliation import ReconciliationEngine, ReconciliationStatus


def _clone_source_with_temp_ledger(src: SourceConfig, tmp_path: Path, df_mutated: pd.DataFrame) -> SourceConfig:
    """Create a SourceConfig pointing to the real raw archives (`api_posts`, `datawrapper`, `chat`) but a mutated `trade_events.csv`."""
    temp_data = tmp_path / src.key / "data"
    temp_data.mkdir(parents=True, exist_ok=True)
    for fname in ("portfolio_holdings.csv", "non_equity_events.csv", "candidate_events.json", "ingestion_report.json"):
        orig = src.data_dir / fname
        if orig.exists():
            shutil.copy2(orig, temp_data / fname)
    df_mutated.to_csv(temp_data / "trade_events.csv", index=False)

    return dataclasses.replace(
        src,
        custom_data_dir=temp_data,
        custom_results_dir=temp_data / "results",
    )


def test_reconciliation_is_strictly_non_circular_when_holdings_deleted(tmp_path: Path):
    """
    Prove that Layer B checkpoints are derived strictly from raw source archives (`datawrapper/*.csv`, `api_posts/*.json`)
    and NEVER from `trade_events.csv`: deleting a real active position from `trade_events.csv` MUST immediately trigger
    `MISSING_IN_SIMULATION` (ERROR -> UNRECONCILED) across every publication!
    """
    settings = load_settings()
    prices = PriceProvider(settings)
    engine = ReconciliationEngine(settings, prices=prices)

    # 1. Beating The Tide: delete active holding DELL -> must fail Datawrapper checkpoint
    btt = settings.sources["beatingthetide"]
    btt_df = pd.read_csv(btt.data_dir / "trade_events.csv")
    btt_mut = _clone_source_with_temp_ledger(btt, tmp_path, btt_df[btt_df["ticker"] != "DELL"])
    btt_audit = engine.validate_and_reconcile_source(btt_mut, save_outputs=False)
    assert btt_audit.overall_status == ReconciliationStatus.UNRECONCILED
    assert any(d.ticker == "DELL" and d.discrepancy_type == "MISSING_IN_SIMULATION" and d.severity == "ERROR" for d in btt_audit.discrepancies)

    # 2. TJ Stocks: delete active holding PRU -> must fail StockTok ETF checkpoints
    tj = settings.sources["tjstocks"]
    tj_df = pd.read_csv(tj.data_dir / "trade_events.csv")
    tj_mut = _clone_source_with_temp_ledger(tj, tmp_path, tj_df[tj_df["ticker"] != "PRU"])
    tj_audit = engine.validate_and_reconcile_source(tj_mut, save_outputs=False)
    assert tj_audit.overall_status == ReconciliationStatus.UNRECONCILED
    assert any(d.ticker == "PRU" and d.discrepancy_type == "MISSING_IN_SIMULATION" and d.severity == "ERROR" for d in tj_audit.discrepancies)

    # 3. Cluseau: delete active Korean holding 453340.KS (Hyundai Green Food) -> must fail June & Sept Portfolio Reviews
    cl = settings.sources["cluseau"]
    cl_df = pd.read_csv(cl.data_dir / "trade_events.csv")
    cl_mut = _clone_source_with_temp_ledger(cl, tmp_path, cl_df[cl_df["ticker"] != "453340.KS"])
    cl_audit = engine.validate_and_reconcile_source(cl_mut, save_outputs=False)
    assert cl_audit.overall_status == ReconciliationStatus.UNRECONCILED
    assert any(d.ticker == "453340.KS" and d.discrepancy_type == "MISSING_IN_SIMULATION" and d.severity == "ERROR" for d in cl_audit.discrepancies)


def test_reconciliation_catches_missing_exit_trades_across_all_sources(tmp_path: Path):
    """
    Prove that deleting an executed SELL trade from `trade_events.csv` immediately triggers
    `UNEXPECTED_IN_SIMULATION` (ERROR -> UNRECONCILED) across all 3 publications!
    """
    settings = load_settings()
    prices = PriceProvider(settings)
    engine = ReconciliationEngine(settings, prices=prices)

    # 1. Beating The Tide: delete PYPL SELL -> must fail Datawrapper closed-pick verification
    btt = settings.sources["beatingthetide"]
    btt_df = pd.read_csv(btt.data_dir / "trade_events.csv")
    btt_mut = _clone_source_with_temp_ledger(btt, tmp_path, btt_df[~((btt_df["ticker"] == "PYPL") & (btt_df["action"] == "SELL"))])
    btt_audit = engine.validate_and_reconcile_source(btt_mut, save_outputs=False)
    assert btt_audit.overall_status == ReconciliationStatus.UNRECONCILED
    assert any(d.ticker == "PYPL" and d.discrepancy_type == "UNEXPECTED_IN_SIMULATION" for d in btt_audit.discrepancies)

    # 2. TJ Stocks: delete FDX SELL on 2026-07-28 -> must fail StockTok ETF 2.0 & Nov 3 checkpoints
    tj = settings.sources["tjstocks"]
    tj_df = pd.read_csv(tj.data_dir / "trade_events.csv")
    tj_mut = _clone_source_with_temp_ledger(tj, tmp_path, tj_df[~((tj_df["ticker"] == "FDX") & (tj_df["action"] == "SELL"))])
    tj_audit = engine.validate_and_reconcile_source(tj_mut, save_outputs=False)
    assert tj_audit.overall_status == ReconciliationStatus.UNRECONCILED
    assert any(d.ticker == "FDX" and d.discrepancy_type == "UNEXPECTED_IN_SIMULATION" for d in tj_audit.discrepancies)

    # 3. Cluseau: delete MOMO SELL on 2026-09-10 -> must fail September 2026 Portfolio Review Removals verification
    cl = settings.sources["cluseau"]
    cl_df = pd.read_csv(cl.data_dir / "trade_events.csv")
    cl_mut = _clone_source_with_temp_ledger(cl, tmp_path, cl_df[~((cl_df["ticker"] == "MOMO") & (cl_df["action"] == "SELL"))])
    cl_audit = engine.validate_and_reconcile_source(cl_mut, save_outputs=False)
    assert cl_audit.overall_status == ReconciliationStatus.UNRECONCILED
    assert any(d.ticker == "MOMO" and d.discrepancy_type == "UNEXPECTED_IN_SIMULATION" for d in cl_audit.discrepancies)


def test_zero_hardcoded_cheats_and_non_circular_checkpoint_discovery_ast():
    """
    Static code & AST audit verifying:
    1. `discover_checkpoints()` never calls `replay_portfolio_to_date` or reads `trade_events.csv`.
    2. Neither `extractor.py`, `parser.py`, nor `reconciliation.py` contains `inception_articles` or hardcoded checkpoint dicts.
    """
    disc_src = textwrap.dedent(inspect.getsource(ReconciliationEngine.discover_checkpoints))
    fn_node = ast.parse(disc_src).body[0]
    assert isinstance(fn_node, ast.FunctionDef)
    exec_body_src = "\n".join(
        ast.unparse(stmt)
        for idx, stmt in enumerate(fn_node.body)
        if not (idx == 0 and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str))
    )
    assert "replay_portfolio_to_date" not in exec_body_src
    assert "trade_events.csv" not in exec_body_src

    for mod in (extractor, parser, reconciliation):
        mod_src = inspect.getsource(mod)
        tree = ast.parse(mod_src)
        assigned_names = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        assert "inception_articles" not in assigned_names
        assert "INCEPTION_ARTICLES" not in assigned_names
        assert "MANUAL_CHECKPOINTS" not in assigned_names


def test_shorts_and_options_excluded_from_long_equity_ledger():
    """Verify short sales (ACIC, JPM, UVE) and option hedges are recorded in `non_equity_events.csv` and never in `trade_events.csv`."""
    settings = load_settings()
    cl = settings.sources["cluseau"]

    long_df = pd.read_csv(cl.data_dir / "trade_events.csv")
    neq_df = pd.read_csv(cl.data_dir / "non_equity_events.csv")

    long_tickers = set(long_df["ticker"].astype(str))
    for short_sym in ("ACIC", "JPM", "UVE"):
        assert short_sym not in long_tickers, f"Short position {short_sym} must never enter long cash equity ledger!"

    neq_tickers = set(neq_df["normalized_ticker"].astype(str))
    for short_sym in ("ACIC", "JPM", "UVE"):
        assert short_sym in neq_tickers, f"Short position {short_sym} must be preserved in non_equity_events.csv!"
    assert "short" in set(neq_df["instrument_type"].astype(str))
