/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Mark, mergeAttributes } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
// types
import type { TEditorCommentAnchorRect, TEditorCommentHandler } from "@/types";

const COMMENT_MARK_NAME = "pageComment";

const getRect = (element: HTMLElement): TEditorCommentAnchorRect => {
  const rect = element.getBoundingClientRect();
  return {
    bottom: rect.bottom,
    height: rect.height,
    left: rect.left,
    right: rect.right,
    top: rect.top,
    width: rect.width,
  };
};

export const PageCommentExtension = (commentHandler?: TEditorCommentHandler) =>
  Mark.create({
    name: COMMENT_MARK_NAME,
    inclusive: false,

    addAttributes() {
      return {
        commentId: {
          default: null,
          parseHTML: (element) => element.getAttribute("data-page-comment-id"),
          renderHTML: ({ commentId }) => (commentId ? { "data-page-comment-id": commentId } : {}),
        },
      };
    },

    parseHTML() {
      return [{ tag: "span[data-page-comment-id]" }];
    },

    renderHTML({ HTMLAttributes }) {
      return ["span", mergeAttributes(HTMLAttributes, { class: "page-comment-highlight" }), 0];
    },

    addProseMirrorPlugins() {
      return [
        new Plugin({
          key: new PluginKey("page-comment-anchors"),
          props: {
            decorations: (state) => {
              const endpoints = new Map<string, number>();

              state.doc.descendants((node, position) => {
                if (!node.isText) return;
                const commentMark = node.marks.find((mark) => mark.type.name === COMMENT_MARK_NAME);
                const commentId = commentMark?.attrs.commentId as string | undefined;
                if (!commentId) return;
                endpoints.set(commentId, Math.max(endpoints.get(commentId) ?? 0, position + node.nodeSize));
              });

              return DecorationSet.create(
                state.doc,
                Array.from(endpoints.entries()).map(([commentId, position]) =>
                  Decoration.widget(
                    position,
                    () => {
                      const button = document.createElement("button");
                      button.type = "button";
                      button.className = "page-comment-anchor";
                      button.contentEditable = "false";
                      button.setAttribute("aria-label", "Open comment");
                      button.setAttribute("title", "Open comment");
                      button.setAttribute("data-page-comment-anchor", commentId);
                      button.innerHTML =
                        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a8 8 0 0 1-8 8H6l-4 3V12a8 8 0 1 1 19 0Z"/><path d="M8 12h.01M12 12h.01M16 12h.01"/></svg>';
                      button.addEventListener("mousedown", (event) => event.preventDefault());
                      button.addEventListener("click", (event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        commentHandler?.onOpenInlineComment?.(commentId, getRect(button));
                      });
                      return button;
                    },
                    { key: commentId, side: 1 }
                  )
                )
              );
            },
          },
        }),
      ];
    },
  });
