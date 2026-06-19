/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { EIssuesStoreType } from "@plane/types";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useIssues } from "@/hooks/store/use-issues";
import { useBacklogPullSync, useBacklogSyncConfig, useBacklogSyncWatcher } from "@/hooks/use-backlog-sync";

type BacklogProjectSyncBridgeProps = {
  workspaceSlug: string;
  projectId: string;
};

export const BacklogProjectSyncBridge = observer(function BacklogProjectSyncBridge({
  workspaceSlug,
  projectId,
}: BacklogProjectSyncBridgeProps) {
  const { enabled } = useBacklogSyncConfig(workspaceSlug, projectId);
  const {
    issues: { silentRefetchIssuesWithExistingPagination },
  } = useIssues(EIssuesStoreType.PROJECT);

  const refreshProjectIssues = () => {
    silentRefetchIssuesWithExistingPagination(workspaceSlug, projectId);
  };

  useBacklogPullSync({
    workspaceSlug,
    projectId,
    enabled,
    scope: "project",
    onComplete: refreshProjectIssues,
  });

  useBacklogSyncWatcher({
    workspaceSlug,
    projectId,
    enabled,
    onSyncDetected: refreshProjectIssues,
  });

  return null;
});

type BacklogIssueSyncBridgeProps = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
};

export const BacklogIssueSyncBridge = observer(function BacklogIssueSyncBridge({
  workspaceSlug,
  projectId,
  issueId,
}: BacklogIssueSyncBridgeProps) {
  const { enabled } = useBacklogSyncConfig(workspaceSlug, projectId);
  const {
    issue: { fetchIssue },
    comment: { refetchComments },
    refetchActivities,
  } = useIssueDetail();

  const refreshIssue = () => {
    fetchIssue(workspaceSlug, projectId, issueId);
    refetchComments(workspaceSlug, projectId, issueId);
    refetchActivities(workspaceSlug, projectId, issueId);
  };

  useBacklogPullSync({
    workspaceSlug,
    projectId,
    enabled,
    scope: "issue",
    issueId,
    onComplete: refreshIssue,
  });

  return null;
});
