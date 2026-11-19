#!/usr/bin/env bash
# Usage: install-tools.sh <tools.env>
#
# Install the CLI tools a tutorial environment needs, as listed in its
# tools.env (KIND=v0.30.0, KUBECTL=..., HELM=..., CLOUD_PROVIDER_KIND=...),
# into <repo>/.tools/<tool>/<version>/. Every download is verified against its
# published SHA256. Idempotent. Nothing outside the repository is touched and
# no shell configuration changes; the tutorial's setup step puts these
# directories first on PATH for that shell only.
#
# Docker is NOT installed here: it is a prerequisite the user installs
# (./tut doctor checks it).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="${TUT_TOOLS_DIR:-$ROOT/.tools}"
ENVFILE="${1:?usage: install-tools.sh <envs/.../tools.env>}"
KIND="" KUBECTL="" HELM="" CLOUD_PROVIDER_KIND=""
# shellcheck source=/dev/null
source "$ENVFILE"

case "$(uname -s)" in
  Linux) OS=linux ;;
  Darwin) OS=darwin ;;
  *) echo "unsupported OS $(uname -s): use Linux, macOS or WSL2" >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64|amd64) ARCH=amd64 ;;
  arm64|aarch64) ARCH=arm64 ;;
  *) echo "unsupported architecture $(uname -m)" >&2; exit 1 ;;
esac

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
log() { printf '  %-22s %s\n' "$1" "$2"; }
fetch() {
  curl -fsSL --retry 3 --retry-delay 2 -o "$2" "$1" \
    || { echo "download failed: $1 (proxy or firewall? see ./tut doctor)" >&2; exit 1; }
}
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | awk '{print $1}'; }
verify() {  # file expected-hash
  local got; got="$(sha256 "$1")"
  [[ "$got" == "$2" ]] || { echo "checksum mismatch for $(basename "$1"): $got != $2" >&2; exit 1; }
}
# TUT_SKIP_TOOLS="helm kubectl": provide these yourself (doctor checks the versions)
want() {  # name version -> success when the tool must be installed
  [[ -n "$2" ]] || return 1                       # not needed by this environment
  if [[ " ${TUT_SKIP_TOOLS:-} " == *" $1 "* ]]; then log "$1" "skipped (TUT_SKIP_TOOLS)"; return 1; fi
  BIN="$TOOLS/$1/$2"
  if [[ -x "$BIN/$1" ]]; then log "$1" "$2 ok"; return 1; fi
  mkdir -p "$BIN"
  return 0
}
done_() { log "$1" "$2 installed"; }

ENVDIR="$(cd "$(dirname "$ENVFILE")" && pwd)"
echo "Tools for env ${ENVDIR#"$ROOT"/envs/} -> ${TOOLS#"$ROOT"/}/ ($OS/$ARCH)"

# kind
if want kind "$KIND"; then
  u="https://github.com/kubernetes-sigs/kind/releases/download/$KIND/kind-$OS-$ARCH"
  fetch "$u" "$TMP/kind"; fetch "$u.sha256sum" "$TMP/kind.sha"
  verify "$TMP/kind" "$(awk '{print $1}' "$TMP/kind.sha")"
  install -m 0755 "$TMP/kind" "$BIN/kind"; done_ kind "$KIND"
fi

# kubectl
if want kubectl "$KUBECTL"; then
  u="https://dl.k8s.io/release/$KUBECTL/bin/$OS/$ARCH/kubectl"
  fetch "$u" "$TMP/kubectl"; fetch "$u.sha256" "$TMP/kubectl.sha"
  verify "$TMP/kubectl" "$(awk '{print $1}' "$TMP/kubectl.sha")"
  install -m 0755 "$TMP/kubectl" "$BIN/kubectl"; done_ kubectl "$KUBECTL"
fi

# helm
if want helm "$HELM"; then
  f="helm-$HELM-$OS-$ARCH.tar.gz"
  fetch "https://get.helm.sh/$f" "$TMP/$f"; fetch "https://get.helm.sh/$f.sha256sum" "$TMP/helm.sha"
  verify "$TMP/$f" "$(awk '{print $1}' "$TMP/helm.sha")"
  tar -xzf "$TMP/$f" -C "$TMP" "$OS-$ARCH/helm"
  install -m 0755 "$TMP/$OS-$ARCH/helm" "$BIN/helm"; done_ helm "$HELM"
fi

# cloud-provider-kind (gives LoadBalancer services an address, like a cloud)
if want cloud-provider-kind "$CLOUD_PROVIDER_KIND"; then
  v="${CLOUD_PROVIDER_KIND#v}"
  base="https://github.com/kubernetes-sigs/cloud-provider-kind/releases/download/$CLOUD_PROVIDER_KIND"
  f="cloud-provider-kind_${v}_${OS}_${ARCH}.tar.gz"
  fetch "$base/$f" "$TMP/$f"; fetch "$base/cloud-provider-kind_${v}_checksums.txt" "$TMP/cpk.sha"
  verify "$TMP/$f" "$(awk -v f="$f" '$2==f {print $1}' "$TMP/cpk.sha")"
  tar -xzf "$TMP/$f" -C "$TMP" cloud-provider-kind
  install -m 0755 "$TMP/cloud-provider-kind" "$BIN/cloud-provider-kind"
  done_ cloud-provider-kind "$CLOUD_PROVIDER_KIND"
fi
