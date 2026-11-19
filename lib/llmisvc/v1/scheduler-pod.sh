#!/usr/bin/env bash
# Usage: scheduler-pod.sh <namespace>
# Prints the name of the EPP scheduler Pod created for an LLMInferenceService.
set -euo pipefail
kubectl get pod -n "${1:?namespace}" \
  -l app.kubernetes.io/component=llminferenceservice-router-scheduler \
  -o jsonpath='{.items[0].metadata.name}'
