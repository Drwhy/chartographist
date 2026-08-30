"""Multi-seed reporting built on top of the headless simulation metrics API."""

import csv
import io

from statistics import median, pstdev


PROFILES = {
    "short": {"cycles": 120, "sample_every": 12},
    "long": {"cycles": 1200, "sample_every": 100},
    "resume": {"cycles": 1200, "sample_every": 100, "resume_at": 600},
}


def _final_state(run):
    if run["samples"]:
        return run["samples"][-1]["state"]
    return run["final"]["state"]


def run_seed_batch(seeds, cycles, sample_every, engine_factory):
    """Run independent seeds and return a JSON-serializable comparison report."""
    seed_values = list(seeds)
    if not seed_values:
        raise ValueError("at least one seed is required")
    if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles < 0:
        raise ValueError("cycles must be a non-negative integer")
    if not isinstance(sample_every, int) or isinstance(sample_every, bool) or sample_every <= 0:
        raise ValueError("sample_every must be a positive integer")

    runs = []
    for seed in seed_values:
        engine = engine_factory(seed)
        samples = engine.run_observed(cycles, sample_every=sample_every)
        runs.append({
            "seed": seed,
            "samples": samples,
            "final": engine.get_metrics_snapshot(),
        })

    final_states = [_final_state(run) for run in runs]
    population = [state["population"] for state in final_states]
    settlements = [state["settlements"] for state in final_states]
    fauna = [state["fauna"] for state in final_states]
    food_saturation = [state["food_saturation"] for state in final_states]
    activity = {
        "transactions": [state["transactions"] > 0 for state in final_states],
        "births": [run["final"]["flows"]["demography"]["births"] > 0 for run in runs],
        "raids": [run["final"]["flows"]["combat"]["raids"] > 0 for run in runs],
        "climate_events": [run["final"]["flows"]["climate"]["events"] > 0 for run in runs],
    }
    activation_rate = {
        name: sum(values) / len(values) for name, values in activity.items()
    }
    never_activated = [
        name for name, rate in activation_rate.items() if rate == 0.0
    ]

    return {
        "settings": {
            "cycles": cycles,
            "sample_every": sample_every,
            "seeds": seed_values,
        },
        "runs": runs,
        "summary": {
            "runs": len(runs),
            "activation_rate": activation_rate,
            "never_activated": never_activated,
            "extinction_rate": sum(value == 0 for value in population) / len(runs),
            "median": {
                "population": median(population),
                "settlements": median(settlements),
                "fauna": median(fauna),
                "food_saturation": median(food_saturation),
            },
            "dispersion": {
                "population": pstdev(population),
                "settlements": pstdev(settlements),
                "fauna": pstdev(fauna),
                "food_saturation": pstdev(food_saturation),
            },
        },
    }


def report_to_csv(report):
    """Render final per-seed states as CSV without rerunning simulations."""
    output = io.StringIO()
    fieldnames = [
        "seed",
        "cycle",
        "population",
        "settlements",
        "fauna",
        "food_saturation",
        "treasury",
        "transactions",
        "cultures",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for run in report.get("runs", []):
        state = _final_state(run)
        writer.writerow({
            "seed": run["seed"],
            "cycle": run["final"]["cycle"],
            **{key: state.get(key, 0) for key in fieldnames[2:]},
        })
    return output.getvalue()
