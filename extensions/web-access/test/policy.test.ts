/* SPDX-License-Identifier: AGPL-3.0-or-later */

import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));

test("web-access has only the audited deterministic dependency surface", () => {
  const packageJson = JSON.parse(
    readFileSync(join(root, "package.json"), "utf8")
  ) as { dependencies: Record<string, string> };
  assert.deepEqual(Object.keys(packageJson.dependencies).sort(), [
    "@earendil-works/pi-ai",
    "@mozilla/readability",
    "linkedom",
    "p-limit",
    "promise.try",
    "turndown",
    "typebox",
    "unpdf",
  ]);
  const bannedModules =
    /(?:exa|brave|firecrawl|gemini|jina|kagi|ollama|parallel|perplexity|search1api|tavily|tinyfish)/i;
  assert.deepEqual(
    readdirSync(root).filter(
      name => name.endsWith(".ts") && bannedModules.test(name)
    ),
    []
  );
});

test("content tool schemas reject undeclared properties without search adapters", () => {
  const source = readFileSync(join(root, "index.ts"), "utf8");
  assert.equal(source.match(/additionalProperties:\s*false/g)?.length, 3);
  assert.doesNotMatch(source, /resources_discover|web_search|torrent_search|native_search/);
});

test("web-access delegates browser operations to the installed Wild Buzzard CLI", () => {
  const client = readFileSync(join(root, "wildbuzzard-cli.ts"), "utf8");
  assert.match(client, /\/usr\/bin\/wildbuzzard/);
  assert.doesNotMatch(client, /browser-control\.json|token|TCPServerSocket/);
});

test("active browser-content sources contain no private Gecko transport", () => {
  const source = readdirSync(root)
    .filter(name => name.endsWith(".ts"))
    .map(name => readFileSync(join(root, name), "utf8"))
    .join("\n");
  assert.doesNotMatch(
    source,
    /WILDBUZZARD_(?:BROWSER_CONTROL|SEARCH_CONNECTION)_FILE|browser-control\.json|TCPServerSocket|ChromeUtils|resource:\/\/|chrome:\/\//
  );
});

test("credential-bearing documents do not receive durable response handles", () => {
  const source = readFileSync(join(root, "index.ts"), "utf8");
  assert.match(source, /hasSensitiveUrlCredentials\(document\.url\)/);
  assert.match(source, /hasSensitiveUrlCredentials\(document\.finalUrl\)/);
  assert.match(source, /persistence:\s*"suppressed-sensitive-url"/);
  assert.match(source, /responseId:\s*null/);
});
