# Buzzard Agent

Buzzard Agent is the standalone home of the agent runtime that was previously
assembled inside the Wild Buzzard Firefox fork. The browser is now an optional
client: the agent and web UI run without Firefox, while browser work uses only
the public `wildbuzzard` command-line contract.

The repository contains:

- `packages/agent`: the debranded Pi agent runtime and Debian packaging;
- `packages/web`: the Pi Web UI, API, session daemon, pinned Node.js runtime,
  and Debian packaging;
- `extensions/buzzard-capabilities`: optional installed-skill discovery with no
  embedded search, torrent, or browser transport;
- `extensions/web-access`: the extracted pi-web-access browser-content adapter,
  loaded only for fetch/crawl tools when the optional browser is present;
- `vendor`: complete pinned Pi, Pi Web, pi-web-access, and transcript sources
  with their original licenses and provenance; and
- `skills/wildbuzzard`: the portable browser-control instructions used by
  agents that have Wild Buzzard installed.

## Runtime boundaries

`buzzard-agent` has no mandatory browser, web-search, or torrent dependency.
Installing `wildbuzzard` adds visible browser control through `/usr/bin/wildbuzzard`.
Installing `buzzard-search` or `buzzard-minijtt` adds their CLI skills.
Missing optional packages are ignored cleanly.

There is no Firefox module import, privileged Gecko socket, bearer-token file,
or private browser API in this repository. Search and torrent discovery are not
implemented here; agents call the independently packaged CLIs described by the
skills shipped with those packages.

`buzzard-agent-web` depends on `buzzard-agent`, owns its web and Node.js runtime,
and exposes a stable local service contract through `buzzard-agent-web`. Any
normal browser can open the returned URL.

See `docs/MIGRATION-FROM-WILDBUZZARD.md` for the ownership split, state-path
compatibility, and the safe order for removing the former Firefox integration.

## Debian packages

Build the packages independently from the repository root:

```bash
make agent-deb
make web-deb
```

Both builds verify and download their pinned Node.js archive unless
`BUZZARD_NODE_ROOT` points to an extracted matching runtime. Build details are
in `packages/agent/README.md` and `packages/web/README.md`.

The release workflow is pinned to Ubuntu 24.04 and builds both packages twice,
checks byte-for-byte reproducibility, verifies provenance and public CLI
boundaries, installs the resulting packages, exercises the live web/session
stack, and uploads the Debian packages and logs. The same check can be run in a
clean Ubuntu 24.04 builder with:

```bash
BUZZARD_CI_RUN_ROOT=/path/on-the-data-drive/buzzard-agent-release \
  ./ci/verify-release.sh
```

## Licensing

Original integration and packaging work is AGPL-3.0-or-later. Vendored projects
remain under their recorded upstream licenses. See `NOTICE`, each `vendor/*`
provenance record, and the installed Debian copyright files.
