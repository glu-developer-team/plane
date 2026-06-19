/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { generateWorkItemLink } from "@plane/utils";
// components
import type { TIssueOperations } from "@/components/issues/issue-detail";
import { IssueParentSelect } from "@/components/issues/issue-detail/parent-select";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useProject } from "@/hooks/store/use-project";

type TIssueEpicSelect = {
  className?: string;
  disabled?: boolean;
  issueId: string;
  issueOperations: TIssueOperations;
  projectId: string;
  workspaceSlug: string;
};

export const IssueEpicSelectRoot = observer(function IssueEpicSelectRoot(props: TIssueEpicSelect) {
  const { issueId, issueOperations, projectId, workspaceSlug } = props;
  const { t } = useTranslation();
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const {
    toggleEpicParentModal,
    removeSubIssue,
    subIssues: { setSubIssueHelpers, fetchSubIssues },
  } = useIssueDetail();
  const { getProjectIdentifierById } = useProject();

  // derived values
  const issue = getIssueById(issueId);
  const parentIssue = issue?.parent_id ? getIssueById(issue.parent_id) : undefined;
  const isEpicParent = parentIssue?.is_epic;

  const handleParentIssue = async (_issueId: string | null = null) => {
    try {
      await issueOperations.update(workspaceSlug, projectId, issueId, { parent_id: _issueId });
      await issueOperations.fetch(workspaceSlug, projectId, issueId, false);
      if (_issueId) await fetchSubIssues(workspaceSlug, projectId, _issueId);
      toggleEpicParentModal(null);
    } catch (_error) {
      console.error("something went wrong while fetching the issue");
    }
  };

  const handleRemoveSubIssue = async (slug: string, projId: string, parentIssueId: string, childIssueId: string) => {
    try {
      setSubIssueHelpers(parentIssueId, "issue_loader", childIssueId);
      await removeSubIssue(slug, projId, parentIssueId, childIssueId);
      await fetchSubIssues(slug, projId, parentIssueId);
      setSubIssueHelpers(parentIssueId, "issue_loader", childIssueId);
    } catch (_error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("common.error.label"),
        message: t("common.something_went_wrong"),
      });
    }
  };

  const projectIdentifier = parentIssue?.project_id ? getProjectIdentifierById(parentIssue.project_id) : undefined;
  const workItemLink = generateWorkItemLink({
    workspaceSlug,
    projectId: parentIssue?.project_id,
    issueId: parentIssue?.id,
    projectIdentifier,
    sequenceId: parentIssue?.sequence_id,
    isEpic: true,
  });

  if (!issue || issue.is_epic) return <></>;

  // Only show epic link when parent is an epic (or empty — user can add one).
  if (parentIssue && !isEpicParent) return <></>;

  return (
    <IssueParentSelect
      {...props}
      handleParentIssue={handleParentIssue}
      handleRemoveSubIssue={handleRemoveSubIssue}
      workItemLink={workItemLink}
      searchEpic={true}
      emptyLabel={t("epic.add.label")}
    />
  );
});
