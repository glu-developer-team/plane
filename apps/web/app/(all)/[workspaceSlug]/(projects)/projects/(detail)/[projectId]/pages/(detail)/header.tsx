/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Plus } from "lucide-react";
// plane imports
import { EPageAccess } from "@plane/constants";
import { PageIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { ICustomSearchSelectOption } from "@plane/types";
import { Breadcrumbs, Header, BreadcrumbNavigationSearchDropdown } from "@plane/ui";
import { getPageName } from "@plane/utils";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { PageAccessIcon } from "@/components/common/page-access-icon";
import { SwitcherIcon, SwitcherLabel } from "@/components/common/switcher-label";
import { PageHeaderActions } from "@/components/pages/header/actions";
import { PageSyncingBadge } from "@/components/pages/header/syncing-badge";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useAppRouter } from "@/hooks/use-app-router";
// plane web imports
import { CommonProjectBreadcrumbs } from "@/plane-web/components/breadcrumbs/common";
import { PageDetailsHeaderExtraActions } from "@/plane-web/components/pages";
import { EPageStoreType, usePage, usePageStore } from "@/plane-web/hooks/store";

export interface IPagesHeaderProps {
  showButton?: boolean;
}

const storeType = EPageStoreType.PROJECT;

export const PageDetailsHeader = observer(function PageDetailsHeader() {
  const router = useAppRouter();
  const { workspaceSlug, pageId, projectId } = useParams();
  const { loader } = useProject();
  const { getPageById, getCurrentProjectPageIds, fetchParentPages, createPage, getOrderedParentPages } =
    usePageStore(storeType);
  const page = usePage({
    pageId: pageId?.toString() ?? "",
    storeType,
  });

  useEffect(() => {
    if (!workspaceSlug || !projectId || !pageId || !page?.parent_id) return;
    fetchParentPages(workspaceSlug.toString(), projectId.toString(), pageId.toString());
  }, [workspaceSlug, projectId, pageId, page?.parent_id, fetchParentPages]);

  const projectPageIds = getCurrentProjectPageIds(projectId?.toString());
  const parentPages = pageId ? getOrderedParentPages(pageId.toString()) : undefined;

  const switcherOptions = projectPageIds
    .map((id) => {
      const _page = id === pageId ? page : getPageById(id);
      if (!_page) return;
      return {
        value: _page.id,
        query: _page.name,
        content: (
          <div className="flex items-center justify-between gap-2">
            <SwitcherLabel logo_props={_page.logo_props} name={getPageName(_page.name)} LabelIcon={PageIcon} />
            <PageAccessIcon {..._page} />
          </div>
        ),
      };
    })
    .filter((option) => option !== undefined) as ICustomSearchSelectOption[];

  const handleCreateSubPage = async () => {
    if (!workspaceSlug || !projectId || !page) return;
    try {
      const newPage = await createPage({
        parent_id: page.id,
        access: page.access ?? EPageAccess.PUBLIC,
      });
      if (newPage?.id) {
        router.push(`/${workspaceSlug}/projects/${projectId}/pages/${newPage.id}`);
      }
    } catch (err: unknown) {
      const error = err as { error?: string };
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error!",
        message: error?.error || "Sub-page could not be created. Please try again.",
      });
    }
  };

  if (!page) return null;

  return (
    <Header>
      <Header.LeftItem>
        <div>
          <Breadcrumbs isLoading={loader === "init-loader"}>
            <CommonProjectBreadcrumbs workspaceSlug={workspaceSlug?.toString()} projectId={projectId?.toString()} />
            <Breadcrumbs.Item
              component={
                <BreadcrumbLink
                  label="Pages"
                  href={`/${workspaceSlug}/projects/${projectId}/pages/`}
                  icon={<PageIcon className="h-4 w-4 text-tertiary" />}
                />
              }
            />
            {parentPages?.map((parentPage) => (
              <Breadcrumbs.Item
                key={parentPage.id}
                component={
                  <BreadcrumbLink
                    label={getPageName(parentPage.name)}
                    href={`/${workspaceSlug}/projects/${projectId}/pages/${parentPage.id}`}
                    icon={<PageIcon className="h-4 w-4 text-tertiary" />}
                  />
                }
              />
            ))}
            <Breadcrumbs.Item
              component={
                <BreadcrumbNavigationSearchDropdown
                  selectedItem={pageId?.toString() ?? ""}
                  navigationItems={switcherOptions}
                  onChange={(value: string) => {
                    router.push(`/${workspaceSlug}/projects/${projectId}/pages/${value}`);
                  }}
                  title={getPageName(page?.name)}
                  icon={
                    <Breadcrumbs.Icon>
                      <SwitcherIcon logo_props={page.logo_props} LabelIcon={PageIcon} size={16} />
                    </Breadcrumbs.Icon>
                  }
                  isLast
                />
              }
            />
          </Breadcrumbs>
        </div>
      </Header.LeftItem>
      <Header.RightItem>
        {page.canCurrentUserEditPage && page.isContentEditable && (
          <button
            type="button"
            onClick={handleCreateSubPage}
            className="grid size-7 place-items-center rounded-md text-secondary transition-colors hover:bg-layer-transparent-hover hover:text-primary"
            title="Add sub-page"
          >
            <Plus className="size-4" />
          </button>
        )}
        <PageSyncingBadge syncStatus={page.isSyncingWithServer} />
        <PageDetailsHeaderExtraActions page={page} storeType={storeType} />
        <PageHeaderActions page={page} storeType={storeType} />
      </Header.RightItem>
    </Header>
  );
});
