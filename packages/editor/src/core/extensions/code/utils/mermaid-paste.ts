/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const MERMAID_FIRST_LINE =
  /^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram-v2|stateDiagram|erDiagram|gantt|pie|journey|gitGraph|C4Context|mindmap|timeline|sankey-beta|xychart-beta|block-beta)\b/i;

const MERMAID_FENCE = /^```\s*mermaid\s*\n?([\s\S]*?)```?\s*$/i;

export function normalizePastedPlainText(text: string): string {
  return text.replace(/\r\n?/g, "\n");
}

export function extractMermaidFromPaste(text: string): string | null {
  const normalized = normalizePastedPlainText(text).trim();
  if (!normalized) return null;

  const fenceMatch = normalized.match(MERMAID_FENCE);
  if (fenceMatch) {
    return fenceMatch[1].trim();
  }

  const firstLine = normalized.split("\n")[0]?.trim() ?? "";
  if (MERMAID_FIRST_LINE.test(firstLine)) {
    return normalized;
  }

  return null;
}

export function isMermaidLanguage(language: string | null | undefined): boolean {
  return language === "mermaid";
}
