/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import { Transition } from "@headlessui/react";
import { observer } from "mobx-react";
import type { TPageNavigationTabs } from "@plane/types";
import type { EPageStoreType } from "@/plane-web/hooks/store";
import { usePage, usePageStore } from "@/plane-web/hooks/store";
import { PageListBlock } from "./block";

type TPageListBlockRoot = {
  paddingLeft: number;
  pageId: string;
  storeType: EPageStoreType;
  pageType?: TPageNavigationTabs;
  selectedPageId?: string;
  variant?: "default" | "sidebar";
  expandedPageIds?: string[];
  setExpandedPageIds?: React.Dispatch<React.SetStateAction<string[]>>;
};

export const PageListBlockRoot = observer(function PageListBlockRoot(props: TPageListBlockRoot) {
  const {
    paddingLeft,
    pageId,
    storeType,
    pageType,
    selectedPageId,
    variant = "default",
    expandedPageIds = [],
    setExpandedPageIds,
  } = props;
  const [localIsExpanded, setLocalIsExpanded] = useState(false);
  const [subPagesLoaded, setSubPagesLoaded] = useState(false);
  const { getPageById } = usePageStore(storeType);
  const page = usePage({
    pageId,
    storeType,
  });

  const isActivePage = selectedPageId === pageId;
  const isExpanded = setExpandedPageIds ? expandedPageIds.includes(pageId) : localIsExpanded;
  const { sub_pages_count, subPageIds } = page ?? {};
  const shouldShowSubPages = isExpanded && sub_pages_count !== undefined && sub_pages_count > 0;

  useEffect(() => {
    if (isExpanded && sub_pages_count && sub_pages_count > 0 && !subPagesLoaded && page) {
      page.fetchSubPages();
      setSubPagesLoaded(true);
    }
  }, [isExpanded, sub_pages_count, subPagesLoaded, page]);

  const getChildrenPageIds = useCallback(
    (parentId: string): string[] => {
      const children: string[] = [];
      const collectChildren = (id: string) => {
        const currentPage = getPageById(id);
        if (!currentPage) return;
        const subpageIds = currentPage.subPageIds || [];
        subpageIds.forEach((childId) => {
          children.push(childId);
          collectChildren(childId);
        });
      };
      collectChildren(parentId);
      return children;
    },
    [getPageById]
  );

  const handleToggleExpanded = () => {
    if (setExpandedPageIds) {
      setExpandedPageIds((prev) => {
        const currentSet = new Set(prev);
        if (currentSet.has(pageId)) {
          getChildrenPageIds(pageId).forEach((id) => currentSet.delete(id));
          currentSet.delete(pageId);
        } else {
          currentSet.add(pageId);
        }
        return Array.from(currentSet);
      });
    } else {
      setLocalIsExpanded((prev) => !prev);
    }
  };

  if (!page) return null;
  if (page.deleted_at) return null;

  return (
    <div data-active-page={isActivePage ? "true" : undefined}>
      <PageListBlock
        handleToggleExpanded={handleToggleExpanded}
        isExpanded={isExpanded}
        isSelected={isActivePage}
        paddingLeft={paddingLeft}
        pageId={pageId}
        storeType={storeType}
        pageType={pageType}
        variant={variant}
      />
      {shouldShowSubPages && (
        <Transition
          show={isExpanded}
          enter="transition ease-out duration-100"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="transition ease-in duration-75"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div>
            {subPageIds?.map((subPageId) => (
              <PageListBlockRoot
                key={subPageId}
                paddingLeft={paddingLeft + 20}
                pageId={subPageId}
                storeType={storeType}
                pageType={pageType}
                selectedPageId={selectedPageId}
                variant={variant}
                expandedPageIds={expandedPageIds}
                setExpandedPageIds={setExpandedPageIds}
              />
            ))}
          </div>
        </Transition>
      )}
    </div>
  );
});
