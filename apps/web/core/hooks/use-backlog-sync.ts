/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useRef } from "react";
import useSWR from "swr";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IBacklogSyncJobStatus } from "@plane/types";
import { PROJECT_BACKLOG_SYNC } from "@/constants/backlog-sync";
import { backlogIntegrationService } from "@/services/integration/backlog.service";

const TERMINAL_STATUSES = new Set(["completed", "failed"]);

function backlogPullHasListChanges(stats: Record<string, unknown> | undefined): boolean {
  if (!stats) return false;
  return (
    Number(stats.created ?? 0) > 0 ||
    Number(stats.updated ?? 0) > 0 ||
    Number(stats.comments_created ?? 0) > 0 ||
    Number(stats.activities_created ?? 0) > 0
  );
}

function backlogPullHasIssueChanges(stats: Record<string, unknown> | undefined): boolean {
  if (!stats) return false;
  return (
    Number(stats.created ?? 0) > 0 ||
    Number(stats.updated ?? 0) > 0 ||
    Number(stats.comments_created ?? 0) > 0 ||
    Number(stats.activities_created ?? 0) > 0
  );
}

function markBacklogSyncSeen(projectId: string, completedAt: string) {
  sessionStorage.setItem(`backlog_sync:${projectId}`, completedAt);
}

async function pollJobUntilDone(
  workspaceSlug: string,
  projectId: string,
  jobId: string,
  signal: AbortSignal
): Promise<IBacklogSyncJobStatus | null> {
  while (!signal.aborted) {
    // eslint-disable-next-line no-await-in-loop -- poll Celery job until terminal status
    const status = await backlogIntegrationService.getJobStatus(workspaceSlug, projectId, jobId);
    if (TERMINAL_STATUSES.has(status.status)) {
      return status;
    }
    // eslint-disable-next-line no-await-in-loop -- wait between poll attempts
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return null;
}

type UseBacklogPullSyncOptions = {
  workspaceSlug: string;
  projectId: string;
  enabled: boolean;
  scope: "project" | "issue";
  issueId?: string;
  onComplete?: () => void;
  hasChanges?: (stats: Record<string, unknown> | undefined) => boolean;
};

export function useBacklogPullSync({
  workspaceSlug,
  projectId,
  enabled,
  scope,
  issueId,
  onComplete,
  hasChanges = scope === "issue" ? backlogPullHasIssueChanges : backlogPullHasListChanges,
}: UseBacklogPullSyncOptions) {
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const hasChangesRef = useRef(hasChanges);
  hasChangesRef.current = hasChanges;

  const triggerPull = useCallback(async () => {
    if (!enabled || !workspaceSlug || !projectId) return;
    if (scope === "issue" && !issueId) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await backlogIntegrationService.pull(workspaceSlug, projectId, {
        scope,
        issue_id: issueId,
      });
      const result = await pollJobUntilDone(workspaceSlug, projectId, response.job_id, controller.signal);
      if (!result || result.status === "failed") {
        if (result?.status === "failed") {
          setToast({
            type: TOAST_TYPE.ERROR,
            title: "Backlog sync failed",
            message: "Could not pull updates from Backlog.",
          });
        }
        return;
      }

      const syncState = await backlogIntegrationService.getSyncState(workspaceSlug, projectId);
      if (syncState.last_sync_completed_at) {
        markBacklogSyncSeen(projectId, syncState.last_sync_completed_at);
      }

      if (hasChangesRef.current(result.stats)) {
        onCompleteRef.current?.();
      }
    } catch {
      if (!controller.signal.aborted) {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Backlog sync failed",
          message: "Could not start Backlog pull.",
        });
      }
    }
  }, [enabled, workspaceSlug, projectId, scope, issueId]);

  useEffect(() => {
    if (!enabled) return;

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      triggerPull();
    }, 5000);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      abortRef.current?.abort();
    };
  }, [enabled, workspaceSlug, projectId, scope, issueId, triggerPull]);
}

export function useBacklogSyncConfig(workspaceSlug: string, projectId: string) {
  const { data, mutate, isLoading } = useSWR(
    workspaceSlug && projectId ? PROJECT_BACKLOG_SYNC(workspaceSlug, projectId) : null,
    () => backlogIntegrationService.getConfig(workspaceSlug, projectId),
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  return {
    config: data,
    enabled: Boolean(data?.enabled),
    isLoading,
    mutate,
  };
}

type UseBacklogSyncWatcherOptions = {
  workspaceSlug: string;
  projectId: string;
  enabled: boolean;
  onSyncDetected?: () => void;
};

export function useBacklogSyncWatcher({
  workspaceSlug,
  projectId,
  enabled,
  onSyncDetected,
}: UseBacklogSyncWatcherOptions) {
  const onSyncRef = useRef(onSyncDetected);
  onSyncRef.current = onSyncDetected;
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!enabled || !workspaceSlug || !projectId) return;

    const storageKey = `backlog_sync:${projectId}`;

    const tick = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const state = await backlogIntegrationService.getSyncState(workspaceSlug, projectId);
        if (!state.enabled || !state.last_sync_completed_at) return;

        const lastSeen = sessionStorage.getItem(storageKey);
        const completedAt = new Date(state.last_sync_completed_at).getTime();
        const seenAt = lastSeen ? new Date(lastSeen).getTime() : 0;

        if (completedAt > seenAt) {
          markBacklogSyncSeen(projectId, state.last_sync_completed_at);
          if (backlogPullHasListChanges(state.last_pull_stats)) {
            if (debounceRef.current) clearTimeout(debounceRef.current);
            debounceRef.current = setTimeout(() => {
              onSyncRef.current?.();
            }, 500);
          }
        }
      } catch {
        // ignore polling errors
      }
    };

    tick();
    const interval = setInterval(tick, 5000);
    const onVisibility = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [enabled, workspaceSlug, projectId]);
}
