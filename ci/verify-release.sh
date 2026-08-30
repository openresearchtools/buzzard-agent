#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later

set -eu
umask 022

repository=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$repository"
run_root=${BUZZARD_CI_RUN_ROOT:-"$repository/ci-output"}
case "$run_root" in
  ''|/|"$repository") echo "unsafe CI run root: $run_root" >&2; exit 1 ;;
esac
if [ -e "$run_root" ]; then
  echo "CI run root already exists: $run_root" >&2
  exit 1
fi

. /etc/os-release
if [ "$ID" != ubuntu ] || [ "$VERSION_ID" != 24.04 ]; then
  echo "release verification requires Ubuntu 24.04" >&2
  exit 1
fi
if [ "$(uname -m)" != x86_64 ]; then
  echo "release verification requires x86-64" >&2
  exit 1
fi

artifact_root="$run_root/artifacts"
artifacts="$artifact_root/final"
logs="$run_root/logs"
work="$run_root/work"
cache="$run_root/cache"
mkdir -p "$artifacts" "$logs" "$work/tmp" "$cache"

run_logged() {
  name=$1
  shift
  printf 'running %s\n' "$name"
  if "$@" >"$logs/$name.log" 2>&1; then
    printf 'passed %s\n' "$name"
  else
    cat "$logs/$name.log" >&2
    return 1
  fi
}

export TMPDIR="$work/tmp"
export BUZZARD_AGENT_CACHE_ROOT="$cache/agent"
export BUZZARD_AGENT_WEB_CACHE_ROOT="$cache/web"
export BUZZARD_AGENT_NPM_CACHE="$cache/npm-agent"
export BUZZARD_AGENT_WEB_NPM_CACHE="$cache/npm-web"
node_root=$("$repository/packages/agent/scripts/prepare-node.sh")
export BUZZARD_NODE_ROOT="$node_root"
export PATH="$node_root/bin:$PATH"
export npm_config_cache="$cache/npm-tests"
export npm_config_audit=false
export npm_config_fund=false
export npm_config_update_notifier=false

run_logged agent-boundaries python3 -m unittest packages.agent.tests.test_package
run_logged web-boundaries python3 -m unittest packages.web.tests.test_component
run_logged provenance-trees python3 ci/verify-provenance.py
run_logged capabilities-tests npm --prefix extensions/buzzard-capabilities test
run_logged web-access-install npm --prefix extensions/web-access ci --ignore-scripts
run_logged web-access-typecheck npm --prefix extensions/web-access run typecheck
run_logged web-access-tests npm --prefix extensions/web-access test
if [ "${RUN_FULL_UPSTREAM_SUITE:-1}" = 1 ]; then
  run_logged upstream-suite-classification \
    "$repository/packages/agent/scripts/test-prepared-upstream.sh" \
    "$work/upstream-suite" "$logs/upstream-suite.log"
fi

run_logged agent-build "$repository/packages/agent/build-deb.sh" "$artifacts"
export BUZZARD_AGENT_WEB_BUILD_ROOT="$work/web-build"
export BUZZARD_AGENT_WEB_DIST_ROOT="$artifacts"
run_logged web-build "$repository/packages/web/scripts/build-deb.sh"

agent="$artifacts/buzzard-agent_0.84.1+buzzard1_amd64.deb"
web="$artifacts/buzzard-agent-web_1.202608.0+buzzard1_amd64.deb"
test -f "$agent"
test -f "$web"
run_logged package-verification python3 "$repository/ci/verify-packages.py" "$agent" "$web"

if [ "${VERIFY_REPRODUCIBLE:-1}" = 1 ]; then
  repro="$work/repro"
  repro_artifacts="$artifact_root/repro"
  mkdir -p "$repro_artifacts" "$repro/tmp"
  TMPDIR="$repro/tmp" run_logged agent-reproducible-build "$repository/packages/agent/build-deb.sh" "$repro_artifacts"
  BUZZARD_AGENT_WEB_BUILD_ROOT="$repro/web-build" \
    BUZZARD_AGENT_WEB_DIST_ROOT="$repro_artifacts" \
    TMPDIR="$repro/tmp" \
    run_logged web-reproducible-build "$repository/packages/web/scripts/build-deb.sh"
  cmp "$agent" "$repro_artifacts/$(basename "$agent")"
  cmp "$web" "$repro_artifacts/$(basename "$web")"
fi

(
  cd "$artifacts"
  sha256sum ./*.deb > SHA256SUMS
)
{
  dpkg-deb -f "$agent" Package Version Architecture Depends Suggests
  dpkg-deb -f "$web" Package Version Architecture Depends
} > "$logs/package-metadata.txt"
printf 'release-verification-ok %s\n' "$run_root"
