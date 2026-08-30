/* SPDX-License-Identifier: AGPL-3.0-or-later */

import assert from "node:assert/strict";
import test from "node:test";
import { WEB_TOOL_NAMES } from "../activation.ts";

test("only browser-content tools are managed by the runtime adapter", () => {
  assert.deepEqual(WEB_TOOL_NAMES, [
    "fetch_content",
    "crawl_content",
    "get_web_content",
  ]);
});
