<!-- tut-translation source=README.md sha=8559b134b951 -->
# 한 번 적용하면 리소스 10개가 생깁니다 — LLMInferenceService의 구조

<!-- tut:header -->

<!-- tutorial.yaml에서 `./tut sync`로 생성됨 — 직접 수정하지 마세요. -->
> **상태:** ✅ 안정 · **검증된 KServe:** v0.18.0 · **환경:** [`kind-kserve/v1`](../../envs/kind-kserve/v1/) · **GPU:** 불필요
>
> 🌐 [English](README.md)

<!-- /tut -->

LLMInferenceService를 `kubectl apply`로 한 번 적용하면 컨트롤러가 Kubernetes 리소스를
10개 이상 생성합니다. 이 튜토리얼에서는 리소스가 생성되는 과정을 보고 각각 어떤 역할을 하는지 살펴봅니다.

> **핵심 질문** — LLMInferenceService YAML 파일 하나를 적용하면 클러스터 안에서 어떤 일이 일어납니까?

이 튜토리얼에서 살펴볼 내용입니다.

- LLMInferenceService 하나에서 어떤 리소스가 생성되는지 살펴봅니다. vLLM 워크로드, EPP 스케줄러,
  InferencePool, HTTPRoute와 그 사이를 연결하는 Service가 생성됩니다.
- 직접 작성하지 않은 설정이 어디에서 오는지 살펴봅니다. KServe가 기본으로 제공하는 LLMInferenceServiceConfig의
  설정을 사용자가 적용한 객체에 병합합니다.
- Gateway, HTTPRoute, InferencePool, 스케줄러, vLLM Pod가 어떻게 연결되는지 살펴봅니다.
- 스케줄러 Pod 안에서 무엇이 실행되고 기본 설정에서 어떤 구성 요소를 사용하는지 살펴봅니다.
- OwnerReference 덕분에 LLMInferenceService만 삭제해도 정리가 끝나는 이유를 살펴봅니다.

## 0단계 환경 준비

KServe의 LLMInferenceService를 사용할 수 있는 Kind 클러스터를 준비하고(위 환경 링크 참조),
아래에서 사용할 네임스페이스를 생성합니다. 이 단계는 다시 실행해도 안전합니다.

<!-- tut:setup -->

```bash run
# Generated from tutorial.yaml by `./tut sync` — do not edit by hand.
export KSERVE_VERSION="${KSERVE_VERSION:-v0.18.0}"
export NS="${NS:-llmisvc-anatomy}"
export REPO_ROOT="$(git rev-parse --show-toplevel)"
source "$REPO_ROOT/tools/local-config.sh"   # your settings in .tut.env, if any
export TUT_LIB="$REPO_ROOT/lib"
# pinned CLI tools of the environment, for this shell only
export PATH="$REPO_ROOT/.tools/kind/v0.30.0:$REPO_ROOT/.tools/kubectl/v1.34.13:$REPO_ROOT/.tools/helm/v3.16.3:$REPO_ROOT/.tools/cloud-provider-kind/v0.12.0:$PATH"
# what this tutorial needs from the environment (env_options in tutorial.yaml)
TUT_ENV_TYPES=llmisvc TUT_ENV_MODE=standard TUT_ENV_KEDA=false "$REPO_ROOT/envs/kind-kserve/v1/setup.sh"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
cd "$REPO_ROOT/tutorials/llmisvc-anatomy"
```

<!-- /tut -->

## 1단계 적용 전 상태 기록

먼저 현재 상태를 기록합니다. 이 시점에는 네임스페이스가 비어 있어야 합니다.

```bash run
echo "=== Before Apply ==="
kubectl get pods,svc,deploy,inferencepool,httproute -n "$NS" 2>/dev/null || true
```

## 2단계 LLMInferenceService 배포

YAML 파일 하나를 적용합니다. KServe가 기본으로 제공하는 설정이 자동으로 주입되므로
별도의 `LLMInferenceServiceConfig`를 작성할 필요가 없습니다.

<!-- tut:define llmisvc-demo-model -->

```bash run
kubectl apply -f manifests/llmisvc-cpu.yaml -n "$NS"
```

<!-- /tut -->

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

이 YAML의 주요 필드입니다.

