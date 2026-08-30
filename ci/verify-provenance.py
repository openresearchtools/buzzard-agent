#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import hashlib
import subprocess
import tempfile
import tomllib
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]


def git_tree(directory: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="buzzard-provenance-git-") as temporary:
        git_dir = Path(temporary) / "repository.git"
        subprocess.run(["git", "init", "--bare", "--quiet", git_dir], check=True)
        command = [
            "git",
            f"--git-dir={git_dir}",
            f"--work-tree={directory}",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.filemode=true",
        ]
        subprocess.run([*command, "add", "--force", "--all"], check=True)
        return subprocess.run(
            [*command, "write-tree"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()


def verify_tree(component: str, key: str) -> None:
    root = REPOSITORY / "vendor" / component
    metadata = tomllib.loads((root / "UPSTREAM.toml").read_text(encoding="utf-8"))
    source = root / metadata.get("source_directory", metadata.get("source_tree", "upstream"))
    actual = git_tree(source)
    if actual != metadata[key]:
        raise AssertionError(f"{component} Git tree mismatch: {actual} != {metadata[key]}")
    license_path = root / metadata["license_file"]
    if not license_path.is_file():
        license_path = source / metadata["license_file"]
    if not license_path.is_file() or metadata["license"] != "MIT":
        raise AssertionError(f"{component} license provenance is incomplete")
    print(f"{component} {actual}")


def verify_manifest(component: str) -> None:
    root = REPOSITORY / "vendor" / component
    source = root / "upstream"
    for line in (root / "SOURCE-MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        relative = relative.removeprefix("./")
        path = root / relative if relative.startswith("upstream/") else source / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise AssertionError(f"{component} manifest mismatch: {relative}")
    print(f"{component} source manifest verified")


def main() -> None:
    verify_tree("pi", "git_tree")
    verify_tree("pi-web", "tree")
    verify_tree("pi-web-access", "tree")
    verify_manifest("pi")
    verify_manifest("youtube-transcript-api")


if __name__ == "__main__":
    main()
