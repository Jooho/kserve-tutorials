# PoC 3 — Scale the model

<!-- tut:header -->

<!-- Generated from tutorial.yaml by `./tut sync` — do not edit by hand. -->
> **Status:** 🚧 draft · **Tested with KServe:** v0.18.0, v0.17.0 · **Environment:** — · **GPU:** not required

<!-- /tut -->

Proof of concept for **shared steps**. Scaling needs a deployed, configured
model: this tutorial **uses** `poc-model` (PoC 1) and `poc-config` (PoC 2).

- **Standalone** (search, All, CI): every step below runs.
- **In the learning path** "PoC: shared steps": PoC 1 and 2 already did them, so
  their `run` steps are hidden and only their `verify` steps run.

## Step 0: Environment

<!-- tut:setup -->

```bash run
# Generated from tutorial.yaml by `./tut sync` — do not edit by hand.
export KSERVE_VERSION="${KSERVE_VERSION:-v0.18.0}"
export NS="${NS:-poc-shared-3-scale}"
export REPO_ROOT="$(git rev-parse --show-toplevel)"
source "$REPO_ROOT/tools/local-config.sh"   # your settings in .tut.env, if any
export TUT_LIB="$REPO_ROOT/lib"
cd "$REPO_ROOT/tutorials/poc-shared-3-scale"
```

<!-- /tut -->

## Step 1: Prerequisites

<!-- tut:use poc-model -->

<!-- Copied from poc-shared-1-deploy (tut:define poc-model) by `./tut sync` — do not edit by hand. -->

```bash run
POC_HOME="${POC_HOME:-${TMPDIR:-/tmp}/tut-poc}"
mkdir -p "$POC_HOME/$NS"
echo "${MODEL:-tiny-llm}" > "$POC_HOME/$NS/model"
echo "deployed model '${MODEL:-tiny-llm}' in $NS"
```

```bash verify
POC_HOME="${POC_HOME:-${TMPDIR:-/tmp}/tut-poc}"
test -s "$POC_HOME/$NS/model"
echo "model ready in $NS: $(cat "$POC_HOME/$NS/model")"
```

<!-- /tut -->

<!-- tut:use poc-config -->

<!-- Copied from poc-shared-2-config (tut:define poc-config) by `./tut sync` — do not edit by hand. -->

```bash run
POC_HOME="${POC_HOME:-${TMPDIR:-/tmp}/tut-poc}"
echo "max_tokens=128" > "$POC_HOME/$NS/config"
```

```bash verify
POC_HOME="${POC_HOME:-${TMPDIR:-/tmp}/tut-poc}"
grep -qx "max_tokens=128" "$POC_HOME/$NS/config"
echo "config ready in $NS"
```

<!-- /tut -->

## Step 2: Scale to 3 replicas

```bash run
POC_HOME="${POC_HOME:-${TMPDIR:-/tmp}/tut-poc}"
echo 3 > "$POC_HOME/$NS/replicas"
```

```bash verify
POC_HOME="${POC_HOME:-${TMPDIR:-/tmp}/tut-poc}"
test "$(cat "$POC_HOME/$NS/replicas")" = 3
echo "$(cat "$POC_HOME/$NS/model") runs with 3 replicas in $NS"
```

## Cleanup

```bash cleanup
POC_HOME="${POC_HOME:-${TMPDIR:-/tmp}/tut-poc}"
rm -f "$POC_HOME/$NS/model" "$POC_HOME/$NS/config" "$POC_HOME/$NS/replicas"
rmdir "$POC_HOME/$NS" 2>/dev/null || true   # only if nothing else is left
```
