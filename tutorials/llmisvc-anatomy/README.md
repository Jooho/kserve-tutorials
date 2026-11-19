# One Apply, Ten Resources — LLMInferenceService Anatomy

<!-- tut:header -->

<!-- Generated from tutorial.yaml by `./tut sync` — do not edit by hand. -->
> **Status:** 🚧 draft · **Tested with KServe:** v0.18.0 · **Environment:** [`kind-llmisvc/v1`](../../envs/kind-llmisvc/v1/) · **GPU:** not required

<!-- /tut -->

A single `kubectl apply` of an LLMInferenceService makes the controller create 10+
Kubernetes resources. This tutorial watches that happen and explains what each
resource is for.

> **Key question:** what happens inside the cluster when you apply one
> LLMInferenceService YAML?

## Step 0: Environment

This prepares a Kind cluster with KServe LLMInferenceService (see the environment
link above) and creates the namespace used below. It is safe to run again.

<!-- tut:setup -->

```bash run
# Generated from tutorial.yaml by `./tut sync` — do not edit by hand.
export KSERVE_VERSION="${KSERVE_VERSION:-v0.18.0}"
export NS="${NS:-llmisvc-anatomy}"
export REPO_ROOT="$(git rev-parse --show-toplevel)"
export TUT_LIB="$REPO_ROOT/lib"
"$REPO_ROOT/envs/kind-llmisvc/v1/setup.sh"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
cd "$REPO_ROOT/tutorials/llmisvc-anatomy"
```

<!-- /tut -->

## Step 1: Snapshot before applying

Record the current state first. The namespace should be empty.

```bash run
echo "=== Before Apply ==="
kubectl get pods,svc,deploy,inferencepool,httproute -n "$NS" 2>/dev/null || true
```

## Step 2: Deploy the LLMInferenceService

Apply a single YAML. The well-known config is injected automatically, so no
separate `LLMInferenceServiceConfig` is needed.

```bash run
kubectl apply -f manifests/llmisvc-cpu.yaml -n "$NS"
```

<details>
<summary>manifests/llmisvc-cpu.yaml</summary>

<!-- tut:include manifests/llmisvc-cpu.yaml -->

```yaml
apiVersion: serving.kserve.io/v1alpha2
kind: LLMInferenceService
metadata:
  name: demo-model
spec:
  model:
    uri: "hf://facebook/opt-125m"
    name: facebook/opt-125m
  replicas: 1
  router:
    scheduler: {}
    route: {}
    gateway: {}
  template:
    containers:
      - name: main
        image: public.ecr.aws/q9t5s3a7/vllm-cpu-release-repo:v0.19.0
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
        env:
          - name: USER
            value: nonroot
          - name: VLLM_LOGGING_LEVEL
            value: DEBUG
          - name: VLLM_CPU_KVCACHE_SPACE
            value: "1"
          - name: VLLM_ADDITIONAL_ARGS
            value: "--block-size 16"
        resources:
          limits:
            cpu: "2"
            memory: 7Gi
          requests:
            cpu: 200m
            memory: 2Gi
        livenessProbe:
          initialDelaySeconds: 180
          periodSeconds: 30
          timeoutSeconds: 30
          failureThreshold: 8
        readinessProbe:
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
```

<!-- /tut -->

</details>

Key points of this YAML:

| Field | Value | Description |
|-------|-------|-------------|
| `model.uri` | `hf://facebook/opt-125m` | Downloaded from Hugging Face automatically |
| `router.route: {}` | Required | No HTTPRoute is created without it |
| `securityContext.runAsUser` | `1000` | Needed because the vLLM CPU image is built as root |
| `baseRefs` | None | The well-known config is injected (see below) |

### Well-known LLMInferenceServiceConfig injection

KServe installs **well-known LLMInferenceServiceConfigs** into the cluster:

| Config | Role |
|--------|------|
| `kserve-config-llm-template` | vLLM container template (command, probes, security) |
| `kserve-config-llm-scheduler` | EPP scheduler + tokenizer sidecar |

