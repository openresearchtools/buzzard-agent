/* SPDX-License-Identifier: AGPL-3.0-or-later */

import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test, { after, before } from "node:test";
import { closeStoredContentDatabase } from "../database.ts";
import type { ExtractedContent } from "../extract.ts";
import {
  clearStoredContent,
  createStoredDocuments,
  getStoredContent,
  hasStoredContent,
  MAX_PAGE_CHARS,
  pageStoredContent,
  restoreContent,
  RESULT_TTL_MS,
  storedContentReference,
  storeContent,
} from "../storage.ts";

const databaseDirectory = mkdtempSync(
  join(tmpdir(), "buzzard-agent-content-storage-test-")
);
const previousDatabase = process.env.BUZZARD_AGENT_WEB_CONTENT_DATABASE;

before(() => {
  process.env.BUZZARD_AGENT_WEB_CONTENT_DATABASE = join(
    databaseDirectory,
    "web-content.sqlite"
  );
});

after(() => {
  closeStoredContentDatabase();
  if (previousDatabase === undefined) {
    delete process.env.BUZZARD_AGENT_WEB_CONTENT_DATABASE;
  } else {
    process.env.BUZZARD_AGENT_WEB_CONTENT_DATABASE = previousDatabase;
  }
  rmSync(databaseDirectory, { recursive: true });
});

function document(
  content = "A distinctive browser content passage about Gecko extraction."
): ExtractedContent {
  return {
    url: "https://example.test/docs",
    finalUrl: "https://example.test/docs",
    title: "Buzzard Agent documentation",
    content,
    error: null,
    mimeType: "text/plain",
    status: 200,
    provenance: "gecko",
    trust: "untrusted",
  };
}

test("content handles expire after one hour and restore only live entries", () => {
  clearStoredContent();
  const now = Date.now();
  const stored = createStoredDocuments([document()], "session-a", "fetch", now);
  storeContent(stored);
  assert.deepEqual(Object.keys(storedContentReference(stored)).sort(), [
    "expiresAt",
    "id",
    "sessionScope",
    "type",
  ]);
  assert.equal(hasStoredContent("session-a", now), true);
  restoreContent(
    [
      {
        type: "custom",
        customType: "buzzard-agent-web-content",
        data: storedContentReference(stored),
      },
    ],
    "session-a",
    now + 1
  );
  assert.equal(getStoredContent(stored.id, "session-a", now + 1).id, stored.id);
  assert.deepEqual(
    getStoredContent(stored.id, "session-a", now + RESULT_TTL_MS - 1),
    stored
  );
  assert.throws(
    () => getStoredContent(stored.id, "session-a", now + RESULT_TTL_MS),
    /missing or expired/
  );
  assert.equal(hasStoredContent("session-a", now + RESULT_TTL_MS), false);
});

test("stored content is bounded, selectable, and passage searchable", () => {
  const stored = createStoredDocuments([document()], "session-a");
  const page = pageStoredContent(stored, {
    url: "https://example.test/docs",
    offset: 0,
    limit: 80,
    findText: [
      "distinctive browser content passage",
      "GECKO EXTRACTION",
      "browser passage about Gecko extraction",
      "not present anywhere",
    ],
  });
  assert.equal(page.content.length, 80);
  assert.ok(page.totalCharacters > page.content.length);
  assert.equal(page.passages[0].mode, "exact");
  assert.equal(page.passages[1].mode, "case-insensitive");
  assert.equal(page.passages[2].mode, "fuzzy");
  assert.equal(page.passages[3].mode, "none");
  assert.throws(
    () => pageStoredContent(stored, { limit: MAX_PAGE_CHARS + 1 }),
    /1 to 30000/
  );
});

test("stored handles and restored references are isolated by agent session", () => {
  clearStoredContent();
  const stored = createStoredDocuments([document()], "session-a");
  storeContent(stored);
  assert.throws(
    () => getStoredContent(stored.id, "session-b"),
    /missing or expired/
  );
  assert.equal(hasStoredContent("session-b"), false);
  restoreContent(
    [
      {
        type: "custom",
        customType: "buzzard-agent-web-content",
        data: storedContentReference(stored),
      },
    ],
    "session-b"
  );
  assert.equal(hasStoredContent("session-b"), false);
  assert.equal(hasStoredContent("session-a"), true);
});

test("stored documents strip URL secrets", () => {
  const stored = createStoredDocuments(
    [
      {
        ...document("Fixture content"),
        url: "https://user:password@example.test/source?q=gecko&access_token=source-secret#token=fragment-secret&section=content",
        finalUrl: "https://example.test/final?page=2&api_key=final-secret",
      },
    ],
    "session-a"
  );
  const serialized = JSON.stringify(stored.documents);
  assert.doesNotMatch(
    serialized,
    /source-secret|fragment-secret|final-secret|user|password/
  );
  assert.match(serialized, /q=gecko/);
  assert.match(serialized, /page=2/);
  assert.match(serialized, /section=content/);
});

test("storage failures do not expose local database paths", () => {
  closeStoredContentDatabase();
  const invalidParent = join(databaseDirectory, "sensitive-parent");
  writeFileSync(invalidParent, "not a directory");
  process.env.BUZZARD_AGENT_WEB_CONTENT_DATABASE = join(
    invalidParent,
    "web-content.sqlite"
  );
  try {
    assert.throws(
      () => clearStoredContent(),
      error => {
        assert.equal(
          (error as Error).message,
          "Buzzard Agent web-content storage is unavailable"
        );
        assert.doesNotMatch((error as Error).message, /sensitive/);
        return true;
      }
    );
  } finally {
    closeStoredContentDatabase();
    process.env.BUZZARD_AGENT_WEB_CONTENT_DATABASE = join(
      databaseDirectory,
      "web-content.sqlite"
    );
  }
});
