from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import pandas as pd

from .config import Settings
from .prices import PriceProvider


def compute_xirr(cashflows: list[tuple[date, float]]) -> float | None:
    """Compute annualized IRR (XIRR) for irregular cashflows. Returns decimal (e.g. 0.25 = 25%)."""
    if not cashflows:
        return None
    # Aggregate same-day cashflows
    by_day: dict[date, float] = {}
    for dt, amt in cashflows:
        by_day[dt] = by_day.get(dt, 0.0) + amt

    items = sorted((d, a) for d, a in by_day.items() if abs(a) > 1e-9)
    if len(items) < 2:
        return None
    has_neg = any(a < 0 for _, a in items)
    has_pos = any(a > 0 for _, a in items)
    if not (has_neg and has_pos):
        return None

    d0 = items[0][0]
    years = [(d - d0).days / 365.25 for d, _ in items]
    if max(years) <= 0:
        return None

    def npv(rate: float) -> float:
        base = 1.0 + rate
        if base <= 0:
            return float("inf")
        return sum(amt / (base ** y) for (_, amt), y in zip(items, years))

    def d_npv(rate: float) -> float:
        base = 1.0 + rate
        if base <= 0:
            return float("inf")
        return sum(-y * amt / (base ** (y + 1.0)) for (_, amt), y in zip(items, years) if y > 0)

    # Newton-Raphson first
    guess = 0.15
    for _ in range(80):
        val = npv(guess)
        if abs(val) < 1e-6:
            return guess
        deriv = d_npv(guess)
        if abs(deriv) < 1e-12:
            break
        nxt = guess - val / deriv
        if nxt <= -0.9999:
            nxt = (guess - 0.9999) / 2.0
        if nxt > 100.0:
            nxt = 100.0
        if abs(nxt - guess) < 1e-8:
            return nxt
        guess = nxt

    # Bisection fallback
    lo, hi = -0.999, 50.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(120):
        mid = 0.5 * (lo + hi)
        f_mid = npv(mid)
        if abs(f_mid) < 1e-6 or (hi - lo) < 1e-8:
            return mid
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


@dataclass
class Position:
    ticker: str
    market: str
    shares: float = 0.0
    cost_basis_total: float = 0.0
    realized_pnl: float = 0.0
    total_bought_usd: float = 0.0
    total_sold_usd: float = 0.0
    buys_count: int = 0
    sells_count: int = 0


@dataclass
class ExecutedTrade:
    date: str
    ticker: str
    action: str
    shares_delta: float
    price: float
    dollar_amount: float
    realized_pnl: float
    notes: str


@dataclass
class SimulationResult:
    strategy_name: str
    start_date: str
    end_date: str
    allocation_mode: str
    seeded_count: int
    trades: list[ExecutedTrade]
    positions: dict[str, Position]
    external_cash_invested: float
    ending_equity_value: float
    ending_cash_balance: float
    ending_total_value: float
    realized_pnl: float
    unrealized_pnl: float
    net_profit: float
    roi_pct: float
    xirr_pct: float | None
    benchmark_ticker: str
    benchmark_ending_value: float
    benchmark_net_profit: float
    benchmark_roi_pct: float
    benchmark_xirr_pct: float | None
    position_summary: pd.DataFrame = field(default_factory=pd.DataFrame)


