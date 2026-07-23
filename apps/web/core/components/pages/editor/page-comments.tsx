/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { MessageSquare, Quote, X } from "lucide-react";
import type { EditorRefApi, TEditorCommentAnchorRect, TEditorCommentSelection } from "@plane/editor";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import type { TPageComment } from "@plane/types";
import { Avatar, Button, TextArea } from "@plane/ui";
import { calculateTimeAgo, getFileURL } from "@plane/utils";
import { ProjectPageService } from "@/services/page";

type Props = {
  editorRef: React.RefObject<EditorRefApi>;
  pageId: string;
  projectId: string;
  workspaceSlug: string;
};

type TPopover =
  | { type: "compose"; selection: TEditorCommentSelection }
  | { type: "detail"; commentId: string; rect: TEditorCommentAnchorRect };

export type TPageCommentsRef = {
  openInlineComment: (commentId: string, rect: TEditorCommentAnchorRect) => void;
  startInlineComment: (selection: TEditorCommentSelection) => void;
};

const CommentAuthor = ({ item }: { item: TPageComment }) => (
  <div className="flex min-w-0 items-center gap-2">
    <Avatar size="sm" src={getFileURL(item.actor_detail?.avatar_url ?? "")} name={item.actor_detail?.display_name} />
    <span className="truncate text-13 font-medium text-primary">
      {item.actor_detail?.display_name ?? "Deactivated user"}
    </span>
    <span className="flex-shrink-0 text-11 text-tertiary">{calculateTimeAgo(item.created_at)}</span>
  </div>
);