| 필드 | 값 | 설명 |
|-------|-------|-------------|
| `model.uri` | `hf://facebook/opt-125m` | Hugging Face에서 모델을 자동으로 다운로드합니다. |
| `router.route: {}` | 필수 | 이 필드를 지정해야 HTTPRoute가 생성됩니다. |
| `securityContext.runAsUser` | `1000` | vLLM CPU 이미지를 루트 사용자로 빌드하므로 이 값을 지정해야 합니다. |
| `baseRefs` | 없음 | KServe가 기본으로 제공하는 설정을 자동으로 주입합니다. 자세한 내용은 아래에서 확인할 수 있습니다. |

### KServe가 기본으로 제공하는 LLMInferenceServiceConfig 자동 주입

KServe는 클러스터에 **KServe가 기본으로 제공하는 LLMInferenceServiceConfig**를 설치합니다.

| 설정 | 역할 |
|--------|------|
| `kserve-config-llm-template` | vLLM 컨테이너 템플릿(실행 명령, 상태 검사, 보안 설정) |
| `kserve-config-llm-scheduler` | EPP 스케줄러와 토크나이저 사이드카 |

LLMInferenceService를 생성하면 컨트롤러가 이 설정들을 자동으로 **병합합니다**.
`baseRefs`를 생략해도 실행 명령, 상태 검사, EPP 스케줄러 설정이 들어갑니다.
이 YAML에서 직접 재정의하는 필드는 `image`, `env`, `resources`뿐입니다.

## 3단계 리소스 생성 과정 확인

적용 직후 두 번째 터미널에서 리소스가 하나씩 생성되는 모습을 확인합니다.
관찰을 끝내려면 `Ctrl+C`를 누릅니다.

```bash skip
watch -n 1 "kubectl get pods,svc,deploy,lws,inferencepool,httproute -n $NS 2>/dev/null"
```

그런 다음 LLMInferenceService가 `Ready` 상태를 보고할 때까지 기다립니다.
모델을 다운로드하고 CPU에서 vLLM을 시작하는 데 몇 분 걸립니다.

```bash verify
kubectl wait --for=condition=Ready llminferenceservice/demo-model -n "$NS" --timeout=900s
```

## 리소스 구성도

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

## 4단계 리소스별 역할 확인

### 1. LeaderWorkerSet — 워크로드 관리

```bash run
kubectl get lws -n "$NS" -o wide
```

LWS는 P/D 분리, DP+EP 등 여러 노드에 걸친 배포에서 vLLM Pod를 관리합니다.
`parallelism` 없이 `replicas`만 지정한 단일 노드 배포에는 일반 Deployment를 사용합니다.
이 튜토리얼에서는 **LWS가 생성되지 않으므로** 위 명령을 실행하면 `No resources found`가 출력됩니다.

### 2. EPP 스케줄러 — 요청을 보낼 Pod 선택

```bash run
kubectl get deploy -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler
kubectl logs -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler --tail=20
```

EPP(엔드포인트 선택 플러그인)는 대기열에 쌓인 요청 수, KV 캐시 사용률 등의 지표를 보고
각 요청을 처리할 vLLM Pod를 선택합니다.

#### 스케줄러 Pod의 내부 구성

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

| 컨테이너 | 이미지 | 역할 |
|-----------|-------|------|
| `storage-initializer` (초기화) | `kserve/storage-initializer` | `STORAGE_ALLOW_PATTERNS`로 걸러낸 토크나이저 파일만 다운로드합니다. |
| `main` (스케줄러) | `llm-d/llm-d-inference-scheduler` | EPP 스케줄러입니다. ExtProc gRPC로 Envoy와 통신하고 점수를 계산한 뒤 Pod를 선택합니다. |
| `tokenizer` (사이드카) | `llm-d/llm-d-uds-tokenizer` | 기본 설정에서는 **대기 상태**입니다. `precise-prefix-cache-scorer`가 Unix 소켓으로 이 컨테이너를 사용합니다. |

스케줄러 Pod에는 위 컨테이너 3개만 있어야 합니다.

```bash verify
POD=$("$TUT_LIB/llmisvc/v1/scheduler-pod.sh" "$NS")
test "$(kubectl get pod -n "$NS" "$POD" -o jsonpath='{.spec.initContainers[*].name}')" = "storage-initializer"
test "$(kubectl get pod -n "$NS" "$POD" -o jsonpath='{.spec.containers[*].name}' | wc -w)" -eq 2
```

#### 스케줄링 플러그인(KServe가 기본으로 제공하는 설정에서 가져옴)

```bash run
kubectl describe pod -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler \
  | grep -A 15 "config-text" || true
```

기본 설정은 다음과 같습니다.

