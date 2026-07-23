/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { MessageSquare, Quote } from "lucide-react";
import type { EditorRefApi } from "@plane/editor";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import type { TPageComment } from "@plane/types";
import { Avatar, Button, TextArea } from "@plane/ui";
import { calculateTimeAgo, getFileURL } from "@plane/utils";
import { ProjectPageService } from "@/services/page";

type TSelection = {
  from: number;
  to: number;
  text: string;
};

type Props = {
  editorRef: React.RefObject<EditorRefApi>;
  pageId: string;
  projectId: string;
  workspaceSlug: string;
};

export function PageComments({ editorRef, pageId, projectId, workspaceSlug }: Props) {
  const service = useMemo(() => new ProjectPageService(), []);
  const [comments, setComments] = useState<TPageComment[]>([]);
  const [selection, setSelection] = useState<TSelection | null>(null);
  const [comment, setComment] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchComments = useCallback(async () => {
    setIsLoading(true);
    try {
      setComments(await service.fetchComments(workspaceSlug, projectId, pageId));
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Could not load comments",
        message: "Please refresh the page and try again.",
      });
    } finally {
      setIsLoading(false);
    }
  }, [pageId, projectId, service, workspaceSlug]);

  useEffect(() => {
    setSelection(null);
    setComment("");
    void fetchComments();
  }, [fetchComments]);

  const handleStartComment = () => {
    const selected = editorRef.current?.getSelection();
    if (!selected) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Select text first",
        message: "Highlight a line or passage in the page before adding a comment.",
      });
      return;
    }
    setSelection(selected);
  };

  const handleSubmit = async () => {
    const trimmedComment = comment.trim();
    if (!selection || !trimmedComment) return;

    setIsSubmitting(true);
    try {
      const createdComment = await service.createComment(workspaceSlug, projectId, pageId, {
        comment: trimmedComment,
        selected_text: selection.text,
        selection_from: selection.from,
        selection_to: selection.to,
      });
      setComments((current) => [...current, createdComment]);
      setSelection(null);
      setComment("");
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Comment added",
        message: "Your comment is now visible at the bottom of this page.",
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Could not add comment",
        message: "Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="border-subtle-1 mt-10 border-t pt-6 pb-24">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="size-4 text-secondary" aria-hidden="true" />
          <h2 className="text-15 font-semibold text-primary">Comments</h2>
          <span className="text-12 text-tertiary">{comments.length}</span>
        </div>
        <Button variant="neutral-primary" size="sm" onClick={handleStartComment}>
          Comment selected text
        </Button>
      </div>

      {selection && (
        <div className="border-subtle-1 bg-layer-1 mb-5 rounded-lg border p-3">
          <div className="mb-3 flex gap-2 rounded-md bg-surface-2 px-3 py-2">
            <Quote className="mt-0.5 size-4 flex-shrink-0 text-tertiary" aria-hidden="true" />
            <p className="line-clamp-4 whitespace-pre-wrap text-13 text-secondary">{selection.text}</p>
          </div>
          <TextArea
            autoFocus
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="Write a comment…"
            maxLength={5000}
            className="min-h-20"
          />
          <div className="mt-3 flex justify-end gap-2">
            <Button
              variant="neutral-primary"
              size="sm"
              onClick={() => {
                setSelection(null);
                setComment("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={isSubmitting}
              disabled={!comment.trim()}
              onClick={handleSubmit}
            >
              Add comment
            </Button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="py-6 text-center text-13 text-tertiary">Loading comments…</p>
      ) : comments.length === 0 ? (
        <div className="border-subtle-1 rounded-lg border border-dashed px-4 py-8 text-center">
          <p className="text-13 font-medium text-secondary">No comments yet</p>
          <p className="mt-1 text-12 text-tertiary">Select text in the page to start a discussion.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {comments.map((item) => (
            <article key={item.id} className="border-subtle-1 rounded-lg border p-4">
              <div className="mb-3 flex items-center gap-2">
                <Avatar
                  size="sm"
                  src={getFileURL(item.actor_detail?.avatar_url ?? "")}
                  name={item.actor_detail?.display_name}
                />
                <span className="text-13 font-medium text-primary">
                  {item.actor_detail?.display_name ?? "Deactivated user"}
                </span>
                <span className="text-11 text-tertiary">{calculateTimeAgo(item.created_at)}</span>
              </div>
              <blockquote className="border-accent-strong mb-3 border-l-2 pl-3 text-12 whitespace-pre-wrap text-tertiary">
                {item.selected_text}
              </blockquote>
              <p className="text-13 whitespace-pre-wrap text-primary">{item.comment}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
