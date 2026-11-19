# PoC 1 — Deploy a (fake) model

<!-- tut:header -->

<!-- Generated from tutorial.yaml by `./tut sync` — do not edit by hand. -->
> **Status:** 🚧 draft · **Tested with KServe:** v0.18.0 · **Environment:** — · **GPU:** not required

<!-- /tut -->

Proof of concept for **shared steps**. Nothing here needs a cluster: "deploying
a model" writes a file under `${TMPDIR:-/tmp}/tut-poc/$NS`.

This tutorial **defines** the shared step `poc-model`. PoC 2 and PoC 3 reuse it
with one line (`<!-- tut:use poc-model -->`).

## Step 0: Environment

<!-- tut:setup -->

```bash run
# Generated from tutorial.yaml by `./tut sync` — do not edit by hand.
export KSERVE_VERSION="${KSERVE_VERSION:-v0.18.0}"
export NS="${NS:-poc-shared-1-deploy}"
export REPO_ROOT="$(git rev-parse --show-toplevel)"
source "$REPO_ROOT/tools/local-config.sh"   # your settings in .tut.env, if any
export TUT_LIB="$REPO_ROOT/lib"
cd "$REPO_ROOT/tutorials/poc-shared-1-deploy"
```

<!-- /tut -->

## Step 1: Deploy the model

<!-- tut:define poc-model -->

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

## Cleanup

```bash cleanup
POC_HOME="${POC_HOME:-${TMPDIR:-/tmp}/tut-poc}"
rm -f "$POC_HOME/$NS/model"
rmdir "$POC_HOME/$NS" 2>/dev/null || true   # only if nothing else is left
```
