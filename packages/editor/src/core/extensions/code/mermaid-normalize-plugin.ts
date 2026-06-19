/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Node as ProseMirrorNode, Schema } from "@tiptap/pm/model";
import type { EditorState, Transaction } from "@tiptap/pm/state";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { looksLikeMermaidLine, looksLikeMermaidSource, normalizeMermaidSource } from "./utils/normalize-mermaid-source";

function collectParagraphText(node: ProseMirrorNode): string {
  return node.textContent.replace(/\r\n?/g, "\n");
}

function isMermaidFragmentNode(node: ProseMirrorNode): boolean {
  if (node.type.name === "codeBlock") {
    return looksLikeMermaidSource(node.textContent);
  }

  if (node.type.name === "paragraph") {
    const text = collectParagraphText(node);
    const lines = text.split("\n").filter((line) => line.trim().length > 0);
    return lines.length > 0 && lines.every((line) => looksLikeMermaidLine(line));
  }

  return false;
}

function isMermaidSeedNode(node: ProseMirrorNode): boolean {
  if (node.type.name !== "codeBlock") return false;

  if (node.attrs.language === "mermaid") return true;

  return looksLikeMermaidSource(node.textContent);
}

type TMermaidRepairRange = {
  from: number;
  mergedSource: string;
  to: number;
};

function findMermaidRepairRanges(doc: ProseMirrorNode): TMermaidRepairRange[] {
  const ranges: TMermaidRepairRange[] = [];

  for (let index = 0; index < doc.childCount; index += 1) {
    const node = doc.child(index);
    if (!isMermaidSeedNode(node)) continue;

    const parts = [normalizeMermaidSource(node.textContent)];
    let endIndex = index + 1;

    while (endIndex < doc.childCount) {
      const sibling = doc.child(endIndex);
      if (!isMermaidFragmentNode(sibling)) break;

      const siblingText =
        sibling.type.name === "paragraph" ? collectParagraphText(sibling) : normalizeMermaidSource(sibling.textContent);

      if (siblingText.trim()) {
        parts.push(siblingText.trim());
      }

      endIndex += 1;
    }

    const mergedSource = parts.filter(Boolean).join("\n");
    const normalizedCurrent = normalizeMermaidSource(node.textContent);
    const shouldMerge = endIndex > index + 1;
    const shouldNormalize = mergedSource !== normalizedCurrent;

    if (!shouldMerge && !shouldNormalize) continue;

    let from = 0;
    for (let i = 0; i < index; i += 1) {
      from += doc.child(i).nodeSize;
    }

    let to = from;
    for (let i = index; i < endIndex; i += 1) {
      to += doc.child(i).nodeSize;
    }

    ranges.push({ from, to, mergedSource });
    index = endIndex - 1;
  }

  return ranges;
}

function normalizeMermaidBlocks(doc: ProseMirrorNode, schema: Schema, tr: Transaction): boolean {
  let changed = false;

  doc.descendants((node, pos) => {
    if (node.type.name !== "codeBlock" || node.attrs.language !== "mermaid") {
      return;
    }

    const normalized = normalizeMermaidSource(node.textContent);
    if (normalized === node.textContent) {
      return;
    }

    const from = pos + 1;
    const to = pos + node.nodeSize - 1;
    tr.replaceWith(from, to, normalized ? schema.text(normalized) : []);
    changed = true;
  });

  return changed;
}

export function MermaidNormalizePlugin() {
  return new Plugin({
    key: new PluginKey("mermaidNormalize"),
    appendTransaction: (_transactions, _oldState, newState: EditorState) => {
      const { schema } = newState;
      const codeBlockType = schema.nodes.codeBlock;
      if (!codeBlockType) return null;

      const repairRanges = findMermaidRepairRanges(newState.doc);
      if (repairRanges.length === 0) {
        const tr = newState.tr;
        return normalizeMermaidBlocks(newState.doc, schema, tr) ? tr : null;
      }

      let tr = newState.tr;

      for (const range of repairRanges.toReversed()) {
        const mergedNode = codeBlockType.create(
          { language: "mermaid" },
          range.mergedSource ? schema.text(range.mergedSource) : undefined
        );
        tr.replaceWith(range.from, range.to, mergedNode);
      }

      normalizeMermaidBlocks(tr.doc, schema, tr);

      return tr.docChanged ? tr : null;
    },
  });
}