When an LLMInferenceService is created, the controller **merges** these configs
automatically. Even without `baseRefs`, the command, probes and EPP scheduler are
configured; you only override `image`, `env` and `resources` inline.

## Step 3: Watch the resources appear

Right after applying, watch the resources being created one by one (in a second
terminal; press `Ctrl+C` to stop):

```bash skip
watch -n 1 "kubectl get pods,svc,deploy,lws,inferencepool,httproute -n $NS 2>/dev/null"
```

Then wait until the service reports `Ready`. Downloading the model and starting
vLLM on CPU takes a few minutes.

```bash verify
kubectl wait --for=condition=Ready llminferenceservice/demo-model -n "$NS" --timeout=900s
```

## Resource map

```text
kubectl apply -f llmisvc-cpu.yaml
        │
        ▼
┌─ KServe LLMInferenceService controller ──────────────────────┐
│                                                               │
│  1. TLS certificates                                          │
│     └── Secret (self-signed certs)                            │
│                                                               │
│  2. Workload (model serving)                                  │
│     ├── Deployment (vLLM Pod, single node)                    │
│     │   └ LeaderWorkerSet is used for multi-node              │
│     ├── Service (*-workload-svc, port 8000)                   │
│     └── ServiceAccount                                        │
│                                                               │
│  3. Scheduler (request routing)                               │
│     ├── Deployment (EPP scheduler + tokenizer sidecar)        │
│     ├── Service (*-epp-service, gRPC 9002 etc.)               │
│     ├── Role + RoleBinding (RBAC)                             │
│     └── ServiceAccount                                        │
│                                                               │
│  4. Traffic wiring                                            │
│     ├── InferencePool (scheduler ↔ workload)                  │
│     └── HTTPRoute (Gateway → InferencePool)                   │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## Step 4: What each resource does

### 1. LeaderWorkerSet — workload management

```bash run
kubectl get lws -n "$NS" -o wide
```

LWS manages vLLM Pods in multi-node deployments (P/D disaggregation, DP+EP, ...).
A single-node deployment (only `replicas`, no `parallelism`) uses a regular
Deployment, so **no LWS is created here** and the command above prints
`No resources found`.

### 2. EPP scheduler — where each request goes

```bash run
kubectl get deploy -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler
kubectl logs -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler --tail=20
```

The EPP (Endpoint Picker Plugin) decides which vLLM Pod receives each request,
based on queue depth, KV-cache utilization and similar signals.

#### Inside the scheduler Pod

```bash run
kubectl get pod -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler \
  -o custom-columns='INIT:.spec.initContainers[*].image,CONTAINERS:.spec.containers[*].image'
```

```text
┌─────────────────────────────────────────────┐
│  Scheduler Pod                              │
│                                             │
│  Init: storage-initializer                  │
│    └ Downloads only tokenizer files from HF │
│      (tokenizer.json, vocab.json, etc.)     │
│      Does NOT download model weights        │
│                                             │
│  ┌─────────────┐            ┌────────────┐  │
│  │  scheduler  │            │ tokenizer  │  │
│  │  (main)     │   (idle)   │ (sidecar)  │  │
│  │  gRPC:9002  │            │ HTTP:8082  │  │
│  │  health:9003│            │ (health)   │  │
│  │  metrics:   │            │ Idle in    │  │
│  │   9090      │            │ default    │  │
│  │  Scoring,   │            │ config     │  │
│  │  Pod select │            │            │  │
│  └─────────────┘            └────────────┘  │
└─────────────────────────────────────────────┘
         ▲
         │ gRPC (ExtProc)
    Envoy Gateway
