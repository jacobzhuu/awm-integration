#!/usr/bin/env python3
"""Batch runner for the local AWM verification wrapper."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from verify_awm import ensure_output_directories, run_verification

DEFAULT_OUTPUT_DIR = Path("artifacts") / "awm"
ROOT_DIR = Path(__file__).resolve().parent


def load_pairs_config(config_path: str | Path) -> dict[str, Any]:
    """Load the JSON config that defines local model pairs."""
    resolved_path = Path(config_path).expanduser().resolve()
    data = json.loads(resolved_path.read_text(encoding="utf-8"))
    pairs = data.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("pairs config must contain a non-empty 'pairs' list")
    data["resolved_path"] = str(resolved_path)
    return data


def write_summary_csv(csv_path: Path, results: list[dict[str, Any]]) -> None:
    """Persist the flat summary used by downstream tooling."""
    fieldnames = [
        "pair_name",
        "pair_label",
        "model_a_name",
        "model_a_path",
        "model_b_name",
        "model_b_path",
        "status",
        "decision",
        "absolute_z_score",
        "average_wq_weights_pct",
        "average_wk_weights_pct",
        "average_wq_wk_weights_pct",
        "reference_similarity_pct",
        "log_path",
        "result_path",
        "error",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            metrics = result.get("metrics", {})
            writer.writerow(
                {
                    "pair_name": result.get("pair_name"),
                    "pair_label": result.get("pair_label"),
                    "model_a_name": result.get("model_a", {}).get("name"),
                    "model_a_path": result.get("model_a", {}).get("path"),
                    "model_b_name": result.get("model_b", {}).get("name"),
                    "model_b_path": result.get("model_b", {}).get("path"),
                    "status": result.get("status"),
                    "decision": result.get("decision"),
                    "absolute_z_score": metrics.get("absolute_z_score"),
                    "average_wq_weights_pct": metrics.get("average_wq_weights_pct"),
                    "average_wk_weights_pct": metrics.get("average_wk_weights_pct"),
                    "average_wq_wk_weights_pct": metrics.get("average_wq_wk_weights_pct"),
                    "reference_similarity_pct": metrics.get("reference_similarity_pct"),
                    "log_path": result.get("artifacts", {}).get("log_path"),
                    "result_path": result.get("artifacts", {}).get("result_path"),
                    "error": result.get("error"),
                }
            )


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for batch execution."""
    parser = argparse.ArgumentParser(
        description="Run AWM verification across a JSON list of local model pairs.",
    )
    parser.add_argument(
        "--pairs-config",
        default=str(ROOT_DIR / "configs" / "local_demo_pairs.json"),
        help="Path to the JSON file defining local model pairs.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda", "auto"],
        help="Device forwarded to verify_awm.py/main.py.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Root directory used to store logs/ and results/.",
    )
    return parser


def main() -> int:
    """CLI entrypoint."""
    args = build_argument_parser().parse_args()
    config = load_pairs_config(args.pairs_config)
    _, _, results_dir = ensure_output_directories(args.output_dir)
    started_at = datetime.now(timezone.utc).isoformat()
    config_path = Path(config["resolved_path"])
    batch_slug = f"batch_{config_path.stem}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    all_results: list[dict[str, Any]] = []

    pairs = config["pairs"]
    for index, pair in enumerate(pairs, start=1):
        pair_name = pair.get("name") or f"pair_{index}"
        label = pair.get("label")
        print(f"[{index}/{len(pairs)}] Running {pair_name}")
        result = run_verification(
            model_a=pair["model_a"],
            model_b=pair["model_b"],
            device=args.device,
            output_dir=args.output_dir,
            pair_name=pair_name,
            label=label,
        )
        all_results.append(result)
        decision = result.get("decision") or result.get("status")
        z_score = result.get("metrics", {}).get("absolute_z_score")
        print(f"  -> {decision} (z={z_score})")

    finished_at = datetime.now(timezone.utc).isoformat()
    status_counts = Counter(result.get("status") for result in all_results)
    decision_counts = Counter(result.get("decision") for result in all_results if result.get("decision"))
    summary = {
        "tool": "awm_batch",
        "pairs_config": str(config_path),
        "device": args.device,
        "started_at": started_at,
        "finished_at": finished_at,
        "total_pairs": len(all_results),
        "status_counts": dict(status_counts),
        "decision_counts": dict(decision_counts),
        "results": all_results,
    }

    summary_json_path = results_dir / f"{batch_slug}_summary.json"
    summary_csv_path = results_dir / f"{batch_slug}_summary.csv"
    summary_json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_summary_csv(summary_csv_path, all_results)

    print(json.dumps(
        {
            "summary_json_path": str(summary_json_path),
            "summary_csv_path": str(summary_csv_path),
            "status_counts": dict(status_counts),
            "decision_counts": dict(decision_counts),
        },
        indent=2,
        sort_keys=True,
    ))
    return 0 if status_counts.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