export const PageComments = forwardRef<TPageCommentsRef, Props>(function PageComments(
  { editorRef, pageId, projectId, workspaceSlug },
  ref
) {
  const service = useMemo(() => new ProjectPageService(), []);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [comments, setComments] = useState<TPageComment[]>([]);
  const [pageComment, setPageComment] = useState("");
  const [inlineComment, setInlineComment] = useState("");
  const [popover, setPopover] = useState<TPopover | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchComments = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await service.fetchComments(workspaceSlug, projectId, pageId);
      setComments(data);
      return data;
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Could not load comments",
        message: "Please refresh the page and try again.",
      });
      return [];
    } finally {
      setIsLoading(false);
    }
  }, [pageId, projectId, service, workspaceSlug]);

  useEffect(() => {
    setPopover(null);
    setPageComment("");
    setInlineComment("");
    void fetchComments();
  }, [fetchComments]);

  useImperativeHandle(
    ref,
    () => ({
      startInlineComment: (selection) => {
        setInlineComment("");
        setPopover({ type: "compose", selection });
      },
      openInlineComment: (commentId, rect) => {
        setPopover({ type: "detail", commentId, rect });
        if (!comments.some((item) => item.id === commentId)) void fetchComments();
      },
    }),
    [comments, fetchComments]
  );

  useEffect(() => {
    if (!popover) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPopover(null);
    };
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!popoverRef.current?.contains(event.target as Node)) setPopover(null);
    };
    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("mousedown", closeOnOutsideClick);
    };
  }, [popover]);

  const submitPageComment = async () => {
    const text = pageComment.trim();
    if (!text) return;
    setIsSubmitting(true);
    try {
      const created = await service.createComment(workspaceSlug, projectId, pageId, {
        comment: text,
        selected_text: "",
        selection_from: null,
        selection_to: null,
        is_inline: false,
      });
      setComments((current) => [...current, created]);
      setPageComment("");
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Could not add comment", message: "Please try again." });
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitInlineComment = async () => {
    if (popover?.type !== "compose") return;
    const text = inlineComment.trim();
    if (!text) return;
    setIsSubmitting(true);
    try {
      const { selection } = popover;
      const created = await service.createComment(workspaceSlug, projectId, pageId, {
        comment: text,
        selected_text: selection.text,
        selection_from: selection.from,
        selection_to: selection.to,
        is_inline: true,
      });
      const marked = editorRef.current?.addPageCommentMark(created.id, selection.from, selection.to);
      setComments((current) => [...current, created]);
      setPopover(null);
      setInlineComment("");
      setToast({
        type: marked ? TOAST_TYPE.SUCCESS : TOAST_TYPE.ERROR,
        title: marked ? "Inline comment added" : "Comment saved, but the text changed",
        message: marked ? "The passage is now highlighted." : "Refresh and select the passage again.",
      });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Could not add comment", message: "Please try again." });
    } finally {
      setIsSubmitting(false);
    }
  };

  const directComments = comments.filter((item) => !item.is_inline);
  const activeComment = popover?.type === "detail" ? comments.find((item) => item.id === popover.commentId) : undefined;
  const anchorRect = popover?.type === "compose" ? popover.selection.rect : popover?.rect;
  const popoverStyle = anchorRect
    ? {
        left: Math.max(16, Math.min(anchorRect.left, window.innerWidth - 352)),
        top: Math.max(16, Math.min(anchorRect.bottom + 10, window.innerHeight - 300)),
      }
    : undefined;

  return (
    <>
      {popover && popoverStyle && (
        <div
          ref={popoverRef}
          role="dialog"
          aria-label={popover.type === "compose" ? "Add inline comment" : "Comment details"}
          style={popoverStyle}
          className="fixed z-50 w-[336px] overflow-hidden rounded-xl border border-subtle bg-surface-1 shadow-raised-300"
        >
          <div className="flex items-center justify-between border-b border-subtle-1 px-4 py-3">
            <span className="text-13 font-semibold text-primary">
              {popover.type === "compose" ? "Comment on selection" : "Comment"}
            </span>
            <button
              type="button"
              aria-label="Close"
              onClick={() => setPopover(null)}
              className="grid size-7 place-items-center rounded-md text-tertiary hover:bg-layer-1 hover:text-primary"
            >
              <X className="size-4" />
            </button>
          </div>
          {popover.type === "compose" ? (
            <div className="p-4">
              <div className="bg-amber-50 text-amber-950 mb-3 flex max-h-24 gap-2 overflow-y-auto rounded-lg px-3 py-2.5">
                <Quote className="text-amber-700 mt-0.5 size-4 flex-shrink-0" aria-hidden="true" />
                <p className="text-12 whitespace-pre-wrap">{popover.selection.text}</p>
              </div>
              <TextArea
                value={inlineComment}
                onChange={(event) => setInlineComment(event.target.value)}
                placeholder="Write a comment…"
                maxLength={5000}
                className="min-h-24"
              />
              <div className="mt-3 flex justify-end gap-2">
                <Button variant="neutral-primary" size="sm" onClick={() => setPopover(null)}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  loading={isSubmitting}
                  disabled={!inlineComment.trim()}
                  onClick={submitInlineComment}
                >
                  Comment
                </Button>
              </div>
            </div>
          ) : activeComment ? (
            <div className="p-4">
              <CommentAuthor item={activeComment} />
              <blockquote className="bg-amber-50 text-amber-950 mt-3 rounded-lg px-3 py-2.5 text-12 whitespace-pre-wrap">
                {activeComment.selected_text}
              </blockquote>
              <p className="mt-3 text-13 whitespace-pre-wrap text-primary">{activeComment.comment}</p>
            </div>
          ) : (
            <p className="p-6 text-center text-13 text-tertiary">Loading comment…</p>
          )}
        </div>
      )}

      <section className="mt-10 border-t border-subtle-1 pt-6 pb-24">
        <div className="mb-4 flex items-center gap-2">
          <MessageSquare className="size-4 text-secondary" aria-hidden="true" />
          <h2 className="text-15 font-semibold text-primary">Comments</h2>
          <span className="text-12 text-tertiary">{directComments.length}</span>
        </div>

        <div className="mb-6 rounded-xl border border-subtle-1 bg-layer-1 p-3">
          <TextArea
            value={pageComment}
            onChange={(event) => setPageComment(event.target.value)}
            placeholder="Write a comment on this page…"
            maxLength={5000}
            className="min-h-20 bg-surface-1"
          />
          <div className="mt-3 flex justify-end">
            <Button
              variant="primary"
              size="sm"
              loading={isSubmitting}
              disabled={!pageComment.trim()}
              onClick={submitPageComment}
            >
              Add comment
            </Button>
          </div>
        </div>

        {isLoading ? (
          <p className="py-6 text-center text-13 text-tertiary">Loading comments…</p>
        ) : directComments.length === 0 ? (
          <div className="rounded-lg border border-dashed border-subtle-1 px-4 py-7 text-center">
            <p className="text-13 font-medium text-secondary">No page comments yet</p>
            <p className="mt-1 text-12 text-tertiary">Start the conversation above.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {directComments.map((item) => (
              <article key={item.id} className="rounded-xl border border-subtle-1 bg-surface-1 p-4">
                <CommentAuthor item={item} />
                {item.selected_text && (
                  <blockquote className="mt-3 rounded-lg bg-layer-1 px-3 py-2 text-12 whitespace-pre-wrap text-tertiary">
                    {item.selected_text}
                  </blockquote>
                )}
                <p className="mt-3 text-13 whitespace-pre-wrap text-primary">{item.comment}</p>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
});
