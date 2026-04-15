#!/usr/bin/env bash
#
# Script to download language model checkpoints from the Hugging Face Hub.
#
# Usage:
#   ./download_models.sh             # list supported configs
#   ./download_models.sh sft_pairs   # download models for one config
#   ./download_models.sh all         # download all mapped models

set -euo pipefail

# This should match CHECKPOINT_BASE_DIR in configs.py.
CHECKPOINT_BASE_DIR="/share/zhuzy/models/awm"

get_config_keys() {
    python3 -c "from configs import AVAILABLE_CONFIGS; print(' '.join(AVAILABLE_CONFIGS.keys()))"
}

get_hf_ids() {
    local config_name=$1
    python3 -c "
import sys
from configs import AVAILABLE_CONFIGS, MODEL_HF_MAP

config_name = '$config_name'

hf_ids = set()

if config_name == 'all':
    configs_to_process = AVAILABLE_CONFIGS.values()
elif config_name in AVAILABLE_CONFIGS:
    configs_to_process = [AVAILABLE_CONFIGS[config_name]]
else:
    print(f'Error: Config \"{config_name}\" not found.', file=sys.stderr)
    sys.exit(1)

for config in configs_to_process:
    for folder_name in config.get('model_paths', {}).values():
        if folder_name in MODEL_HF_MAP:
            hf_ids.add(MODEL_HF_MAP[folder_name])
        else:
            print(f'Warning: No Hugging Face ID mapping found for folder \"{folder_name}\" in configs.py', file=sys.stderr)

print(' '.join(sorted(list(hf_ids))))
"
}

ensure_hf_cli() {
    if ! command -v hf >/dev/null 2>&1; then
        echo "Error: 'hf' CLI not found. Install huggingface-hub with: pip install -U huggingface-hub"
        exit 1
    fi
}

download_model() {
    local hf_id=$1
    local folder_name
    folder_name=$(echo "$hf_id" | awk -F/ '{print $NF}')
    local target_dir="$CHECKPOINT_BASE_DIR/$folder_name"

    if [ -d "$target_dir" ] && [ -n "$(ls -A "$target_dir" 2>/dev/null)" ]; then
        echo "--> Model '$hf_id' already exists at '$target_dir'. Skipping."
        return 0
    fi

    mkdir -p "$target_dir"
    echo "--> Downloading '$hf_id' to '$target_dir'..."
    if hf download "$hf_id" --local-dir "$target_dir"; then
        echo "--> Successfully downloaded '$hf_id'."
    else
        echo "--> Error downloading '$hf_id'. Please check the error message above."
        return 1
    fi
}

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )
if [ ! -f "$SCRIPT_DIR/configs.py" ]; then
    echo "Error: This script must be run from the AWM repository root."
    exit 1
fi
cd "$SCRIPT_DIR"

ensure_hf_cli
CONFIG_KEYS=$(get_config_keys)
TARGET_CONFIG=${1:-}

if [ -z "$TARGET_CONFIG" ]; then
    echo "Usage: $0 [config_name | all]"
    echo ""
    echo "Available configurations:"
    for key in $CONFIG_KEYS; do
        echo "  - $key"
    done
    echo "  - all (to download all models from all configurations)"
    exit 0
fi

echo "Parsing configuration '$TARGET_CONFIG'..."
MODELS_TO_DOWNLOAD=$(get_hf_ids "$TARGET_CONFIG")
if [ -z "$MODELS_TO_DOWNLOAD" ]; then
    echo "No models found to download for '$TARGET_CONFIG'. This could be due to an incorrect config name or missing mappings in MODEL_HF_MAP."
    exit 1
fi

mkdir -p "$CHECKPOINT_BASE_DIR"
read -r -a model_array <<< "$MODELS_TO_DOWNLOAD"

echo "Found ${#model_array[@]} unique models to download for configuration '$TARGET_CONFIG'."
echo "------------------------------------------------------------------"

i=1
for model_id in $MODELS_TO_DOWNLOAD; do
    echo "[${i}/${#model_array[@]}] Processing model: $model_id"
    download_model "$model_id"
    i=$((i+1))
done

echo "------------------------------------------------------------------"
echo "All download tasks completed."
