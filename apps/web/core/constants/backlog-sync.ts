/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export const BACKLOG_PULL_DEBOUNCE_MS = 5000;
export const BACKLOG_SYNC_STATE_POLL_MS = 5000;
export const BACKLOG_JOB_POLL_MS = 1000;

export const PROJECT_BACKLOG_SYNC = (workspaceSlug: string, projectId: string) =>
  `PROJECT_BACKLOG_SYNC_${workspaceSlug}_${projectId}`;

export const backlogSyncStorageKey = (projectId: string) => `backlog_sync:${projectId}`;
