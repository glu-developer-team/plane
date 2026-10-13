import type { Node as ProseMirrorNode } from "@tiptap/pm/model";

export const resolvePageCommentRange = (
  doc: ProseMirrorNode,
  selectedText: string,
  selectionFrom: number | null,
  selectionTo: number | null
): { from: number; to: number } | undefined => {
  if (!selectedText) return undefined;

  const matchesText = (from: number, to: number) => doc.textBetween(from, to, "", "\uFFFC") === selectedText;
  if (
    selectionFrom !== null &&
    selectionTo !== null &&
    Number.isInteger(selectionFrom) &&
    Number.isInteger(selectionTo) &&
    selectionFrom >= 0 &&
    selectionFrom < selectionTo &&
    selectionTo <= doc.content.size &&
    matchesText(selectionFrom, selectionTo)
  ) {
    return { from: selectionFrom, to: selectionTo };
  }

  const matches: { from: number; to: number }[] = [];
  doc.descendants((node, position) => {
    if (!node.isTextblock) return;

    const text = node.textBetween(0, node.content.size, "", "\uFFFC");
    let offset = text.indexOf(selectedText);
    while (offset !== -1) {
      const from = position + 1 + offset;
      const to = from + selectedText.length;
      if (matchesText(from, to)) matches.push({ from, to });
      offset = text.indexOf(selectedText, offset + 1);
    }

    return false;
  });

  return matches.length === 1 ? matches[0] : undefined;
};
