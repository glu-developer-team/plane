/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { normalizeMermaidSource } from "./normalize-mermaid-source";

const MERMAID_FIRST_LINE =
  /^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram-v2|stateDiagram|erDiagram|gantt|pie|journey|gitGraph|C4Context|mindmap|timeline|sankey-beta|xychart-beta|block-beta)\b/i;

export function normalizePastedPlainText(text: string): string {
  return text.replace(/\r\n?/g, "\n");
}

export function extractMermaidFromPaste(text: string): string | null {
  const normalized = normalizePastedPlainText(text).trim();
  if (!normalized) return null;

  const mermaidSource = normalizeMermaidSource(normalized);
  if (!mermaidSource) return null;

  const firstLine = mermaidSource.split("\n")[0]?.trim() ?? "";
  if (MERMAID_FIRST_LINE.test(firstLine)) {
    return mermaidSource;
  }

  return null;
}
