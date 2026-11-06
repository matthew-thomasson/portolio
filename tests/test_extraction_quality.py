from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from btt_sim.config import load_settings
from btt_sim.extractor import ExtractedCandidate, ExtractionEngine, unpack_substack_widgets


def _run_production_item(engine: ExtractionEngine, item: dict[str, Any]) -> tuple[list[ExtractedCandidate], list[ExtractedCandidate]]:
    """
    Execute the EXACT production ExtractionEngine entrypoint (`extract_from_article` or `extract_from_chat`)
    used by `parse_source_data()`, then apply the exact production long-security filter.
    """
    # Use a fresh resolver per isolated test document so cross-item state cannot leak cheats
    fresh_engine = ExtractionEngine(engine.settings, prices=engine.prices)
    itype = item["input_type"]
    payload = item["payload"]

    if itype == "article":
        raw_cands = fresh_engine.extract_from_article(payload)
    elif itype == "chat":
        author_ids = set(payload.get("author_ids") or [])
        raw_cands = fresh_engine.extract_from_chat(
            chat_threads=payload.get("threads") or [],
            chat_replies=payload.get("replies_map") or {},
            author_ids=author_ids,
        )
    else:
        raise ValueError(f"Unsupported input_type: {itype}")

    # Apply exact production filtering for simulated long cash securities:
    # confirmed + long instrument (equity/preferred/etf/mutual_fund) + BUY/ADD/TRIM/SELL + primary discovery layer + deduplicated per (date, ticker, action)
    confirmed_long: list[ExtractedCandidate] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for c in raw_cands:
        if (
            c.execution_status == "confirmed"
            and c.instrument_type in ("equity", "preferred", "etf", "mutual_fund")
            and c.action in ("BUY", "ADD", "TRIM", "SELL")
            and not (c.action == "HOLD" and c.discovery_layer == "checkpoint_review")
            and c.normalized_ticker not in fresh_engine.known_shorts
        ):
            dedup_key = (c.effective_date, c.normalized_ticker, c.action)
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                confirmed_long.append(c)

    return confirmed_long, raw_cands


