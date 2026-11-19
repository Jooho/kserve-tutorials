# Source this file (bash) to load <repo>/.tut.env: personal settings that are
# not in git, e.g. KIND_CLUSTER_NAME=tut. Values already set in the shell win.
# Used by ./tut and by every tutorial's generated setup step, so the UI, the
# runner and someone pasting README commands all see the same settings.
# Write it with: make config CLUSTER=tut   (or ./tut config KEY=VALUE)
__tut_cfg="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.tut.env"
TUT_CONFIG_LOADED=""
if [ -f "$__tut_cfg" ]; then
  while IFS='=' read -r __tut_k __tut_v || [ -n "$__tut_k" ]; do
    __tut_k="${__tut_k//[[:space:]]/}"
    __tut_v="${__tut_v#"${__tut_v%%[![:space:]]*}"}"   # trim leading spaces
    __tut_v="${__tut_v%"${__tut_v##*[![:space:]]}"}"   # trim trailing spaces
    case "$__tut_k" in ''|\#*) continue ;; esac
    [[ "$__tut_k" =~ ^[A-Z_][A-Z0-9_]*$ ]] || continue
    if [ -z "${!__tut_k+x}" ]; then
      export "$__tut_k=$__tut_v"
      TUT_CONFIG_LOADED="$TUT_CONFIG_LOADED $__tut_k"
    fi
  done < "$__tut_cfg"
fi
export TUT_CONFIG_LOADED
unset __tut_cfg __tut_k __tut_v
