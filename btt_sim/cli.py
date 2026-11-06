from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

from .config import Settings, SourceConfig, load_settings
from .downloader import (
    download_chat_archive,
    extract_datawrapper_datasets,
    fetch_all_api_posts,
    resolve_cookie_name,
    run_sbstck_dl,
)
from .extractor import EXTRACTOR_VERSION
from .ingestion import validate_source_archive
from .parser import parse_source_data
from .prices import PriceProvider
from .reconciliation import PortfolioReconciliationAudit, ReconciliationEngine
from .simulator import PortfolioSimulator, SimulationResult, compute_attribution

console = Console()


def _fmt_money(v: float | None) -> str:
    return f"${v:,.2f}" if v is not None else "N/A"


def _fmt_pct(v: float | None) -> str:
    return f"{v:+.2f}%" if v is not None else "N/A"


def _get_target_sources(settings: Settings, source_arg: str) -> list[SourceConfig]:
    if source_arg == "all":
        return list(settings.sources.values())
    return [settings.get_source(source_arg)]


def _needs_reparse(src: SourceConfig) -> bool:
    events_path = src.data_dir / "trade_events.csv"
    cand_path = src.data_dir / "candidate_events.json"
    cache_path = src.data_dir / "extraction_cache.json"
    if not events_path.exists() or not cand_path.exists() or not cache_path.exists():
        return True
    try:
        cache_obj = json.loads(cache_path.read_text(encoding="utf-8"))
        if cache_obj.get("_version") != EXTRACTOR_VERSION:
            return True
    except Exception:
        return True

    try:
        ref_mtime = min(cache_path.stat().st_mtime, events_path.stat().st_mtime)

        # 1. API post files: reparse if file count grew or any post file was modified
        if src.api_posts_dir.exists():
            post_files = list(src.api_posts_dir.glob("*.json"))
            cached_posts_count = len(cache_obj.get("posts", {})) if isinstance(cache_obj.get("posts"), dict) else 0
            if len(post_files) > cached_posts_count:
                return True
            for pf in post_files:
                if pf.stat().st_mtime > ref_mtime:
                    return True

        # 2. Chat archives: reparse if chat threads or replies updated
        for cf_name in ("chat_threads.json", "chat_replies.json"):
            cf = src.chat_dir / cf_name
            if cf.exists() and cf.stat().st_mtime > ref_mtime:
                return True

        # 3. Datawrapper CSV datasets
        if src.datawrapper_dir.exists():
            for df in src.datawrapper_dir.glob("*.csv"):
                if df.stat().st_mtime > ref_mtime:
                    return True

        # 4. Baseline portfolio holdings
        ph = src.data_dir / "portfolio_holdings.csv"
        if ph.exists() and ph.stat().st_mtime > events_path.stat().st_mtime:
            return True
    except Exception:
        return True

    return False


def _ensure_validated_and_reconciled(
    settings: Settings,
    src: SourceConfig,
    prices: PriceProvider | None = None,
    quiet: bool = False,
) -> PortfolioReconciliationAudit:
    """
    Universal Analysis Gate:
    1. Validate source archive completeness (Layer A input integrity).
    2. Incrementally parse/extract primary transactions if missing or extractor version changed.
    3. Independently discover & reconcile portfolio checkpoints (Layer B verification).
    """
    ing = validate_source_archive(src, save_report=True)
    if not ing.is_valid and not quiet:
        console.print(
            f"[bold red]⚠ Archive Integrity Warning ({src.display_name}):[/bold red] "
            f"{ing.posts_paywall_truncated_count} truncated paid posts, "
            f"{ing.posts_empty_or_corrupt_count} corrupt/empty posts."
        )

    if _needs_reparse(src):
        if not quiet:
            console.print(f"[dim]Running incremental primary extraction (v{EXTRACTOR_VERSION}) for {src.display_name}...[/dim]")
        parse_source_data(src, settings)

    engine = ReconciliationEngine(settings, prices=prices)
    audit = engine.validate_and_reconcile_source(src, save_outputs=True)

    if not quiet:
        st_val = audit.overall_status.value
        st_col = "green" if st_val == "FULLY_RECONCILED" else ("yellow" if st_val == "RECONCILED_WITH_WARNINGS" else "red")
        console.print(
            f"[bold cyan]✓ Universal Verification ({src.display_name}):[/bold cyan] "
            f"[{st_col}]{st_val}[/{st_col}] "
            f"(ArchiveValid={audit.is_archive_valid} | Checkpoints={audit.checkpoints_evaluated} | "
            f"UnresolvedErrors={audit.unresolved_errors} | Warnings={audit.warnings_count})"
        )
        if audit.unresolved_errors > 0:
            console.print(
                f"[bold red]  ! {audit.unresolved_errors} unresolved checkpoint discrepancy error(s) detected! "
                f"Inspect {src.results_dir / 'reconciliation_audit.json'} before trusting simulation outputs.[/bold red]"
            )
    return audit


