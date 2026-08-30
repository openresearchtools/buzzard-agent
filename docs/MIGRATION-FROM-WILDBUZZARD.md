# Migration from the browser-integrated agent

This repository owns the agent runtime and web application that were formerly
assembled inside Wild Buzzard. It intentionally does not own browser chrome,
Gecko services, or privileged browser APIs.

## Ownership after extraction

| Capability | Owner | Runtime boundary |
| --- | --- | --- |
| Agent CLI, prompts, tools, sessions, extensions | `buzzard-agent` | `/usr/bin/buzzard-agent` |
| Agent web UI, API, session daemon | `buzzard-agent-web` | `/usr/bin/buzzard-agent-web` and loopback HTTP |
| Browser automation | Wild Buzzard | `/usr/bin/wildbuzzard` public JSON CLI |
| Web search | `buzzard-search` | `/usr/bin/buzzard-search` protocol 1 and its installed skill |
| Torrent discovery | `buzzard-minijtt` | `/usr/bin/buzzard-minijtt` protocol 1 and its installed skill |
| Torrent download, blockers, Tor, Waterfox-derived browser features | Wild Buzzard | Browser-owned UI and generic browser-control commands |

Search and torrent discovery packages are optional. The agent discovers their
installed skills and calls their CLIs directly; it does not proxy them through
Firefox, MCP, or a private socket. Torrent discovery does not itself authorize
a download. A browser import or download remains an explicit user-confirmed
browser action.

## Safe migration order

1. Install `buzzard-agent` and, if wanted, `buzzard-agent-web` before removing
   the browser-integrated copies.
2. Run `buzzard-agent-web status --json`. Existing Wild Buzzard web data and
   configuration are used in place when the new default paths do not exist.
3. Start the independent services with `buzzard-agent-web start --json` and
   open the returned `url` in any browser.
4. Verify browser automation separately with `/usr/bin/wildbuzzard help` and
   the installed Wild Buzzard skill.
5. Only then remove the old Firefox Agent page, sidebar, toolbar and service
   supervision code. Keep the browser's generic CLI, torrent core, blocking,
   Tor, and Waterfox-derived features.

New web state defaults to `$XDG_DATA_HOME/buzzard-agent/web`; configuration
defaults to `$XDG_CONFIG_HOME/buzzard-agent/web/config.json`; agent state
defaults to `~/.buzzard-agent/agent`. When the new web paths are absent, the
launcher recognizes the former `$XDG_DATA_HOME/wildbuzzard/agent` and
`$XDG_CONFIG_HOME/wildbuzzard/agent/config.json` paths. It does not move or
delete them.

The extracted `extensions/web-access` tree supplies only browser-content fetch,
crawl, and stored-content tools. Historical combined search and torrent source
is omitted from the active tree; the independent CLI packages replace those
contracts, and the original Wild Buzzard commit remains recorded for audit.
