#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later

set -eu

. /etc/os-release
case "$ID:$VERSION_ID" in
  ubuntu:24.04|debian:13) ;;
  *) echo "installed smoke requires Ubuntu 24.04 or Debian 13" >&2; exit 1 ;;
esac

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/buzzard-agent-installed.XXXXXX")
web_pid=
sessiond_pid=
cleanup() {
  test -z "$web_pid" || kill "$web_pid" 2>/dev/null || true
  test -z "$sessiond_pid" || kill "$sessiond_pid" 2>/dev/null || true
  rm -rf -- "$work_dir"
}
trap cleanup EXIT HUP INT TERM

export HOME="$work_dir/home"
export XDG_RUNTIME_DIR="$work_dir/run"
export XDG_CONFIG_HOME="$work_dir/config"
export XDG_DATA_HOME="$work_dir/data"
export BUZZARD_AGENT_DIR="$work_dir/agent"
export BUZZARD_AGENT_WEB_PORT=18765
export BUZZARD_AGENT_WEB_LOCAL_ONLY=1
export BUZZARD_AGENT_WEB_OFFLINE=1
mkdir -p "$HOME" "$XDG_RUNTIME_DIR" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$BUZZARD_AGENT_DIR"

buzzard-agent --no-extensions --version
buzzard-agent-web version
buzzard-agent-web endpoint --json
buzzard-agent-web sessiond >"$work_dir/sessiond.log" 2>&1 &
sessiond_pid=$!
buzzard-agent-web serve >"$work_dir/web.log" 2>&1 &
web_pid=$!

node=/usr/lib/buzzard-agent-web/node/bin/node
attempt=1
while [ "$attempt" -le 80 ]; do
  if "$node" -e 'fetch("http://127.0.0.1:18765/api/machines/local/health").then(response => response.json().then(body => { if (!response.ok || body?.ok !== true || body?.web?.available !== true || body?.sessiond?.available !== true) process.exit(1); })).catch(() => process.exit(1));' >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 80 ]; then
    cat "$work_dir/sessiond.log" "$work_dir/web.log" >&2
    exit 1
  fi
  sleep 0.25
  attempt=$((attempt + 1))
done

buzzard-agent-web doctor
"$node" -e 'fetch("http://127.0.0.1:18765/").then(response => response.text()).then(text => { if (!text.includes("Buzzard Agent Web") || /PI WEB|Pi Web|WildBuzzard|wildbuzzard|WILDBUZZARD/.test(text)) process.exit(1); }).catch(() => process.exit(1));'
printf 'installed-smoke-ok %s %s\n' "$PRETTY_NAME" "$(buzzard-agent --no-extensions --version | head -n 1)"
