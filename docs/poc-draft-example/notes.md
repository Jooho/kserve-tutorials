# Draft notes: inferencegraph-ensemble

`./tut _draftcheck inferencegraph-ensemble` → **0 error(s), 0 warning(s)**, dry run: 27 steps.
Nothing has been run against a cluster.

## What I built

`tutorials/inferencegraph-ensemble/` follows `docs/TUTORIAL.md` (the two-stage
story: Ensemble only, then Sequence + Combiner), with the steps of
`scripts/1.prepare.sh`, `scripts/2.deploy.sh`, `upload_models.sh`,
`test_inferencegraph.sh` and `cleanup.sh` inlined:

| Step | What | From |
|---|---|---|
| 0 | generated setup (`KSERVE_VERSION`, `NS=kserve-graph-demo`, `cd`) | — |
| 1 | Kind cluster, StorageClass check, ingress-nginx | 1-1.setup_kind_cluster.sh |
| 2 | KServe quick install + ingress config patch + controller restart | 1-2.install_kserve.sh |
| 3 | namespace | 2.deploy.sh |
| 4 | train both models (in a venv) | 1-3.train_models.sh, train.py |
| 5 | build + `kind load` the combiner, pull + `kind load` MLServer | 1-4.build_combiner.sh, 1.prepare.sh |
| 6 | PVC, helper Pod, `kubectl cp` models, delete helper | 2.deploy.sh, upload_models.sh |
| 7 | three InferenceServices | 2.deploy.sh |
| 8 | Ensemble-only graph + Ingress + port-forward + request | TUTORIAL.md §3, 2.deploy.sh, test_inferencegraph.sh |
| 9 | Sequence + Combiner graph + request | TUTORIAL.md §4 |
| Cleanup | graph, Ingress, ISVCs, PVC, namespace, port-forward | cleanup.sh |

Files:

- `manifests/` — the author's YAML unchanged except where listed below, plus
  `kind-cluster.yaml` (was a heredoc in 1-1), `model-upload-helper.yaml` (was a
  heredoc in upload_models.sh) and `inferencegraph/ensemble-only.yaml` (was a
  heredoc in TUTORIAL.md §3.2). Subfolders mirror the input's `k8s/` layout so
  `kubectl delete -f manifests/inferenceservices/` still works.
- `combiner/` (app.py, Dockerfile, requirements.txt), `scripts/train.py`,
  `requirements.txt`, `data/inference_request.json` — copied unchanged.
- `images/architecture.svg`, `images/inferencegraph.svg` — copied unchanged.
- `.gitignore` — ignores `models/` and `data/sample_data.json`, which
  `train.py` writes into the tutorial directory when it runs.
