/* SPDX-License-Identifier: AGPL-3.0-or-later */

import assert from "node:assert/strict";
import test from "node:test";
import { discoveredSkillPaths } from "../index.ts";

test("discovers only installed optional capabilities", () => {
  const existing = new Set([
    "/usr/bin/wildbuzzard",
    "/repo/skills",
    "/usr/bin/buzzard-search",
    "/usr/share/buzzard-search/skills",
    "/usr/bin/buzzard-minijtt",
    "/usr/share/buzzard-minijtt/skills",
  ]);
  assert.deepEqual(
    discoveredSkillPaths("/repo/extensions/buzzard-capabilities", {}, path =>
      existing.has(path)
    ),
    [
      "/repo/skills",
      "/usr/share/buzzard-search/skills",
      "/usr/share/buzzard-minijtt/skills",
    ]
  );
});

test("accepts explicit skill roots without optional packages", () => {
  const separator = process.platform === "win32" ? ";" : ":";
  const environment = {
    BUZZARD_AGENT_SKILL_PATHS: [`/skills/one`, `/skills/two`].join(separator),
  };
  assert.deepEqual(
    discoveredSkillPaths("/repo/extensions/buzzard-capabilities", environment, path =>
      path.startsWith("/skills/")
    ),
    ["/skills/one", "/skills/two"]
  );
});
