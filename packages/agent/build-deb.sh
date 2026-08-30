#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later

set -eu
umask 022

component_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repository_dir=$(CDPATH= cd -- "$component_dir/../.." && pwd -P)
source_dir=${BUZZARD_AGENT_SOURCE:-"${repository_dir}/vendor/pi/upstream"}
integration_dir=${BUZZARD_AGENT_INTEGRATION_SOURCE:-"${repository_dir}/extensions/buzzard-capabilities"}
web_access_dir=${BUZZARD_AGENT_WEB_ACCESS_SOURCE:-"${repository_dir}/extensions/web-access"}
skills_dir=${BUZZARD_AGENT_SKILLS_SOURCE:-"${repository_dir}/skills"}
output_dir=${1:-"${component_dir}/dist"}
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/buzzard-agent-deb.XXXXXX")
trap 'rm -rf -- "$work_dir"' EXIT HUP INT TERM
stage="$work_dir/buzzard-agent"

node_root=$("$component_dir/scripts/prepare-node.sh")
PATH="$node_root/bin:$PATH"
export PATH
export npm_config_cache=${BUZZARD_AGENT_NPM_CACHE:-"$component_dir/.cache/npm"}
export npm_config_audit=false
export npm_config_fund=false
export npm_config_update_notifier=false
if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
  SOURCE_DATE_EPOCH=$(awk -F ' = ' '$1 == "source_date_epoch" { print $2; exit }' \
    "$repository_dir/vendor/pi/UPSTREAM.toml")
fi
case "$SOURCE_DATE_EPOCH" in
  ''|*[!0-9]*) echo "SOURCE_DATE_EPOCH must be an integer" >&2; exit 2 ;;
esac
export SOURCE_DATE_EPOCH TZ=UTC LC_ALL=C
mkdir -p "$stage/DEBIAN" "$stage/usr/bin" "$stage/usr/lib/buzzard-agent/node/bin" \
  "$stage/usr/share/buzzard-agent/skills" \
  "$stage/usr/share/doc/buzzard-agent" "$output_dir"
"$component_dir/scripts/build-runtime.sh" "$source_dir" "$stage/usr/lib/buzzard-agent/app"
mkdir -p "$stage/usr/lib/buzzard-agent/app/extensions/buzzard-capabilities" \
  "$stage/usr/lib/buzzard-agent/app/extensions/web-access" \
  "$stage/usr/lib/buzzard-agent/app/skills"
install -m 0755 "$component_dir/bin/buzzard-agent" "$stage/usr/bin/buzzard-agent"
install -m 0755 "$node_root/bin/node" "$stage/usr/lib/buzzard-agent/node/bin/node"
install -m 0644 "$integration_dir/index.ts" "$stage/usr/lib/buzzard-agent/app/extensions/buzzard-capabilities/index.ts"
install -m 0644 "$integration_dir/package.json" "$stage/usr/lib/buzzard-agent/app/extensions/buzzard-capabilities/package.json"
install -m 0644 "$integration_dir/README.md" "$stage/usr/share/doc/buzzard-agent/capability-extension.md"
for source in \
  activation.ts crawl.ts database.ts declared-web-links.ts \
  extract.ts gecko-client.ts github.ts index.ts page-answer.ts pdf-extract.ts \
  rsc-extract.ts safe-output.ts session-generation.ts storage.ts \
  wildbuzzard-cli.ts youtube.ts package.json package-lock.json \
  LICENSE.pi-web-access UPSTREAM.toml README.md; do
  install -m 0644 "$web_access_dir/$source" \
    "$stage/usr/lib/buzzard-agent/app/extensions/web-access/$source"
done
(
  cd "$stage/usr/lib/buzzard-agent/app/extensions/web-access"
  npm ci --omit=dev --ignore-scripts
)
install -m 0644 "$web_access_dir/runtime-package.json" \
  "$stage/usr/lib/buzzard-agent/app/extensions/web-access/package.json"
install -m 0644 "$web_access_dir/README.md" "$stage/usr/share/doc/buzzard-agent/browser-content-extension.md"
cp -a "$skills_dir/." "$stage/usr/lib/buzzard-agent/app/skills/"
cp -a "$skills_dir/." "$stage/usr/share/buzzard-agent/skills/"
find "$stage/usr/lib/buzzard-agent/app/skills" "$stage/usr/share/buzzard-agent/skills" \
  -type d -exec chmod 0755 {} +
find "$stage/usr/lib/buzzard-agent/app/skills" "$stage/usr/share/buzzard-agent/skills" \
  -type f -exec chmod 0644 {} +
if [ -f "$node_root/LICENSE" ]; then
  install -m 0644 "$node_root/LICENSE" "$stage/usr/lib/buzzard-agent/node/LICENSE"
fi
install -m 0644 "$source_dir/LICENSE" "$stage/usr/share/doc/buzzard-agent/LICENSE.upstream"
install -m 0644 "$component_dir/NOTICE" "$stage/usr/share/doc/buzzard-agent/NOTICE"
install -m 0644 "$component_dir/runtime-lock.json" "$stage/usr/share/doc/buzzard-agent/runtime-lock.json"
install -m 0644 "$repository_dir/NOTICE" "$stage/usr/share/doc/buzzard-agent/NOTICE.repository"
install -m 0644 "$repository_dir/LICENSE" "$stage/usr/share/doc/buzzard-agent/LICENSE.downstream"
install -m 0644 "$repository_dir/EXTRACTION.toml" "$stage/usr/share/doc/buzzard-agent/EXTRACTION.toml"
install -m 0644 "$repository_dir/vendor/pi/UPSTREAM.toml" "$stage/usr/share/doc/buzzard-agent/pi-upstream.toml"
install -m 0644 "$repository_dir/vendor/pi/SOURCE-MANIFEST.sha256" "$stage/usr/share/doc/buzzard-agent/pi-source-manifest.sha256"
install -m 0644 "$repository_dir/vendor/pi-web-access/UPSTREAM.toml" "$stage/usr/share/doc/buzzard-agent/pi-web-access-upstream.toml"
install -m 0644 "$component_dir/debian/copyright" "$stage/usr/share/doc/buzzard-agent/copyright"
gzip -n -9 -c "$component_dir/debian/changelog" > "$stage/usr/share/doc/buzzard-agent/changelog.gz"
find "$stage" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +

install -m 0644 "$component_dir/debian/binary-control" "$stage/DEBIAN/control"
touch -h -d "@$SOURCE_DATE_EPOCH" "$stage/DEBIAN/control"
dpkg-deb --root-owner-group --uniform-compression -Zzstd -z10 --build \
  "$stage" "$output_dir/buzzard-agent_0.84.1+buzzard1_amd64.deb"