- `tutorial.yaml` — title, summary, tags `[inferencegraph, inferenceservice,
  mlserver, storage, ensemble, intermediate]`, `kserve: v0.17.0` (default and
  tested: the version the author's script installed), `requires: {gpu: false,
  cpu: 4, memory: 8Gi}`, `timeout_minutes: 60`, `status: draft`, `langs: [en]`,
  owners kept from the scaffold (`your-github-handle`). **No `env:`** (see below).

## Env, helpers, shared steps

- **No env fits.** The only profile, `kind-llmisvc/v1`, installs KServe with
  `--type llmisvc` (LLMInferenceService + Envoy Gateway). This tutorial needs the
  InferenceService and InferenceGraph controllers, the `kserve-mlserver`
  ClusterServingRuntime and ingress-nginx, none of which that profile provides.
  Installing them on top of the shared env cluster would change a cluster that
  other tutorials share. So cluster creation and the KServe install stay as
  tutorial steps (Steps 1–2), on a **separate Kind cluster named
  `inferencegraph-ensemble`**, and tutorial.yaml has no `env:`.
- Helper scripts (`llmisvc/v1`): not used; they are for LLMInferenceService
  gateways.
- Shared steps (`poc-config`, `poc-model`): not relevant.

## Input commands I changed (and why)

Global:

- `${NAMESPACE}` / `NAMESPACE=kserve-graph-demo` → `"$NS"` (repo convention; the
  generated setup sets `NS` from `namespace:` in tutorial.yaml, which I set to
  `kserve-graph-demo`, so the value is the same).
- `k8s/...` paths → `manifests/...`.
- All color codes, banners, `print_*` functions, `echo` progress lines and
  "next steps" text removed.

1-1.setup_kind_cluster.sh:

- Docker / kubectl / kind checks and the `sudo mv` installs of kubectl and kind:
  **left out** (rule 10: install nothing system-wide; tools belong to an env).
  The README lists Docker, kind, kubectl, curl, python3 as prerequisites instead.
- Interactive "delete and recreate? (y/N)" prompt: replaced with
  `kind get clusters | grep -qx "$CLUSTER_NAME" || kind create cluster ...`
  (non-interactive, safe to run twice) plus `kubectl config use-context`.
- `CLUSTER_NAME` default `kind` → `inferencegraph-ensemble`, so the tutorial
  never reuses (and installs KServe into) a cluster created by the
  `kind-llmisvc/v1` env, whose default name is also `kind` (hard rule 1).
- `cat <<EOF > /tmp/kind-cluster-config.yaml` + `kind create cluster --config
  /tmp/...` → `manifests/kind-cluster.yaml` + `kind create cluster --name
  "$CLUSTER_NAME" --config manifests/kind-cluster.yaml` (YAML in manifests/;
  `name:` dropped from the file because `--name` sets it).
- `kubectl label node kind-${CLUSTER_NAME}-control-plane ...` →
  `${CLUSTER_NAME}-control-plane`. The original node name was wrong (Kind names
  nodes `<cluster>-control-plane`); the error was hidden by `|| true`, and the
  label is already set by the kubeadm patch, so this is cosmetic.
- `sleep 5` before `kubectl wait ... pod`: replaced with
  `kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller
  --timeout=300s` (wait, don't sleep; `kubectl wait` on Pods can fail with "no
  matching resources" right after apply). The author's `kubectl wait ... pod`
  is kept unchanged as a `verify` block.
- Final `kubectl get nodes` / `kubectl get storageclass` listing: kept
  `kubectl get storageclass`; node readiness is covered by the existing
  `kubectl wait --for=condition=Ready nodes --all`.

1-2.install_kserve.sh:

- `install/v0.17.0/...` and "Installing KServe v0.17.0" → `install/${KSERVE_VERSION}/...`
  (rule 5). The early `exit 0` when the CRD exists became an `if ! ...; then ... fi`.
- The URL still points to `refs/heads/master` as tested (see TODO).

1-3.train_models.sh:

- `pip install -r requirements.txt` (into whatever Python is active) → inside a
  venv at `${TUT_CACHE:-~/.cache/kserve-tutorials}/venv-inferencegraph-ensemble`,
  activated in a subshell (rule 10). The commands `pip install -r
  requirements.txt` and `python3 scripts/train.py` are otherwise unchanged; the
  "skip if models exist" guard is kept.

1-4.build_combiner.sh / 1.prepare.sh:

- `COMBINER_IMAGE` default `ensemble-combiner:latest` → `ensemble-combiner:v1`,
  and the same tag in `manifests/inferenceservices/ensemble-combiner.yaml`
  (lint M001: images must be pinned, no `latest`).
- `docker pull ${MLSERVER_IMAGE} &` + `wait ${PULL_PID}` (background pre-pull) →
  a plain `docker pull` followed by `kind load` (no background jobs in steps).

2.deploy.sh:

- `kubectl get pvc/model-pvc -n ... || true` → kept without `|| true`; the
  "PVC may stay Pending" note moved to the prose; `sleep 2` dropped.
- `./scripts/upload_models.sh` → inlined (Step 6).
- The ISVC wait loop with `|| echo "Warning: ... not ready yet"` (which hid
  failures) → one `verify` block: `kubectl wait --for=condition=Ready isvc/...
  (all three) --timeout=600s` (300s → 600s for a CPU-only CI runner with cold
  image pulls).
- Deploys `ensemble-only.yaml` first (TUTORIAL.md §3) before the final
  `housing-price-graph.yaml`, and the Ingress together with the first graph.

upload_models.sh:

- Heredoc Pod → `manifests/model-upload-helper.yaml`; `image: busybox` →
  `busybox:1.36` (M001).
- `kubectl wait ... --timeout=60s` → `--timeout=180s` (CI cold pull of busybox
  plus first-use PVC provisioning).
- `kubectl exec ... ls -R /mnt/models/` kept, plus a `verify` that every model
  file exists on the volume.
- `kubectl delete pod model-upload-helper ... --force --grace-period=0` → added
  `--ignore-not-found` (D012, safe to run twice).
- "models directory not found" guard dropped (the previous step's verify covers it).

test_inferencegraph.sh:

- `lsof` check for an existing port-forward → `pkill -f "[p]ort-forward -n
  ingress-nginx svc/ingress-nginx-controller 8080:80" || true` before starting
  a new one (safe to run twice; the `[p]` keeps pkill from matching the
  runner's own shell). `kubectl port-forward ... 8080:80 > /dev/null 2>&1 &`
  kept as is. The `for i in {1..10}; ... sleep 1` readiness loop → the request
  is a `verify retry=12 delay=5`.
- The feature table (`jq` + `printf`, with Korean labels) and the `bc` price
  conversion: **left out** (decoration; `jq` and `bc` are not provided by any
  environment).
- `curl -s ... | jq '.'` and the `grep -q "error"` check → `curl -sf ... -o
  <tmp file>` + `python3` that prints the JSON and asserts on it (no `jq`
  dependency; `-f` makes HTTP errors fail the check).
- New checks that prove the prose: the Ensemble response has entries from
  both `xgboost-predictor` and `lightgbm-predictor`; the Sequence response comes
  from `ensemble-combiner` and equals the average of the two Ensemble values
  (± 1e-4).

TUTORIAL.md:

- `kubectl rollout status deployment/housing-price-graph ... --timeout=60s` →
  `--timeout=300s` (first rollout pulls the router image), preceded by
  `kubectl wait --for=condition=Ready ig/housing-price-graph`.
- `cat > /tmp/ensemble-only.yaml <<EOF ... ` → `manifests/inferencegraph/ensemble-only.yaml`.

cleanup.sh:

- `kubectl delete -f k8s/...` kept (paths changed). **Added**: delete the
  Ingress (the input's cleanup left it behind), stop the port-forward, delete
  the namespace, remove the two temp response files. The Kind cluster is not
  deleted by cleanup (repo rule D007: cleanup never deletes the cluster); a
  `skip` block shows `kind delete cluster`.

Left out entirely: README_KO.md, docs/*_KO.md and the `_ko` images (the
tutorial is `langs: [en]`; translate later with `./tut translation draft`),
docs/BLOG*.md, images/combiner.svg (app.py is included instead),
data/sample_data.json and models/* (regenerated by `train.py`).

## TODOs for the author

1. **Run it**: `./tut run inferencegraph-ensemble --twice`. None of the steps
   has been executed in this form, in particular: the venv training, the
   `verify` assertions on the responses, `kubectl wait ig ... Ready` (I assumed
   InferenceGraph reports a `Ready` condition in raw mode) and the second pass
   (re-applying `ensemble-only.yaml` over the Sequence graph; the request check
   retries until the new router answers).
2. **Missing env.** This tutorial needs an environment profile such as
   `envs/kind-isvc/v1`: a Kind cluster + ingress-nginx + KServe standard mode
   (InferenceService/InferenceGraph controllers, `kserve-mlserver`), with the
   CLI tools pinned in `tools.env`. Until it exists, `kind`/`kubectl` come from
   the reader's PATH (not pinned), the downloads (KServe installer,
   ingress-nginx manifest, MLServer image) are not retried (CI-002), and CI has
   no teardown for the cluster. Once the env exists, set `env:` and drop
   Steps 1–2 (and the `CLUSTER_NAME` lines). Suggest adding this to
   docs/backlog.md (I may not edit it in this run).
3. **KServe version.** `kserve: v0.17.0` is what the author's script installed.
   The installer URL is
   `raw.githubusercontent.com/kserve/kserve/refs/heads/master/install/${KSERVE_VERSION}/kserve-standard-mode-full-install-with-manifests.sh`
   — taken from **master**, as tested. Check whether the same file exists at
   the tag (`refs/tags/${KSERVE_VERSION}`) and pin to it; check whether the
   script needs `helm` or other tools; and test v0.18.0 to add it to `tested`.
4. **MLServer image.** `docker.io/seldonio/mlserver:1.5.0` is preloaded as in
   the input; confirm it is the image `kserve-mlserver` uses in the KServe
   version you test (`kubectl get clusterservingruntime kserve-mlserver -o
   jsonpath='{.spec.containers[0].image}'`); if not, the preload is wasted.
5. **Namespace is fixed.** The manifests carry `namespace: kserve-graph-demo`
   and the combiner `serviceUrl` contains
   `ensemble-combiner-predictor.kserve-graph-demo.svc.cluster.local`, so
   overriding `NS` breaks the tutorial. Consider dropping `namespace:` from the
   manifests (apply with `-n "$NS"`) and using a namespace-relative
   `serviceUrl` — needs testing.
6. **Host ports 80/443** are mapped by `kind-cluster.yaml` (as tested) but the
   tutorial only uses the port-forward. If another Kind cluster or a local web
   server holds port 80, cluster creation fails. Consider dropping the mapping.
   Port 8080 for the port-forward must also be free.
7. **Unpinned dependencies**: the combiner Dockerfile installs `fastapi uvicorn`
   without versions and `requirements.txt` uses `>=` ranges (only
   `xgboost==3.2.0` is pinned). `train.py` downloads the dataset from the
   internet with no retry.
8. `requires` (`cpu: 4, memory: 8Gi`) and `timeout_minutes: 60` are estimates.
9. Scaffold leftover: `tutorials/inferencegraph-ensemble/manifests/example.yaml`
   is unused; delete it (I could only run `_draftcheck`, not `rm`).
10. Owners still `your-github-handle` (kept from the scaffold as instructed);
    set the real handle.
11. Tags: I picked `intermediate` (it assumes the reader knows what an
    InferenceService is); change to `beginner` if you disagree.
