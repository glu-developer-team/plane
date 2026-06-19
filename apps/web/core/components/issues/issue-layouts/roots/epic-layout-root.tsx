/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane constants
import {
  ISSUE_DISPLAY_FILTERS_BY_PAGE,
  PROJECT_VIEW_TRACKER_ELEMENTS,
  EUserPermissions,
  EUserPermissionsLevel,
} from "@plane/constants";
import { EIssueLayoutTypes, EIssueServiceType, EIssuesStoreType } from "@plane/types";
import { Spinner } from "@plane/ui";
// components
import { ProjectLevelWorkItemFiltersHOC } from "@/components/work-item-filters/filters-hoc/project-level";
import { WorkItemFiltersRow } from "@/components/work-item-filters/filters-row";
// hooks
import { useIssues } from "@/hooks/store/use-issues";
import { useUserPermissions } from "@/hooks/store/user";
import { IssuesStoreContext } from "@/hooks/use-issue-layout-store";
// local imports
import { IssuePeekOverview } from "../../peek-overview";
import { BaseCalendarRoot } from "../calendar/base-calendar-root";
import { BaseGanttRoot } from "../gantt";
import { BaseKanBanRoot } from "../kanban/base-kanban-root";
import { BaseListRoot } from "../list/base-list-root";
import { ProjectIssueQuickActions } from "../quick-action-dropdowns";
import { BaseSpreadsheetRoot } from "../spreadsheet/base-spreadsheet-root";

function EpicIssueLayout(props: { activeLayout: EIssueLayoutTypes | undefined }) {
  const { workspaceSlug } = useParams();
  const { allowPermissions } = useUserPermissions();

  const canEditPropertiesBasedOnProject = (projectId: string) =>
    allowPermissions(
      [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
      EUserPermissionsLevel.PROJECT,
      workspaceSlug?.toString(),
      projectId
    );

  switch (props.activeLayout) {
    case EIssueLayoutTypes.LIST:
      return (
        <BaseListRoot
          QuickActions={ProjectIssueQuickActions}
          canEditPropertiesBasedOnProject={canEditPropertiesBasedOnProject}
          isEpic={true}
        />
      );
    case EIssueLayoutTypes.KANBAN:
      return (
        <BaseKanBanRoot
          QuickActions={ProjectIssueQuickActions}
          canEditPropertiesBasedOnProject={canEditPropertiesBasedOnProject}
          isEpic={true}
        />
      );
    case EIssueLayoutTypes.CALENDAR:
      return (
        <BaseCalendarRoot
          QuickActions={ProjectIssueQuickActions}
          canEditPropertiesBasedOnProject={canEditPropertiesBasedOnProject}
          isEpic={true}
        />
      );
    case EIssueLayoutTypes.GANTT:
      return <BaseGanttRoot isEpic={true} />;
    case EIssueLayoutTypes.SPREADSHEET:
      return (
        <BaseSpreadsheetRoot
          QuickActions={ProjectIssueQuickActions}
          canEditPropertiesBasedOnProject={canEditPropertiesBasedOnProject}
          isEpic={true}
        />
      );
    default:
      return null;
  }
}

export const EpicLayoutRoot = observer(function EpicLayoutRoot() {
  const { workspaceSlug: routerWorkspaceSlug, projectId: routerProjectId } = useParams();
  const workspaceSlug = routerWorkspaceSlug ? routerWorkspaceSlug.toString() : undefined;
  const projectId = routerProjectId ? routerProjectId.toString() : undefined;
  const { issues, issuesFilter } = useIssues(EIssuesStoreType.EPIC);
  const workItemFilters = projectId ? issuesFilter?.getIssueFilters(projectId) : undefined;
  const activeLayout = workItemFilters?.displayFilters?.layout;

  useSWR(
    workspaceSlug && projectId ? `PROJECT_EPICS_${workspaceSlug}_${projectId}` : null,
    async () => {
      if (workspaceSlug && projectId) {
        await issuesFilter?.fetchFilters(workspaceSlug, projectId);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  if (!workspaceSlug || !projectId || !workItemFilters) return <></>;

  return (
    <IssuesStoreContext.Provider value={EIssuesStoreType.EPIC}>
      <ProjectLevelWorkItemFiltersHOC
        enableSaveView
        entityType={EIssuesStoreType.EPIC}
        entityId={projectId}
        filtersToShowByLayout={ISSUE_DISPLAY_FILTERS_BY_PAGE.epics.filters}
        initialWorkItemFilters={workItemFilters}
        updateFilters={issuesFilter?.updateFilterExpression.bind(issuesFilter, workspaceSlug, projectId)}
        projectId={projectId}
        workspaceSlug={workspaceSlug}
      >
        {({ filter: projectEpicsFilter }) => (
          <div className="relative flex h-full w-full flex-col overflow-hidden">
            {projectEpicsFilter && (
              <WorkItemFiltersRow
                filter={projectEpicsFilter}
                trackerElements={{
                  saveView: PROJECT_VIEW_TRACKER_ELEMENTS.PROJECT_HEADER_SAVE_AS_VIEW_BUTTON,
                }}
              />
            )}
            <div className="relative h-full w-full overflow-auto bg-surface-1">
              {issues?.getIssueLoader() === "mutation" && (
                <div className="shadow-sm fixed top-[70px] right-[20px] z-50 flex h-[40px] w-[40px] items-center justify-center rounded-sm bg-layer-1">
                  <Spinner className="h-4 w-4" />
                </div>
              )}
              <EpicIssueLayout activeLayout={activeLayout} />
            </div>
            <IssuePeekOverview />
            <IssuePeekOverview serviceType={EIssueServiceType.ISSUES} />
          </div>
        )}
      </ProjectLevelWorkItemFiltersHOC>
    </IssuesStoreContext.Provider>
  );
});
