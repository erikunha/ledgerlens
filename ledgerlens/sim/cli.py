"""`ledgerlens-sim`: build the ledger database and the scenario manifest, deterministically.

    ledgerlens-sim --days 90 --seed 42 --scenarios all

The same seed, source and options always give the same database hash and the same manifest bytes.
Nothing here uses the network. The run prints which source it used.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from ledgerlens.sim.config import (
    DATA,
    DEFAULT_END,
    DEFAULT_MAX_TRANSACTIONS,
    SCENARIO_IDS,
    SOURCES,
    SimConfig,
)
from ledgerlens.sim.fx import FxUnavailable
from ledgerlens.sim.pipeline import SourceUnavailable, build_ledger, write_manifest
from ledgerlens.sim.sources.sample import write_sample

DEFAULT_DB = DATA / "ledger.db"
DEFAULT_MANIFEST = DATA / "scenarios.json"
DEFAULT_LOCK = DATA / "sources.lock.json"


def _scenarios(text: str) -> tuple[str, ...]:
    value = text.strip().lower()
    if value == "all":
        return SCENARIO_IDS
    if value in ("none", ""):
        return ()
    wanted = tuple(part.strip().upper() for part in text.split(",") if part.strip())
    unknown = [item for item in wanted if item not in SCENARIO_IDS]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown scenario(s): {', '.join(unknown)} (use all, none or S01 to S12)")
    return tuple(sorted(set(wanted)))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ledgerlens-sim",
        description="Build data/ledger.db and data/scenarios.json from public data, the sample or a seeded generator.",
    )
    parser.add_argument(
        "--days", type=int, default=90, help="days of the source to use, counted back from its last day"
    )
    parser.add_argument("--seed", type=int, default=42, help="seed of every random choice")
    parser.add_argument("--scenarios", type=_scenarios, default=SCENARIO_IDS, help="all, none, or a list like S01,S03")
    parser.add_argument(
        "--source", choices=SOURCES, default="auto", help="auto uses the first of public, sample, synthetic"
    )
    parser.add_argument("--max-transactions", type=int, default=DEFAULT_MAX_TRANSACTIONS)
    parser.add_argument("--end", type=date.fromisoformat, default=DEFAULT_END, help="last simulated day (YYYY-MM-DD)")
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB, help="SQLite file to create (an existing one is replaced)"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--raw", type=Path, default=None, help="Online Retail II file (zip, xlsx or csv)")
    parser.add_argument("--sample", type=Path, default=None, help="derived sample (JSON lines)")
    parser.add_argument(
        "--write-sample", type=Path, default=None, help="also write the selected, shifted invoices here"
    )
    parser.add_argument(
        "--lock", type=Path, default=DEFAULT_LOCK, help="sources.lock.json, read for the sample metadata"
    )
    return parser


def _sample_meta(args: argparse.Namespace, shift: int, count: int, selection: dict) -> dict:
    sha = None
    if Path(args.lock).exists():
        entry = json.loads(Path(args.lock).read_text(encoding="utf-8")).get("sources", {}).get("uci_online_retail_ii")
        sha = entry and entry.get("sha256")
    return {
        "derived_from": "UCI Online Retail II, https://doi.org/10.24432/C5CG6D",
        "license": "CC BY 4.0",
        "attribution": "Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.",
        "changes": (
            "invoices selected (stratified by day) and time-shifted; amounts are still pounds; merchants, "
            "currencies, customer countries and payment methods are assigned later by the simulator"
        ),
        "time_shift_days": shift,
        "seed": args.seed,
        "days": args.days,
        "end": args.end.isoformat(),
        "max_transactions": args.max_transactions,
        "invoices": count,
        "selection": selection,
        "source_sha256": sha,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    defaults = SimConfig()
    cfg = SimConfig(
        seed=args.seed,
        days=args.days,
        end=args.end,
        source=args.source,
        max_transactions=args.max_transactions,
        scenarios=args.scenarios,
        raw_path=args.raw or defaults.raw_path,
        sample_path=args.sample or defaults.sample_path,
    )
    try:
        cfg.validate()
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    try:
        result = build_ledger(cfg, Path(args.db))
    except SourceUnavailable as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except FxUnavailable as error:
        print(
            f"error: {error}. The recorded exchange-rate series does not cover the window; "
            "use fewer --days or run scripts/record_fixtures.py with a wider --start.",
            file=sys.stderr,
        )
        return 1

    manifest = result.manifest
    write_manifest(manifest, Path(args.manifest))
    if args.write_sample is not None:
        if result.source != "public":
            print("error: --write-sample derives from the public file; use --source public", file=sys.stderr)
            result.conn.close()
            return 2
        meta = _sample_meta(
            args,
            manifest["transform"]["time_shift_days"],
            len(result.selected_invoices),
            manifest["transform"]["selection"],
        )
        write_sample(result.selected_invoices, Path(args.write_sample), meta)
    counts = manifest["counts"]
    print(f"source: {result.source}")
    print(
        f"transactions {counts['transactions']} (public origin {counts['public_origin_transactions']}), "
        f"refunds {counts['refunds']}, chargebacks {counts['chargebacks']}, settlements {counts['settlements']}, "
        f"events {counts['events']}"
    )
    selection = manifest["transform"]["selection"]
    print(
        f"cancellations linked {selection['cancellations_linked']} of {selection['cancellations_in_window']} "
        f"(matching rate {selection['matching_rate']}), time shift {manifest['transform']['time_shift_days']} days"
    )
    print(f"scenarios: {', '.join(s['id'] for s in manifest['scenarios']) or 'none'}")
    print(f"db {args.db}  manifest {args.manifest}  sha256 {manifest['db_canonical_sha256']}")
    result.conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
