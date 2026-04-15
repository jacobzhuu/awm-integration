#!/usr/bin/env python3
"""Structured wrapper around the existing AWM local comparison entrypoint."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NEGATIVE_REFERENCE_SIMILARITY_PCT = 0.38
NEGATIVE_PAIR_MEAN = 0.00375
NEGATIVE_PAIR_STD = 0.0028
RELATED_Z_THRESHOLD = 2.0
UNCERTAIN_Z_THRESHOLD = 1.0
DEFAULT_OUTPUT_DIR = Path("artifacts") / "awm"

METRIC_PATTERNS = {
    "average_wq_weights_pct": re.compile(
        r"Average Wq_weights\s+Similarity\(%\)\s*=\s*([0-9.]+)"
    ),
    "average_wk_weights_pct": re.compile(
        r"Average Wk_weights\s+Similarity\(%\)\s*=\s*([0-9.]+)"
    ),
    "average_wq_wk_weights_pct": re.compile(
        r"Average Wq_Wk_weights\s+Similarity\(%\)\s*=\s*([0-9.]+)"
    ),
    "reference_similarity_pct": re.compile(
        r"Reference Similarity\(%\).*?=\s*([0-9.]+)"
    ),
    "absolute_z_score": re.compile(
        r"Absolute Z-Score vs negative pairs\s*=\s*([0-9.]+)"
    ),
}


ROOT_DIR = Path(__file__).resolve().parent


def slugify(value: str) -> str:
    """Turn a label into a stable filename fragment."""
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "awm_run"


def ensure_output_directories(output_dir: str | Path) -> tuple[Path, Path, Path]:
    """Create the output root plus logs/results subdirectories."""
    root_dir = Path(output_dir).expanduser().resolve()
    logs_dir = root_dir / "logs"
    results_dir = root_dir / "results"
    logs_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    return root_dir, logs_dir, results_dir


def classify_z_score(z_score: float | None) -> str | None:
    """Apply the fixed decision thresholds required by the integration layer."""
    if z_score is None:
        return None
    if z_score >= RELATED_Z_THRESHOLD:
        return "related"
    if z_score >= UNCERTAIN_Z_THRESHOLD:
        return "uncertain"
    return "not_related"


def parse_metrics(log_text: str) -> dict[str, float]:
    """Extract the summary metrics emitted by main.py."""
    metrics: dict[str, float] = {}
    missing_keys: list[str] = []

    for key, pattern in METRIC_PATTERNS.items():
        match = pattern.search(log_text)
        if match is None:
            missing_keys.append(key)
            continue
        metrics[key] = float(match.group(1))

    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(f"Failed to parse AWM metrics from main.py output: {missing}")

    return metrics


def build_command(model_a: str, model_b: str, device: str) -> list[str]:
    """Build the subprocess invocation against the upstream entrypoint."""
    return [
        sys.executable,
        str(ROOT_DIR / "main.py"),
        "--model_paths",
        model_a,
        model_b,
        "--device",
        device,
    ]


def run_verification(
    model_a: str,
    model_b: str,
    device: str = "cpu",
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    pair_name: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Run a single AWM comparison and persist both raw and structured outputs."""
    root_dir, logs_dir, results_dir = ensure_output_directories(output_dir)
    model_a_path = Path(model_a).expanduser().resolve()
    model_b_path = Path(model_b).expanduser().resolve()
    model_a_name = model_a_path.name
    model_b_name = model_b_path.name
    pair_label = label or f"{model_a_name} vs {model_b_name}"
    pair_identifier = pair_name or pair_label
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_slug = f"{slugify(pair_identifier)}_{timestamp}"
    log_path = logs_dir / f"{run_slug}.log"
    result_path = results_dir / f"{run_slug}.json"
    command = build_command(str(model_a_path), str(model_b_path), device)
    started_at = datetime.now(timezone.utc).isoformat()

    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    finished_at = datetime.now(timezone.utc).isoformat()
    log_text = completed.stdout
    log_path.write_text(log_text, encoding="utf-8")

    result: dict[str, Any] = {
        "tool": "awm",
        "status": "success" if completed.returncode == 0 else "failed",
        "pair_name": pair_identifier,
        "pair_label": pair_label,
        "started_at": started_at,
        "finished_at": finished_at,
        "command": command,
        "command_str": shlex.join(command),
        "device": device,
        "model_a": {
            "name": model_a_name,
            "path": str(model_a_path),
        },
        "model_b": {
            "name": model_b_name,
            "path": str(model_b_path),
        },
        "artifacts": {
            "output_root": str(root_dir),
            "log_path": str(log_path),
            "result_path": str(result_path),
        },
        "reference_distribution": {
            "mean_similarity": NEGATIVE_PAIR_MEAN,
            "std_similarity": NEGATIVE_PAIR_STD,
            "reference_similarity_pct": NEGATIVE_REFERENCE_SIMILARITY_PCT,
        },
        "thresholds": {
            "related": f"z >= {RELATED_Z_THRESHOLD}",
            "uncertain": f"{UNCERTAIN_Z_THRESHOLD} <= z < {RELATED_Z_THRESHOLD}",
            "not_related": f"z < {UNCERTAIN_Z_THRESHOLD}",
        },
        "return_code": completed.returncode,
    }

    if completed.returncode == 0:
        try:
            metrics = parse_metrics(log_text)
            result["metrics"] = metrics
            result["decision"] = classify_z_score(metrics["absolute_z_score"])
        except ValueError as exc:
            result["status"] = "failed"
            result["error"] = str(exc)
    else:
        result["error"] = "main.py exited with a non-zero return code"

    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for single pair verification."""
    parser = argparse.ArgumentParser(
        description="Run a single AWM verification job against two local model paths.",
    )
    parser.add_argument("--model-a", required=True, help="Path to the first local model directory.")
    parser.add_argument("--model-b", required=True, help="Path to the second local model directory.")
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda", "auto"],
        help="Device forwarded to main.py.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Root directory used to store logs/ and results/.",
    )
    return parser


def main() -> int:
    """CLI entrypoint."""
    parser = build_argument_parser()
    args = parser.parse_args()
    result = run_verification(
        model_a=args.model_a,
        model_b=args.model_b,
        device=args.device,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
