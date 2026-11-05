from __future__ import annotations

import json
from pathlib import Path
import pytest

from btt_sim.config import load_settings
from btt_sim.extractor import ExtractionEngine, ExtractedCandidate


def test_corpus_precision_recall_and_f1():
    """Evaluate extraction classification quality on independently labelled ground truth corpus."""
    settings = load_settings()
    engine = ExtractionEngine(settings)

    corpus_path = Path(__file__).parent / "corpus" / "labelled_ground_truth.json"
    assert corpus_path.exists(), f"Ground truth corpus not found at {corpus_path}"

    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    assert len(corpus) >= 40, f"Expected at least 40 labelled excerpts, got {len(corpus)}"

    tp = fp = tn = fn = 0
    failures: list[tuple[str, str]] = []

    for item in corpus:
        expected_is_trade = item["is_trade"]
        cand = engine.classify_statement(item["text"], item["source_publication"])
        predicted_is_trade = cand is not None

        if expected_is_trade and predicted_is_trade:
            tp += 1
            if item.get("expected_action") and cand.action != item["expected_action"]:
                failures.append((item["id"], f"Action mismatch: expected {item['expected_action']}, got {cand.action}"))
            if item.get("expected_ticker") and cand.ticker != item["expected_ticker"]:
                failures.append((item["id"], f"Ticker mismatch: expected {item['expected_ticker']}, got {cand.ticker}"))
            if item.get("expected_market") and cand.market != item["expected_market"]:
                failures.append((item["id"], f"Market mismatch: expected {item['expected_market']}, got {cand.market}"))
        elif not expected_is_trade and not predicted_is_trade:
            tn += 1
        elif not expected_is_trade and predicted_is_trade:
            fp += 1
            failures.append((item["id"], f"False Positive: expected non-trade, got {cand.action} {cand.ticker}"))
        elif expected_is_trade and not predicted_is_trade:
            fn += 1
            failures.append((item["id"], "False Negative: expected trade, got None"))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print(f"\nCorpus Evaluation Results (N={len(corpus)}):")
    print(f"TP: {tp} | TN: {tn} | FP: {fp} | FN: {fn}")
    print(f"Precision: {precision:.2%}")
    print(f"Recall:    {recall:.2%}")
    print(f"F1 Score:  {f1:.2%}")

    if failures:
        msg = "\n".join(f"[{fid}] {reason}" for fid, reason in failures)
        pytest.fail(f"Quality benchmark failures ({len(failures)}):\n{msg}")

    assert precision >= 0.95, f"Precision {precision:.2%} is below required 95%"
    assert recall >= 0.95, f"Recall {recall:.2%} is below required 95%"
    assert f1 >= 0.95, f"F1 Score {f1:.2%} is below required 95%"


def test_korean_and_international_ticker_normalization():
    """Verify numeric and non-US tickers normalize to correct exchange suffixes."""
    settings = load_settings()
    engine = ExtractionEngine(settings)

    # Korean 6-digit numeric tickers
    sym, mkt = engine._normalize_ticker_market("453340")
    assert sym == "453340.KS" and mkt == ":kr:"

    sym, mkt = engine._normalize_ticker_market("013030", "KQ")
    assert sym == "013030.KQ" and mkt == ":kr:"

    sym, mkt = engine._normalize_ticker_market("139130")
    assert sym == "139130.KS" and mkt == ":kr:"

    # Japanese 4-digit numeric & alphanumeric tickers
    sym, mkt = engine._normalize_ticker_market("7089", "JT")
    assert sym == "7089.T" and mkt == ":jp:"

    sym, mkt = engine._normalize_ticker_market("9220", "JP")
    assert sym == "9220.T" and mkt == ":jp:"

    sym, mkt = engine._normalize_ticker_market("6626")
    assert sym == "6626.T" and mkt == ":jp:"

    sym, mkt = engine._normalize_ticker_market("285A")
    assert sym == "285A.T" and mkt == ":jp:"

    # Australian, Canadian, European, Hong Kong
    sym, mkt = engine._normalize_ticker_market("CCV", "AU")
    assert sym == "CCV.AX" and mkt == ":au:"

    sym, mkt = engine._normalize_ticker_market("IFOS", "CA")
    assert sym == "IFOS.V" and mkt == ":ca:"

    sym, mkt = engine._normalize_ticker_market("ABCA", "FP")
    assert sym == "ABCA.PA" and mkt == ":eu:"

    sym, mkt = engine._normalize_ticker_market("3600", "HK")
    assert sym == "3600.HK" and mkt == ":hk:"


def test_non_trade_watchlist_and_commentary_rejection():
    """Ensure watchlist pitches, conditional ideas, and macro opinions are never classified as trades."""
    settings = load_settings()
    engine = ExtractionEngine(settings)

    non_trades = [
        "Puma (PUM.DE) is on my watchlist below 32 EUR, but I have not purchased shares yet.",
        "BABA is worth a look here given the cloud valuation, but I am waiting for earnings.",
        "Brookfield (BN) remains on the radar if valuation improves towards 10x FCF.",
        "If the stock drops to 6.50 I will re-enter the position.",
        "Closer to the Comfort Systems (FIX) earnings report, I will collar my position. I haven’t put on the trade yet.",
        "REITs remain deeply unloved as 10-year yields march towards 4.5% across global markets.",
        "I view International General Insurance (IGIC) as an elite insurer with stellar underwriting discipline.",
        "Matt, do you think Hyundai Green Food is still attractive at 21,000 KRW?",
    ]

    for stmt in non_trades:
        cand = engine.classify_statement(stmt)
        assert cand is None, f"Expected non-trade, but got candidate: {cand}"


def test_primary_chat_alert_extraction():
    """Verify primary extraction from subscriber chat threads."""
    settings = load_settings()
    engine = ExtractionEngine(settings)

    mock_chat_threads = [
        {
            "communityPost": {
                "created_at": "2026-10-14T14:30:00Z",
                "body": "Closing out the IFOS position today for a 30% loss",
            }
        },
        {
            "communityPost": {
                "created_at": "2026-10-16T15:00:00Z",
                "body": "GoDaddy getting close to $110... Taking a third of the position off here",
            }
        },
        {
            "communityPost": {
                "created_at": "2026-10-30T16:00:00Z",
                "body": "Closed remaining GDDY at $116 in Chat",
            }
        },
        {
            "communityPost": {
                "created_at": "2026-10-30T17:00:00Z",
                "body": "Trade Update on Kioxia (Closed)",
            }
        },
        {
            "communityPost": {
                "created_at": "2026-07-29T13:00:00Z",
                "body": "totally sold HRTG, totally sold WSBF, cut CBL in half",
            }
        },
    ]

    extracted = engine.extract_from_chat(mock_chat_threads)
    assert len(extracted) >= 6

    tickers = {c.ticker: c for c in extracted}
    assert "IFOS" in tickers
    assert tickers["IFOS"].action == "SELL"
    assert tickers["IFOS"].normalized_ticker == "IFOS.V"
    assert tickers["IFOS"].effective_date == "2026-10-14"

    assert "GDDY" in tickers
    assert "285A.T" in tickers
    assert tickers["285A.T"].action == "SELL"
    assert tickers["285A.T"].market == ":jp:"

    assert "HRTG" in tickers
    assert tickers["HRTG"].action == "SELL"
    assert "WSBF" in tickers
    assert tickers["WSBF"].action == "SELL"
    assert "CBL" in tickers
    assert tickers["CBL"].action == "TRIM"
