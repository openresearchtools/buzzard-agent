/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Derived from pi-web-access. Copyright (c) 2025 Nico Bailon. */

import { createHash, randomUUID } from "node:crypto";
import type { ExtractedContent } from "./extract.ts";
import {
  clearStoredContentDatabase,
  deleteExpiredStoredContent,
  loadStoredContent,
  persistStoredContent,
} from "./database.ts";
import { sanitizePersistedUrl } from "./safe-output.ts";

export const RESULT_TTL_MS = 60 * 60 * 1000;
export const MAX_PAGE_CHARS = 30_000;

export interface StoredContent {
  id: string;
  sessionScope: string;
  type: "fetch" | "crawl";
  createdAt: number;
  expiresAt: number;
  documents: ExtractedContent[];
}

export interface StoredContentReference {
  id: string;
  sessionScope: string;
  type: StoredContent["type"];
  expiresAt: number;
}

interface SessionEntry {
  type: string;
  customType?: string;
  data?: unknown;
}

type PassageMode = "exact" | "case-insensitive" | "fuzzy" | "none";

const results = new Map<string, StoredContent>();

function sessionScope(sessionId: string): string {
  if (
    typeof sessionId !== "string" ||
    !sessionId ||
    sessionId.length > 512 ||
    /[\0-\x1f\x7f]/.test(sessionId)
  ) {
    throw new Error("Agent session identity is invalid");
  }
  return createHash("sha256")
    .update("buzzard-agent-web-content-session-v1\0")
    .update(sessionId)
    .digest("hex");
}

function resultKey(scope: string, id: string): string {
  return `${scope}:${id}`;
}

function isStoredContent(value: unknown): value is StoredContent {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const item = value as Partial<StoredContent>;
  return (
    typeof item.id === "string" &&
    typeof item.sessionScope === "string" &&
    /^[a-f0-9]{64}$/.test(item.sessionScope) &&
    ["fetch", "crawl"].includes(item.type ?? "") &&
    Number.isFinite(item.createdAt) &&
    Number.isFinite(item.expiresAt) &&
    Array.isArray(item.documents)
  );
}

function isStoredContentReference(
  value: unknown
): value is StoredContentReference {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const item = value as Partial<StoredContentReference>;
  return (
    Object.keys(item).length === 4 &&
    typeof item.id === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      item.id
    ) &&
    typeof item.sessionScope === "string" &&
    /^[a-f0-9]{64}$/.test(item.sessionScope) &&
    ["fetch", "crawl"].includes(item.type ?? "") &&
    Number.isFinite(item.expiresAt)
  );
}

export function storedContentReference(
  value: StoredContent
): StoredContentReference {
  return {
    id: value.id,
    sessionScope: value.sessionScope,
    type: value.type,
    expiresAt: value.expiresAt,
  };
}

export function createStoredDocuments(
  documents: ExtractedContent[],
  sessionId: string,
  type: "fetch" | "crawl" = "fetch",
  now = Date.now()
): StoredContent {
  return {
    id: randomUUID(),
    sessionScope: sessionScope(sessionId),
    type,
    createdAt: now,
    expiresAt: now + RESULT_TTL_MS,
    documents: documents.map(document => ({
      ...document,
      url: sanitizePersistedUrl(document.url),
      finalUrl: sanitizePersistedUrl(document.finalUrl),
    })),
  };
}

export function storeContent(value: StoredContent): void {
  purgeExpired();
  if (!isStoredContent(value)) {
    throw new Error("Stored web content is invalid");
  }
  results.set(resultKey(value.sessionScope, value.id), value);
  persistStoredContent(value);
}

export function getStoredContent(
  id: string,
  sessionId: string,
  now = Date.now()
): StoredContent {
  if (!/^[a-f0-9-]{36}$/i.test(id)) {
    throw new Error("Web content handle is invalid");
  }
  const scope = sessionScope(sessionId);
  const key = resultKey(scope, id);
  const loaded =
    results.get(key) ?? loadStoredContent(id, scope, now) ?? undefined;
  if (loaded && !isStoredContent(loaded)) {
    throw new Error("Stored web content is invalid");
  }
  const value = loaded;
  if (!value || value.expiresAt <= now) {
    results.delete(key);
    throw new Error("Web content handle is missing or expired");
  }
  if (value.sessionScope !== scope) {
    throw new Error("Web content handle is missing or expired");
  }
  results.set(key, value);
  return value;
}

