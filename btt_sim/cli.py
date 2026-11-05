from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
from rich.console import Console
from rich.table import Table

from .config import Settings, SourceConfig, load_settings
from .downloader import (
    extract_datawrapper_datasets,
    fetch_all_api_posts,
    resolve_cookie_name,
    run_sbstck_dl,
)
from .parser import parse_source_data
from .prices import PriceProvider
from .simulator import PortfolioSimulator, SimulationResult

console = Console()


def _fmt_money(v: float | None) -> str:
    return f"${v:,.2f}" if v is not None else "N/A"


def _fmt_pct(v: float | None) -> str:
    return f"{v:+.2f}%" if v is not None else "N/A"


def _get_target_sources(settings: Settings, source_arg: str) -> list[SourceConfig]:
    if source_arg == "all":
        return list(settings.sources.values())
    return [settings.get_source(source_arg)]


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
        manifest = extract_datawrapper_datasets(src)
        console.print(f"[green]{src.display_name} download complete. ({len(manifest)} Datawrapper tables)[/green]")


def cmd_parse(args: argparse.Namespace) -> None:
    settings = load_settings()
    sources = _get_target_sources(settings, args.source)
    for src in sources:
        console.print(f"\n[bold blue]=== Parsing {src.display_name} ===[/bold blue]")
        holdings_df, events_df = parse_source_data(src)
        console.print(f"[bold green]Parsed {len(holdings_df)} holdings and {len(events_df)} trade events.[/bold green]")
        console.print(f"  Holdings CSV: {src.data_dir / 'portfolio_holdings.csv'}")
        console.print(f"  Events CSV:   {src.data_dir / 'trade_events.csv'}")
        if not events_df.empty:
            counts = events_df["action"].value_counts().to_dict()
            console.print(f"  Event breakdown: {counts}")


def cmd_trades(args: argparse.Namespace) -> None:
    settings = load_settings()
    sources = _get_target_sources(settings, args.source)
    for src in sources:
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

        table = Table(title=f"{src.display_name} Trade History ({len(df)} trades shown)")
        table.add_column("Date", style="cyan")
        table.add_column("Ticker", style="bold yellow")
        table.add_column("Action", style="bold")
        table.add_column("Rating", style="green")
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
            if len(notes) > 60:
                notes = notes[:57] + "..."

            table.add_row(
                str(r.get("date", "")),
                str(r.get("ticker", "")),
                f"[{act_color}]{act}[/{act_color}]",
                str(r.get("rating_after", "")),
                px_val,
                wgt_val,
                trim_val,
                str(r.get("source_slug", "")),
                notes,
            )
        console.print(table)


def _run_sim_for_source(
    settings: Settings,
    prices: PriceProvider,
    src: SourceConfig,
    args: argparse.Namespace,
) -> tuple[SimulationResult | None, SimulationResult | None]:
    holdings_path = src.data_dir / "portfolio_holdings.csv"
    events_path = src.data_dir / "trade_events.csv"
    if not events_path.exists():
        console.print(f"[yellow]{src.display_name}: trade_events.csv not found. Run `uv run btt parse --source {src.key}` first.[/yellow]")
        return None, None

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
        return None, None

    sim = PortfolioSimulator(settings, prices, holdings_df, events_df)
    reinvest = None if args.reinvest is None else args.reinvest

    res_a = sim.run_strategy(
        seed_existing_buys=True,
        start_date=args.start,
        end_date=args.end,
        allocation_mode=args.mode,
        unit_usd=args.unit,
        add_unit_usd=args.add_unit,
        trim_fraction=args.trim_fraction,
        reinvest_sales_cash=reinvest,
    )
    res_b = sim.run_strategy(
        seed_existing_buys=False,
        start_date=args.start,
        end_date=args.end,
        allocation_mode=args.mode,
        unit_usd=args.unit,
        add_unit_usd=args.add_unit,
        trim_fraction=args.trim_fraction,
        reinvest_sales_cash=reinvest,
    )
    return res_a, res_b


def cmd_simulate(args: argparse.Namespace) -> None:
    settings = load_settings()
    prices = PriceProvider(settings)
    sources = _get_target_sources(settings, args.source)

    for src in sources:
        console.print(f"\n[bold blue]=== Simulation: {src.display_name} ({args.start} -> {args.end or 'Latest'}) ===[/bold blue]")
        res_a, res_b = _run_sim_for_source(settings, prices, src, args)
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
        tbl.add_row("External Capital Deployed", _fmt_money(res_a.external_cash_invested), _fmt_money(res_b.external_cash_invested), _fmt_money(res_a.external_cash_invested - res_b.external_cash_invested))
        tbl.add_row("Ending Value (Equity + Cash)", _fmt_money(res_a.ending_total_value), _fmt_money(res_b.ending_total_value), _fmt_money(res_a.ending_total_value - res_b.ending_total_value))
        tbl.add_row("Net Profit ($)", _fmt_money(res_a.net_profit), _fmt_money(res_b.net_profit), _fmt_money(res_a.net_profit - res_b.net_profit))
        tbl.add_row("Total Return on Capital (%)", _fmt_pct(res_a.roi_pct), _fmt_pct(res_b.roi_pct), _fmt_pct(res_a.roi_pct - res_b.roi_pct))
        tbl.add_row("Annualized XIRR (%)", _fmt_pct(res_a.xirr_pct), _fmt_pct(res_b.xirr_pct), _fmt_pct((res_a.xirr_pct - res_b.xirr_pct) if (res_a.xirr_pct is not None and res_b.xirr_pct is not None) else None))
        tbl.add_row(f"Matched-Cash-Flow {res_a.benchmark_ticker} ROI (%)", _fmt_pct(res_a.benchmark_roi_pct), _fmt_pct(res_b.benchmark_roi_pct), _fmt_pct(res_a.benchmark_roi_pct - res_b.benchmark_roi_pct))
        tbl.add_row(f"Excess XIRR vs {res_a.benchmark_ticker} (Alpha)", _fmt_pct((res_a.xirr_pct - res_a.benchmark_xirr_pct) if (res_a.xirr_pct and res_a.benchmark_xirr_pct) else None), _fmt_pct((res_b.xirr_pct - res_b.benchmark_xirr_pct) if (res_b.xirr_pct and res_b.benchmark_xirr_pct) else None), "—")
        console.print(tbl)

        out_dir = src.results_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        tag = f"{res_a.start_date}_to_{res_a.end_date}_{res_a.allocation_mode}"
        res_a.position_summary.to_csv(out_dir / f"positions_strategy_A_{tag}.csv", index=False)
        res_b.position_summary.to_csv(out_dir / f"positions_strategy_B_{tag}.csv", index=False)
        pd.DataFrame([t.__dict__ for t in res_a.trades]).to_csv(out_dir / f"trades_strategy_A_{tag}.csv", index=False)
        pd.DataFrame([t.__dict__ for t in res_b.trades]).to_csv(out_dir / f"trades_strategy_B_{tag}.csv", index=False)

    prices.save_ticker_map()


