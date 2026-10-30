# Sourced into the wrapped interactive bash process.
if [ -f "$HOME/.bashrc" ]; then . "$HOME/.bashrc"; fi
__ph_b64() { printf '%s' "$1" | base64 | tr -d '\n'; }
__ph_end() {
  local ec=$? cmd
  cmd=$(HISTTIMEFORMAT= builtin history 1 | sed -e 's/^ *[0-9]* *//')
  printf '\033]777;phantom;end;%s;%s;%s\007' "$ec" "$( __ph_b64 "$PWD" )" "$( __ph_b64 "$cmd" )"
  return "$ec"
}
PS0='\e]777;phantom;start\a'
PROMPT_COMMAND="__ph_end${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
export PHANTOMSHELL_ACTIVE=1