def _evaluate_split(items: list[dict[str, Any]], engine: ExtractionEngine) -> tuple[dict[str, Any], list[str]]:
    tp = fp = fn = tn_docs = 0
    action_correct = action_total = 0
    ticker_correct = ticker_total = 0
    date_correct = date_total = 0
    sizing_correct = sizing_total = 0
    exec_vs_idea_correct = exec_vs_idea_total = 0
    failures: list[str] = []

    for item in items:
        iid = item["id"]
        expected = item.get("expected_confirmed_long_trades") or []
        pred_long, all_cands = _run_production_item(engine, item)

        exec_vs_idea_total += 1
        if bool(expected) == bool(pred_long):
            exec_vs_idea_correct += 1

        if not expected and not pred_long:
            tn_docs += 1
            # Also verify non-equity / non-confirmed metadata when specified
            if item.get("expected_non_equity_actions"):
                got_neq = {c.action for c in all_cands if c.instrument_type not in ("equity", "preferred", "etf", "mutual_fund")}
                if not set(item["expected_non_equity_actions"]).issubset(got_neq):
                    failures.append(f"[{iid}] Expected non-equity actions {item['expected_non_equity_actions']}, got {got_neq} (all={all_cands})")
            continue

        # Match predicted trades against expected trades by normalized_ticker + effective_date (or normalized_ticker fallback)
        unmatched_pred = list(pred_long)
        for exp in expected:
            exp_sym = exp["normalized_ticker"]
            exp_act = exp["action"]
            exp_mkt = exp["market"]
            exp_dt = exp["effective_date"]

            match_idx = None
            for idx, p in enumerate(unmatched_pred):
                if p.normalized_ticker == exp_sym and p.action == exp_act:
                    match_idx = idx
                    break
            if match_idx is None:
                for idx, p in enumerate(unmatched_pred):
                    if p.normalized_ticker == exp_sym or p.ticker == exp_sym.split(".")[0]:
                        match_idx = idx
                        break

            if match_idx is None:
                fn += 1
                failures.append(f"[{iid}] FN missing expected {exp_act} {exp_sym} ({exp_dt}); predicted={[f'{x.action}:{x.normalized_ticker}@{x.effective_date}' for x in pred_long]}")
            else:
                p = unmatched_pred.pop(match_idx)
                tp += 1

                action_total += 1
                if p.action == exp_act:
                    action_correct += 1
                else:
                    failures.append(f"[{iid}] Action mismatch for {exp_sym}: expected {exp_act}, got {p.action}")

                ticker_total += 1
                if p.normalized_ticker == exp_sym and p.market == exp_mkt:
                    ticker_correct += 1
                else:
                    failures.append(f"[{iid}] Ticker/market mismatch: expected {exp_sym} ({exp_mkt}), got {p.normalized_ticker} ({p.market})")

                date_total += 1
                if p.effective_date == exp_dt:
                    date_correct += 1
                else:
                    failures.append(f"[{iid}] Effective date mismatch for {exp_sym}: expected {exp_dt}, got {p.effective_date}")

                if "trim_fraction" in exp and exp["trim_fraction"] is not None:
                    sizing_total += 1
                    if p.trim_fraction is not None and abs(p.trim_fraction - float(exp["trim_fraction"])) <= 0.02:
                        sizing_correct += 1
                    else:
                        failures.append(f"[{iid}] Trim sizing mismatch for {exp_sym}: expected {exp['trim_fraction']}, got {p.trim_fraction}")

        for extra in unmatched_pred:
            fp += 1
            failures.append(f"[{iid}] FP unexpected confirmed long trade: {extra.action} {extra.normalized_ticker} ({extra.effective_date}) from '{extra.exact_text}'")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    metrics = {
        "documents_count": len(items),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negative_documents": tn_docs,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "action_accuracy": round(action_correct / action_total, 4) if action_total else 1.0,
        "ticker_exchange_accuracy": round(ticker_correct / ticker_total, 4) if ticker_total else 1.0,
        "effective_date_accuracy": round(date_correct / date_total, 4) if date_total else 1.0,
        "sizing_accuracy": round(sizing_correct / sizing_total, 4) if sizing_total else 1.0,
        "execution_vs_idea_accuracy": round(exec_vs_idea_correct / exec_vs_idea_total, 4) if exec_vs_idea_total else 1.0,
    }
    return metrics, failures


