"""
gap-scanner: a paper-only cross-exchange arbitrage scanner.

Streams public order books from several exchanges, flags price gaps for the
same coin, then runs every gap through three filters (fees, depth, latency).
Whatever survives gets a simulated fill on a paper balance. No orders are
ever sent and no API keys are used.

    python scanner.py            # run until Ctrl+C
    python scanner.py --minutes 60
"""

import argparse
import asyncio
import csv
import os
import time
from dataclasses import dataclass, field

import ccxt.pro as ccxtpro
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

import config as cfg


@dataclass
class Stats:
    found: int = 0
    fees: int = 0
    depth: int = 0
    latency: int = 0
    filled: int = 0
    pnl: float = 0.0
    edges: list = field(default_factory=list)
    recent: list = field(default_factory=list)
    started: float = field(default_factory=time.time)


stats = Stats()
books = {}  # (exchange, base) -> order book
symbols = {}  # (exchange, base) -> symbol actually used, e.g. "BTC/USDT"
fees = {}  # exchange -> taker fee
rtt = {}  # exchange -> round-trip seconds
open_gaps = set()  # (base, buy_ex, sell_ex) currently above threshold


def log_gap(row):
    new = not os.path.exists(cfg.LOG_CSV)
    with open(cfg.LOG_CSV, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "base", "buy_on", "sell_on", "spread_bps", "net_bps", "outcome"])
        w.writerow(row)
    stats.recent = ([row] + stats.recent)[:8]


def vwap(levels, usd):
    """Average price to fill `usd` worth against a side of the book, or None if too thin."""
    left, cost, qty = usd, 0.0, 0.0
    for price, amount, *_ in levels:
        take = min(left, price * amount)
        cost += take
        qty += take / price
        left -= take
        if left <= 1e-9:
            return cost / qty
    return None


def net_edge(buy_price, sell_price, buy_ex, sell_ex):
    """Edge after both taker fees and the transfer cost, as a fraction of trade size."""
    gross = sell_price / buy_price - 1
    return gross - fees[buy_ex] - fees[sell_ex] - cfg.TRANSFER_COST_USD / cfg.TRADE_SIZE_USD


async def check(base, buy_ex, sell_ex):
    """Run one gap through fees -> depth -> latency, then paper-fill it."""
    a, b = books[(buy_ex, base)], books[(sell_ex, base)]
    ask, bid = a["asks"][0][0], b["bids"][0][0]
    spread_bps = (bid / ask - 1) * 1e4
    ts = time.strftime("%H:%M:%S")

    # 1. Fees: is there anything left at the top of the book?
    top = net_edge(ask, bid, buy_ex, sell_ex)
    if top <= 0:
        stats.fees += 1
        return log_gap([ts, base, buy_ex, sell_ex, f"{spread_bps:.1f}", f"{top*1e4:.1f}", "killed: fees"])

    # 2. Depth: does it survive walking the book for the full size?
    buy_px, sell_px = vwap(a["asks"], cfg.TRADE_SIZE_USD), vwap(b["bids"], cfg.TRADE_SIZE_USD)
    deep = net_edge(buy_px, sell_px, buy_ex, sell_ex) if buy_px and sell_px else -1
    if deep <= 0:
        stats.depth += 1
        return log_gap([ts, base, buy_ex, sell_ex, f"{spread_bps:.1f}", f"{deep*1e4:.1f}", "killed: depth"])

    # 3. Latency: wait as long as our slower leg would take, then look again.
    await asyncio.sleep(max(rtt.get(buy_ex, 0.3), rtt.get(sell_ex, 0.3)))
    a, b = books[(buy_ex, base)], books[(sell_ex, base)]
    buy_px, sell_px = vwap(a["asks"], cfg.TRADE_SIZE_USD), vwap(b["bids"], cfg.TRADE_SIZE_USD)
    late = net_edge(buy_px, sell_px, buy_ex, sell_ex) if buy_px and sell_px else -1
    if late <= 0:
        stats.latency += 1
        return log_gap([ts, base, buy_ex, sell_ex, f"{spread_bps:.1f}", f"{late*1e4:.1f}", "killed: latency"])

    # Survivor: simulated fill on the paper balance.
    stats.filled += 1
    stats.pnl += late * cfg.TRADE_SIZE_USD
    stats.edges.append(late)
    log_gap([ts, base, buy_ex, sell_ex, f"{spread_bps:.1f}", f"{late*1e4:.1f}", "paper fill"])


