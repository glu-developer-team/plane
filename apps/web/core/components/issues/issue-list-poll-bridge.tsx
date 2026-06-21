/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { EIssuesStoreType } from "@plane/types";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useIssues } from "@/hooks/store/use-issues";
import { useModule } from "@/hooks/store/use-module";
import { useIssueListPollSync } from "@/hooks/use-issue-list-poll-sync";

type ModuleIssueListPollBridgeProps = {
  workspaceSlug: string;
  projectId: string;
  moduleId: string;
};

export const ModuleIssueListPollBridge = observer(function ModuleIssueListPollBridge({
  workspaceSlug,
  projectId,
  moduleId,
}: ModuleIssueListPollBridgeProps) {
  const {
    issues: { silentRefetchIssuesWithExistingPagination },
  } = useIssues(EIssuesStoreType.MODULE);
  const { fetchModuleDetails } = useModule();
  const {
    peekIssue,
    issue: { fetchIssue },
    fetchActivities,
    comment: { refetchComments },
  } = useIssueDetail();

  useIssueListPollSync({
    enabled: Boolean(workspaceSlug && projectId && moduleId),
    onPoll: async () => {
      await silentRefetchIssuesWithExistingPagination(workspaceSlug, projectId);
      await fetchModuleDetails(workspaceSlug, projectId, moduleId);

      if (peekIssue?.workspaceSlug && peekIssue.projectId && peekIssue.issueId) {
        await fetchIssue(peekIssue.workspaceSlug, peekIssue.projectId, peekIssue.issueId);
        await refetchComments(peekIssue.workspaceSlug, peekIssue.projectId, peekIssue.issueId);
        await fetchActivities(peekIssue.workspaceSlug, peekIssue.projectId, peekIssue.issueId);
      }
    },
  });

  return null;
});