```

| Container | Image | Role |
|-----------|-------|------|
| `storage-initializer` (init) | `kserve/storage-initializer` | Downloads only tokenizer files (filtered by `STORAGE_ALLOW_PATTERNS`) |
| `main` (scheduler) | `llm-d/llm-d-inference-scheduler` | EPP scheduler; talks to Envoy over ExtProc gRPC and picks a Pod after scoring |
| `tokenizer` (sidecar) | `llm-d/llm-d-uds-tokenizer` | **Idle** by default; used by `precise-prefix-cache-scorer` over a Unix socket |

The scheduler Pod must have exactly the three containers above:

```bash verify
POD=$("$TUT_LIB/llmisvc/v1/scheduler-pod.sh" "$NS")
test "$(kubectl get pod -n "$NS" "$POD" -o jsonpath='{.spec.initContainers[*].name}')" = "storage-initializer"
test "$(kubectl get pod -n "$NS" "$POD" -o jsonpath='{.spec.containers[*].name}' | wc -w)" -eq 2
```

#### Scheduling plugins (from the well-known config)

```bash run
kubectl describe pod -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler \
  | grep -A 15 "config-text" || true
```

Default configuration:

- `queue-scorer` (weight 2) — prefers Pods with fewer queued requests
- `prefix-cache-scorer` (weight 3) — prefers Pods with a higher prefix-cache hit rate (from vLLM metrics)
- `max-score-picker` — picks the Pod with the highest combined score

#### Why the tokenizer sidecar is idle

The well-known config (`kserve-config-llm-scheduler`) always injects the
tokenizer, but the default `prefix-cache-scorer` only reads vLLM metrics. The
tokenizer is used only after switching to `precise-prefix-cache-scorer`.

<details>
<summary>precise-prefix-cache-scorer — when the tokenizer is used</summary>

With `precise-prefix-cache-scorer` the tokenizer becomes active:

1. The tokenizer tokenizes the prompt and computes block hashes
2. vLLM publishes cache events over ZMQ
3. The scheduler matches block hashes with cache events to pick the exact Pod

| | `prefix-cache-scorer` (default) | `precise-prefix-cache-scorer` |
|---|---|---|
| Data source | vLLM metrics (`prefix_cache_hit_rate`) | vLLM's real-time ZMQ event stream |
| Method | Uses the hit rate reported by vLLM | Scheduler tokenizes → block hash → exact match |
| Tokenizer | **Not used** (injected but idle) | **Used** (over a Unix domain socket) |
| Extra vLLM config | None | `--enable-kvcache`, `--block-size`, ZMQ publishing |

The tokenizer and scheduler talk over a **Unix domain socket**
(`/tmp/tokenizer/tokenizer-uds.socket`) inside the same Pod, which avoids the
kernel network stack:

```bash skip
kubectl exec -n "$NS" "$("$TUT_LIB/llmisvc/v1/scheduler-pod.sh" "$NS")" -c main -- ls -la /tmp/tokenizer/
```

Configuration example: [precise-prefix-kv-cache-routing](https://github.com/kserve/kserve/tree/master/docs/samples/llmisvc/precise-prefix-kv-cache-routing)
</details>

### 3. InferencePool — linking scheduler and workload

```bash run
kubectl get inferencepool -n "$NS" -o yaml
```

InferencePool is a CRD from the Gateway API Inference Extension. It lets the
scheduler discover the workload Pods and route to them.

### 4. HTTPRoute — traffic from the Gateway

```bash run
kubectl get httproute -n "$NS" -o yaml
```

The HTTPRoute forwards requests received by the Gateway to the InferencePool,
and from there to the scheduler.

### 5. Services — internal wiring

```bash run
kubectl get svc -n "$NS"
```

| Service | Purpose | Ports |
|---------|---------|-------|
| `*-workload-svc` | Exposes the vLLM Pod | 8000 (HTTPS) |
| `*-epp-service` | Exposes the EPP scheduler | 9002 (gRPC), 9003 (health), 9090 (metrics), 5557 (ZMQ) |

> The metrics port (9090) is plain HTTP but requires a bearer token
> (`metrics-endpoint-auth: true`). Reading those metrics is covered in the
> request-flow tutorial of this series.

## Step 5: Check the result

```bash run
echo "--- Pods ---";          kubectl get pods -n "$NS" -o wide
echo "--- Services ---";      kubectl get svc -n "$NS"
echo "--- InferencePool ---"; kubectl get inferencepool -n "$NS"
echo "--- HTTPRoute ---";     kubectl get httproute -n "$NS"
echo "--- Secrets ---";       kubectl get secret -n "$NS"
```

Expected (nothing before applying → after applying):

```text
Pods:          2 (vLLM x1 + scheduler x1)
Services:      2 (workload-svc + epp-service)
Deployments:   2 (workload + scheduler)
InferencePool: 1
HTTPRoute:     1
Secrets:       1+ (TLS certs)
```

The same expectations, checked automatically:

```bash verify
count() { kubectl get "$1" -n "$NS" --no-headers 2>/dev/null | wc -l; }
test "$(count deploy)" -eq 2
test "$(count svc)" -ge 2
test "$(count inferencepool)" -eq 1
test "$(count httproute)" -eq 1
```

## Step 6: Send a request

Once the LLMInferenceService is `Ready`, send a completion request through the
Gateway. In Kind the Gateway is reached through a NodePort on the worker node;
the shared `llmisvc/v1` module works out the URL.

```bash run
GATEWAY_URL=$("$TUT_LIB/llmisvc/v1/gateway-url.sh" "$NS" demo-model)
echo "$GATEWAY_URL"
```

```bash verify retry=10 delay=15
"$TUT_LIB/llmisvc/v1/completion.sh" "$GATEWAY_URL" facebook/opt-125m "Kubernetes is"
```

<details>
<summary>lib/llmisvc/v1/gateway-url.sh</summary>

<!-- tut:include ../../lib/llmisvc/v1/gateway-url.sh -->

```bash skip
#!/usr/bin/env bash
# Usage: gateway-url.sh <namespace> <llmisvc-name>
# Prints the URL that reaches the LLMInferenceService through the Envoy Gateway.
# In Kind there is no external load balancer, so we use the worker node IP and
# the Gateway service NodePort.
set -euo pipefail
ns="${1:?namespace}"; name="${2:?llmisvc name}"
node_ip=$(docker inspect "${KIND_CLUSTER_NAME:-kind}-worker" \
  --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
node_port=$(kubectl get svc -n envoy-gateway-system \
  -l gateway.envoyproxy.io/owning-gateway-name \
  -o jsonpath='{.items[0].spec.ports[0].nodePort}')
echo "http://${node_ip}:${node_port}/${ns}/${name}"
```

<!-- /tut -->

</details>

<details>
<summary>lib/llmisvc/v1/completion.sh</summary>

<!-- tut:include ../../lib/llmisvc/v1/completion.sh -->

```bash skip
#!/usr/bin/env bash
# Usage: completion.sh <url> <model> [prompt] [max_tokens]
# Sends POST <url>/v1/completions, prints the JSON answer and fails unless
# the first choice contains text.
set -euo pipefail
url="${1:?url}"; model="${2:?model}"; prompt="${3:-Kubernetes is}"; max="${4:-20}"
body=$(python3 -c 'import json,sys; print(json.dumps({"model":sys.argv[1],"prompt":sys.argv[2],"max_tokens":int(sys.argv[3])}))' \
  "$model" "$prompt" "$max")
curl -sf "${url}/v1/completions" -H "Content-Type: application/json" -d "$body" \
  | python3 -c 'import json, sys; r = json.load(sys.stdin); print(json.dumps(r, indent=2)); assert r["choices"][0]["text"], "empty completion"'
```

<!-- /tut -->

</details>

## Cleanup

Deleting the LLMInferenceService removes every resource the controller created
(Deployments, Services, InferencePool, HTTPRoute, ...) through OwnerReference
cascading deletion.

```bash cleanup
kubectl delete llminferenceservice demo-model -n "$NS" --ignore-not-found --wait=true
kubectl delete namespace "$NS" --ignore-not-found
```

The Kind cluster itself is shared by the tutorials in this environment; remove it
with the environment's `teardown.sh` when you are done.

## What we learned

- One LLMInferenceService YAML creates 10+ resources
- The **well-known LLMInferenceServiceConfig** is injected, so no separate config is needed
- The scheduler Pod has three containers: init (tokenizer download) + scheduler + tokenizer (idle by default)
- Core structure: **Deployment (workload)** ↔ **InferencePool** ↔ **scheduler** ↔ **HTTPRoute** ↔ **Gateway**
- Cleanup cascades through OwnerReferences