def cmd_check_auth(args: argparse.Namespace) -> None:
    settings = load_settings()
    sources = _get_target_sources(settings, args.source)
    for src in sources:
        if not src.cookie_val:
            console.print(f"[yellow]{src.display_name}: No cookie set in .env ({src.key.upper()}_COOKIE_VAL).[/yellow]")
            continue
        cname, is_paid = resolve_cookie_name(src)
        status = "[bold green]PAID ACCESS UNLOCKED[/bold green]" if is_paid else "[bold red]COOKIE UNVERIFIED[/bold red]"
        console.print(f"{src.display_name} ({src.url}): {status} (using {cname})")


def cmd_audit(args: argparse.Namespace) -> None:
    """Run comprehensive source coverage and independent checkpoint reconciliation audit."""
    settings = load_settings()
    prices = PriceProvider(settings)
    sources = _get_target_sources(settings, args.source)
    engine = ReconciliationEngine(settings, prices=prices)

    for src in sources:
        if _needs_reparse(src):
            console.print(f"[dim]Refreshing primary extraction (v{EXTRACTOR_VERSION}) for {src.display_name}...[/dim]")
            parse_source_data(src, settings)

        rep = engine.audit_source(src)
        audit = rep.audit
        assert audit is not None

        # 1. High-level source & reconciliation metrics
        table = Table(title=f"Source Archive & Reconciliation Audit: {src.display_name}")
        table.add_column("Audit Metric", style="cyan")
        table.add_column("Result", style="bold")
        st_col = (
            "green"
            if rep.overall_status == "FULLY_RECONCILED"
            else ("yellow" if rep.overall_status == "RECONCILED_WITH_WARNINGS" else "red")
        )
        table.add_row("Overall Reconciliation Status", f"[{st_col}]{rep.overall_status}[/{st_col}]")
        table.add_row("API Posts Downloaded (Paid)", f"{rep.api_posts_count} ({rep.paid_posts_count} paid)")
        table.add_row(
            "Paywall-Truncated / Zero-Byte Posts",
            f"[red]{rep.truncated_posts_count} / {rep.zero_byte_posts_count}[/red]"
            if (rep.truncated_posts_count or rep.zero_byte_posts_count)
            else "[green]0 / 0[/green]",
        )
        table.add_row("Subscriber Chat Threads / Replies", f"{rep.chat_threads_count} threads / {rep.chat_replies_count} replies")
        table.add_row("Datawrapper Tables Extracted", str(rep.datawrapper_tables_count))
        table.add_row("Validated Long Trade Events (Unique Tickers)", f"{rep.trade_events_count} ({rep.unique_simulated_tickers} tickers)")
        table.add_row("Independent Checkpoints Evaluated", str(rep.checkpoints_count))
        table.add_row("Disclosed Checkpoint Positions Checked", str(rep.disclosed_positions_checked))
        table.add_row("Positions Reconciled Cleanly", str(rep.reconciled_count))
        table.add_row(
            "Unresolved Discrepancy Errors",
            f"[bold red]{rep.unresolved_discrepancies_count}[/bold red]" if rep.unresolved_discrepancies_count else "[green]0[/green]",
        )
        table.add_row(
            "Warnings (e.g. Silent Disappearances)",
            f"[bold yellow]{rep.warnings_count}[/bold yellow]" if rep.warnings_count else "[green]0[/green]",
        )
        console.print(table)

        # 2. Checkpoint-by-checkpoint reconciliation table
        cp_table = Table(title=f"Independent Point-in-Time Checkpoints: {src.display_name}")
        cp_table.add_column("Eval Date", style="cyan")
        cp_table.add_column("Checkpoint Title", style="bold")
        cp_table.add_column("Type", style="dim")
        cp_table.add_column("Active", justify="right")
        cp_table.add_column("Closed", justify="right")
        cp_table.add_column("Errors", justify="right")
        cp_table.add_column("Warnings", justify="right")

        for cp in audit.checkpoints:
            cp_discs = [d for d in audit.discrepancies if d.checkpoint_id == cp.checkpoint_id]
            n_err = sum(1 for d in cp_discs if d.severity == "ERROR" and not d.is_resolved)
            n_warn = sum(1 for d in cp_discs if d.severity == "WARNING")
            n_act = sum(1 for v in cp.disclosed_positions.values() if v.get("status") == "active")
            n_cls = sum(1 for v in cp.disclosed_positions.values() if v.get("status") == "closed")
            err_str = f"[bold red]{n_err}[/bold red]" if n_err else "[green]0[/green]"
            warn_str = f"[yellow]{n_warn}[/yellow]" if n_warn else "0"
            cp_table.add_row(
                cp.evaluation_date,
                cp.title[:56],
                cp.checkpoint_type.value,
                str(n_act),
                str(n_cls),
                err_str,
                warn_str,
            )
        console.print(cp_table)

        # 3. Print any ERROR or WARNING discrepancies with root cause
        notable = [d for d in audit.discrepancies if d.severity in ("ERROR", "WARNING")]
        if notable:
            console.print("[bold]Notable Checkpoint Findings & Automated Root-Cause Attribution:[/bold]")
            for d in notable:
                col = "red" if d.severity == "ERROR" else "yellow"
                console.print(
                    f"  - [{col}][{d.severity}] {d.checkpoint_date} | {d.ticker} ({d.discrepancy_type} -> {d.root_cause.value})[/{col}]: "
                    f"{d.evidence_summary}"
                )

        out_rep = src.results_dir / "coverage_report.json"
        src.results_dir.mkdir(parents=True, exist_ok=True)
        out_rep.write_text(json.dumps(rep.to_dict(), indent=2), encoding="utf-8")
        console.print(f"[dim]Saved coverage & reconciliation report to {out_rep}[/dim]\n")

    prices.save_ticker_map()


