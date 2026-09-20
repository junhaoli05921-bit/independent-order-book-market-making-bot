# Publication audit

## Provenance

The source is the owner's `market-making-bot/market_making_toy.ipynb` from the supplied GitHub starter pack, whose original README identifies `Market Making Bot final.ipynb` as its source. The supplied file was retained unchanged in the local source pack. The public notebook preserves its synthetic generator, microprice quoting rule, inventory skew, order-arrival assumptions, and bilingual explanations. It contains no external data reads, requests, authentication code, or exchange adapters.

## Corrections to the supplied notebook

1. **Hard-limit sizing:** the original soft-limit rule could allow an oversized configured `base_size` to jump over the hard limit. Each side is now capped by its own remaining capacity. Default size-2 behavior is preserved.
2. **Outstanding exposure:** netting pending buys against pending sells does not give worst-case exposure. The unused `potential_inventory()` example is replaced with `inventory_bounds()`, returning separate lower and upper position bounds. Its documentation explicitly says it is not integrated into execution.
3. **Markout:** the original field was signed filled quantity times the next mid-price change, then averaged only over nonzero net-filled steps and labelled a per-fill markout. It is now named `signed_mid_move`. A separate fill-price markout accounts for buys and sells individually, and both diagnostics divide by total executed units. Simultaneous opposite-side fills remain in the denominator.
4. **Drawdown:** the running peak now includes the initial zero-equity state. The reported maximum drawdown is an absolute loss from that peak, not a percentage.
5. **Scope and experiments:** explanations now say that the 100 trials share one market path, and clearly disclose quote-independent fill probabilities. The exchange-integration checklist is labelled future work. Mean PnL or a high winning fraction is not presented as proof of significance or a trading edge.
6. **Input and execution checks:** basic market-size and risk-parameter validation, a hard-limit invariant inside the simulation, and deterministic risk/rounding/ledger checks were added. Zero requested size is no longer incorrectly labelled stale data.

No market-data or execution realism was added. The changes improve correctness and reporting; they do not turn this toy fill model into a historical backtester or production trading system.

## Verification scope

`python run_notebook.py --output-dir results` executes every code cell as Python, checks hard-limit capacity across every integer inventory from -20 through +20 and order sizes 0/1/2/50, checks soft-limit/stale/volatile behavior and tick rounding, verifies pending-exposure bounds, and reconciles filled inventory and cash to final marked PnL. Every step of all 101 runs has a hard-limit assertion. It also renders the plotting cell with Matplotlib's Agg backend.

The checked runtime and exact numerical results are recorded in `verified_results/summary.json`. A sequential Python run validates this notebook's plain-Python cells; it does not independently validate JupyterLab's UI. All saved notebook outputs and execution counts remain cleared.

The checked run passed on 20 September 2026. A separate comparison against the untouched starter-pack source found exactly equal default-run PnL, inventory, buy/sell quantities, and bid/ask quotes. The oversized-order regression was reproduced: at inventory `14` with configured size `50`, the original bid size was `50`, while the corrected bid size is `6`. Notebook schema validation also passed, and all cell metadata, outputs, and execution counts were checked clean. The exported diagnostic chart was visually inspected.

Not verified: live exchange behavior, empirical fill probabilities, historical performance, multiple market-path robustness, a mid-price versus microprice baseline comparison, asynchronous order/risk handling, or execution at any venue.
