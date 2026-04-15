#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

python main.py --help >/dev/null

VERIFY_OUTPUT=$(python verify_awm.py \
  --model-a /share/OLMo-1B-hf \
  --model-b /share/phi-1.5 \
  --device cpu \
  --output-dir "$ROOT_DIR/artifacts/awm")

echo "$VERIFY_OUTPUT"

RESULT_JSON=$(printf '%s' "$VERIFY_OUTPUT" | python -c 'import json, sys; print(json.load(sys.stdin)["artifacts"]["result_path"])')

test -f "$RESULT_JSON"

echo "Smoke test passed: $RESULT_JSON"