def cmd_download(args: argparse.Namespace) -> None:
    settings = load_settings()
    sources = _get_target_sources(settings, args.source)
    for src in sources:
        console.print(f"\n[bold blue]=== Downloading {src.display_name} ({src.url}) ===[/bold blue]")
        cname, is_paid = resolve_cookie_name(src)
        if src.cookie_val:
            status = "[green]PAID UNLOCKED[/green]" if is_paid else "[yellow]FREE / UNVERIFIED[/yellow]"
            console.print(f"Auth cookie: {cname} -> {status}")
        else:
            console.print("[yellow]No cookie set — fetching public/free posts only.[/yellow]")

        if not args.skip_sbstck_dl:
            run_sbstck_dl(
                src,
                settings.sbstck_bin,
                cookie_name=cname,
                after=args.after,
                before=args.before,
                download_images=not args.no_images,
            )

        fetch_all_api_posts(
            src,
            cookie_name=cname,
            after=args.after,
            before=args.before,
            force=args.force,
        )
        chat_stats = download_chat_archive(
            src,
            cookie_name=cname,
            force=args.force,
        )
        manifest = extract_datawrapper_datasets(src)
        ing = validate_source_archive(src, save_report=True)
        console.print(
            f"[green]{src.display_name} download complete:[/green] "
            f"{ing.posts_total_files} API posts ({ing.posts_paid_count} paid), "
            f"{chat_stats.get('threads_count', 0)} chat threads / {chat_stats.get('replies_count', 0)} replies, "
            f"{len(manifest)} Datawrapper tables (ArchiveValid={ing.is_valid})."
        )


def cmd_parse(args: argparse.Namespace) -> None:
    settings = load_settings()
    sources = _get_target_sources(settings, args.source)
    for src in sources:
        console.print(f"\n[bold blue]=== Parsing {src.display_name} (Extractor v{EXTRACTOR_VERSION}) ===[/bold blue]")
        holdings_df, events_df = parse_source_data(src, settings)
        console.print(f"[bold green]Parsed {len(holdings_df)} baseline holdings and {len(events_df)} validated trade events.[/bold green]")
        console.print(f"  Holdings CSV:   {src.data_dir / 'portfolio_holdings.csv'}")
        console.print(f"  Events CSV:     {src.data_dir / 'trade_events.csv'}")
        console.print(f"  Candidates JSON:{src.data_dir / 'candidate_events.json'}")
        if not events_df.empty:
            counts = events_df["action"].value_counts().to_dict()
            console.print(f"  Event breakdown: {counts}")


def cmd_trades(args: argparse.Namespace) -> None:
    settings = load_settings()
    prices = PriceProvider(settings)
    sources = _get_target_sources(settings, args.source)
    for src in sources:
        _ensure_validated_and_reconciled(settings, src, prices=prices)
        events_path = src.data_dir / "trade_events.csv"
        if not events_path.exists() or events_path.stat().st_size == 0:
            console.print(f"[yellow]{src.display_name}: trade_events.csv not found.[/yellow]")
            continue
        try:
            df = pd.read_csv(events_path)
        except Exception as e:
            console.print(f"[red]Error reading {events_path}: {e}[/red]")
            continue
        if df.empty:
            console.print(f"[yellow]{src.display_name}: No trade events recorded.[/yellow]")
            continue

        df["date"] = df["date"].astype(str).str.slice(0, 10)
        df = df.sort_values("date", ascending=False)
        if getattr(args, "limit", None):
            df = df.head(args.limit)

        table = Table(title=f"{src.display_name} Validated Long Trade Ledger ({len(df)} trades shown)")
        table.add_column("Date", style="cyan")
        table.add_column("Ticker", style="bold yellow")
        table.add_column("Action", style="bold")
        table.add_column("Layer", style="green")
        table.add_column("Ref Px", justify="right")
        table.add_column("Weight", justify="right")
        table.add_column("Trim", justify="right")
        table.add_column("Source Slug", style="dim")
        table.add_column("Notes")

        for _, r in df.iterrows():
            act = str(r.get("action", ""))
            act_color = "green" if act in ("BUY", "ADD") else ("red" if act == "SELL" else "yellow")
            px_val = f"${float(r['ref_price']):.2f}" if pd.notna(r.get("ref_price")) and str(r.get("ref_price")) != "" else "—"
            wgt_val = f"{float(r['target_weight'])*100:.1f}%" if pd.notna(r.get("target_weight")) and str(r.get("target_weight")) != "" else "—"
            trim_val = f"{float(r['trim_fraction'])*100:.0f}%" if pd.notna(r.get("trim_fraction")) and str(r.get("trim_fraction")) != "" else "—"
            notes = str(r.get("notes", ""))
            if len(notes) > 58:
                notes = notes[:55] + "..."

            table.add_row(
                str(r.get("date", "")),
                str(r.get("ticker", "")),
                f"[{act_color}]{act}[/{act_color}]",
                str(r.get("discovery_layer", "primary_article")),
                px_val,
                wgt_val,
                trim_val,
                str(r.get("source_slug", ""))[:32],
                notes,
            )
        console.print(table)
    prices.save_ticker_map()


