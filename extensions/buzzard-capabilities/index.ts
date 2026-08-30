/* SPDX-License-Identifier: AGPL-3.0-or-later */

import { existsSync } from "node:fs";
import { delimiter, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

type InstalledCapability = {
  command: string;
  skillRoot: string;
};

const INSTALLED_CAPABILITIES: readonly InstalledCapability[] = [
  {
    command: "/usr/bin/buzzard-search",
    skillRoot: "/usr/share/buzzard-search/skills",
  },
  {
    command: "/usr/bin/buzzard-minijtt",
    skillRoot: "/usr/share/buzzard-minijtt/skills",
  },
];

export function discoveredSkillPaths(
  extensionDirectory = dirname(fileURLToPath(import.meta.url)),
  environment: NodeJS.ProcessEnv = process.env,
  exists: (path: string) => boolean = existsSync
): string[] {
  const paths: string[] = [];
  if (exists("/usr/bin/wildbuzzard")) {
    const bundledBrowserSkills = resolve(extensionDirectory, "..", "..", "skills");
    if (exists(bundledBrowserSkills)) paths.push(bundledBrowserSkills);
    if (exists("/usr/share/wildbuzzard/skills")) {
      paths.push("/usr/share/wildbuzzard/skills");
    }
  }
  for (const capability of INSTALLED_CAPABILITIES) {
    if (exists(capability.command) && exists(capability.skillRoot)) {
      paths.push(capability.skillRoot);
    }
  }
  for (const path of (environment.BUZZARD_AGENT_SKILL_PATHS || "")
    .split(delimiter)
    .filter(Boolean)) {
    if (exists(path)) paths.push(path);
  }
  return [...new Set(paths)];
}

export default function buzzardCapabilities(pi: ExtensionAPI) {
  pi.on("resources_discover", async () => ({
    skillPaths: discoveredSkillPaths(),
  }));
}
