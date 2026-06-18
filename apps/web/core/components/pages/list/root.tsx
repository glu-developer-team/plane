/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import type { TPageNavigationTabs } from "@plane/types";
import { ListLayout } from "@/components/core/list";
import type { EPageStoreType } from "@/plane-web/hooks/store";
import { usePageStore } from "@/plane-web/hooks/store";
import { PageListBlockRoot } from "./block-root";

type TPagesListRoot = {
  pageType: TPageNavigationTabs;
  storeType: EPageStoreType;
  selectedPageId?: string;
  variant?: "default" | "sidebar";
  expandedPageIds?: string[];
  setExpandedPageIds?: React.Dispatch<React.SetStateAction<string[]>>;
};

export const PagesListRoot = observer(function PagesListRoot(props: TPagesListRoot) {
  const {
    pageType,
    storeType,
    selectedPageId,
    variant = "default",
    expandedPageIds: controlledExpandedPageIds,
    setExpandedPageIds: controlledSetExpandedPageIds,
  } = props;
  const [localExpandedPageIds, setLocalExpandedPageIds] = useState<string[]>([]);
  const expandedPageIds = controlledExpandedPageIds ?? localExpandedPageIds;
  const setExpandedPageIds = controlledSetExpandedPageIds ?? setLocalExpandedPageIds;
  const { getCurrentProjectFilteredPageIdsByTab } = usePageStore(storeType);
  const filteredPageIds = getCurrentProjectFilteredPageIdsByTab(pageType);

  if (!filteredPageIds) return <></>;

  return (
    <ListLayout>
      {filteredPageIds.map((pageId) => (
        <PageListBlockRoot
          key={pageId}
          paddingLeft={0}
          pageId={pageId}
          storeType={storeType}
          pageType={pageType}
          selectedPageId={selectedPageId}
          variant={variant}
          expandedPageIds={expandedPageIds}
          setExpandedPageIds={setExpandedPageIds}
        />
      ))}
    </ListLayout>
  );
});