def _run_sim_for_source(
    settings: Settings,
    prices: PriceProvider,
    src: SourceConfig,
    args: argparse.Namespace,
    quiet_audit: bool = False,
) -> tuple[SimulationResult | None, SimulationResult | None, pd.DataFrame, PortfolioReconciliationAudit]:
    audit = _ensure_validated_and_reconciled(settings, src, prices=prices, quiet=quiet_audit)

    holdings_path = src.data_dir / "portfolio_holdings.csv"
    events_path = src.data_dir / "trade_events.csv"
    if not events_path.exists():
        console.print(f"[yellow]{src.display_name}: trade_events.csv not found. Run `uv run btt --source {src.key} parse` first.[/yellow]")
        return None, None, pd.DataFrame(), audit

    holdings_df = pd.DataFrame()
    if holdings_path.exists() and holdings_path.stat().st_size > 0:
        try:
            holdings_df = pd.read_csv(holdings_path)
        except Exception:
            holdings_df = pd.DataFrame()

    events_df = pd.DataFrame()
    if events_path.exists() and events_path.stat().st_size > 0:
        try:
            events_df = pd.read_csv(events_path)
        except Exception:
            events_df = pd.DataFrame()
    if events_df.empty:
        console.print(f"[yellow]{src.display_name}: No trade events found in {events_path}.[/yellow]")
        return None, None, events_df, audit

    sim = PortfolioSimulator(settings, prices, holdings_df, events_df)
    reinvest = None if getattr(args, "reinvest", None) is None else args.reinvest

    res_a = sim.run_strategy(
        seed_existing_buys=True,
        start_date=args.start,
        end_date=getattr(args, "end", None),
        allocation_mode=getattr(args, "mode", None),
        unit_usd=getattr(args, "unit", None),
        add_unit_usd=getattr(args, "add_unit", None),
        trim_fraction=getattr(args, "trim_fraction", None),
        reinvest_sales_cash=reinvest,
    )
    res_b = sim.run_strategy(
        seed_existing_buys=False,
        start_date=args.start,
        end_date=getattr(args, "end", None),
        allocation_mode=getattr(args, "mode", None),
        unit_usd=getattr(args, "unit", None),
        add_unit_usd=getattr(args, "add_unit", None),
        trim_fraction=getattr(args, "trim_fraction", None),
        reinvest_sales_cash=reinvest,
    )
    return res_a, res_b, events_df, audit


