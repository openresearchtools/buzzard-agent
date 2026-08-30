#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import argparse
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path


PRIVATE_CONTRACTS = (
    "WILDBUZZARD_BROWSER_CONTROL_FILE",
    "WILDBUZZARD_SEARCH_CONNECTION_FILE",
    "browser-control.json",
    "TCPServerSocket",
    "ChromeUtils",
    "resource://",
    "chrome://",
    "native_search",
    "torrent_search",
)


def field(package: Path, name: str) -> str:
    return subprocess.run(
        ["dpkg-deb", "-f", package, name],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def dependency_names(value: str) -> set[str]:
    return {re.split(r"\s|\(", item.strip(), maxsplit=1)[0] for item in value.split(",")}


def extract(package: Path, destination: Path) -> None:
    subprocess.run(["dpkg-deb", "-x", package, destination], check=True)


def assert_safe_tree(root: Path) -> None:
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if path.is_symlink():
            target = (path.parent / os.readlink(path)).resolve()
            if not target.is_relative_to(root.resolve()):
                raise AssertionError(f"escaping package symlink: {path} -> {target}")
        elif path.is_file():
            if mode & (stat.S_IWOTH | stat.S_ISUID | stat.S_ISGID):
                raise AssertionError(f"unsafe package mode {stat.filemode(mode)}: {path}")


def textual_files(root: Path):
    suffixes = {".js", ".mjs", ".ts", ".json", ".html", ".md", ".toml", ".webmanifest"}
    for path in root.rglob("*"):
        if path.name.endswith(".d.ts"):
            continue
        if path.is_file() and path.suffix in suffixes:
            yield path


def assert_no_private_contract(root: Path) -> None:
    for path in textual_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for forbidden in PRIVATE_CONTRACTS:
            if forbidden in text:
                raise AssertionError(f"private browser contract {forbidden!r} in {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent", type=Path)
    parser.add_argument("web", type=Path)
    args = parser.parse_args()

    expected = {
        args.agent: (
            "buzzard-agent",
            "0.84.1+buzzard1",
            {"ca-certificates", "fd-find", "ripgrep", "libc6", "libgcc-s1", "libstdc++6"},
        ),
        args.web: (
            "buzzard-agent-web",
            "1.202608.0+buzzard1",
            {"buzzard-agent", "libc6", "libgcc-s1", "libstdc++6", "ca-certificates"},
        ),
    }
    for package, (name, version, dependencies) in expected.items():
        if field(package, "Package") != name:
            raise AssertionError(f"wrong package identity: {package}")
        if field(package, "Version") != version or field(package, "Architecture") != "amd64":
            raise AssertionError(f"wrong package version or architecture: {package}")
        if dependency_names(field(package, "Depends")) != dependencies:
            raise AssertionError(f"wrong dependencies: {package}: {field(package, 'Depends')}")

    if dependency_names(field(args.agent, "Suggests")) != {
        "wildbuzzard",
        "buzzard-search",
        "buzzard-minijtt",
        "git",
        "yt-dlp",
    }:
        raise AssertionError("agent optional package boundary changed")

    with tempfile.TemporaryDirectory(prefix="buzzard-agent-package-check-") as directory:
        root = Path(directory)
        agent_root = root / "agent"
        web_root = root / "web"
        extract(args.agent, agent_root)
        extract(args.web, web_root)
        assert_safe_tree(agent_root)
        assert_safe_tree(web_root)

        if {path.name for path in (agent_root / "usr/bin").iterdir()} != {"buzzard-agent"}:
            raise AssertionError("agent package exports unexpected commands")
        if {path.name for path in (web_root / "usr/bin").iterdir()} != {"buzzard-agent-web"}:
            raise AssertionError("web package exports unexpected commands")

        for relative in (
            "EXTRACTION.toml",
            "LICENSE.downstream",
            "LICENSE.upstream",
            "NOTICE",
            "NOTICE.repository",
            "pi-source-manifest.sha256",
            "pi-upstream.toml",
            "pi-web-access-upstream.toml",
        ):
            if not (agent_root / "usr/share/doc/buzzard-agent" / relative).is_file():
                raise AssertionError(f"missing agent provenance: {relative}")
        for relative in (
            "EXTRACTION.toml",
            "LICENSE.downstream",
            "LICENSE.pi-web",
            "NOTICE",
            "NOTICE.repository",
            "upstream.toml",
        ):
            if not (web_root / "usr/share/doc/buzzard-agent-web" / relative).is_file():
                raise AssertionError(f"missing web provenance: {relative}")

        for skills_root in (
            agent_root / "usr/lib/buzzard-agent/app/skills",
            agent_root / "usr/share/buzzard-agent/skills",
        ):
            for path in skills_root.rglob("*"):
                expected_mode = 0o755 if path.is_dir() else 0o644
                if stat.S_IMODE(path.stat().st_mode) != expected_mode:
                    raise AssertionError(f"wrong skill mode: {path}")

        pty = web_root / "usr/lib/buzzard-agent-web/app/node_modules/node-pty/build/Release/pty.node"
        if stat.S_IMODE(pty.stat().st_mode) != 0o644:
            raise AssertionError("node-pty native library must not be executable")

        agent_extensions = agent_root / "usr/lib/buzzard-agent/app/extensions"
        web_runtime = web_root / "usr/lib/buzzard-agent-web/app/node_modules/@jmfederico/pi-web/dist"
        assert_no_private_contract(agent_extensions)
        assert_no_private_contract(web_runtime)

        capabilities = (agent_extensions / "buzzard-capabilities/index.ts").read_text(encoding="utf-8")
        for executable in ("/usr/bin/wildbuzzard", "/usr/bin/buzzard-search", "/usr/bin/buzzard-minijtt"):
            if executable not in capabilities:
                raise AssertionError(f"missing public capability contract: {executable}")
        adapter = (agent_extensions / "web-access/wildbuzzard-cli.ts").read_text(encoding="utf-8")
        if "/usr/bin/wildbuzzard" not in adapter or "spawn(" not in adapter:
            raise AssertionError("browser-content adapter is not using the public CLI")
        gecko_client = (agent_extensions / "web-access/gecko-client.ts").read_text(encoding="utf-8")
        if '"gecko_render"' not in gecko_client:
            raise AssertionError("browser-content adapter does not use the bounded render command")

    print("package identities, dependencies, modes, provenance, and public CLI boundaries verified")


if __name__ == "__main__":
    main()
