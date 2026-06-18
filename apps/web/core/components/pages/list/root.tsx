/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// types
import type { TPageNavigationTabs } from "@plane/types";
// components
import { ListLayout } from "@/components/core/list";
// plane web hooks
import type { EPageStoreType } from "@/plane-web/hooks/store";
import { usePageStore } from "@/plane-web/hooks/store";
// local imports
import { PageListBlockRoot } from "./block-root";

type TPagesListRoot = {
  pageType: TPageNavigationTabs;
  storeType: EPageStoreType;
};

export const PagesListRoot = observer(function PagesListRoot(props: TPagesListRoot) {
  const { pageType, storeType } = props;
  const [expandedPageIds, setExpandedPageIds] = useState<string[]>([]);
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
          expandedPageIds={expandedPageIds}
          setExpandedPageIds={setExpandedPageIds}
        />
      ))}
    </ListLayout>
  );
});
