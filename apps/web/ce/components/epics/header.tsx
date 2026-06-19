/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Circle } from "lucide-react";
import {
  EUserPermissions,
  EUserPermissionsLevel,
  EProjectFeatureKey,
  SPACE_BASE_PATH,
  SPACE_BASE_URL,
} from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { NewTabIcon } from "@plane/propel/icons";
import { Tooltip } from "@plane/propel/tooltip";
import { EIssuesStoreType } from "@plane/types";
import { Breadcrumbs, Header } from "@plane/ui";
import { CountChip } from "@/components/common/count-chip";
import { HeaderFilters } from "@/components/issues/filters";
import { useIssues } from "@/hooks/store/use-issues";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";
import { usePlatformOS } from "@/hooks/use-platform-os";
import { ProjectFeatureBreadcrumb } from "@/plane-web/components/breadcrumbs/project-feature";
import { CommonProjectBreadcrumbs } from "@/plane-web/components/breadcrumbs/common";
import { CreateUpdateEpicModal } from "@/plane-web/components/epics/epic-modal";

export const EpicsHeader = observer(function EpicsHeader() {
  const router = useAppRouter();
  const { workspaceSlug, projectId } = useParams();
  const {
    issues: { getGroupIssueCount },
  } = useIssues(EIssuesStoreType.EPIC);
  const { t } = useTranslation();
  const { currentProjectDetails, loader } = useProject();
  const { allowPermissions } = useUserPermissions();
  const { isMobile } = usePlatformOS();
  const [isEpicModalOpen, setIsEpicModalOpen] = useState(false);

  const SPACE_APP_URL = (SPACE_BASE_URL.trim() === "" ? window.location.origin : SPACE_BASE_URL) + SPACE_BASE_PATH;
  const publishedURL = `${SPACE_APP_URL}/issues/${currentProjectDetails?.anchor}`;
  const epicsCount = getGroupIssueCount(undefined, undefined, false);
  const canUserCreateEpic = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT
  );

  return (
    <>
      <Header>
        <Header.LeftItem>
          <div className="flex items-center gap-2.5">
            <Breadcrumbs onBack={() => router.back()} isLoading={loader === "init-loader"} className="flex-grow-0">
              <CommonProjectBreadcrumbs workspaceSlug={workspaceSlug?.toString()} projectId={projectId?.toString()} />
              <ProjectFeatureBreadcrumb
                workspaceSlug={workspaceSlug?.toString() ?? ""}
                projectId={projectId?.toString() ?? ""}
                featureKey={EProjectFeatureKey.EPICS}
                isLast
              />
            </Breadcrumbs>
            {epicsCount && epicsCount > 0 ? (
              <Tooltip
                isMobile={isMobile}
                tooltipContent={`There are ${epicsCount} ${epicsCount > 1 ? "epics" : "epic"} in this project`}
                position="bottom"
              >
                <CountChip count={epicsCount} />
              </Tooltip>
            ) : null}
          </div>
          {currentProjectDetails?.anchor ? (
            <a
              href={publishedURL}
              className="group flex items-center gap-1.5 rounded-sm bg-accent-primary/10 px-2.5 py-1 text-11 font-medium text-accent-primary"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Circle className="h-1.5 w-1.5 fill-accent-primary" strokeWidth={2} />
              {t("workspace_projects.network.public.title")}
              <NewTabIcon className="hidden h-3 w-3 group-hover:block" strokeWidth={2} />
            </a>
          ) : (
            <></>
          )}
        </Header.LeftItem>
        <Header.RightItem>
          <div className="hidden gap-2 md:flex">
            <HeaderFilters
              projectId={projectId?.toString() ?? ""}
              currentProjectDetails={currentProjectDetails}
              workspaceSlug={workspaceSlug?.toString() ?? ""}
              canUserCreateIssue={canUserCreateEpic}
              storeType={EIssuesStoreType.EPIC}
            />
          </div>
          {canUserCreateEpic && (
            <Button variant="primary" size="lg" onClick={() => setIsEpicModalOpen(true)}>
              <div className="block sm:hidden">{t("epic.label", { count: 1 })}</div>
              <div className="hidden sm:block">{t("epic.new")}</div>
            </Button>
          )}
        </Header.RightItem>
      </Header>
      <CreateUpdateEpicModal isOpen={isEpicModalOpen} onClose={() => setIsEpicModalOpen(false)} />
    </>
  );
});