def test_production_path_extraction_benchmark_and_held_out_generalization():
    """
    Evaluate the exact production ExtractionEngine (`extract_from_article` & `extract_from_chat`)
    across both in-archive representative documents AND held-out unseen US & international securities.
    """
    settings = load_settings()
    engine = ExtractionEngine(settings)

    corpus_path = Path(__file__).parent / "corpus" / "production_eval_corpus.json"
    assert corpus_path.exists(), f"Production evaluation corpus missing at {corpus_path}"

    corpus: list[dict[str, Any]] = json.loads(corpus_path.read_text(encoding="utf-8"))
    in_archive = [x for x in corpus if not x.get("is_held_out")]
    held_out = [x for x in corpus if x.get("is_held_out")]

    assert len(in_archive) >= 40, f"Expected >=40 in-archive items, got {len(in_archive)}"
    assert len(held_out) >= 25, f"Expected >=25 held-out unseen items, got {len(held_out)}"

    # Ensure all 7 required held-out categories are represented
    ho_cats = {x["category"] for x in held_out}
    required_cats = {
        "confirmed_purchase",
        "confirmed_addition",
        "partial_trim",
        "full_exit",
        "multi_trade_chat",
        "short_or_option_exclusion",
        "watchlist_or_conditional",
    }
    assert required_cats.issubset(ho_cats), f"Held-out split missing required categories: {required_cats - ho_cats}"

    overall_metrics, overall_failures = _evaluate_split(corpus, engine)
    in_metrics, _ = _evaluate_split(in_archive, engine)
    ho_metrics, ho_failures = _evaluate_split(held_out, engine)

    # Save machine-readable evaluation metrics for documentation synchronization
    out_metrics_path = settings.data_dir / "extraction_eval_metrics.json"
    out_metrics_path.parent.mkdir(parents=True, exist_ok=True)
    out_metrics_path.write_text(
        json.dumps(
            {
                "extractor_version": engine._hash_content("version_probe")[:12],
                "evaluated_entrypoints": ["ExtractionEngine.extract_from_article", "ExtractionEngine.extract_from_chat"],
                "overall": overall_metrics,
                "in_archive_split": in_metrics,
                "held_out_unseen_split": ho_metrics,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if overall_failures:
        pytest.fail("Production-path benchmark failures:\n" + "\n".join(overall_failures))

    assert overall_metrics["precision"] >= 0.95
    assert overall_metrics["recall"] >= 0.95
    assert ho_metrics["precision"] >= 0.95, f"Held-out precision below 95%: {ho_metrics} ({ho_failures})"
    assert ho_metrics["recall"] >= 0.95, f"Held-out recall below 95%: {ho_metrics} ({ho_failures})"


def test_international_gdr_tse_kosdaq_and_adr_normalization():
    """Verify general-purpose normalization across KOSPI, KOSDAQ, TSE, Frankfurt GDR, LSE-IOB, Santiago, and US ADRs."""
    settings = load_settings()
    engine = ExtractionEngine(settings)

    # Korean KOSPI vs KOSDAQ resolution
    assert engine._normalize_ticker_market("453340") == ("453340.KS", ":kr:")
    assert engine._normalize_ticker_market("013030", "KQ") == ("013030.KQ", ":kr:")
    assert engine._normalize_ticker_market("139130") == ("139130.KS", ":kr:")

    # Japanese 4-digit, colon-suffix TYO, and alphanumeric TSE codes (e.g. Kioxia 285A)
    assert engine._normalize_ticker_market("8399:TYO") == ("8399.T", ":jp:")
    assert engine._normalize_ticker_market("285A") == ("285A.T", ":jp:")
    assert engine._normalize_ticker_market("6626", "JP") == ("6626.T", ":jp:")

    # Frankfurt GDR (HY9H -> HY9H.F) & London IOB GDR (SMSD LI -> SMSD.IL)
    assert engine._normalize_ticker_market("HY9H", context="Frankfurt GDR in EUR") == ("HY9H.F", ":de:")
    assert engine._normalize_ticker_market("SMSD", "LI") == ("SMSD.IL", ":uk:")

    # Santiago Stock Exchange CLP context (ILC -> ILC.SN) vs US ADR with country flag (KB with KR -> KB)
    assert engine._normalize_ticker_market("ILC", context="target of CLP 38,300") == ("ILC.SN", ":cl:")
    assert engine._normalize_ticker_market("KB", "KS") == ("KB", ":kr:")

    # Australia, Canada, France, Portugal, Hong Kong 4-digit zero-padding
    assert engine._normalize_ticker_market("CCV", "AU") == ("CCV.AX", ":au:")
    assert engine._normalize_ticker_market("IFOS", "V") == ("IFOS.V", ":ca:")
    assert engine._normalize_ticker_market("ABCA", "FP") == ("ABCA.PA", ":fr:")
    assert engine._normalize_ticker_market("CTT", "PL") == ("CTT.LS", ":pt:")
    assert engine._normalize_ticker_market("700", "HKG") == ("0700.HK", ":hk:")


def test_cashtag_widget_unpacking_and_acronym_protection():
    """Verify Substack CashtagToDOM and StockTickerToDOM spans unpack to explicit $TICKER tokens."""
    raw_html = (
        '<p>Bought <span data-component-name="CashtagToDOM" data-attrs="{&quot;symbol&quot;:&quot;TCBX&quot;}"></span> '
        'and <span data-component-name="StockTickerToDOM" data-attrs="{&quot;symbol&quot;:&quot;NWG&quot;}"></span> '
        'while NIM and BOK policy rates stabilized.</p>'
    )
    unpacked = unpack_substack_widgets(raw_html)
    assert "$TCBX" in unpacked
    assert "$NWG" in unpacked