def scan(base):
    """Compare every pair of venues for one coin and open/close gaps."""
    venues = [ex for ex in cfg.EXCHANGES if (ex, base) in books]
    for buy_ex in venues:
        for sell_ex in venues:
            if buy_ex == sell_ex:
                continue
            a, b = books[(buy_ex, base)], books[(sell_ex, base)]
            if not a["asks"] or not b["bids"]:
                continue
            key = (base, buy_ex, sell_ex)
            spread_bps = (b["bids"][0][0] / a["asks"][0][0] - 1) * 1e4
            if spread_bps >= cfg.MIN_SPREAD_BPS:
                if key not in open_gaps:  # count each gap once, when it opens
                    open_gaps.add(key)
                    stats.found += 1
                    asyncio.create_task(check(base, buy_ex, sell_ex))
            else:
                open_gaps.discard(key)


async def watch(ex, base):
    """Keep one order book fresh: websocket where possible, REST polling otherwise."""
    exchange = clients[ex]
    sym = symbols[(ex, base)]
    limit = cfg.BOOK_LIMITS.get(ex, cfg.BOOK_LIMIT)
    while True:
        try:
            if ex in cfg.REST_ONLY:
                books[(ex, base)] = await exchange.fetch_order_book(sym, limit)
                await asyncio.sleep(cfg.REST_POLL_S)
            else:
                books[(ex, base)] = await exchange.watch_order_book(sym, limit)
            scan(base)
        except Exception:
            await asyncio.sleep(2)


async def measure_latency(ex):
    exchange = clients[ex]
    while True:
        try:
            t0 = time.perf_counter()
            await exchange.fetch_ticker(symbols[next(k for k in symbols if k[0] == ex)])
            rtt[ex] = time.perf_counter() - t0
        except Exception:
            pass
        await asyncio.sleep(cfg.LATENCY_REFRESH_S)


def view():
    killed = stats.fees + stats.depth + stats.latency
    mins = (time.time() - stats.started) / 60
    funnel = Table(title=f"gap-scanner · paper mode · {mins:.1f} min · {len(books)} books live", expand=True)
    for col in ["found", "killed: fees", "killed: depth", "killed: latency", "paper fills", "paper P&L"]:
        funnel.add_column(col, justify="right")
    avg = sum(stats.edges) / len(stats.edges) * 100 if stats.edges else 0
    funnel.add_row(
        f"{stats.found:,}", f"[red]{stats.fees:,}", f"[red]{stats.depth:,}", f"[red]{stats.latency:,}",
        f"[green]{stats.filled:,}", f"[green]${stats.pnl:+.2f}[/] ({avg:.3f}% avg)",
    )
    lat = Table(title="round trip", expand=True)
    for ex in cfg.EXCHANGES:
        lat.add_column(ex, justify="right")
    lat.add_row(*[f"{rtt[ex]*1000:.0f} ms" if ex in rtt else "…" for ex in cfg.EXCHANGES])
    recent = Table(title="latest gaps", expand=True)
    for col in ["time", "coin", "buy on", "sell on", "spread bps", "net bps", "outcome"]:
        recent.add_column(col)
    for r in stats.recent:
        style = "green" if r[-1] == "paper fill" else "red"
        recent.add_row(*r[:-1], f"[{style}]{r[-1]}")
    note = f"paper balance ${cfg.PAPER_BALANCE_USD:,.0f} · trade size ${cfg.TRADE_SIZE_USD:,.0f} · no real orders"
    return Panel(Group(funnel, lat, recent), subtitle=note)


clients = {}


async def main(minutes):
    for ex in cfg.EXCHANGES:
        clients[ex] = getattr(ccxtpro, ex)({"enableRateLimit": True})
    await asyncio.gather(*(clients[ex].load_markets() for ex in cfg.EXCHANGES), return_exceptions=True)

    for ex, c in clients.items():
        if not c.markets:
            continue
        for base in cfg.BASES:
            sym = next((f"{base}/{q}" for q in cfg.QUOTES if f"{base}/{q}" in c.markets), None)
            if sym:
                symbols[(ex, base)] = sym
                fees[ex] = c.markets[sym].get("taker") or cfg.DEFAULT_TAKER_FEE

    tasks = [asyncio.create_task(watch(ex, base)) for ex, base in symbols]
    tasks += [asyncio.create_task(measure_latency(ex)) for ex in {ex for ex, _ in symbols}]

    deadline = time.time() + minutes * 60 if minutes else float("inf")
    try:
        with Live(view(), refresh_per_second=4) as live:
            while time.time() < deadline:
                await asyncio.sleep(0.25)
                live.update(view())
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*(c.close() for c in clients.values()), return_exceptions=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Paper-only cross-exchange gap scanner")
    p.add_argument("--minutes", type=float, default=0, help="stop after N minutes (default: run until Ctrl+C)")
    try:
        asyncio.run(main(p.parse_args().minutes))
    except KeyboardInterrupt:
        pass
