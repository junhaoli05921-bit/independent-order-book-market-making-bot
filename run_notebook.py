"""Execute the notebook offline and export an auditable synthetic-run summary."""

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def verify(namespace):
    """Check risk boundaries, rounding, and cash/inventory accounting."""
    sizes = namespace["quote_sizes"]
    for inventory in range(-20, 21):
        for base_size in (0, 1, 2, 50):
            buy, sell = sizes(inventory, base_size=base_size)
            assert 0 <= buy <= 20 - inventory
            assert 0 <= sell <= 20 + inventory
    assert sizes(20) == (0, 2)
    assert sizes(-20) == (2, 0)
    assert sizes(0, stale=True) == (0, 0)
    assert sizes(0, volatile=True) == (1, 1)
    assert namespace["bid_to_tick"](99.923) == 99.92
    assert namespace["ask_to_tick"](99.923) == 99.93

    state = namespace["BotState"]()
    state.apply_fill("buy", 100.0, 2)
    state.apply_fill("sell", 101.0, 1)
    assert state.inventory == 1
    assert np.isclose(state.cash, -99.015)
    assert np.isclose(state.marked_pnl(101.0), 1.985)
    state.inventory = 18
    state.outstanding = {
        "buy": {"side": "buy", "quantity": 4},
        "sell": {"side": "sell", "quantity": 4},
    }
    assert state.inventory_bounds() == (14, 22)

    result, final_state = namespace["result"], namespace["final_state"]
    assert result["inventory"].abs().max() <= 20
    assert max(namespace["trial_max_inventories"]) <= 20
    assert final_state.inventory == int(result["signed_fill"].sum())
    ledger_cash = sum(
        (-1 if fill["side"] == "buy" else 1) * fill["price"] * fill["quantity"]
        - fill["fee"]
        for fill in final_state.fills
    )
    assert np.isclose(ledger_cash, final_state.cash)
    assert np.isclose(
        result["pnl"].iloc[-1],
        ledger_cash + final_state.inventory * result["next_mid"].iloc[-1],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    notebook_path = Path(__file__).with_name("market_making_toy.ipynb")
    notebook_bytes = notebook_path.read_bytes()
    notebook = json.loads(notebook_bytes)
    namespace = {"__name__": "__main__"}
    stdout = io.StringIO()
    executed_cells = 0
    # A noninteractive backend makes the exact same plotting cell work headlessly.
    with redirect_stdout(stdout):
        for index, cell in enumerate(notebook["cells"], start=1):
            if cell["cell_type"] != "code":
                continue
            code = "".join(cell["source"])
            exec(compile(code, f"{notebook_path.name}:cell-{index}", "exec"), namespace)
            executed_cells += 1
        verify(namespace)

    result = namespace["result"]
    trials = np.asarray(namespace["trial_pnls"])
    total_quantity = int(result["filled_quantity"].sum())
    summary = {
        "scope": "Synthetic accounting experiment; not historical or live performance",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "notebook_sha256": hashlib.sha256(notebook_bytes).hexdigest(),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "execution": {
            "code_cells_executed": executed_cells,
            "risk_rounding_accounting_checks": "passed",
            "execution_method": "sequential Python exec of every code cell; Agg plotting backend",
        },
        "parameters": {
            "market_seed": 7,
            "market_snapshots": len(namespace["market"]),
            "single_order_flow_seed": 123,
            "trial_order_flow_seeds": list(range(100)),
            "position_limit": 20,
            "base_order_size": 2,
            "fee_per_unit": 0.005,
            "market_spread": 0.10,
            "quote_half_spread": 0.08,
            "volatile_quote_half_spread": 0.11,
            "inventory_skew_coefficient": 0.025,
        },
        "single_run": {
            "steps": len(result),
            "final_marked_pnl": float(result["pnl"].iloc[-1]),
            "maximum_drawdown_absolute": float(-namespace["drawdown"].min()),
            "maximum_absolute_inventory": int(result["inventory"].abs().max()),
            "final_inventory": int(namespace["final_state"].inventory),
            "total_bought": int(result["buy_filled"].sum()),
            "total_sold": int(result["sell_filled"].sum()),
            "total_fees": float(sum(f["fee"] for f in namespace["final_state"].fills)),
            "signed_mid_move_per_filled_unit": float(result["signed_mid_move"].sum() / total_quantity),
            "fill_price_markout_per_filled_unit_before_fees": float(result["fill_markout"].sum() / total_quantity),
        },
        "same_market_path_100_order_flow_trials": {
            "mean_final_marked_pnl": float(trials.mean()),
            "median_final_marked_pnl": float(np.median(trials)),
            "positive_pnl_fraction": float((trials > 0).mean()),
            "minimum_final_marked_pnl": float(trials.min()),
            "maximum_final_marked_pnl": float(trials.max()),
            "maximum_absolute_inventory": max(namespace["trial_max_inventories"]),
        },
        "limitations": [
            "Fill probability ignores quote distance and competing prices, overstating spread capture.",
            "No queue priority, partial fills, latency, asynchronous cancels, or market impact.",
            "All trials use one synthetic market path; no out-of-sample or live validation.",
            "PnL is in arbitrary price-times-quantity units, includes fees and marks open inventory to mid.",
            "No terminal liquidation cost; fill markout excludes fees.",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (args.output_dir / "execution.log").write_text(stdout.getvalue(), encoding="utf-8")
    result.to_csv(args.output_dir / "single_run.csv", index=False)
    pd.DataFrame({"order_flow_seed": range(100), "final_marked_pnl": trials}).to_csv(
        args.output_dir / "trial_results.csv", index=False
    )
    namespace["fig"].savefig(args.output_dir / "diagnostics.png", dpi=140)
    plt.close("all")
    print(json.dumps(summary["single_run"], indent=2))
    print(f"All cells and verification checks passed. Results: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
