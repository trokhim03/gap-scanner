# The Claude Code prompt

Paste this into Claude Code in an empty folder:

```
Build a crypto arbitrage scanner in Python. Paper mode only, never place real orders.

1. Use ccxt to stream order books (watch_order_book) for BTC, ETH, SOL, XRP, DOGE, ADA,
   AVAX, LINK, TON, SUI on Binance, Coinbase, Kraken, OKX and Bybit (USDT pairs,
   USD/USDC where USDT isn't listed).
2. For each pair, compare the best ask on one venue with the best bid on another.
   Flag a gap when the spread is above 0.05%.
3. Fee filter: subtract the taker fee on both legs (load real fee tiers from each
   exchange) plus transfer cost. Drop the gap if net edge <= 0.
4. Depth filter: walk the order book for a $500 trade on both legs. Drop it if
   slippage eats the edge.
5. Latency filter: measure round-trip time to each venue. Wait that long, re-check
   the books, and drop the gap if it's gone.
6. Simulate fills for every survivor on a $1,000 paper balance.
7. Log every gap to a CSV with the reason it died, and show a live summary:
   found / killed by fees / depth / latency / survived / paper P&L.
```

Then run it for a few hours, not a few minutes.
