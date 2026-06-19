/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { EIssuesStoreType, EUserProjectRoles } from "@plane/types";
import { useState } from "react";
import { useUserPermissions } from "@/hooks/store/user";
import { useWorkItemFilterInstance } from "@/hooks/store/work-item-filters/use-work-item-filter-instance";
import { CreateUpdateEpicModal } from "@/plane-web/components/epics/epic-modal";

export const ProjectEpicsEmptyState = observer(function ProjectEpicsEmptyState() {
  const { projectId: routerProjectId } = useParams();
  const projectId = routerProjectId ? routerProjectId.toString() : undefined;
  const { t } = useTranslation();
  const { allowPermissions } = useUserPermissions();
  const [isEpicModalOpen, setIsEpicModalOpen] = useState(false);
  const projectEpicsFilter = useWorkItemFilterInstance(EIssuesStoreType.EPIC, projectId);

  const canPerformEmptyStateActions = allowPermissions(
    [EUserProjectRoles.ADMIN, EUserProjectRoles.MEMBER],
    EUserPermissionsLevel.PROJECT
  );

  return (
    <div className="relative h-full w-full overflow-y-auto">
      {projectEpicsFilter?.hasActiveFilters ? (
        <EmptyStateDetailed
          assetKey="search"
          title={t("common_empty_state.search.title")}
          description={t("common_empty_state.search.description")}
          actions={[
            {
              label: t("project_issues.empty_state.issues_empty_filter.secondary_button.text"),
              onClick: projectEpicsFilter?.clearFilters,
              disabled: !canPerformEmptyStateActions || !projectEpicsFilter,
              variant: "secondary",
            },
          ]}
        />
      ) : (
        <EmptyStateDetailed
          assetKey="work-item"
          title={t("project_empty_state.epics.title")}
          description={t("project_empty_state.epics.description")}
          actions={[
            {
              label: t("project_empty_state.epics.cta_primary"),
              onClick: () => setIsEpicModalOpen(true),
              disabled: !canPerformEmptyStateActions,
              variant: "primary",
            },
          ]}
        />
      )}
      <CreateUpdateEpicModal isOpen={isEpicModalOpen} onClose={() => setIsEpicModalOpen(false)} />
    </div>
  );
});
