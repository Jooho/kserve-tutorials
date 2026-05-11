# 00. Environment Setup

Set up the environment for the LLMInferenceService demo series. Install KServe LLMInferenceService on a Kind cluster.

> **All demos (00–05) run on a Kind cluster without GPU.**

## Prerequisites

| Item | Description |
|------|-------------|
| Docker | Required to run the Kind cluster |
| Go | Required to build `cloud-provider-kind` |
| kubectl | Kubernetes CLI |

## Step 1: Clone KServe Source

All installation scripts are included in the KServe source.

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
KSERVE_SRC="${REPO_ROOT}/kserve"
if [ ! -d "$KSERVE_SRC/.git" ]; then
  git clone --depth 1 https://github.com/kserve/kserve.git "$KSERVE_SRC"
else
  git -C "$KSERVE_SRC" pull --ff-only 2>/dev/null || true
fi
cd "$KSERVE_SRC"
```

## Step 2: Kind Cluster + KServe LLMInferenceService Installation

### Create Kind Cluster

```bash
./hack/setup/dev/manage.kind-with-registry.sh
```

This script:
- Creates a Kind cluster (control-plane + worker node)
- Creates and connects a local Docker registry (`localhost:5001`)
- Configures containerd registry settings

### Install KServe LLMInferenceService

```bash
./hack/kserve-install.sh --type llmisvc --kustomize
```

This single command installs all of the following:
- cert-manager, Gateway API CRDs, Gateway Inference Extension
- Envoy Gateway + Envoy AI Gateway
- LWS Operator
- KServe LLMInferenceService controller + well-known LLMInferenceServiceConfig
- `cloud-provider-kind` (assigns LoadBalancer External IP in Kind)

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    LLMInferenceService                       │
│                  (KServe LLMInferenceService CRD)            │
├──────────────────────────────┬───────────────────────────────┤
│       Gateway Stack          │     Independent Components    │
│                              │                               │
│  Envoy AI Gateway            │  LWS Operator                 │
│    ├─ Envoy Gateway          │  (Worker group management)    │
│    │   └─ Gateway API CRDs   │                               │
│    └─ Gateway Inference Ext  │  cert-manager                 │
│       (InferencePool etc.)   │  (Certificate management)     │
│                              │                               │
├──────────────────────────────┴───────────────────────────────┤
│                     Kind Cluster (CPU)                       │
└──────────────────────────────────────────────────────────────┘
```

### Installed Components

| Component | Role |
|-----------|------|
| cert-manager | Automatic TLS certificate management |
| Gateway API CRDs | Kubernetes Gateway API standard |
| Gateway Inference Extension | AI inference CRDs such as InferencePool |
| Envoy Gateway | Gateway API implementation (L7 proxy) |
| Envoy AI Gateway | AI workload-specific routing (token-based etc.) |
| LWS Operator | LeaderWorkerSet - worker group management for P/D disaggregation |
| KServe LLMInferenceService | LLMInferenceService CRD and controller |
| cloud-provider-kind | Assigns LoadBalancer External IP in Kind |

### Verify Installation

```bash
kubectl get pods -n kserve
kubectl get crd llminferenceservices.serving.kserve.io
kubectl get gateway -A
kubectl get pods -n envoy-gateway-system
kubectl get pods -n lws-system
```

## Step 3: Create Namespace

```bash
NS=kserve-demo
kubectl create namespace $NS
```

All subsequent demos use `NS=kserve-demo`.

### Create ServiceAccount for EPP Metrics Access

The EPP Scheduler metrics endpoint requires authentication (`metrics-endpoint-auth: true`).
To query metrics directly in demos, create a SA with GET permission for `/metrics`.

```bash
kubectl create clusterrole metrics-reader --verb=get --non-resource-url="/metrics"
kubectl create serviceaccount metrics-reader -n $NS
kubectl create clusterrolebinding metrics-reader-binding \
  --clusterrole=metrics-reader --serviceaccount=$NS:metrics-reader
```

## Step 4: Install Prometheus + Grafana (Optional)

Required for the 03-monitoring demo. Install here or in [03-monitoring](../03-monitoring/) Step 0.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  --set grafana.service.type=NodePort \
  --set grafana.service.nodePort=30090
```

ServiceMonitor, EPP auth configuration, and dashboard import are covered in [03-monitoring](../03-monitoring/).

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Pod `Pending` | Insufficient resources | Check Kind worker node resources |
| `CreateContainerConfigError` | `runAsNonRoot` conflict | Add `securityContext.runAsUser: 1000` |
| `ImagePullBackOff` | Registry unreachable | Check proxy/firewall settings |
| LLMInferenceService `WaitingForGateway` | HTTPRoute not created | Check if `router.route: {}` is missing |
| Gateway `Programmed=False` | LB not configured | Check if `cloud-provider-kind` is running |

## GPU Environment (Optional)

With a GPU cluster, you can run additional demos such as P/D disaggregation (KV cache transfer).
Differences in GPU environments:

| Item | CPU (Kind) | GPU (OpenShift etc.) |
|------|-----------|----------------------|
| Model | `hf://facebook/opt-125m` | `oci://quay.io/redhat-ai-services/modelcar-catalog:qwen2.5-0.5b-instruct` |
| Image | `vllm-cpu-release-repo` | well-known config default (`llm-d-cuda`) |
| LLMInferenceServiceConfig | Not needed (uses well-known) | Custom or well-known |
| Demo scope | 00–05 all | 00–05 + KV cache transfer |

## Next Step

After setup is complete, proceed to [01-anatomy](../01-anatomy/) to dissect the resources created by LLMInferenceService.
