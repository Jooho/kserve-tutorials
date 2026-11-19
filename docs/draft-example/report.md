# Draft report: inferencegraph-ensemble

- input: `/home/user/jooho/kserve-tutorials/inferencegraph-ensemble` (copied to `build/draft/inferencegraph-ensemble/input`, original unchanged)
- AI exit code: 0 (log: `build/draft/inferencegraph-ensemble/agent.log`)
- AI notes: `build/draft/inferencegraph-ensemble/notes.md`
- lint: 0 error(s), 0 warning(s)
- input script commands in the tutorial (variable names may differ): 39/59 (control flow, prompts, echo and tool checks are not counted)
- images / binary files copied in: 2 used, 1 unused removed (manifests/example.yaml (template))
- files changed outside tutorials/inferencegraph-ensemble/ and build/: 0

## Input commands not in the tutorial

Changed or left out on purpose? The AI notes should say why; otherwise add them.

- `scripts/1-1.setup_kind_cluster.sh:73` `curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl"`
- `scripts/1-1.setup_kind_cluster.sh:74` `chmod +x kubectl`
- `scripts/1-1.setup_kind_cluster.sh:75` `sudo mv kubectl /usr/local/bin/`
- `scripts/1-1.setup_kind_cluster.sh:101` `curl -Lo ./kind "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-${OS}-${ARCH}"`
- `scripts/1-1.setup_kind_cluster.sh:102` `chmod +x ./kind`
- `scripts/1-1.setup_kind_cluster.sh:103` `sudo mv ./kind /usr/local/bin/kind`
- `scripts/1-1.setup_kind_cluster.sh:136` `cat <<EOF > /tmp/kind-cluster-config.yaml`
- `scripts/1-1.setup_kind_cluster.sh:157` `kind create cluster --config /tmp/kind-cluster-config.yaml`
- `scripts/1-1.setup_kind_cluster.sh:183` `kubectl label node kind-${CLUSTER_NAME}-control-plane ingress-ready=true --overwrite 2>/dev/null || true`
- `scripts/1-1.setup_kind_cluster.sh:191` `sleep 5`
- `scripts/1-1.setup_kind_cluster.sh:209` `kubectl get nodes`
- `scripts/1-2.install_kserve.sh:15` `curl -s "https://raw.githubusercontent.com/kserve/kserve/refs/heads/master/install/v0.17.0/kserve-standard-mode-full-install-with-manifests.`
- `scripts/1.prepare.sh:23` `docker pull ${MLSERVER_IMAGE} &`
- `scripts/2.deploy.sh:24` `kubectl get pvc/model-pvc -n ${NAMESPACE} || true`
- `scripts/2.deploy.sh:26` `sleep 2`
- `scripts/2.deploy.sh:44` `kubectl wait --for=condition=Ready isvc/${isvc} -n ${NAMESPACE} --timeout=300s || echo "Warning: ${isvc} not ready yet"`
- `scripts/test_inferencegraph.sh:35` `kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller ${LOCAL_PORT}:80 > /dev/null 2>&1 &`
- `scripts/test_inferencegraph.sh:45` `sleep 1`
- `scripts/upload_models.sh:22` `cat <<EOF | kubectl apply -f -`
- `scripts/upload_models.sh:44` `kubectl wait --for=condition=Ready pod/model-upload-helper -n ${NAMESPACE} --timeout=60s`

## Next

1. Read the AI notes and this report.
2. `./tut ui` → open **inferencegraph-ensemble** → ✎ Edit: fix what is listed, Save & sync.
3. Run all in the UI, then `./tut run inferencegraph-ensemble --twice`.