- `queue-scorer`(가중치 2)는 대기 중인 요청이 적은 Pod에 더 높은 점수를 줍니다.
- `prefix-cache-scorer`(가중치 3)는 vLLM 지표를 기준으로 접두사 캐시 적중률이 높은 Pod에 더 높은 점수를 줍니다.
- `max-score-picker`는 합산 점수가 가장 높은 Pod를 선택합니다.

#### 토크나이저 사이드카가 대기 상태인 이유

KServe가 기본으로 제공하는 설정인 `kserve-config-llm-scheduler`는 토크나이저를 항상 주입합니다.
기본 플러그인인 `prefix-cache-scorer`는 vLLM 지표만 읽습니다.
토크나이저는 `precise-prefix-cache-scorer`로 바꿨을 때만 사용합니다.

<details>
<summary>precise-prefix-cache-scorer에서 토크나이저를 사용하는 방식</summary>

`precise-prefix-cache-scorer`를 사용하면 토크나이저가 다음과 같이 동작합니다.

1. 토크나이저가 프롬프트를 토큰으로 나누고 블록 해시를 계산합니다.
2. vLLM이 ZMQ로 캐시 이벤트를 발행합니다.
3. 스케줄러가 블록 해시를 캐시 이벤트와 대조해 정확히 일치하는 Pod를 선택합니다.

| | `prefix-cache-scorer` (기본값) | `precise-prefix-cache-scorer` |
|---|---|---|
| 데이터 출처 | vLLM 지표(`prefix_cache_hit_rate`) | vLLM의 실시간 ZMQ 이벤트 스트림 |
| 방식 | vLLM이 보고한 적중률을 사용합니다. | 스케줄러가 토큰화하고 블록 해시를 계산한 뒤 정확히 일치하는 항목을 찾습니다. |
| 토크나이저 | **사용하지 않습니다.** 주입 후 대기 상태로 있습니다. | **사용합니다.** Unix 도메인 소켓으로 통신합니다. |
| 추가 vLLM 설정 | 없음 | `--enable-kvcache`, `--block-size`, ZMQ 이벤트 발행 |

토크나이저와 스케줄러는 같은 Pod 안의 **Unix 도메인 소켓**
(`/tmp/tokenizer/tokenizer-uds.socket`)으로 통신하므로 커널 네트워크 스택을 거치지 않습니다.

```bash skip
kubectl exec -n "$NS" "$("$TUT_LIB/llmisvc/v1/scheduler-pod.sh" "$NS")" -c main -- ls -la /tmp/tokenizer/
```

