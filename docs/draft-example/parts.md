# Reusable parts

Use these instead of writing the same thing again. Declare envs and helper
modules in tutorial.yaml (`env:`, `uses:`); use shared steps with one line.

## Environments (`env:` in tutorial.yaml)

An env creates the cluster and installs KServe; the generated setup step runs it.
If none fits, do NOT create one: write the setup as steps and add a TODO to the notes.

### `kind-llmisvc/v1`

- what: Kind cluster (control-plane + worker) with a local registry, KServe LLMInferenceService and its gateway stack, installed with KServe's own hack scripts checked out at the requested KServe tag. CPU only.
- KServe: {'min': 'v0.17.1'}
- frozen: False
- use: `env: kind-llmisvc/v1`
- used by: inferencegraph-ensemble, llmisvc-anatomy
- details: envs/kind-llmisvc/v1/README.md, envs/kind-llmisvc/v1/setup.sh
- tools:

```
# CLI tools this environment needs, installed by setup.sh into
# <repo>/.tools/<tool>/<version>/ (never system-wide) and put on PATH only by
# the tutorial's setup step. kind and helm follow KServe's kserve-deps.env (v0.18.0).
KIND=v0.30.0                  # default node image: kindest/node:v1.34.0
KUBECTL=v1.34.13              # matches Kubernetes 1.34
HELM=v3.16.3
CLOUD_PROVIDER_KIND=v0.12.0   # LoadBalancer addresses for kind, like a cloud
```

## Helper scripts (`uses:` in tutorial.yaml, called from steps)

### `llmisvc/v1` — Helpers for tutorials that deploy an LLMInferenceService on a Kind cluster.

- use: `uses: [llmisvc/v1]` in tutorial.yaml
- used by: llmisvc-anatomy

- `"$TUT_LIB/llmisvc/v1/gateway-url.sh"` — Print the Gateway URL of an LLMInferenceService (Kind NodePort). (source: lib/llmisvc/v1/gateway-url.sh)
- `"$TUT_LIB/llmisvc/v1/scheduler-pod.sh"` — Print the name of the EPP scheduler Pod in a namespace. (source: lib/llmisvc/v1/scheduler-pod.sh)
- `"$TUT_LIB/llmisvc/v1/completion.sh"` — Send an OpenAI-style completion request and check that text comes back. (source: lib/llmisvc/v1/completion.sh)

## Shared steps (`<!-- tut:use name -->` + `<!-- /tut -->`, then ./tut sync)

- `poc-config` — defined in poc-shared-2-config; used by poc-shared-3-scale
- `poc-model` — defined in poc-shared-1-deploy; used by poc-shared-2-config, poc-shared-3-scale
