<!-- tut-translation source=README.md sha=4d9af683ccf4 -->
# 내 튜토리얼

<!-- tut:header -->

<!-- tutorial.yaml에서 `./tut sync`로 생성됨 — 직접 수정하지 마세요. -->
> **상태:** 🚧 작성 중 · **검증된 KServe:** v0.18.0 · **환경:** [`kind-llmisvc/v1`](../../envs/kind-llmisvc/v1/) · **GPU:** 불필요
>
> 🌐 [English](README.md)

<!-- /tut -->

한 문단: 무엇을 만들고 왜 중요한지.

> **핵심 질문:** 이 튜토리얼이 답하는 단 하나의 질문.

## Step 0: 환경 준비

<!-- tut:setup -->

```bash run
# Generated from tutorial.yaml by `./tut sync` — do not edit by hand.
export KSERVE_VERSION="${KSERVE_VERSION:-v0.18.0}"
export NS="${NS:-my-tutorial}"
export REPO_ROOT="$(git rev-parse --show-toplevel)"
"$REPO_ROOT/envs/kind-llmisvc/v1/setup.sh"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
cd "$REPO_ROOT/tutorials/_template"
```

<!-- /tut -->

## Step 1: 무언가 하기

모든 셸 블록에는 역할이 있습니다: `run`(실행), `verify`(실행, 반드시 성공),
`cleanup`(마지막에 항상 실행), `skip`(보여주기만).

```bash run
kubectl apply -f manifests/example.yaml -n "$NS"
```

<details>
<summary>manifests/example.yaml</summary>

<!-- tut:include manifests/example.yaml -->

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: example
data:
  hello: world
```

<!-- /tut -->

</details>

## Step 2: 동작 확인

```bash verify
test "$(kubectl get configmap example -n "$NS" -o jsonpath='{.data.hello}')" = "world"
```

시간이 지나야 참이 되는 조건에는 `retry=N delay=S`를 씁니다:

```bash verify retry=5 delay=5
kubectl get configmap example -n "$NS"
```

## 정리

```bash cleanup
kubectl delete namespace "$NS" --ignore-not-found
```
