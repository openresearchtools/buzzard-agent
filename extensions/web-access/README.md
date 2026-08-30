# Buzzard browser-content extension

This extracted pi-web-access derivative supplies bounded `fetch_content`,
`crawl_content`, and `get_web_content` tools when `/usr/bin/wildbuzzard` is
installed. Rendering goes only through the public Wild Buzzard JSON CLI; there
is no Firefox import, private token, direct socket, or MCP transport.

The Debian package does not load this extension when the browser command is
absent. Git repository extraction uses `/usr/bin/git` when installed, YouTube
caption extraction uses `/usr/bin/yt-dlp` when installed, and both fall back to
browser rendering when their optional helper is unavailable.

Search and torrent discovery are deliberately not implemented here. Agents call
the independently packaged `/usr/bin/buzzard-search` and
`/usr/bin/buzzard-minijtt` protocols through the skills those packages
install. Native torrent downloads and transfer control remain browser-owned.

The active extension tree contains only the browser-content implementation.
Historical combined search/torrent code is recoverable from the source commit
recorded in `EXTRACTION.toml`, while pristine pi-web-access and its MIT license
remain under `vendor/pi-web-access`. The installed `package.json` is the
dependency-only `runtime-package.json`.
