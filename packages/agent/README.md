# Buzzard Agent

Buzzard Agent is the independently installable Debian package for the coding
agent previously used by Wild Buzzard. It is built from the pristine, pinned
source in `vendor/pi/upstream`, then receives deterministic
downstream identity changes in a temporary build tree.

The package installs `/usr/bin/buzzard-agent` and keeps its state under
`~/.buzzard-agent/agent`. It does not embed the browser UI, web search, torrent
search, torrent application, or quick-search implementation. Those are
separate Debian dependencies and can also be used by other applications.

Its default capability extension discovers installed CLI skills. It does not
start an MCP server or embed search/torrent implementations. Pass
`--no-extensions` to disable the built-ins, or set
`BUZZARD_AGENT_BUILTIN_EXTENSIONS=0`. Agents control the
browser directly with the `wildbuzzard` CLI when that optional package is
installed. `buzzard-search` and `buzzard-minijtt` remain optional apt
packages.

The package depends on `fd-find` and `ripgrep`, so the built-in file discovery
and text-search tools also work offline without downloading helper binaries at
runtime.

When `/usr/bin/wildbuzzard` exists, the extracted browser-content extension
also exposes bounded fetch, crawl, and stored-content tools over that same CLI.
It contains no search or torrent-discovery tool. Optional `git` and `yt-dlp`
helpers improve repository and caption extraction and otherwise degrade to
browser rendering.

The launcher accepts the Pi Web compatibility environment used for agent and
session directories and maps it to the Buzzard Agent names. Existing web
sessions therefore keep their original locations during package extraction.

Run `./build-deb.sh [output-directory]` with curl, xz, Python 3, and
`dpkg-deb` available. The build verifies and downloads the exact Node.js and
npm runtime in `runtime-lock.json` unless `BUZZARD_NODE_ROOT` points to that
same extracted runtime. It uses upstream's pinned npm lockfiles and requires
npm registry access unless the npm cache is already complete.
