#!/usr/bin/env bash
# Usage: completion.sh <url> <model> [prompt] [max_tokens] [temperature]
# Sends POST <url>/v1/completions, prints the JSON answer and fails unless
# the first choice contains text. temperature defaults to 0 (greedy): the same
# prompt gives the same answer every run, as in the tutorial text.
set -euo pipefail
url="${1:?url}"; model="${2:?model}"; prompt="${3:-Kubernetes is}"; max="${4:-20}"; temp="${5:-0}"
body=$(python3 -c 'import json,sys; print(json.dumps({"model":sys.argv[1],"prompt":sys.argv[2],"max_tokens":int(sys.argv[3]),"temperature":float(sys.argv[4])}))' \
  "$model" "$prompt" "$max" "$temp")
curl -sf "${url}/v1/completions" -H "Content-Type: application/json" -d "$body" \
  | python3 -c 'import json, sys; r = json.load(sys.stdin); print(json.dumps(r, indent=2)); assert r["choices"][0]["text"], "empty completion"'
