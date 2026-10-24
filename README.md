# gap-scanner

A paper-only cross-exchange arbitrage scanner, built with Claude Code.

It watches the same coins on five exchanges, flags every price gap, then tries to kill each one before it costs you money. Whatever survives gets a simulated fill on a paper balance.

**No API keys. No real orders. Public market data only.**

```
gaps found ──► fees ──► depth ──► latency ──► paper fill
               ✕         ✕         ✕           ✓
```

## What it does

- Streams public order books for **BTC, ETH, SOL, XRP, DOGE, ADA, AVAX, LINK, TON, SUI** on **Binance, Coinbase, Kraken, OKX and Bybit**
- Flags a gap when the best bid on one venue beats the best ask on another by more than 0.05%
- Runs every gap through three filters:

| Filter | Question it asks | Kills the gap when |
| --- | --- | --- |
| **Fees** | Is anything left after paying taker fees on both legs + moving the coins? | net edge ≤ 0 at the top of the book |
| **Depth** | Does the edge survive filling the full trade size, not just the first level? | VWAP across the book eats the edge |
| **Latency** | Is the gap still there after our slower round trip to the exchanges? | it closed before both legs could land |

- Survivors get a simulated fill on a $1,000 paper balance
- Every gap and the reason it died goes to `gaps.csv`

## Quickstart

```bash
git clone https://github.com/trokhim03/gap-scanner
cd gap-scanner
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scanner.py --minutes 60
```

Leave it running for an hour or more. Most of what you'll see in the first few minutes dies at the fee filter, and that's the point.

## Settings

Everything lives in [`config.py`](config.py): venues, coins, gap threshold, trade size, transfer cost, paper balance.

Taker fees are read from each exchange's market data (your real tier may be lower). Coinbase's public websocket needs an API key, so its book is polled over REST once a second instead.

## Example output

```
gap-scanner · paper mode · 2.0 min
found  killed: fees  killed: depth  killed: latency  paper fills  paper P&L
   18            18              0                0            0     $+0.00

time      coin  buy on     sell on   spread bps  net bps  outcome
13:34:29  SUI   coinbase…  bybit            8.4    -71.6  killed: fees
13:34:14  ETH   coinbase…  okx              5.1    -79.9  killed: fees
```

## Build it yourself with Claude Code

The whole thing started as one prompt. It's in [`PROMPT.md`](PROMPT.md): paste it into Claude Code and you'll get your own version.

## Disclaimer

This is an educational tool. It never places orders and nothing here is financial advice. Moving real money between exchanges adds withdrawal times and network fees this scanner only estimates.

## License

MIT
