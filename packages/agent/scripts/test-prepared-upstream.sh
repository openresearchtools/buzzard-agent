#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later

set -eu
umask 022

component=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
repository=$(CDPATH= cd -- "$component/../.." && pwd -P)
source_root="$repository/vendor/pi/upstream"
work=${1:?usage: test-prepared-upstream.sh WORK_DIRECTORY LOG_FILE}
log=${2:?usage: test-prepared-upstream.sh WORK_DIRECTORY LOG_FILE}

if [ "$(id -u)" -eq 0 ]; then
  echo "the prepared upstream suite must run as an unprivileged user" >&2
  exit 1
fi
if [ -e "$work" ]; then
  echo "test work directory already exists: $work" >&2
  exit 1
fi
for command in python3 rg; do
  command -v "$command" >/dev/null 2>&1 || { echo "$command is required" >&2; exit 1; }
done
if ! command -v fd >/dev/null 2>&1 && ! command -v fdfind >/dev/null 2>&1; then
  echo "fd-find is required" >&2
  exit 1
fi

mkdir -p "$work/source" "$work/runtime" "$work/home" "$work/tmp" "$(dirname -- "$log")"
cp -a "$source_root/." "$work/source/"
python3 "$component/scripts/debrand.py" "$work/source"

node_root=$("$component/scripts/prepare-node.sh")
export PATH="$node_root/bin:$PATH"
for command in npm node; do
  command -v "$command" >/dev/null 2>&1 || { echo "$command is required" >&2; exit 1; }
done
export HOME="$work/home"
export TMPDIR="$work/tmp"
export npm_config_cache="$work/npm-cache"
export npm_config_audit=false
export npm_config_fund=false
export npm_config_update_notifier=false
export PI_TELEMETRY=0

cp "$work/source/packages/coding-agent/install-lock/package.json" "$work/runtime/package.json"
cp "$work/source/packages/coding-agent/install-lock/package-lock.json" "$work/runtime/package-lock.json"
(
  cd "$work/runtime"
  npm ci --omit=dev --ignore-scripts
)
mkdir -p "$work/source/packages/ai/src/providers/data"
cp -R "$work/runtime/node_modules/@earendil-works/pi-ai/dist/providers/data/." \
  "$work/source/packages/ai/src/providers/data/"

(
  cd "$work/source"
  npm ci --ignore-scripts
  npm run check
  npm run build:offline
) >"$log" 2>&1

test_status=0
(
  cd "$work/source"
  npm test
) >>"$log" 2>&1 || test_status=$?
if [ "$test_status" -eq 0 ]; then
  echo "upstream suite unexpectedly had no downstream divergences" >&2
  exit 1
fi
python3 "$component/scripts/classify-upstream-test-log.py" "$log"
printf 'prepared-upstream-suite-classified status=%s\n' "$test_status"