def cmd_simulate(args: argparse.Namespace) -> None:
    settings = load_settings()
    prices = PriceProvider(settings)
    sources = _get_target_sources(settings, args.source)

    for src in sources:
        console.print(f"\n[bold blue]=== Simulation: {src.display_name} ({args.start} -> {args.end or 'Latest'}) ===[/bold blue]")
        res_a, res_b, events_df, audit = _run_sim_for_source(settings, prices, src, args)
        if not res_a or not res_b:
            continue

        tbl = Table(
            title=f"{src.display_name} ({res_a.start_date} -> {res_a.end_date} | mode={res_a.allocation_mode})",
            show_lines=True,
        )
        tbl.add_column("Metric", style="bold")
        tbl.add_column("Strategy A: Seed BUYs at T0 + Follow", justify="right", style="cyan")
        tbl.add_column("Strategy B: Future Trades Only from T0", justify="right", style="magenta")
        tbl.add_column("Difference (A - B)", justify="right", style="green")

        tbl.add_row("Seeded Positions on T0", str(res_a.seeded_count), str(res_b.seeded_count), f"{res_a.seeded_count - res_b.seeded_count:+d}")
        tbl.add_row("Total Executed Trades", str(len(res_a.trades)), str(len(res_b.trades)), f"{len(res_a.trades) - len(res_b.trades):+d}")
        tbl.add_row("Unique Simulated Positions", str(len(res_a.positions)), str(len(res_b.positions)), f"{len(res_a.positions) - len(res_b.positions):+d}")
        tbl.add_row("External Capital Deployed", _fmt_money(res_a.external_cash_invested), _fmt_money(res_b.external_cash_invested), _fmt_money(res_a.external_cash_invested - res_b.external_cash_invested))
        tbl.add_row("Ending Value (Equity + Cash)", _fmt_money(res_a.ending_total_value), _fmt_money(res_b.ending_total_value), _fmt_money(res_a.ending_total_value - res_b.ending_total_value))
        tbl.add_row("Net Profit ($)", _fmt_money(res_a.net_profit), _fmt_money(res_b.net_profit), _fmt_money(res_a.net_profit - res_b.net_profit))
        tbl.add_row("Total Return on Capital (%)", _fmt_pct(res_a.roi_pct), _fmt_pct(res_b.roi_pct), _fmt_pct(res_a.roi_pct - res_b.roi_pct))
        tbl.add_row("Annualized XIRR (%)", _fmt_pct(res_a.xirr_pct), _fmt_pct(res_b.xirr_pct), _fmt_pct((res_a.xirr_pct - res_b.xirr_pct) if (res_a.xirr_pct is not None and res_b.xirr_pct is not None) else None))
        tbl.add_row(f"Matched-Cash-Flow {res_a.benchmark_ticker} ROI (%)", _fmt_pct(res_a.benchmark_roi_pct), _fmt_pct(res_b.benchmark_roi_pct), _fmt_pct(res_a.benchmark_roi_pct - res_b.benchmark_roi_pct))
        tbl.add_row(f"Matched-Cash-Flow {res_a.benchmark_ticker} XIRR (%)", _fmt_pct(res_a.benchmark_xirr_pct), _fmt_pct(res_b.benchmark_xirr_pct), "—")
        tbl.add_row(
            f"Excess XIRR vs {res_a.benchmark_ticker} (Alpha)",
            _fmt_pct((res_a.xirr_pct - res_a.benchmark_xirr_pct) if (res_a.xirr_pct is not None and res_a.benchmark_xirr_pct is not None) else None),
            _fmt_pct((res_b.xirr_pct - res_b.benchmark_xirr_pct) if (res_b.xirr_pct is not None and res_b.benchmark_xirr_pct is not None) else None),
            "—",
        )
        console.print(tbl)

        neq_path = src.data_dir / "non_equity_events.csv"
        attr_a = compute_attribution(res_a, events_df, neq_path)
        attr_b = compute_attribution(res_b, events_df, neq_path)

        if attr_a["geographic_attribution"]:
            gtbl = Table(title=f"{src.display_name} Geographic Attribution (Strategy A)")
            gtbl.add_column("Region", style="cyan")
            gtbl.add_column("Positions (Open)", justify="right")
            gtbl.add_column("Gross Bought ($)", justify="right")
            gtbl.add_column("Realized PnL ($)", justify="right")
            gtbl.add_column("Unrealized PnL ($)", justify="right")
            gtbl.add_column("Total PnL ($)", justify="right", style="bold")
            gtbl.add_column("Return on Bought %", justify="right")
            for g in attr_a["geographic_attribution"]:
                gtbl.add_row(
                    g["region"],
                    f"{g['positions_count']} ({g['open_positions_count']})",
                    _fmt_money(g["capital_deployed_usd"]),
                    _fmt_money(g["realized_pnl_usd"]),
                    _fmt_money(g["unrealized_pnl_usd"]),
                    _fmt_money(g["total_pnl_usd"]),
                    _fmt_pct(g["return_on_deployed_pct"]),
                )
            console.print(gtbl)

        out_dir = src.results_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        tag = f"{res_a.start_date}_to_{res_a.end_date}_{res_a.allocation_mode}"
        target_dirs = [out_dir]
        if src.key == "beatingthetide":
            target_dirs.append(settings.data_dir / "results")

        summary_payload = {
            "source_key": src.key,
            "display_name": src.display_name,
            "reconciliation_status": audit.overall_status.value,
            "unresolved_errors": audit.unresolved_errors,
            "warnings_count": audit.warnings_count,
            "start_date": res_a.start_date,
            "end_date": res_a.end_date,
            "allocation_mode": res_a.allocation_mode,
            "strategy_A": {
                "seeded_count": res_a.seeded_count,
                "trades_count": len(res_a.trades),
                "positions_count": len(res_a.positions),
                "open_positions_count": sum(1 for p in res_a.positions.values() if p.shares > 1e-9),
                "external_cash_invested": round(res_a.external_cash_invested, 2),
                "ending_equity_value": round(res_a.ending_equity_value, 2),
                "ending_cash_balance": round(res_a.ending_cash_balance, 2),
                "ending_total_value": round(res_a.ending_total_value, 2),
                "realized_pnl": round(res_a.realized_pnl, 2),
                "unrealized_pnl": round(res_a.unrealized_pnl, 2),
                "net_profit": round(res_a.net_profit, 2),
                "roi_pct": round(res_a.roi_pct, 2),
                "xirr_pct": round(res_a.xirr_pct, 2) if res_a.xirr_pct is not None else None,
                "benchmark_ticker": res_a.benchmark_ticker,
                "benchmark_ending_value": round(res_a.benchmark_ending_value, 2),
                "benchmark_net_profit": round(res_a.benchmark_net_profit, 2),
                "benchmark_roi_pct": round(res_a.benchmark_roi_pct, 2),
                "benchmark_xirr_pct": round(res_a.benchmark_xirr_pct, 2) if res_a.benchmark_xirr_pct is not None else None,
            },
            "strategy_B": {
                "seeded_count": res_b.seeded_count,
                "trades_count": len(res_b.trades),
                "positions_count": len(res_b.positions),
                "open_positions_count": sum(1 for p in res_b.positions.values() if p.shares > 1e-9),
                "external_cash_invested": round(res_b.external_cash_invested, 2),
                "ending_equity_value": round(res_b.ending_equity_value, 2),
                "ending_cash_balance": round(res_b.ending_cash_balance, 2),
                "ending_total_value": round(res_b.ending_total_value, 2),
                "realized_pnl": round(res_b.realized_pnl, 2),
                "unrealized_pnl": round(res_b.unrealized_pnl, 2),
                "net_profit": round(res_b.net_profit, 2),
                "roi_pct": round(res_b.roi_pct, 2),
                "xirr_pct": round(res_b.xirr_pct, 2) if res_b.xirr_pct is not None else None,
                "benchmark_ticker": res_b.benchmark_ticker,
                "benchmark_ending_value": round(res_b.benchmark_ending_value, 2),
                "benchmark_net_profit": round(res_b.benchmark_net_profit, 2),
                "benchmark_roi_pct": round(res_b.benchmark_roi_pct, 2),
                "benchmark_xirr_pct": round(res_b.benchmark_xirr_pct, 2) if res_b.benchmark_xirr_pct is not None else None,
            },
        }

        for d in target_dirs:
            d.mkdir(parents=True, exist_ok=True)
            res_a.position_summary.to_csv(d / f"positions_strategy_A_{tag}.csv", index=False)
            res_b.position_summary.to_csv(d / f"positions_strategy_B_{tag}.csv", index=False)
            pd.DataFrame([t.__dict__ for t in res_a.trades]).to_csv(d / f"trades_strategy_A_{tag}.csv", index=False)
            pd.DataFrame([t.__dict__ for t in res_b.trades]).to_csv(d / f"trades_strategy_B_{tag}.csv", index=False)
            (d / f"attribution_strategy_A_{tag}.json").write_text(json.dumps(attr_a, indent=2), encoding="utf-8")
            (d / f"attribution_strategy_B_{tag}.json").write_text(json.dumps(attr_b, indent=2), encoding="utf-8")
            (d / f"summary_metrics_{tag}.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    prices.save_ticker_map()


def cmd_compare(args: argparse.Namespace) -> None:
    """Compare all publications side-by-side with mandatory reconciliation gating."""
    settings = load_settings()
    prices = PriceProvider(settings)

    tbl = Table(
        title=f"Multi-Source Newsletter Comparison ({args.start} -> {args.end or 'Latest'} | Mode: {args.mode or settings.allocation_mode})",
        show_lines=True,
    )
    tbl.add_column("Newsletter / Source", style="bold")
    tbl.add_column("Reconciliation Status", justify="center")
    tbl.add_column("Strategy A Profit ($)", justify="right", style="cyan")
    tbl.add_column("Strategy A ROI %", justify="right", style="cyan")
    tbl.add_column("Strategy A XIRR %", justify="right", style="cyan")
    tbl.add_column("Strategy B Profit ($)", justify="right", style="magenta")
    tbl.add_column("Strategy B ROI %", justify="right", style="magenta")
    tbl.add_column("Strategy B XIRR %", justify="right", style="magenta")
    tbl.add_column("SPY Benchmark XIRR (A)", justify="right")

    comparison_rows: list[dict] = []
    for src in settings.sources.values():
        res_a, res_b, _, audit = _run_sim_for_source(settings, prices, src, args)
        st_val = audit.overall_status.value
        st_col = "green" if st_val == "FULLY_RECONCILED" else ("yellow" if st_val == "RECONCILED_WITH_WARNINGS" else "red")
        st_badge = f"[{st_col}]{st_val}[/{st_col}]"

        if not res_a or not res_b:
            tbl.add_row(src.display_name, st_badge, "No data", "No data", "No data", "No data", "No data", "No data", "—")
            continue
        tbl.add_row(
            src.display_name,
            st_badge,
            _fmt_money(res_a.net_profit),
            _fmt_pct(res_a.roi_pct),
            _fmt_pct(res_a.xirr_pct),
            _fmt_money(res_b.net_profit),
            _fmt_pct(res_b.roi_pct),
            _fmt_pct(res_b.xirr_pct),
            _fmt_pct(res_a.benchmark_xirr_pct),
        )
        comparison_rows.append(
            {
                "source_key": src.key,
                "display_name": src.display_name,
                "reconciliation_status": st_val,
                "unresolved_errors": audit.unresolved_errors,
                "warnings_count": audit.warnings_count,
                "start_date": res_a.start_date,
                "end_date": res_a.end_date,
                "a_seeded": res_a.seeded_count,
                "a_trades": len(res_a.trades),
                "a_positions": len(res_a.positions),
                "a_external_capital": round(res_a.external_cash_invested, 2),
                "a_ending_value": round(res_a.ending_total_value, 2),
                "a_net_profit": round(res_a.net_profit, 2),
                "a_roi_pct": round(res_a.roi_pct, 2),
                "a_xirr_pct": round(res_a.xirr_pct, 2) if res_a.xirr_pct is not None else None,
                "a_spy_roi_pct": round(res_a.benchmark_roi_pct, 2),
                "a_spy_xirr_pct": round(res_a.benchmark_xirr_pct, 2) if res_a.benchmark_xirr_pct is not None else None,
                "b_trades": len(res_b.trades),
                "b_positions": len(res_b.positions),
                "b_external_capital": round(res_b.external_cash_invested, 2),
                "b_ending_value": round(res_b.ending_total_value, 2),
                "b_net_profit": round(res_b.net_profit, 2),
                "b_roi_pct": round(res_b.roi_pct, 2),
                "b_xirr_pct": round(res_b.xirr_pct, 2) if res_b.xirr_pct is not None else None,
                "b_spy_roi_pct": round(res_b.benchmark_roi_pct, 2),
                "b_spy_xirr_pct": round(res_b.benchmark_xirr_pct, 2) if res_b.benchmark_xirr_pct is not None else None,
            }
        )

    if comparison_rows:
        out_cmp = settings.data_dir / "results"
        out_cmp.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(comparison_rows).to_csv(out_cmp / f"multi_source_comparison_{args.start}.csv", index=False)

    prices.save_ticker_map()
    console.print(tbl)


def cmd_sweep(args: argparse.Namespace) -> None:
    settings = load_settings()
    prices = PriceProvider(settings)
    sources = _get_target_sources(settings, args.source)

    for src in sources:
        _ensure_validated_and_reconciled(settings, src, prices=prices)
        holdings_path = src.data_dir / "portfolio_holdings.csv"
        events_path = src.data_dir / "trade_events.csv"
        if not events_path.exists():
            continue

        holdings_df = pd.read_csv(holdings_path) if holdings_path.exists() and holdings_path.stat().st_size > 0 else pd.DataFrame()
        events_df = pd.read_csv(events_path)
        if events_df.empty:
            continue

        sim = PortfolioSimulator(settings, prices, holdings_df, events_df)
        dates = pd.date_range(start=args.start_from, end=args.start_to, freq=args.freq)
        tbl = Table(title=f"{src.display_name} Entry Sensitivity Sweep (End={args.end or 'Latest'})")
        tbl.add_column("Start Date (T0)")
        tbl.add_column("A Seeded", justify="right")
        tbl.add_column("A ROI %", justify="right", style="cyan")
        tbl.add_column("A XIRR %", justify="right", style="cyan")
        tbl.add_column("B ROI %", justify="right", style="magenta")
        tbl.add_column("B XIRR %", justify="right", style="magenta")
        tbl.add_column("Winner (XIRR)", justify="center")

        sweep_rows: list[dict] = []
        for dt in dates:
            d_str = dt.strftime("%Y-%m-%d")
            ra = sim.run_strategy(True, d_str, end_date=args.end, allocation_mode=args.mode, unit_usd=args.unit)
            rb = sim.run_strategy(False, d_str, end_date=args.end, allocation_mode=args.mode, unit_usd=args.unit)
            winner = "—"
            if ra.xirr_pct is not None and rb.xirr_pct is not None:
                winner = "Strategy A" if ra.xirr_pct > rb.xirr_pct else "Strategy B"
            tbl.add_row(d_str, str(ra.seeded_count), _fmt_pct(ra.roi_pct), _fmt_pct(ra.xirr_pct), _fmt_pct(rb.roi_pct), _fmt_pct(rb.xirr_pct), winner)
            sweep_rows.append(
                {
                    "start_date": d_str,
                    "a_seeded": ra.seeded_count,
                    "a_roi_pct": round(ra.roi_pct, 2),
                    "a_xirr_pct": round(ra.xirr_pct, 2) if ra.xirr_pct is not None else None,
                    "b_roi_pct": round(rb.roi_pct, 2),
                    "b_xirr_pct": round(rb.xirr_pct, 2) if rb.xirr_pct is not None else None,
                    "spy_xirr_a_pct": round(ra.benchmark_xirr_pct, 2) if ra.benchmark_xirr_pct is not None else None,
                    "spy_xirr_b_pct": round(rb.benchmark_xirr_pct, 2) if rb.benchmark_xirr_pct is not None else None,
                }
            )
        console.print(tbl)

        if sweep_rows:
            sw_df = pd.DataFrame(sweep_rows)
            for d in [src.results_dir] + ([settings.data_dir / "results"] if src.key == "beatingthetide" else []):
                d.mkdir(parents=True, exist_ok=True)
                sw_df.to_csv(d / "sweep_comparison.csv", index=False)
    prices.save_ticker_map()


def main() -> None:
    parser = argparse.ArgumentParser(prog="btt", description="Multi-Source Substack Downloader & Portfolio Simulator")
    parser.add_argument(
        "--source",
        default="beatingthetide",
        choices=["beatingthetide", "tjstocks", "cluseau", "all"],
        help="Target publication source (default: beatingthetide)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_auth = sub.add_parser("check-auth", help="Verify paid Substack cookie for source(s)")
    p_auth.set_defaults(func=cmd_check_auth)

    p_audit = sub.add_parser("audit", help="Run source coverage and independent checkpoint reconciliation audit")
    p_audit.set_defaults(func=cmd_audit)

    p_rec = sub.add_parser("reconcile", help="Alias for audit: reconcile source disclosures against trade ledger")
    p_rec.set_defaults(func=cmd_audit)

    p_dl = sub.add_parser("download", help="Download archive, posts, chats, and tables for source(s)")
    p_dl.add_argument("--after", help="Only download posts after YYYY-MM-DD")
    p_dl.add_argument("--before", help="Only download posts before YYYY-MM-DD")
    p_dl.add_argument("--no-images", action="store_true", help="Skip downloading post images")
    p_dl.add_argument("--skip-sbstck-dl", action="store_true", help="Skip sbstck-dl HTML mirror and only fetch API JSON + chats + tables")
    p_dl.add_argument("--force", action="store_true", help="Re-download existing API JSON posts and chats")
    p_dl.set_defaults(func=cmd_download)

    p_parse = sub.add_parser("parse", help="Parse downloaded posts, chats & tables into holdings and trade events")
    p_parse.set_defaults(func=cmd_parse)

    p_trades = sub.add_parser("trades", help="Display validated trade history table for source(s)")
    p_trades.add_argument("--limit", type=int, help="Limit number of most recent trades to display")
    p_trades.set_defaults(func=cmd_trades)

    p_sim = sub.add_parser("simulate", help="Compare Strategy A vs Strategy B for source(s)")
    p_sim.add_argument("--start", required=True, help="Start date T0 (YYYY-MM-DD)")
    p_sim.add_argument("--end", help="End date T1 (YYYY-MM-DD, defaults to latest)")
    p_sim.add_argument("--mode", choices=["fixed_unit", "target_weight"], help="Position sizing mode")
    p_sim.add_argument("--unit", type=float, help="Dollar unit per BUY")
    p_sim.add_argument("--add-unit", type=float, help="Dollar unit per ADD")
    p_sim.add_argument("--trim-fraction", type=float, help="Fraction of position sold on TRIM")
    p_sim.add_argument("--reinvest", dest="reinvest", action="store_true", default=None)
    p_sim.add_argument("--no-reinvest", dest="reinvest", action="store_false")
    p_sim.set_defaults(func=cmd_simulate)

    p_cmp = sub.add_parser("compare", help="Compare all three sources side by side")
    p_cmp.add_argument("--start", required=True, help="Start date T0 (YYYY-MM-DD)")
    p_cmp.add_argument("--end", help="End date T1 (YYYY-MM-DD)")
    p_cmp.add_argument("--mode", choices=["fixed_unit", "target_weight"])
    p_cmp.add_argument("--unit", type=float)
    p_cmp.add_argument("--add-unit", type=float)
    p_cmp.add_argument("--trim-fraction", type=float)
    p_cmp.add_argument("--reinvest", dest="reinvest", action="store_true", default=None)
    p_cmp.add_argument("--no-reinvest", dest="reinvest", action="store_false")
    p_cmp.set_defaults(func=cmd_compare)

    p_swp = sub.add_parser("sweep", help="Sweep start dates T0 for source(s)")
    p_swp.add_argument("--from", dest="start_from", required=True)
    p_swp.add_argument("--to", dest="start_to", required=True)
    p_swp.add_argument("--end", help="Evaluation end date T1")
    p_swp.add_argument("--freq", default="MS")
    p_swp.add_argument("--mode", choices=["fixed_unit", "target_weight"])
    p_swp.add_argument("--unit", type=float)
    p_swp.set_defaults(func=cmd_sweep)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