[정밀 접두사 KV 캐시 라우팅 설정 예시](https://github.com/kserve/kserve/tree/master/docs/samples/llmisvc/precise-prefix-kv-cache-routing)
</details>

### 3. InferencePool — 스케줄러와 워크로드 연결

```bash run
kubectl get inferencepool -n "$NS" -o yaml
```

InferencePool은 Gateway API Inference Extension이 제공하는 CRD입니다.
스케줄러는 InferencePool로 워크로드 Pod를 찾고 해당 Pod로 요청을 보낼 수 있습니다.

### 4. HTTPRoute — Gateway에서 받은 트래픽 전달

```bash run
kubectl get httproute -n "$NS" -o yaml
```

HTTPRoute는 Gateway가 받은 요청을 InferencePool로 전달합니다. 요청은 거기서 스케줄러로 이어집니다.

### 5. Service — 내부 연결

```bash run
kubectl get svc -n "$NS"
```

| Service | 용도 | 포트 |
|---------|---------|-------|
| `*-workload-svc` | vLLM Pod에 이름을 부여합니다. 추론 요청에는 사용하지 않습니다(아래 설명 참조). | 8000 (HTTPS) |
| `*-epp-service` | EPP 스케줄러를 노출합니다. | 9002 (gRPC), 9003 (상태 확인), 9090 (지표), 5557 (ZMQ) |

> 지표 포트(9090)는 일반 HTTP를 사용하며 베어러 토큰이 필요합니다
> (`metrics-endpoint-auth: true`). 지표를 읽는 방법은 이 시리즈의 요청 흐름 튜토리얼에서 다룹니다.

> **추론 요청은 `*-workload-svc`를 거치지 않습니다.**
> `/v1/completions`, `/v1/chat/completions`, `/v1/responses`에 대한 HTTPRoute의
> 백엔드는 InferencePool입니다. EPP가 Pod를 선택하면 Envoy가 해당 Pod의 IP에 직접 연결합니다.
> 워크로드 Service는 나머지 용도에 쓰입니다. HTTPRoute의 마지막 규칙은
> `/<namespace>/demo-model` 아래의 다른 경로를 이 Service로 보냅니다.
> 모니터링 시스템은 이 Service로 vLLM Pod를 찾고, 클러스터 내부 클라이언트는 이 Service 이름으로
> vLLM을 호출할 수 있습니다. 요청 흐름 튜토리얼에서 Envoy 로그에 찍힌 Pod IP를 확인할 수 있습니다.

## 5단계 결과 확인

```bash run
echo "--- Pods ---";          kubectl get pods -n "$NS" -o wide
echo "--- Services ---";      kubectl get svc -n "$NS"
echo "--- InferencePool ---"; kubectl get inferencepool -n "$NS"
echo "--- HTTPRoute ---";     kubectl get httproute -n "$NS"
echo "--- Secrets ---";       kubectl get secret -n "$NS"
```

적용 전에는 리소스가 없으며, 적용 후에는 다음과 같이 생성됩니다.

```text
Pods:          2 (vLLM x1 + scheduler x1)
Services:      2 (workload-svc + epp-service)
Deployments:   2 (workload + scheduler)
InferencePool: 1
HTTPRoute:     1
Secrets:       1+ (TLS certs)
```

아래 명령으로 같은 결과를 자동으로 확인합니다.

```bash verify
count() { kubectl get "$1" -n "$NS" --no-headers 2>/dev/null | wc -l; }
test "$(count deploy)" -eq 2
test "$(count svc)" -ge 2
test "$(count inferencepool)" -eq 1
test "$(count httproute)" -eq 1
```

## 6단계 요청 보내기

LLMInferenceService가 `Ready` 상태가 되면 Gateway로 텍스트 완성 요청을 보냅니다.
Kind에서는 작업자 노드의 NodePort로 Gateway에 접속합니다. 공용 모듈 `llmisvc/v1`이 URL을 구합니다.

```bash run
GATEWAY_URL=$("$TUT_LIB/llmisvc/v1/gateway-url.sh" "$NS" demo-model)
echo "$GATEWAY_URL"
```

```bash verify retry=10 delay=15
"$TUT_LIB/llmisvc/v1/completion.sh" "$GATEWAY_URL" facebook/opt-125m "Kubernetes is"
```

> **응답 내용으로 판단하지 마세요.** `facebook/opt-125m`은 매개변수가 1억 2,500만 개인
> 소형 *기본* 모델입니다. 전체 튜토리얼을 CPU에서 몇 분 안에 실행할 수 있도록 이 모델을 골랐습니다.
> 이 모델은 지시를 따르지 않고 입력 텍스트의 뒷부분을 이어 씁니다. 어색한 문장을 생성하는 경우가 많고
> 토큰 20개를 생성하면 멈춥니다(`"finish_reason": "length"`). 이 단계에서는 요청이 Gateway와
> 스케줄러를 거쳐 vLLM에 도달하고 응답 텍스트가 돌아오는지 확인합니다.
> `temperature`가 0이므로 실행할 때마다 같은 응답이 나옵니다.

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
```

<!-- /tut -->

</details>

## 정리

LLMInferenceService를 삭제하면 OwnerReference에 따른 연쇄 삭제로 컨트롤러가 생성한
Deployment, Service, InferencePool, HTTPRoute 등의 리소스가 모두 삭제됩니다.

```bash cleanup
kubectl delete llminferenceservice demo-model -n "$NS" --ignore-not-found --wait=true
kubectl delete namespace "$NS" --ignore-not-found
```

이 환경의 튜토리얼은 Kind 클러스터를 함께 사용합니다. 사용을 모두 마치면 환경의 `teardown.sh`로
클러스터를 삭제합니다.

## 배운 내용

- LLMInferenceService YAML 파일 하나를 적용하면 리소스가 10개 이상 생성됩니다.
- **KServe가 기본으로 제공하는 LLMInferenceServiceConfig**를 자동으로 주입하므로 별도로 설정을 작성할 필요가 없습니다.
- 스케줄러 Pod에는 컨테이너가 3개 있습니다. 초기화 컨테이너가 토크나이저 파일을 다운로드하고, 스케줄러와 토크나이저가 실행됩니다. 토크나이저는 기본 설정에서 대기 상태입니다.
- 핵심 연결 구조는 **Deployment(워크로드)** ↔ **InferencePool** ↔ **스케줄러** ↔ **HTTPRoute** ↔ **Gateway**입니다.
- 리소스를 정리할 때는 OwnerReference를 따라 연쇄 삭제가 이뤄집니다.
