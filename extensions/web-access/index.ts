/* SPDX-License-Identifier: AGPL-3.0-or-later */

import { existsSync } from "node:fs";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import pLimit from "p-limit";
import { Type } from "typebox";
import { WEB_TOOL_NAMES } from "./activation.ts";
import {
  crawlWithGecko,
  type CrawlInput,
  type CrawlProgress,
} from "./crawl.ts";
import {
  fetchWithGecko,
  normalizeFetchInput,
  type ExtractedContent,
  type FetchInput,
} from "./extract.ts";
import { extractGitHub, parseGitHubUrl } from "./github.ts";
import { answerFromPage } from "./page-answer.ts";
import {
  hasSensitiveUrlCredentials,
  redactSensitiveText,
  sanitizeAgentOutput,
} from "./safe-output.ts";
import { SessionGeneration } from "./session-generation.ts";
import {
  createStoredDocuments,
  getStoredContent,
  pageStoredContent,
  restoreContent,
  storedContentReference,
  storeContent,
} from "./storage.ts";
import { extractYouTubeCaptions, parseYouTubeUrl } from "./youtube.ts";

function toolResult(value: unknown, details = value) {
  const safeValue = sanitizeAgentOutput(value);
  return {
    content: [
      {
        type: "text" as const,
        text: `[UNTRUSTED_WEB_DATA]\n${JSON.stringify(safeValue, null, 2)}\n[END_UNTRUSTED_WEB_DATA]`,
      },
    ],
    details: sanitizeAgentOutput(details),
  };
}

function persistDocuments(
  pi: ExtensionAPI,
  documents: ExtractedContent[],
  sessionId: string,
  type: "fetch" | "crawl" = "fetch"
) {
  if (
    documents.some(
      document =>
        hasSensitiveUrlCredentials(document.url) ||
        hasSensitiveUrlCredentials(document.finalUrl)
    )
  ) {
    return {
      responseId: null,
      expiresAt: null,
      persistence: "suppressed-sensitive-url" as const,
    };
  }
  const stored = createStoredDocuments(documents, sessionId, type);
  storeContent(stored);
  pi.appendEntry("buzzard-agent-web-content", storedContentReference(stored));
  return {
    responseId: stored.id,
    expiresAt: stored.expiresAt,
    persistence: "stored" as const,
  };
}

