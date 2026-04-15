# Local AWM Integration

This repository now includes a thin integration layer around the upstream `main.py` flow so local lineage checks can be scripted and persisted without changing the core AWM logic.

## Environment

Install dependencies with one of the existing requirement files:

```bash
pip install -r requirements.txt
```

If PyTorch is managed outside the repo, keep using your existing runtime and ignore `requirements.no_torch.txt`.

Recommended cache settings for this environment:

```bash
export HF_HOME=/share/zhuzy/cache/hf
export PIP_CACHE_DIR=/share/zhuzy/cache/pip
export TORCH_HOME=/share/zhuzy/cache/torch
```

CPU is the default execution target for this first local integration pass. `--device auto` and `--device cuda` are still forwarded to upstream `main.py` when available.

## Single Pair Verification

Use `verify_awm.py` to run one local pair and emit a structured JSON result while also saving the raw upstream log.

```bash
python verify_awm.py \
  --model-a /share/OLMo-1B-hf \
  --model-b /share/phi-1.5 \
  --device cpu \
  --output-dir artifacts/awm
```

Outputs are written under:

- `artifacts/awm/logs/`: raw `main.py` console logs
- `artifacts/awm/results/`: structured JSON results

## Batch Verification

Use `run_awm_batch.py` with a JSON config containing multiple pairs.

```bash
python run_awm_batch.py \
  --pairs-config configs/local_demo_pairs.json \
  --device cpu \
  --output-dir artifacts/awm
```

Batch execution produces:

- per-pair JSON results under `artifacts/awm/results/`
- one batch summary JSON
- one batch summary CSV

## Demo Pair Config

`configs/local_demo_pairs.json` contains four ready-to-run local pairs:

- `OLMo-1B-hf vs OLMo-1B-hf`
- `OLMo-1B-hf vs phi-1.5`
- `Qwen2.5-1.5B vs SmolLM2-1.7B`
- `gemma-2-2b vs pythia-1.4b`

## JSON Output Schema

Each `verify_awm.py` run returns a JSON object with these top-level fields:

- `status`: `success` or `failed`
- `pair_name` and `pair_label`
- `model_a` / `model_b`: local names and paths
- `metrics`: parsed AWM summary fields
- `decision`: thresholded verdict derived from z-score
- `artifacts`: saved log path and result path
- `command` / `command_str`: exact upstream invocation
- `reference_distribution`: fixed negative reference constants used by AWM

Parsed metric fields are:

- `average_wq_weights_pct`
- `average_wk_weights_pct`
- `average_wq_wk_weights_pct`
- `reference_similarity_pct`
- `absolute_z_score`

## Decision Rules

The local wrapper applies the fixed interpretation requested for this integration:

- `z >= 2.0` => `related`
- `1.0 <= z < 2.0` => `uncertain`
- `z < 1.0` => `not_related`

## Smoke Test

Run the minimal end-to-end smoke test with:

```bash
bash scripts/smoke_test_awm.sh
```

The smoke test checks `main.py --help`, executes one local verification pair, and confirms that the structured JSON artifact exists.
