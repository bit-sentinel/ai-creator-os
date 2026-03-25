#!/usr/bin/env bash
# Convenience wrapper to run pipelines from cron or shell
# Usage: ./scripts/run_pipeline.sh <pipeline> [account]

set -e
cd "$(dirname "$0")/.."

source venv/bin/activate

PIPELINE="${1:-all}"
ACCOUNT="${2:-}"

if [ -n "$ACCOUNT" ]; then
    python main.py --pipeline "$PIPELINE" --account "$ACCOUNT"
else
    python main.py --pipeline "$PIPELINE"
fi
