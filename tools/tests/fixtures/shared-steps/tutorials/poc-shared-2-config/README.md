# PoC 2 — Configure the model

<!-- tut:header -->

<!-- Generated from tutorial.yaml by `./tut sync` — do not edit by hand. -->
> **Status:** 🚧 draft · **Tested with KServe:** v0.18.0 · **Environment:** — · **GPU:** not required

<!-- /tut -->

Proof of concept for **shared steps**. This tutorial needs a deployed model, so
it **uses** `poc-model` (defined in PoC 1); `./tut sync` copies the steps here.
It also **defines** `poc-config` for PoC 3.

## Step 0: Environment

<!-- tut:setup -->

```bash run
# Generated from tutorial.yaml by `./tut sync` — do not edit by hand.
export KSERVE_VERSION="${KSERVE_VERSION:-v0.18.0}"
export NS="${NS:-poc-shared-2-config}"
export REPO_ROOT="$(git rev-parse --show-toplevel)"
source "$REPO_ROOT/tools/local-config.sh"   # your settings in .tut.env, if any
export TUT_LIB="$REPO_ROOT/lib"
cd "$REPO_ROOT/tutorials/poc-shared-2-config"
```

<!-- /tut -->

## Step 1: A deployed model

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

## Step 2: Configure it

<!-- tut:define poc-config -->

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

## Cleanup

```bash cleanup
POC_HOME="${POC_HOME:-${TMPDIR:-/tmp}/tut-poc}"
rm -f "$POC_HOME/$NS/model" "$POC_HOME/$NS/config"
rmdir "$POC_HOME/$NS" 2>/dev/null || true   # only if nothing else is left
```
