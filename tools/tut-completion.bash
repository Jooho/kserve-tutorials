# Tab completion for ./tut — subcommands, options, tutorial ids, tags,
# collections, KServe versions, languages. Candidates come from `./tut
# __complete`, which reads the CLI's own definitions, so they never drift.
#
# Enable it in your shell (nothing is installed, your config is not changed):
#   source <repo>/tools/tut-completion.bash          # bash
#   autoload -U +X bashcompinit && bashcompinit      # zsh: first these two lines,
#   source <repo>/tools/tut-completion.bash          #      then the same source
# or simply:  eval "$(./tut completion)"
# The UI terminal loads it automatically.
_tut_complete() {
  local cur="${COMP_WORDS[COMP_CWORD]}" tut="${COMP_WORDS[0]}"
  if [ ! -x "$tut" ]; then tut="$(command -v "$tut" 2>/dev/null)" || return 0; fi
  local IFS=$'\n'
  COMPREPLY=($(compgen -W "$("$tut" __complete "${COMP_WORDS[@]:1:COMP_CWORD-1}" 2>/dev/null)" -- "$cur"))
  # KEY= candidates (./tut config): do not add a space after the "="
  if [ ${#COMPREPLY[@]} -eq 1 ] && [[ "${COMPREPLY[0]}" == *= ]]; then
    compopt -o nospace 2>/dev/null
  fi
}
complete -F _tut_complete ./tut tut
