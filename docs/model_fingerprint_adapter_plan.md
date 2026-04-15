# Model-Fingerprint Adapter Plan

## Goal

Prepare a minimal, non-invasive path to integrate the Model-Fingerprint Adapter line as a second verification backend after AWM. This round does not aim to fully run the adapter. The goal is to define the entrypoint, execution envelope, blockers, and output contract so the next implementation pass can plug into the same local workflow.

## Official Entry

The expected official entry should remain whatever the upstream Model-Fingerprint Adapter repository exposes as its documented CLI or Python runner. For the local integration layer here, the adapter backend should be wrapped instead of merged into `main.py`.

Recommended integration principle:

- keep upstream adapter code in its own checkout or subdirectory
- call the official adapter entrypoint from a thin local wrapper
- convert raw backend output into the unified verification schema described below

## Minimal Execution Path

A first runnable adapter integration should look like this:

1. Prepare a dedicated adapter environment with its upstream dependencies.
2. Identify the official adapter command or Python API for a single model verification run.
3. Add a wrapper script in this repository, for example `verify_model_fingerprint.py`.
4. Accept local model path or ownership evidence input through wrapper arguments.
5. Execute the upstream adapter without rewriting its internals.
6. Save raw logs under `artifacts/model_fingerprint/logs/`.
7. Save structured results under `artifacts/model_fingerprint/results/`.
8. Normalize the result into the unified schema so downstream callers can compare AWM, adapter, and watermark outputs consistently.

## Key Dependencies

The exact dependency set depends on the upstream adapter implementation, but the integration should expect these categories:

- Python runtime isolated from the AWM environment if the dependency graph conflicts
- model loading stack for the target architectures
- tokenizer support if the adapter depends on tokenizer-derived features
- any attribution or ownership-specific packages required by the upstream backend
- stable local storage for raw evidence, intermediate caches, and structured outputs

## Likely Blockers

The next implementation round should expect these blockers:

- upstream adapter repository or package may not expose a stable single-run CLI
- dependency conflicts with the current AWM environment are likely
- adapter inputs may require metadata beyond just a local checkpoint path
- verification may depend on ownership-side reference artifacts that are not yet collected
- result semantics may be confidence-oriented rather than z-score-oriented, which requires careful normalization
- GPU or larger-memory requirements may exceed the default CPU-first assumptions used for the AWM local pass

## This Round's Minimal Deliverable

This round stops at preparation. The concrete target is:

- document the adapter as the planned gray-box backend
- define a wrapper-based integration strategy
- define a unified output schema that future adapter runs must satisfy
- avoid touching upstream AWM code paths

## Unified Output Schema

The adapter backend should emit the same outer envelope as AWM, with backend-specific evidence placed under `metrics` and `evidence` fields.

```json
{
  "tool": "model_fingerprint_adapter",
  "status": "success",
  "backend": "adapter",
  "pair_name": "ownership_check_001",
  "started_at": "2026-04-15T00:00:00Z",
  "finished_at": "2026-04-15T00:02:00Z",
  "subject": {
    "path": "/path/to/model_or_artifact"
  },
  "artifacts": {
    "log_path": "artifacts/model_fingerprint/logs/run.log",
    "result_path": "artifacts/model_fingerprint/results/run.json"
  },
  "metrics": {
    "backend_score": 0.91,
    "backend_confidence": 0.88
  },
  "decision": "supported",
  "evidence": {
    "mode": "gray_box",
    "ownership_signal": "adapter_specific"
  },
  "error": null
}
```

## Normalization Guidance

To keep adapter results composable with AWM and watermark outputs:

- `tool` should identify the backend family
- `status` should capture run health only
- `decision` should represent the backend-level verdict after thresholding
- `metrics` should keep raw backend scores without forcing them into AWM's z-score semantics
- `evidence.mode` should be `gray_box`
- `artifacts` must always include both raw log and structured result paths

## Suggested Next Step

Once the upstream adapter repo and its official single-run entry are confirmed, the next task should be to implement the wrapper and one smoke-tested local example without expanding scope into a full benchmark suite.
