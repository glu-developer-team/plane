/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams, useSearchParams } from "next/navigation";
import useSWR from "swr";
import type { TPageNavigationTabs } from "@plane/types";
import { cn } from "@plane/utils";
import { PagesListHeaderRoot } from "@/components/pages/header/root";
import { PagesListMainContent } from "@/components/pages/pages-list-main-content";
import { PagesListRoot } from "@/components/pages/list/root";
import type { EPageStoreType } from "@/plane-web/hooks/store";
import { usePageStore } from "@/plane-web/hooks/store";

const getPageType = (pageType?: string | null): TPageNavigationTabs => {
  if (pageType === "private") return "private";
  if (pageType === "archived") return "archived";
  return "public";
};

type Props = {
  storeType: EPageStoreType;
  selectedPageId?: string;
  className?: string;
};

export const PagesMasterSidebar = observer(function PagesMasterSidebar(props: Props) {
  const { storeType, selectedPageId, className } = props;
  const { workspaceSlug, projectId } = useParams();
  const searchParams = useSearchParams();
  const pageType = getPageType(searchParams.get("type"));
  const { fetchPagesList, getPageById, fetchParentPages } = usePageStore(storeType);
  const [expandedPageIds, setExpandedPageIds] = useState<string[]>([]);

  useSWR(
    workspaceSlug && projectId ? `PROJECT_PAGES_${projectId}` : null,
    workspaceSlug && projectId ? () => fetchPagesList(workspaceSlug.toString(), projectId.toString(), pageType) : null
  );

  useEffect(() => {
    if (!selectedPageId || !workspaceSlug || !projectId) return;

    const expandAncestors = async () => {
      await fetchParentPages(workspaceSlug.toString(), projectId.toString(), selectedPageId);
      const page = getPageById(selectedPageId);
      const ancestorIds: string[] = [];
      let parentId = page?.parent_id;

      while (parentId) {
        ancestorIds.push(parentId);
        parentId = getPageById(parentId)?.parent_id ?? null;
      }

      if (ancestorIds.length > 0) {
        setExpandedPageIds((prev) => Array.from(new Set([...prev, ...ancestorIds])));
      }
    };

    expandAncestors();
  }, [selectedPageId, workspaceSlug, projectId, fetchParentPages, getPageById]);

  if (!workspaceSlug || !projectId) return null;

  return (
    <div className={cn("flex h-full w-full flex-col overflow-hidden bg-surface-1", className)}>
      <PagesListHeaderRoot
        pageType={pageType}
        projectId={projectId.toString()}
        storeType={storeType}
        workspaceSlug={workspaceSlug.toString()}
      />
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <PagesListMainContent pageType={pageType} storeType={storeType}>
          <PagesListRoot
            pageType={pageType}
            storeType={storeType}
            selectedPageId={selectedPageId}
            variant="sidebar"
            expandedPageIds={expandedPageIds}
            setExpandedPageIds={setExpandedPageIds}
          />
        </PagesListMainContent>
      </div>
    </div>
  );
});