def cmd_compare(args: argparse.Namespace) -> None:
    """Compare all three newsletters side-by-side."""
    settings = load_settings()
    prices = PriceProvider(settings)

    tbl = Table(title=f"Multi-Source Newsletter Comparison ({args.start} -> {args.end or 'Latest'} | Mode: {args.mode or settings.allocation_mode})", show_lines=True)
    tbl.add_column("Newsletter / Source", style="bold")
    tbl.add_column("Strategy A Profit ($)", justify="right", style="cyan")
    tbl.add_column("Strategy A ROI %", justify="right", style="cyan")
    tbl.add_column("Strategy A XIRR %", justify="right", style="cyan")
    tbl.add_column("Strategy B Profit ($)", justify="right", style="magenta")
    tbl.add_column("Strategy B ROI %", justify="right", style="magenta")
    tbl.add_column("Strategy B XIRR %", justify="right", style="magenta")
    tbl.add_column("SPY Benchmark XIRR", justify="right")

    for src in settings.sources.values():
        res_a, res_b = _run_sim_for_source(settings, prices, src, args)
        if not res_a or not res_b:
            tbl.add_row(src.display_name, "No data", "No data", "No data", "No data", "No data", "No data", "—")
            continue
        tbl.add_row(
            src.display_name,
            _fmt_money(res_a.net_profit),
            _fmt_pct(res_a.roi_pct),
            _fmt_pct(res_a.xirr_pct),
            _fmt_money(res_b.net_profit),
            _fmt_pct(res_b.roi_pct),
            _fmt_pct(res_b.xirr_pct),
            _fmt_pct(res_a.benchmark_xirr_pct),
        )
    prices.save_ticker_map()
    console.print(tbl)


def cmd_sweep(args: argparse.Namespace) -> None:
    settings = load_settings()
    prices = PriceProvider(settings)
    sources = _get_target_sources(settings, args.source)

    for src in sources:
        holdings_path = src.data_dir / "portfolio_holdings.csv"
        events_path = src.data_dir / "trade_events.csv"
        if not events_path.exists():
            continue

        holdings_df = pd.read_csv(holdings_path) if holdings_path.exists() else pd.DataFrame()
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

        for dt in dates:
            d_str = dt.strftime("%Y-%m-%d")
            ra = sim.run_strategy(True, d_str, end_date=args.end, allocation_mode=args.mode, unit_usd=args.unit)
            rb = sim.run_strategy(False, d_str, end_date=args.end, allocation_mode=args.mode, unit_usd=args.unit)
            winner = "—"
            if ra.xirr_pct is not None and rb.xirr_pct is not None:
                winner = "Strategy A" if ra.xirr_pct > rb.xirr_pct else "Strategy B"
            tbl.add_row(d_str, str(ra.seeded_count), _fmt_pct(ra.roi_pct), _fmt_pct(ra.xirr_pct), _fmt_pct(rb.roi_pct), _fmt_pct(rb.xirr_pct), winner)
        console.print(tbl)
    prices.save_ticker_map()


def main() -> None:
    parser = argparse.ArgumentParser(prog="btt", description="Multi-Source Substack Downloader & Portfolio Simulator")
    parser.add_argument("--source", default="beatingthetide", choices=["beatingthetide", "tjstocks", "cluseau", "all"], help="Target publication source (default: beatingthetide)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_auth = sub.add_parser("check-auth", help="Verify paid Substack cookie for source(s)")
    p_auth.set_defaults(func=cmd_check_auth)

    p_dl = sub.add_parser("download", help="Download archive, posts, and tables for source(s)")
    p_dl.add_argument("--after", help="Only download posts after YYYY-MM-DD")
    p_dl.add_argument("--before", help="Only download posts before YYYY-MM-DD")
    p_dl.add_argument("--no-images", action="store_true", help="Skip downloading post images")
    p_dl.add_argument("--skip-sbstck-dl", action="store_true", help="Skip sbstck-dl HTML mirror and only fetch API JSON + tables")
    p_dl.add_argument("--force", action="store_true", help="Re-download existing API JSON posts")
    p_dl.set_defaults(func=cmd_download)

    p_parse = sub.add_parser("parse", help="Parse downloaded posts & tables into holdings and trade events")
    p_parse.set_defaults(func=cmd_parse)

    p_trades = sub.add_parser("trades", help="Display trade history table for source(s)")
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
