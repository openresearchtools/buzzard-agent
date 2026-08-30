#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import argparse
import hashlib
import json
from pathlib import Path


PRODUCT_SUFFIXES = {".ts", ".html", ".json", ".svg", ".webmanifest"}
PI_PACKAGES = (
    "@earendil-works/pi-agent-core",
    "@earendil-works/pi-ai",
    "@earendil-works/pi-coding-agent",
)
COMMAND_FILES = (
    "extensions/pi-web.ts",
    "src/pluginRecoveryCli.ts",
    "src/shared/pluginRecoveryCommands.ts",
    "src/server/diagnostics/nodePtySpawnHelper.ts",
    "src/server/diagnostics/nodePtyNativeModule.ts",
    "src/client/src/components/settings/SettingsSessiondPanel.ts",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def replace(path: Path, old: str, new: str, minimum: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count < minimum:
        raise ValueError(f"missing downstream replacement in {path}: {old}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def prepare(root: Path, lock_path: Path) -> None:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    pi_web = lock["piWeb"]
    expected = {
        "package.json": pi_web["packageJsonSha256"],
        "package-lock.json": pi_web["packageLockSha256"],
        "LICENSE": pi_web["licenseSha256"],
    }
    for name, sha256 in expected.items():
        if digest(root / name) != sha256:
            raise ValueError(f"pinned Pi Web input differs: {name}")

    package_path = root / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package_lock_path = root / "package-lock.json"
    package_lock = json.loads(package_lock_path.read_text(encoding="utf-8"))
    if package["name"] != pi_web["name"] or package["version"] != pi_web["version"]:
        raise ValueError("pinned Pi Web package identity differs")
    if package_lock.get("lockfileVersion") != 3:
        raise ValueError("Pi Web requires npm lockfile version 3")

    lock_root = package_lock["packages"][""]
    for name in PI_PACKAGES:
        version = lock["piPackages"][name]
        if package["devDependencies"].get(name) != f"^{version}":
            raise ValueError(f"unexpected Pi SDK pin: {name}")
        package.setdefault("dependencies", {})[name] = version
        package["devDependencies"].pop(name)
        lock_root.setdefault("dependencies", {})[name] = version
        lock_root["devDependencies"].pop(name)
    write_json(package_path, package)
    write_json(package_lock_path, package_lock)

    for directory in (root / "src", root / "extensions", root / "pi-web-plugins"):
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix not in PRODUCT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            text = text.replace("PI WEB", "Buzzard Agent Web")
            text = text.replace("Pi Web", "Buzzard Agent Web")
            path.write_text(text, encoding="utf-8")

    for relative in COMMAND_FILES:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        if "pi-web" not in text:
            raise ValueError(f"missing upstream command labels in {relative}")
        path.write_text(text.replace("pi-web", "buzzard-agent-web"), encoding="utf-8")

    cli_path = root / "src/cli.ts"
    cli_text = cli_path.read_text(encoding="utf-8")
    cli_path.write_text(
        cli_text.replace("pi-web ", "buzzard-agent-web ").replace(
            "~/.config/wildbuzzard/agent/config.json",
            "~/.config/buzzard-agent/web/config.json",
        ),
        encoding="utf-8",
    )

    replace(root / "src/client/index.html", "Agent — WildBuzzard", "Buzzard Agent Web")
    manifest_path = root / "src/client/public/manifest.webmanifest"
    replace(manifest_path, '"name": "Agent — WildBuzzard"', '"name": "Buzzard Agent Web"')
    replace(
        manifest_path,
        '"description": "WildBuzzard\'s web UI for persistent Pi Coding Agent sessions."',
        '"description": "Web UI for persistent Buzzard Agent sessions."',
    )
    themes_path = root / "src/client/src/plugins/themes/index.ts"
    themes_text = themes_path.read_text(encoding="utf-8")
    themes_path.write_text(
        themes_text.replace("wildBuzzard", "buzzardAgent").replace("wildbuzzard", "buzzard-agent"),
        encoding="utf-8",
    )
    replace(themes_path, 'name: "WildBuzzard Dark"', 'name: "Buzzard Agent Dark"')
    replace(
        themes_path,
        'description: "WildBuzzard\'s dark browser palette."',
        'description: "Buzzard Agent\'s dark palette."',
    )
    replace(themes_path, 'name: "WildBuzzard Light"', 'name: "Buzzard Agent Light"')
    replace(
        themes_path,
        'description: "WildBuzzard\'s light browser palette."',
        'description: "Buzzard Agent\'s light palette."',
    )
    replace(themes_path, 'name: "WildBuzzard",', 'name: "Buzzard Agent",')
    replace(
        root / "src/client/src/theme.ts",
        '"themes:wildbuzzard-dark"',
        '"themes:buzzard-agent-dark"',
    )

    config_path = root / "src/config.ts"
    replace(
        config_path,
        '"wildbuzzard", "agent", "config.json"',
        '"buzzard-agent", "web", "config.json"',
    )
    replace(
        config_path,
        '"wildbuzzard", "agent"',
        '"buzzard-agent", "web"',
    )
    replace(config_path, 'export const DEFAULT_AGENT_COMMAND = "pi";', 'export const DEFAULT_AGENT_COMMAND = "buzzard-agent";')

    active_profile_path = root / "src/shared/activeAgentProfile.ts"
    replace(
        active_profile_path,
        'return name.replace(/(?:\\.[cm]?js|\\.exe|\\.cmd)$/iu, "") === "pi";',
        'return new Set(["pi", "buzzard-agent"]).has(name.replace(/(?:\\.[cm]?js|\\.exe|\\.cmd)$/iu, ""));',
    )

    service_plan_path = root / "src/nativeServices/servicePlan.ts"
    for old, new in (
        ("wildbuzzard-agent-sessiond.service", "buzzard-agent-web-sessiond.service"),
        ("org.wildbuzzard.agent.sessiond", "org.openresearchtools.buzzard-agent-web.sessiond"),
        ("wildbuzzard-agent-web.service", "buzzard-agent-web.service"),
        ("org.wildbuzzard.agent.web", "org.openresearchtools.buzzard-agent-web.web"),
        ("wildbuzzard-agent-ui-dev.service", "buzzard-agent-web-ui-dev.service"),
        ("org.wildbuzzard.agent.ui-dev", "org.openresearchtools.buzzard-agent-web.ui-dev"),
    ):
        replace(service_plan_path, old, new)

    app_path = root / "src/server/app.ts"
    replace(
        app_path,
        'process.env["WILDBUZZARD_AGENT_LOCAL_ONLY"]',
        'process.env["BUZZARD_AGENT_WEB_LOCAL_ONLY"]',
    )
    replace(
        cli_path,
        '''const WILDBUZZARD_SERVICE_ENV_KEYS = [
  "PI_WEB_DATA_DIR",
  "PI_CODING_AGENT_DIR",
  "WILDBUZZARD_AGENT_LOCAL_ONLY",
  "WILDBUZZARD_BROWSER_CONTROL_FILE",
  "WILDBUZZARD_PI_WEB_IDENTITY_FILE",
  "WILDBUZZARD_BUNDLED_GIT",
  "WILDBUZZARD_BUNDLED_NODE",
  "WILDBUZZARD_SEARCH_CONNECTION_FILE",
  "WILDBUZZARD_YTDLP",
  "WILDBUZZARD_CAPTION_FALLBACK_LANGUAGES",
] as const;''',
        '''const BUZZARD_AGENT_SERVICE_ENV_KEYS = [
  "PI_WEB_DATA_DIR",
  "PI_CODING_AGENT_DIR",
  "BUZZARD_AGENT_WEB_LOCAL_ONLY",
  "BUZZARD_AGENT_WEB_IDENTITY_FILE",
] as const;''',
    )
    replace(cli_path, "WILDBUZZARD_SERVICE_ENV_KEYS", "BUZZARD_AGENT_SERVICE_ENV_KEYS")

    identity_path = root / "src/server/wildbuzzardServiceIdentity.ts"
    identity_text = identity_path.read_text(encoding="utf-8")
    identity_text = identity_text.replace("WildBuzzardServiceIdentity", "BuzzardAgentWebServiceIdentity")
    identity_text = identity_text.replace("wildbuzzardServiceIdentity", "buzzardAgentWebServiceIdentity")
    identity_text = identity_text.replace("WILDBUZZARD_PI_WEB_IDENTITY_FILE", "BUZZARD_AGENT_WEB_IDENTITY_FILE")
    generic_identity_path = root / "src/server/buzzardAgentWebServiceIdentity.ts"
    generic_identity_path.write_text(identity_text, encoding="utf-8")
    identity_path.unlink()

    machine_routes_path = root / "src/server/machines/machineRoutes.ts"
    replace(
        machine_routes_path,
        'import { wildbuzzardServiceIdentity } from "../wildbuzzardServiceIdentity.js";',
        'import { buzzardAgentWebServiceIdentity } from "../buzzardAgentWebServiceIdentity.js";',
    )
    replace(machine_routes_path, "x-wildbuzzard-agent-challenge", "x-buzzard-agent-web-challenge")
    replace(machine_routes_path, "wildbuzzardServiceIdentity", "buzzardAgentWebServiceIdentity")
    replace(
        machine_routes_path,
        "WildBuzzard Agent only connects to its bundled local runtime",
        "Buzzard Agent Web is configured for its local runtime",
        minimum=3,
    )

    status_path = root / "src/server/piWebStatus.ts"
    replace(
        status_path,
        '''async function piWebCliCommands(installation: PiWebInstallationInfo | undefined): Promise<NativeServiceCommands> {
  if (installation?.kind !== "npm-global" || !(await hasCommand("pi-web"))) return {};
  return { restart: "pi-web restart", status: "pi-web status" };
}''',
        '''async function piWebCliCommands(_installation: PiWebInstallationInfo | undefined): Promise<NativeServiceCommands> {
  if (!(await hasCommand("buzzard-agent-web"))) return {};
  return { restart: "buzzard-agent-web restart", status: "buzzard-agent-web status" };
}''',
    )
    replace(status_path, 'return join(homedir(), ".config", "systemd", "user");', 'return "/usr/lib/systemd/user";')
    replace(status_path, '"wildbuzzard-agent-restart"', '"buzzard-agent-web-restart"')
    replace(status_path, '"wildbuzzard-agent-restart-web"', '"buzzard-agent-web-restart-web"')
    replace(status_path, '"wildbuzzard-agent-restart-sessiond"', '"buzzard-agent-web-restart-sessiond"')
    replace(
        status_path,
        'const PI_WEB_PACKAGE_NAME = "@jmfederico/pi-web";',
        'const PI_WEB_PACKAGE_NAME = "buzzard-agent-web";',
    )
    updates_path = root / "pi-web-plugins/updates/updatesLogic.ts"
    replace(updates_path, '"@jmfederico/pi-web"', '"buzzard-agent-web"', minimum=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("lock", type=Path)
    arguments = parser.parse_args()
    prepare(arguments.source.resolve(), arguments.lock.resolve())


if __name__ == "__main__":
    main()
