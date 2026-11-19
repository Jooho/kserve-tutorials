#!/usr/bin/env bash
# Dump cluster state after a failed tutorial run (CI only; best effort).
# Usage: diagnose.sh [namespace...]   default: namespaces with an LLMInferenceService or InferenceService
set +e
# prefer the environments' pinned kubectl (.tools/kubectl/<version>/)
for d in "$(dirname "$0")"/../../.tools/kubectl/*/; do [ -x "$d/kubectl" ] && PATH="$d:$PATH"; done
section() { echo; echo "::group::$*"; }
end() { echo "::endgroup::"; }

kubectl cluster-info >/dev/null 2>&1 || { echo "no reachable cluster"; exit 0; }
namespaces=("$@")
if [ ${#namespaces[@]} -eq 0 ]; then
  mapfile -t namespaces < <( { kubectl get llminferenceservice -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\n"}{end}' 2>/dev/null
                              kubectl get inferenceservice -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\n"}{end}' 2>/dev/null; } | sort -u)
fi

section "nodes";            kubectl get nodes -o wide; kubectl describe nodes | grep -A8 -E "Allocated resources|Conditions:"; end
section "pods (all)";       kubectl get pods -A -o wide; end
section "events (warnings)"; kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp | tail -80; end
section "LLMInferenceServices"; kubectl get llminferenceservice -A -o yaml 2>/dev/null | head -400; end
for ns in "${namespaces[@]}" kserve; do
  section "namespace $ns: resources";  kubectl get all,inferencepool,httproute -n "$ns" -o wide 2>/dev/null; end
  section "namespace $ns: describe pods"; kubectl describe pods -n "$ns" | tail -300; end
  for p in $(kubectl get pods -n "$ns" -o name); do
    section "logs $ns/$p"
    kubectl logs -n "$ns" "$p" --all-containers --prefix --tail=150
    kubectl logs -n "$ns" "$p" --all-containers --prefix --tail=80 --previous 2>/dev/null
    end
  done
done
section "gateway"; kubectl get gateway,httproute -A -o wide 2>/dev/null; kubectl get pods,svc -n envoy-gateway-system -o wide; end
exit 0
