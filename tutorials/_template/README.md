# My tutorial

<!-- tut:header -->

<!-- Generated from tutorial.yaml by `./tut sync` — do not edit by hand. -->
> **Status:** 🚧 draft · **Tested with KServe:** v0.18.0 · **Environment:** [`kind-kserve/v1`](../../envs/kind-kserve/v1/) · **GPU:** not required
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
source "$REPO_ROOT/tools/local-config.sh"   # your settings in .tut.env, if any
export TUT_LIB="$REPO_ROOT/lib"
# pinned CLI tools of the environment, for this shell only
export PATH="$REPO_ROOT/.tools/kind/v0.30.0:$REPO_ROOT/.tools/kubectl/v1.34.13:$REPO_ROOT/.tools/helm/v3.16.3:$REPO_ROOT/.tools/cloud-provider-kind/v0.12.0:$PATH"
# what this tutorial needs from the environment (env_options in tutorial.yaml)
TUT_ENV_TYPES=kserve TUT_ENV_MODE=standard TUT_ENV_KEDA=false "$REPO_ROOT/envs/kind-kserve/v1/setup.sh"
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
