# My tutorial

<!-- tut:header -->

<!-- Generated from tutorial.yaml by `./tut sync` — do not edit by hand. -->
> **Status:** 🚧 draft · **Tested with KServe:** v0.18.0 · **Environment:** [`kind-llmisvc/v1`](../../envs/kind-llmisvc/v1/) · **GPU:** not required
>
> 🌐 [한국어](README.ko.md)

<!-- /tut -->

One paragraph: what the reader builds and why it matters.

> **Key question:** the one question this tutorial answers.

## Step 0: Environment

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

## Step 1: Do something

Every shell block has a role: `run` (executed), `verify` (executed, must pass),
`cleanup` (always executed at the end) or `skip` (shown only).

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

## Step 2: Check it worked

```bash verify
test "$(kubectl get configmap example -n "$NS" -o jsonpath='{.data.hello}')" = "world"
```

Use `retry=N delay=S` for things that become true eventually:

```bash verify retry=5 delay=5
kubectl get configmap example -n "$NS"
```

## Cleanup

```bash cleanup
kubectl delete namespace "$NS" --ignore-not-found
```