export default function webAccess(pi: ExtensionAPI) {
  const sessions = new SessionGeneration();

  const sessionIdFor = (context: {
    sessionManager: { getSessionId(): string };
  }) => {
    const sessionId = context.sessionManager.getSessionId();
    if (!sessionId) throw new Error("Agent session identity is unavailable");
    return sessionId;
  };
  const beginOperation = (context: {
    sessionManager: { getSessionId(): string };
  }) => sessions.begin(sessionIdFor(context));
  const restoreSession = (context: {
    sessionManager: {
      getSessionId(): string;
      getBranch(): Array<{ type: string; customType?: string; data?: unknown }>;
    };
  }) => {
    const sessionId = sessionIdFor(context);
    sessions.select(sessionId);
    restoreContent(context.sessionManager.getBranch(), sessionId);
  };
  const activate = () => {
    const managed = new Set(WEB_TOOL_NAMES);
    pi.setActiveTools([
      ...pi.getActiveTools().filter(name => !managed.has(name)),
      ...WEB_TOOL_NAMES,
    ]);
  };

  pi.on("session_start", (_event, context) => {
    restoreSession(context);
    activate();
  });
  pi.on("before_agent_start", (_event, context) => {
    restoreSession(context);
    activate();
  });

  pi.registerTool(
    defineTool({
      name: "fetch_content",
      label: "Fetch web content",
      description:
        "Render HTTP(S) pages through the installed browser CLI and extract bounded readable content. Credential-bearing URLs are never persisted.",
      parameters: Type.Object(
        {
          url: Type.Optional(Type.String({ maxLength: 4096 })),
          urls: Type.Optional(
            Type.Array(Type.String({ maxLength: 4096 }), {
              minItems: 1,
              maxItems: 20,
            })
          ),
          forceClone: Type.Optional(Type.Boolean()),
          mode: Type.Optional(
            Type.Union([
              Type.Literal("readable"),
              Type.Literal("raw"),
              Type.Literal("answer"),
            ])
          ),
          prompt: Type.Optional(Type.String({ maxLength: 4000 })),
          answerModel: Type.Optional(Type.String({ maxLength: 300 })),
          timestamp: Type.Optional(Type.String({ maxLength: 100 })),
          frames: Type.Optional(Type.Integer({ minimum: 1, maximum: 12 })),
        },
        { additionalProperties: false }
      ),
      executionMode: "sequential",
      async execute(_id, params, signal, _update, context) {
        const operation = beginOperation(context);
        const input = normalizeFetchInput(params as FetchInput);
        if (input.forceClone && input.urls.some(url => !parseGitHubUrl(url))) {
          throw new Error(
            "forceClone accepts only public github.com repository, tree, or blob URLs"
          );
        }
        if (input.forceClone && !existsSync("/usr/bin/git")) {
          throw new Error("forceClone requires the optional git package");
        }
        if (input.timestamp || input.frames) {
          throw new Error(
            "Timestamp and frame extraction are not included in the browser-content adapter"
          );
        }
        const fetchMode = input.mode === "answer" ? "readable" : input.mode;
        const render = (url: string) =>
          fetchWithGecko(
            url,
            fetchMode,
            context.cwd,
            operation.sessionId,
            signal
          );
        const extract = async (url: string): Promise<ExtractedContent> => {
          if (
            fetchMode !== "raw" &&
            parseGitHubUrl(url) &&
            existsSync("/usr/bin/git")
          ) {
            try {
              return await extractGitHub(url, signal);
            } catch (error) {
              if (input.forceClone) throw error;
              return render(url);
            }
          }
          if (
            fetchMode !== "raw" &&
            parseYouTubeUrl(url) &&
            existsSync("/usr/bin/yt-dlp")
          ) {
            try {
              const captions = await extractYouTubeCaptions(url, signal);
              if (!captions.error) return captions;
            } catch {}
          }
          return render(url);
        };
        const limit = pLimit(4);
        const extractedDocuments = await Promise.all(
          input.urls.map(url => limit(() => extract(url)))
        );
        const answerLimit = pLimit(4);
        const documents =
          input.mode === "answer"
            ? await Promise.all(
                extractedDocuments.map(document =>
                  answerLimit(async () => {
                    if (document.error) return document;
                    try {
                      const answer = await answerFromPage(
                        {
                          question: input.prompt!,
                          pageText: document.content,
                          sourceUrl: document.finalUrl,
                          model: input.answerModel,
                        },
                        context,
                        signal
                      );
                      return { ...document, content: answer.text, answer };
                    } catch (error) {
                      return {
                        ...document,
                        content: "",
                        error: redactSensitiveText(
                          error instanceof Error ? error.message : String(error),
                          1_000
                        ),
                      };
                    }
                  })
                )
              )
            : extractedDocuments;
        operation.assertCurrent();
        const stored = persistDocuments(pi, documents, operation.sessionId);
        return toolResult({
          responseId: stored.responseId,
          expiresAt: stored.expiresAt,
          persistence: stored.persistence,
          documents: documents.map(document => ({
            ...document,
            content: document.content.slice(0, 4_000),
            truncated: document.content.length > 4_000,
          })),
        });
      },
    })
  );

  pi.registerTool(
    defineTool({
      name: "crawl_content",
      label: "Crawl web content",
      description:
        "Crawl a bounded web scope through the installed browser CLI with robots handling, cancellation, and partial results.",
      parameters: Type.Object(
        {
          url: Type.String({ maxLength: 4096 }),
          includePaths: Type.Optional(
            Type.Array(Type.String({ minLength: 1, maxLength: 1000 }), {
              maxItems: 50,
            })
          ),
          excludePaths: Type.Optional(
            Type.Array(Type.String({ minLength: 1, maxLength: 1000 }), {
              maxItems: 50,
            })
          ),
          maxDepth: Type.Optional(Type.Integer({ minimum: 0, maximum: 8 })),
          limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 100 })),
          timeoutMs: Type.Optional(
            Type.Integer({ minimum: 1000, maximum: 300000 })
          ),
          maxBytes: Type.Optional(
            Type.Integer({ minimum: 65536, maximum: 104857600 })
          ),
          maxConcurrency: Type.Optional(
            Type.Integer({ minimum: 1, maximum: 8 })
          ),
          allowSubdomains: Type.Optional(Type.Boolean()),
          allowExternalLinks: Type.Optional(Type.Boolean()),
          robots: Type.Optional(
            Type.Union([Type.Literal("respect"), Type.Literal("ignore")])
          ),
          sitemap: Type.Optional(
            Type.Union([
              Type.Literal("include"),
              Type.Literal("skip"),
              Type.Literal("only"),
            ])
          ),
          ignoreQueryParameters: Type.Optional(Type.Boolean()),
          render: Type.Optional(
            Type.Union([
              Type.Literal("auto"),
              Type.Literal("never"),
              Type.Literal("always"),
            ])
          ),
        },
        { additionalProperties: false }
      ),
      executionMode: "sequential",
      async execute(_id, params, signal, update, context) {
        const operation = beginOperation(context);
        const result = await crawlWithGecko(
          params as CrawlInput,
          context.cwd,
          operation.sessionId,
          signal,
          undefined,
          typeof update === "function"
            ? (progress: CrawlProgress) => update(toolResult(progress, progress))
            : undefined
        );
        operation.assertCurrent();
        const stored = persistDocuments(
          pi,
          result.documents,
          operation.sessionId,
          "crawl"
        );
        return toolResult({
          ...result,
          responseId: stored.responseId,
          expiresAt: stored.expiresAt,
          persistence: stored.persistence,
          documents: result.documents.map(document => ({
            ...document,
            content: document.content.slice(0, 2_000),
            truncated: document.content.length > 2_000,
          })),
        });
      },
    })
  );

  pi.registerTool(
    defineTool({
      name: "get_web_content",
      label: "Get stored web content",
      description:
        "Read a bounded range or locate passages in a one-hour fetch or crawl response.",
      parameters: Type.Object(
        {
          responseId: Type.String({
            minLength: 36,
            maxLength: 36,
            pattern:
              "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
          }),
          url: Type.Optional(Type.String({ maxLength: 4096 })),
          offset: Type.Optional(Type.Integer({ minimum: 0 })),
          limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 30000 })),
          findText: Type.Optional(
            Type.Array(Type.String({ minLength: 1, maxLength: 500 }), {
              maxItems: 10,
            })
          ),
        },
        { additionalProperties: false }
      ),
      executionMode: "sequential",
      async execute(_id, params, _signal, _update, context) {
        const operation = beginOperation(context);
        return toolResult(
          pageStoredContent(
            getStoredContent(params.responseId, operation.sessionId),
            params
          )
        );
      },
    })
  );
}
