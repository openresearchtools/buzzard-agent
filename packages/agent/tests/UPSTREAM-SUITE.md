# Downstream Pi suite classification

The pristine Pi tests are retained as provenance. After applying the Buzzard
Agent source transformation, 26 upstream assertions intentionally diverge:

- 5 command and system-prompt strings use the downstream product name;
- 7 tests exercise npm/pnpm self-update, which the Debian package disables;
- 1 first-time setup test requires the official upstream distribution;
- 3 user-agent and catalog checks require the upstream network identity;
- 7 provider-attribution checks require upstream attribution values; and
- 3 session/error strings require upstream branding.

`expected-upstream-divergences.json` records every exact test name. The
classifier rejects additions and removals so a new functional regression
cannot be hidden in a broad skip.

The original 43-failure run also contained 17 non-product failures. They are
not allowlisted:

- 10 find-tool tests lacked `fd`; `fd-find` and `ripgrep` are now mandatory
  package and CI dependencies;
- 3 permission tests were run as root and must run as an unprivileged user; and
- 4 theme/watcher tests used the legacy `PI_CODING_AGENT_DIR`; the transformed
  runtime now preserves that compatibility alias behind `BUZZARD_AGENT_DIR`.

`test_package.py` supplies downstream replacement assertions for apt-owned
updates, product and network identity, attribution, session errors, the system
prompt, and legacy path compatibility. The installed launcher disables
automatic version checks, while this upstream-suite harness leaves the version
check environment unset so upstream behavior remains exercised.

Run the classified suite as a non-root user on Ubuntu 24.04 with `fd-find` and
`ripgrep` installed:

```bash
./packages/agent/scripts/test-prepared-upstream.sh /data/work/pi-suite /data/logs/pi-suite.log
```
