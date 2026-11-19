# Interactive conveniences for the UI terminal only (sourced by the UI shell's
# rc file). Nothing here exists in CI or in `./tut run`, so tutorials must never
# rely on it — lint rule D013 rejects the aliases inside README blocks.
# Works with bash 3.2 (macOS /bin/bash): no `source <(...)`, no negative indexes.

alias k=kubectl
alias kc='kubectl config set-context --current --namespace'

# Tab completion. Use bash-completion when it is installed; otherwise define the
# one helper kubectl/helm/kind completion scripts need. Nothing is installed.
for __tut_bc in /usr/share/bash-completion/bash_completion \
                /opt/homebrew/etc/profile.d/bash_completion.sh \
                /usr/local/etc/profile.d/bash_completion.sh \
                /etc/bash_completion; do
  if [ -r "$__tut_bc" ]; then . "$__tut_bc" >/dev/null 2>&1; break; fi
done
unset __tut_bc
if ! declare -F _get_comp_words_by_ref >/dev/null 2>&1; then
  _get_comp_words_by_ref() {
    while [ $# -gt 0 ]; do
      case "$1" in
        cur) cur="${COMP_WORDS[COMP_CWORD]}" ;;
        prev) prev="${COMP_WORDS[COMP_CWORD-1]}" ;;
        words) words=("${COMP_WORDS[@]}") ;;
        cword) cword=$COMP_CWORD ;;
        -n) shift ;;
      esac
      shift
    done
  }
fi

# kc <Tab> completes namespace names
__tut_complete_kc() {
  local cur="${COMP_WORDS[COMP_CWORD]}"
  COMPREPLY=($(compgen -W "$(kubectl get namespaces -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)" -- "$cur"))
}
complete -F __tut_complete_kc kc

# The pinned kubectl/helm/kind only appear on PATH after a tutorial's setup
# step, so load their completion lazily: before each prompt, (re)load it for any
# of them that appeared or moved.
__tut_completion_seen=""
__tut_load_completion() {
  local t p
  for t in kubectl helm kind; do
    p=$(command -v "$t" 2>/dev/null) || continue
    case " $__tut_completion_seen " in *" $t=$p "*) continue ;; esac
    eval "$("$p" completion bash 2>/dev/null)" 2>/dev/null || continue
    __tut_completion_seen="$__tut_completion_seen $t=$p"
    if [ "$t" = kubectl ] && declare -F __start_kubectl >/dev/null 2>&1; then
      complete -o default -F __start_kubectl k
    fi
  done
}
PROMPT_COMMAND="__tut_load_completion${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
