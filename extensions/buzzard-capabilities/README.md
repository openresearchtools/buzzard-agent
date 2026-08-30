# Buzzard capability discovery

This extension exposes instructions for independently installed capabilities.
It does not implement browser control, search, torrent discovery, torrent
downloads, or an MCP transport.

The Wild Buzzard skill is loaded only when `/usr/bin/wildbuzzard` exists.
Search and torrent-search skills are loaded only when their fixed apt commands
and `/usr/share` skill roots both exist. Missing packages are ignored without
changing agent startup.

Additional administrator-managed skill roots can be supplied through the
platform path list in `BUZZARD_AGENT_SKILL_PATHS`.