export function restoreContent(
  entries: SessionEntry[],
  sessionId: string,
  now = Date.now()
): void {
  const scope = sessionScope(sessionId);
  for (const [key, value] of results) {
    if (value.sessionScope === scope) {
      results.delete(key);
    }
  }
  for (const entry of entries) {
    if (
      entry.type === "custom" &&
      entry.customType === "buzzard-agent-web-content" &&
      isStoredContentReference(entry.data) &&
      entry.data.sessionScope === scope &&
      entry.data.expiresAt > now
    ) {
      const stored = loadStoredContent(entry.data.id, scope, now);
      if (stored && isStoredContent(stored) && stored.type === entry.data.type) {
        results.set(resultKey(scope, stored.id), stored);
      }
    }
  }
}

export function purgeExpired(now = Date.now()): void {
  for (const [id, value] of results) {
    if (value.expiresAt <= now) {
      results.delete(id);
    }
  }
  deleteExpiredStoredContent(now);
}

export function hasStoredContent(
  sessionId: string,
  now = Date.now()
): boolean {
  purgeExpired(now);
  const scope = sessionScope(sessionId);
  return [...results.values()].some(value => value.sessionScope === scope);
}

function normalized(value: string): string {
  return value
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

function trigrams(value: string): Set<string> {
  const padded = `  ${normalized(value)}  `;
  const grams = new Set<string>();
  for (let index = 0; index + 3 <= padded.length; index++) {
    grams.add(padded.slice(index, index + 3));
  }
  return grams;
}

function similarity(left: Set<string>, right: Set<string>): number {
  if (!left.size || !right.size) {
    return 0;
  }
  let intersection = 0;
  for (const value of left) {
    if (right.has(value)) {
      intersection++;
    }
  }
  return (2 * intersection) / (left.size + right.size);
}

function fuzzyIndex(content: string, needle: string): number {
  const target = trigrams(needle);
  const width = Math.max(needle.length * 2, 160);
  const step = Math.max(40, Math.floor(width / 3));
  let best = { index: -1, score: 0 };
  for (let index = 0; index < content.length; index += step) {
    const score = similarity(
      target,
      trigrams(content.slice(index, index + width))
    );
    if (score > best.score) {
      best = { index, score };
    }
  }
  return best.score >= 0.42 ? best.index : -1;
}

function passage(
  content: string,
  needle: string
): { index: number; mode: PassageMode; text: string } {
  let index = content.indexOf(needle);
  let mode: PassageMode = "exact";
  if (index < 0) {
    index = content.toLocaleLowerCase().indexOf(needle.toLocaleLowerCase());
    mode = "case-insensitive";
  }
  if (index < 0) {
    index = fuzzyIndex(content, needle);
    mode = "fuzzy";
  }
  if (index < 0) {
    return { index: -1, mode: "none", text: "" };
  }
  const start = Math.max(0, index - 240);
  const end = Math.min(content.length, index + needle.length + 760);
  return { index, mode, text: content.slice(start, end) };
}

export function pageStoredContent(
  value: StoredContent,
  options: {
    url?: string;
    offset?: number;
    limit?: number;
    findText?: string[];
  }
): {
  responseId: string;
  offset: number;
  limit: number;
  totalCharacters: number;
  content: string;
  passages: Array<{
    findText: string;
    index: number;
    mode: PassageMode;
    text: string;
  }>;
} {
  const selected = options.url
    ? value.documents.filter(
        item => item.url === options.url || item.finalUrl === options.url
      )
    : value.documents;
  if (!selected.length) {
    throw new Error("No stored content matched the requested URL");
  }
  const serialized = JSON.stringify(selected, null, 2);
  const offset = options.offset ?? 0;
  const limit = options.limit ?? MAX_PAGE_CHARS;
  if (!Number.isInteger(offset) || offset < 0 || offset > serialized.length) {
    throw new Error("offset is outside the stored content");
  }
  if (!Number.isInteger(limit) || limit < 1 || limit > MAX_PAGE_CHARS) {
    throw new Error(`limit must be an integer from 1 to ${MAX_PAGE_CHARS}`);
  }
  const needles = options.findText ?? [];
  if (needles.length > 10) {
    throw new Error("findText accepts at most 10 values");
  }
  const passages = needles.map(value => {
    if (typeof value !== "string" || !value.trim() || value.length > 500) {
      throw new Error(
        "findText values must be non-empty strings up to 500 characters"
      );
    }
    return { findText: value, ...passage(serialized, value) };
  });
  return {
    responseId: value.id,
    offset,
    limit,
    totalCharacters: serialized.length,
    content: serialized.slice(offset, offset + limit),
    passages,
  };
}

export function clearStoredContent(): void {
  results.clear();
  clearStoredContentDatabase();
}
