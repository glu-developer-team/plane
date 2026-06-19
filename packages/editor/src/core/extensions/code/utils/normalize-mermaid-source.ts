/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const MERMAID_FENCE = /^```\s*mermaid\s*\n?([\s\S]*?)```?\s*$/i;
const MERMAID_FIRST_LINE =
  /^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram-v2|stateDiagram|erDiagram|gantt|pie|journey|gitGraph|C4Context|mindmap|timeline|sankey-beta|xychart-beta|block-beta)\b/i;

export function decodeHtmlEntities(text: string): string {
  if (!text.includes("&")) return text;

  const textarea = document.createElement("textarea");
  textarea.innerHTML = text;
  let decoded = textarea.value;

  // Handle double-encoded entities from HTML sanitization round-trips.
  if (decoded.includes("&")) {
    textarea.innerHTML = decoded;
    decoded = textarea.value;
  }

  return decoded;
}

export function stripMermaidFences(text: string): string {
  const trimmed = text.trim();
  const fenceMatch = trimmed.match(MERMAID_FENCE);
  if (fenceMatch) {
    return fenceMatch[1].trim();
  }

  return trimmed
    .replace(/^```\s*mermaid\s*\n?/i, "")
    .replace(/\n?```\s*$/i, "")
    .trim();
}

export function normalizeMermaidSource(text: string): string {
  return stripMermaidFences(decodeHtmlEntities(text)).trim();
}

export function looksLikeMermaidSource(text: string): boolean {
  const normalized = normalizeMermaidSource(text);
  if (!normalized) return false;

  const firstLine = normalized.split("\n")[0]?.trim() ?? "";
  if (MERMAID_FIRST_LINE.test(firstLine)) {
    return true;
  }

  return /(-->|---|-\)|--\)|\[[^\]]+\]|\([^)]+\)|\[[^\]]+\])/.test(normalized);
}

export function looksLikeMermaidLine(text: string): boolean {
  const line = text.trim();
  if (!line) return false;
  if (line.startsWith("```")) return true;
  if (MERMAID_FIRST_LINE.test(line)) return true;

  return (
    /^[\w-]+\s*(---|-->|-\.->|--o|--x|-\)|--\))\s*[\w-]+/.test(line) ||
    /^[\w-]+\s*[[({][^\])}]*[\])}]/.test(line)
  );
}

export function isMermaidLanguage(language: string | null | undefined): boolean {
  return language === "mermaid";
}