class PortfolioSimulator:
    def __init__(
        self,
        settings: Settings,
        price_provider: PriceProvider,
        holdings_df: pd.DataFrame,
        events_df: pd.DataFrame,
    ) -> None:
        self.settings = settings
        self.prices = price_provider
        self.holdings_df = holdings_df.copy()
        self.events_df = events_df.copy()
        if not self.events_df.empty:
            self.events_df["date"] = self.events_df["date"].astype(str).str.slice(0, 10)
            self.events_df = self.events_df.sort_values(["date", "ticker"]).reset_index(drop=True)

        self.weights_by_ticker: dict[str, float] = {}
        self.markets_by_ticker: dict[str, str] = {}
        if not self.holdings_df.empty:
            for _, r in self.holdings_df.iterrows():
                sym = str(r.get("symbol", "")).strip().upper()
                if sym:
                    wt = r.get("weight")
                    if pd.notna(wt) and float(wt) > 0:
                        self.weights_by_ticker[sym] = float(wt)
                    mkt = str(r.get("market", ":us:")).strip()
                    self.markets_by_ticker[sym] = mkt

    def active_buys_at_date(self, start_date: str) -> list[dict]:
        """Reconstruct holdings opened strictly before start_date whose latest rating as of start_date is BUY."""
        if self.events_df.empty:
            return []

        prior = self.events_df[self.events_df["date"] < start_date]
        state: dict[str, dict] = {}
        for _, ev in prior.iterrows():
            sym = str(ev["ticker"]).strip().upper()
            act = str(ev["action"]).strip().upper()
            rat = str(ev.get("rating_after") or "").strip().upper()
            mkt = str(ev.get("market") or self.markets_by_ticker.get(sym, ":us:")).strip()
            wt = ev.get("target_weight")
            ref_px = ev.get("ref_price")

            if act == "SELL" or rat == "CLOSED":
                state.pop(sym, None)
                continue

            cur = state.get(
                sym,
                {
                    "ticker": sym,
                    "market": mkt,
                    "rating": "BUY",
                    "weight": self.weights_by_ticker.get(sym),
                    "ref_price": float(ref_px) if pd.notna(ref_px) else None,
                    "first_date": str(ev["date"]),
                },
            )
            if act in ("BUY", "ADD"):
                cur["rating"] = rat if rat in ("BUY", "HOLD") else "BUY"
            elif act == "HOLD":
                cur["rating"] = "HOLD"
            elif act == "TRIM":
                cur["rating"] = rat if rat in ("BUY", "HOLD") else "HOLD"
            if pd.notna(wt) and float(wt) > 0:
                cur["weight"] = float(wt)
            if pd.notna(ref_px) and float(ref_px) > 0:
                cur["ref_price"] = float(ref_px)
            state[sym] = cur

        return sorted([v for v in state.values() if v["rating"] == "BUY"], key=lambda x: x["ticker"])

    def run_strategy(
        self,
        seed_existing_buys: bool,
        start_date: str,
        end_date: str | None = None,
        allocation_mode: str | None = None,
        unit_usd: float | None = None,
        add_unit_usd: float | None = None,
        trim_fraction: float | None = None,
        reinvest_sales_cash: bool | None = None,
    ) -> SimulationResult:
        mode = (allocation_mode or self.settings.allocation_mode).lower()
        u_usd = unit_usd if unit_usd is not None else self.settings.default_unit_usd
        add_usd = add_unit_usd if add_unit_usd is not None else self.settings.add_unit_usd
        trim_frac = trim_fraction if trim_fraction is not None else self.settings.trim_fraction
        reinvest = reinvest_sales_cash if reinvest_sales_cash is not None else self.settings.reinvest_sales_cash
        bench = self.settings.benchmark_ticker

        t0 = pd.Timestamp(start_date).strftime("%Y-%m-%d")
        t1 = (
            pd.Timestamp(end_date).strftime("%Y-%m-%d")
            if end_date
            else self.prices.latest_available_date(bench).isoformat()
        )

        positions: dict[str, Position] = {}
        trades: list[ExecutedTrade] = []
        cash_balance = 0.0
        external_invested = 0.0
        cashflows: list[tuple[date, float]] = []
        bench_shares = 0.0
        bench_cash = 0.0

        def fund_purchase(dt_str: str, amount: float) -> None:
            nonlocal cash_balance, external_invested, bench_shares
            dt_obj = date.fromisoformat(dt_str)
            if reinvest and cash_balance > 0:
                used_cash = min(cash_balance, amount)
                cash_balance -= used_cash
                needed = amount - used_cash
            else:
                needed = amount

            if needed > 1e-9:
                external_invested += needed
                cashflows.append((dt_obj, -needed))
                b_px = self.prices.get_price(bench, dt_str, market=":us:", direction="forward")
                if b_px and b_px > 0:
                    bench_shares += needed / b_px

        def receive_sale(dt_str: str, proceeds: float) -> None:
            nonlocal cash_balance, bench_shares, bench_cash
            dt_obj = date.fromisoformat(dt_str)
            if reinvest:
                cash_balance += proceeds
            else:
                cashflows.append((dt_obj, proceeds))
                b_px = self.prices.get_price(bench, dt_str, market=":us:", direction="forward")
                if b_px and b_px > 0:
                    sell_sh = min(bench_shares, proceeds / b_px)
                    bench_shares -= sell_sh
                    leftover = proceeds - sell_sh * b_px
                    if leftover > 1e-9:
                        bench_cash += leftover

        def execute_buy(dt_str: str, sym: str, mkt: str, dollars: float, act_label: str, ref_px: float | None, note: str) -> None:
            if dollars <= 0:
                return
            px = self.prices.get_price(sym, dt_str, market=mkt, direction="forward", fallback_price=ref_px)
            if not px or px <= 0:
                return
            fund_purchase(dt_str, dollars)
            sh = dollars / px
            pos = positions.setdefault(sym, Position(ticker=sym, market=mkt))
            pos.shares += sh
            pos.cost_basis_total += dollars
            pos.total_bought_usd += dollars
            pos.buys_count += 1
            trades.append(
                ExecutedTrade(
                    date=dt_str,
                    ticker=sym,
                    action=act_label,
                    shares_delta=sh,
                    price=px,
                    dollar_amount=dollars,
                    realized_pnl=0.0,
                    notes=note,
                )
            )

        def execute_sell_fraction(dt_str: str, sym: str, mkt: str, frac: float, act_label: str, ref_px: float | None, note: str) -> None:
            pos = positions.get(sym)
            if not pos or pos.shares <= 1e-9:
                return
            frac = max(0.0, min(1.0, frac))
            if frac <= 0:
                return
            px = self.prices.get_price(sym, dt_str, market=mkt, direction="forward", fallback_price=ref_px)
            if not px or px <= 0:
                return
            sh_sold = pos.shares * frac
            proceeds = sh_sold * px
            cost_removed = pos.cost_basis_total * frac
            pnl = proceeds - cost_removed

            pos.shares -= sh_sold
            pos.cost_basis_total -= cost_removed
            if pos.shares < 1e-9:
                pos.shares = 0.0
                pos.cost_basis_total = 0.0
            pos.realized_pnl += pnl
            pos.total_sold_usd += proceeds
            pos.sells_count += 1
            receive_sale(dt_str, proceeds)
            trades.append(
                ExecutedTrade(
                    date=dt_str,
                    ticker=sym,
                    action=act_label,
                    shares_delta=-sh_sold,
                    price=px,
                    dollar_amount=proceeds,
                    realized_pnl=pnl,
                    notes=note,
                )
            )

        # Step 1: Seed existing active BUYs on t0 if Strategy A
        seeded_count = 0
        if seed_existing_buys:
            active_buys = self.active_buys_at_date(t0)
            seeded_count = len(active_buys)
            if active_buys:
                if mode == "target_weight":
                    known_w = [b["weight"] for b in active_buys if b.get("weight") and b["weight"] > 0]
                    default_w = (sum(known_w) / len(known_w)) if known_w else (1.0 / len(active_buys))
                    raw_weights = [b["weight"] if (b.get("weight") and b["weight"] > 0) else default_w for b in active_buys]
                    total_w = sum(raw_weights)
                    total_seed_budget = u_usd * len(active_buys)
                    allocs = [total_seed_budget * (w / total_w) for w in raw_weights]
                else:
                    allocs = [u_usd for _ in active_buys]

                for b, dollars in zip(active_buys, allocs):
                    execute_buy(
                        t0,
                        b["ticker"],
                        b["market"],
                        dollars,
                        "SEED_BUY",
                        b.get("ref_price"),
                        f"Seeded active BUY as of {t0} (originally picked {b['first_date']})",
                    )

        # Average weight for sizing new picks in target_weight mode
        avg_wt = (
            sum(self.weights_by_ticker.values()) / len(self.weights_by_ticker)
            if self.weights_by_ticker
            else 0.03
        )

        # Step 2: Process chronological events in [t0, t1]
        if not self.events_df.empty:
            window = self.events_df[(self.events_df["date"] >= t0) & (self.events_df["date"] <= t1)]
            for _, ev in window.iterrows():
                dt_str = str(ev["date"])
                sym = str(ev["ticker"]).strip().upper()
                mkt = str(ev.get("market") or self.markets_by_ticker.get(sym, ":us:")).strip()
                act = str(ev["action"]).strip().upper()
                ref_px = float(ev["ref_price"]) if pd.notna(ev.get("ref_price")) else None
                note = str(ev.get("notes") or ev.get("source_slug") or "")

                if act == "BUY":
                    cur_pos = positions.get(sym)
                    if cur_pos and cur_pos.shares > 1e-9:
                        # Already held (e.g. HOLD -> BUY upgrade while held): treat as ADD
                        dollars = add_usd
                        execute_buy(dt_str, sym, mkt, dollars, "UPGRADE_ADD", ref_px, note)
                    else:
                        if mode == "target_weight":
                            wt = (
                                float(ev["target_weight"])
                                if pd.notna(ev.get("target_weight")) and float(ev["target_weight"]) > 0
                                else self.weights_by_ticker.get(sym, avg_wt)
                            )
                            dollars = u_usd * (wt / avg_wt) if avg_wt > 0 else u_usd
                        else:
                            dollars = u_usd
                        execute_buy(dt_str, sym, mkt, dollars, "BUY", ref_px, note)

                elif act == "ADD":
                    execute_buy(dt_str, sym, mkt, add_usd, "ADD", ref_px, note)

                elif act == "TRIM":
                    tf = (
                        float(ev["trim_fraction"])
                        if pd.notna(ev.get("trim_fraction")) and 0 < float(ev["trim_fraction"]) <= 1.0
                        else trim_frac
                    )
                    execute_sell_fraction(dt_str, sym, mkt, tf, "TRIM", ref_px, note)

                elif act == "SELL":
                    execute_sell_fraction(dt_str, sym, mkt, 1.0, "SELL", ref_px, note)

                # HOLD requires no trade

        # Step 3: Mark-to-market at t1
        ending_equity = 0.0
        realized_total = 0.0
        unrealized_total = 0.0
        summary_rows: list[dict] = []

        for sym, pos in sorted(positions.items()):
            mkt_val = 0.0
            end_px = None
            unreal = 0.0
            if pos.shares > 1e-9:
                end_px = self.prices.get_price(sym, t1, market=pos.market, direction="backward")
                if end_px and end_px > 0:
                    mkt_val = pos.shares * end_px
                    unreal = mkt_val - pos.cost_basis_total
            ending_equity += mkt_val
            realized_total += pos.realized_pnl
            unrealized_total += unreal
            tot_pnl = pos.realized_pnl + unreal
            ret_pct = (tot_pnl / pos.total_bought_usd * 100.0) if pos.total_bought_usd > 0 else 0.0
            summary_rows.append(
                {
                    "ticker": sym,
                    "shares_end": round(pos.shares, 4),
                    "end_price": round(end_px, 2) if end_px else None,
                    "bought_usd": round(pos.total_bought_usd, 2),
                    "sold_usd": round(pos.total_sold_usd, 2),
                    "ending_value": round(mkt_val, 2),
                    "realized_pnl": round(pos.realized_pnl, 2),
                    "unrealized_pnl": round(unreal, 2),
                    "total_pnl": round(tot_pnl, 2),
                    "return_on_bought_pct": round(ret_pct, 2),
                }
            )

        ending_total = ending_equity + cash_balance
        t1_dt = date.fromisoformat(t1)
        strat_cf = list(cashflows)
        if ending_total > 1e-9:
            strat_cf.append((t1_dt, ending_total))

        xirr_val = compute_xirr(strat_cf)
        net_profit = realized_total + unrealized_total
        roi_pct = (net_profit / external_invested * 100.0) if external_invested > 0 else 0.0

        # Benchmark valuation at t1
        bench_end_px = self.prices.get_price(bench, t1, market=":us:", direction="backward") or 0.0
        bench_end_val = bench_shares * bench_end_px + bench_cash
        bench_cf = [(d, a) for d, a in cashflows]
        if bench_end_val > 1e-9:
            bench_cf.append((t1_dt, bench_end_val))
        bench_xirr = compute_xirr(bench_cf)

        # Total net cash withdrawn when reinvest=False must be included when computing benchmark net profit
        withdrawn_cash = sum(a for _, a in cashflows if a > 0)
        bench_net_profit = (bench_end_val + withdrawn_cash) - external_invested
        bench_roi_pct = (bench_net_profit / external_invested * 100.0) if external_invested > 0 else 0.0

        strat_name = "Seed Active BUYs at T0 + Follow Trades" if seed_existing_buys else "Fresh Signals Only from T0"

        return SimulationResult(
            strategy_name=strat_name,
            start_date=t0,
            end_date=t1,
            allocation_mode=mode,
            seeded_count=seeded_count,
            trades=trades,
            positions=positions,
            external_cash_invested=external_invested,
            ending_equity_value=ending_equity,
            ending_cash_balance=cash_balance,
            ending_total_value=ending_total,
            realized_pnl=realized_total,
            unrealized_pnl=unrealized_total,
            net_profit=net_profit,
            roi_pct=roi_pct,
            xirr_pct=(xirr_val * 100.0) if xirr_val is not None else None,
            benchmark_ticker=bench,
            benchmark_ending_value=bench_end_val,
            benchmark_net_profit=bench_net_profit,
            benchmark_roi_pct=bench_roi_pct,
            benchmark_xirr_pct=(bench_xirr * 100.0) if bench_xirr is not None else None,
            position_summary=pd.DataFrame(summary_rows),
        )
