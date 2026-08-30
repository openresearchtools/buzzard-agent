#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import hashlib
import json
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path


COMPONENT = Path(__file__).resolve().parents[1]
REPOSITORY = COMPONENT.parents[1]
VENDOR = REPOSITORY / "vendor/pi"
UPSTREAM = VENDOR / "upstream"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BuzzardAgentPackageTests(unittest.TestCase):
    def test_pristine_source_matches_provenance(self):
        metadata = tomllib.loads((VENDOR / "UPSTREAM.toml").read_text(encoding="utf-8"))
        self.assertEqual(metadata["version"], "0.84.1")
        self.assertEqual(metadata["commit"], "53fa77ccd8a279eb87e92294ef3687b03ff80112")
        self.assertEqual(metadata["git_tree"], "70a1ca9fe2bd7dfdcf00d53a60b02be4978e40e9")
        self.assertEqual(metadata["license"], "MIT")
        self.assertEqual(sha256(UPSTREAM / "LICENSE"), metadata["license_sha256"])
        self.assertEqual(sha256(VENDOR / "SOURCE-MANIFEST.sha256"), metadata["source_manifest_sha256"])

        entries = (VENDOR / "SOURCE-MANIFEST.sha256").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(entries), metadata["source_files"])
        for entry in entries:
            expected, relative = entry.split("  ./", 1)
            self.assertEqual(sha256(UPSTREAM / relative), expected, relative)

    def test_upstream_packages_select_0841(self):
        packages = {}
        for relative in (
            "packages/agent/package.json",
            "packages/ai/package.json",
            "packages/coding-agent/package.json",
        ):
            package = json.loads((UPSTREAM / relative).read_text(encoding="utf-8"))
            packages[package["name"]] = package["version"]
        self.assertEqual(
            packages,
            {
                "@earendil-works/pi-agent-core": "0.84.1",
                "@earendil-works/pi-ai": "0.84.1",
                "@earendil-works/pi-coding-agent": "0.84.1",
            },
        )
        extension = json.loads((REPOSITORY / "extensions/web-access/package.json").read_text(encoding="utf-8"))
        self.assertEqual(extension["dependencies"]["@earendil-works/pi-ai"], "0.84.1")

    def test_debranding_is_outside_pristine_source(self):
        with tempfile.TemporaryDirectory(prefix="buzzard-agent-test-") as directory:
            work = Path(directory) / "source"
            shutil.copytree(UPSTREAM, work)
            subprocess.run(["python3", COMPONENT / "scripts/debrand.py", work], check=True)

            package = json.loads((work / "packages/coding-agent/package.json").read_text(encoding="utf-8"))
            self.assertEqual(package["name"], "@earendil-works/pi-coding-agent")
            self.assertEqual(package["piConfig"], {"configDir": ".pi"})
            self.assertEqual(package["bin"], {"pi": "dist/cli.js"})

            source_root = work / "packages/coding-agent/src"
            combined = "\n".join(path.read_text(encoding="utf-8") for path in source_root.rglob("*.ts"))
            for forbidden in (
                'Start without extensions using "pi',
                "operating inside pi",
                "Pi can explain",
                "Pi works best",
                "restart pi",
                "pi exiting",
                "outside pi",
                "within Pi",
                "Location of pi executable",
                "Update pi",
                "${APP_NAME} update pi",
            ):
                self.assertNotIn(forbidden, combined)

        upstream_package = json.loads((UPSTREAM / "packages/coding-agent/package.json").read_text(encoding="utf-8"))
        self.assertEqual(upstream_package["name"], "@earendil-works/pi-coding-agent")
        self.assertEqual(upstream_package["bin"], {"pi": "dist/cli.js"})

    def test_debian_package_composes_independent_modules(self):
        control = (COMPONENT / "debian/control").read_text(encoding="utf-8")
        binary_control = (COMPONENT / "debian/binary-control").read_text(encoding="utf-8")
        for package in ("wildbuzzard", "buzzard-search", "buzzard-minijtt"):
            self.assertIn(package, control)
            self.assertIn(package, binary_control)
        self.assertIn("Suggests:", control)
        self.assertIn("Suggests:", binary_control)
        for package in ("fd-find", "ripgrep"):
            self.assertIn(package, control.split("Suggests:", 1)[0])
            self.assertIn(package, binary_control.split("Suggests:", 1)[0])
        self.assertNotIn("Depends: ${misc:Depends}, buzzard-", control)
        self.assertNotIn("buzzard-agent-web", control)
        self.assertNotIn("buzzard-agent-web", binary_control)
        self.assertNotIn("node_modules/@jmfederico/pi-web", (COMPONENT / "scripts/build-runtime.sh").read_text(encoding="utf-8"))

    def test_downstream_identity_and_update_boundaries(self):
        with tempfile.TemporaryDirectory(prefix="buzzard-agent-boundaries-") as directory:
            work = Path(directory) / "source"
            shutil.copytree(UPSTREAM, work)
            subprocess.run(["python3", COMPONENT / "scripts/debrand.py", work], check=True)

            source = work / "packages/coding-agent/src"
            config = (source / "config.ts").read_text(encoding="utf-8")
            self.assertIn(
                "process.env[ENV_AGENT_DIR] || process.env.PI_CODING_AGENT_DIR",
                config,
            )
            startup = (source / "cli/startup-ui.ts").read_text(encoding="utf-8")
            self.assertIn(
                "process.env[ENV_AGENT_DIR] || process.env.PI_CODING_AGENT_DIR",
                startup,
            )
            package_cli = (source / "package-manager-cli.ts").read_text(encoding="utf-8")
            self.assertIn("Buzzard Agent is managed by Debian packages", package_cli)
            self.assertIn('source === "self" || source === "buzzard-agent"', package_cli)
            self.assertNotIn('source === "self" || source === "pi"', package_cli)
            self.assertNotIn("\n\t\t\t\trunSelfUpdate(", package_cli)
            self.assertIn(
                "buzzard-agent/${version}",
                (source / "utils/pi-user-agent.ts").read_text(encoding="utf-8"),
            )
            attribution = (source / "core/provider-attribution.ts").read_text(encoding="utf-8")
            for value in (
                "https://github.com/openresearchtools/buzzard-agent",
                '"X-OpenRouter-Title": "Buzzard Agent"',
                '"X-BILLING-INVOKE-ORIGIN": "BuzzardAgent"',
                '"x-opencode-client": "buzzard-agent"',
            ):
                self.assertIn(value, attribution)
            self.assertIn(
                "not a valid Buzzard Agent session",
                (source / "core/session-manager.ts").read_text(encoding="utf-8"),
            )
            system_prompt = (source / "core/system-prompt.ts").read_text(encoding="utf-8")
            self.assertIn("operating inside Buzzard Agent", system_prompt)
            self.assertNotIn("operating inside pi", system_prompt)

    def test_expected_upstream_divergences_are_exactly_classified(self):
        expectations = COMPONENT / "tests/expected-upstream-divergences.json"
        document = json.loads(expectations.read_text(encoding="utf-8"))
        entries = document["expected"]
        self.assertEqual(len(entries), 26)
        self.assertEqual(len({entry["name"] for entry in entries}), 26)
        with tempfile.TemporaryDirectory(prefix="buzzard-agent-classifier-") as directory:
            log = Path(directory) / "upstream.log"
            log.write_text(
                "\n".join(f" FAIL  {entry['name']}" for entry in entries),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    "python3",
                    COMPONENT / "scripts/classify-upstream-test-log.py",
                    log,
                    "--expectations",
                    expectations,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("classified 26 intentional downstream divergences", result.stdout)

    def test_release_ci_is_standalone_and_pinned(self):
        workflow = (REPOSITORY / ".github/workflows/release-verification.yml").read_text(encoding="utf-8")
        self.assertIn("runs-on: ubuntu-24.04", workflow)
        self.assertRegex(workflow, r"actions/checkout@[0-9a-f]{40}")
        self.assertRegex(workflow, r"actions/upload-artifact@[0-9a-f]{40}")
        self.assertIn("debian:13-slim", workflow)
        for forbidden in ("firefox", "./mach", "/host-source"):
            self.assertNotIn(forbidden, workflow.lower())
        release = (REPOSITORY / "ci/verify-release.sh").read_text(encoding="utf-8")
        for required in (
            "packages/agent/build-deb.sh",
            "packages/web/scripts/build-deb.sh",
            "verify-packages.py",
            "verify-provenance.py",
            "test-prepared-upstream.sh",
            "agent-boundaries",
            "web-boundaries",
            "cmp \"$agent\"",
            "cmp \"$web\"",
        ):
            self.assertIn(required, release)
        package_verifier = (REPOSITORY / "ci/verify-packages.py").read_text(encoding="utf-8")
        self.assertIn('path.name.endswith(".d.ts")', package_verifier)

    def test_launcher_and_runtime_identity(self):
        launcher = (COMPONENT / "bin/buzzard-agent").read_text(encoding="utf-8")
        self.assertIn("/usr/lib/buzzard-agent/app/node_modules/@earendil-works/pi-coding-agent/dist/cli.js", launcher)
        self.assertIn("extensions/buzzard-capabilities/index.ts", launcher)
        self.assertIn("extensions/web-access/index.ts", launcher)
        self.assertIn("/usr/bin/wildbuzzard", launcher)
        self.assertIn("--no-extensions", launcher)
        self.assertIn("PI_SKIP_VERSION_CHECK=1", launcher)
        self.assertIn("PI_TELEMETRY=0", launcher)
        suite_runner = (COMPONENT / "scripts/test-prepared-upstream.sh").read_text(encoding="utf-8")
        self.assertNotIn("export PI_SKIP_VERSION_CHECK", suite_runner)
        self.assertIn('BUZZARD_AGENT_DIR="$PI_WEB_AGENT_DIR"', launcher)
        self.assertIn('BUZZARD_AGENT_SESSION_DIR="$PI_WEB_AGENT_SESSION_DIR"', launcher)
        build = (COMPONENT / "build-deb.sh").read_text(encoding="utf-8")
        self.assertIn("extensions/buzzard-capabilities", build)
        self.assertIn("extensions/web-access", build)
        self.assertIn("app/skills", build)
        self.assertIn("-type d -exec chmod 0755", build)
        self.assertIn("-type f -exec chmod 0644", build)
        for provenance in (
            "EXTRACTION.toml",
            "pi-upstream.toml",
            "pi-source-manifest.sha256",
            "pi-web-access-upstream.toml",
        ):
            self.assertIn(provenance, build)
        self.assertLess(
            build.index('"$component_dir/scripts/build-runtime.sh"'),
            build.index('mkdir -p "$stage/usr/lib/buzzard-agent/app/extensions/buzzard-capabilities"'),
        )
        for obsolete in ("contracts.ts", "searxng.ts", "torrent.ts", "torrent-contracts.ts"):
            self.assertFalse((REPOSITORY / "extensions/web-access" / obsolete).exists())
            self.assertNotIn(obsolete, build)
        runtime = json.loads((COMPONENT / "runtime-package.json").read_text(encoding="utf-8"))
        self.assertEqual(runtime["name"], "buzzard-agent-runtime")
        self.assertEqual(runtime["piConfig"]["name"], "buzzard-agent")
        self.assertEqual(runtime["buzzardAgentUpstream"]["commit"], "53fa77ccd8a279eb87e92294ef3687b03ff80112")


if __name__ == "__main__":
    unittest.main()
