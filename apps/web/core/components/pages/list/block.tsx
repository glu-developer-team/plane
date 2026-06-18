/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

"use client";

import { useCallback, useRef, useState } from "react";
import { observer } from "mobx-react";
import { ChevronRight, Loader } from "lucide-react";
// plane imports
import { PageIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TPageNavigationTabs } from "@plane/types";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { cn, getPageName } from "@plane/utils";
// components
import { ListItem } from "@/components/core/list";
import { BlockItemAction } from "@/components/pages/list/block-item-action";
// hooks
import { useAppRouter } from "@/hooks/use-app-router";
import { usePlatformOS } from "@/hooks/use-platform-os";
// plane web hooks
import type { EPageStoreType } from "@/plane-web/hooks/store";
import { usePage } from "@/plane-web/hooks/store";

type TPageListBlock = {
  handleToggleExpanded: () => void;
  isExpanded: boolean;
  paddingLeft: number;
  pageId: string;
  storeType: EPageStoreType;
  pageType?: TPageNavigationTabs;
};

export const PageListBlock = observer(function PageListBlock(props: TPageListBlock) {
  const { handleToggleExpanded, isExpanded, paddingLeft, pageId, storeType } = props;
  const [isFetchingSubPages, setIsFetchingSubPages] = useState(false);
  const parentRef = useRef(null);
  const router = useAppRouter();
  const page = usePage({
    pageId,
    storeType,
  });
  const { isMobile } = usePlatformOS();

  const handleSubPagesToggle = useCallback(async () => {
    handleToggleExpanded();
    setIsFetchingSubPages(true);
    try {
      if (!isExpanded) {
        await page?.fetchSubPages?.();
      }
    } catch {
      handleToggleExpanded();
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error!",
        message: "Failed to fetch sub-pages. Please try again.",
      });
    } finally {
      setIsFetchingSubPages(false);
    }
  }, [isExpanded, page, handleToggleExpanded]);

  if (!page) return null;

  const { name, logo_props, getRedirectionLink, sub_pages_count, deleted_at } = page;
  const shouldShowSubPagesButton = sub_pages_count !== undefined && sub_pages_count > 0;

  if (deleted_at) return null;

  return (
    <div ref={parentRef} className="relative">
      <ListItem
        title={getPageName(name)}
        itemLink={getRedirectionLink()}
        onItemClick={() => router.push(getRedirectionLink())}
        leftElementClassName="gap-2"
        prependTitleElement={
          <div
            className="flex flex-shrink-0 items-center gap-1"
            style={{
              paddingLeft: `${paddingLeft}px`,
            }}
          >
            {shouldShowSubPagesButton ? (
              <button
                type="button"
                className="grid size-5 flex-shrink-0 place-items-center rounded-sm text-secondary hover:text-primary"
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  handleSubPagesToggle();
                }}
                disabled={isFetchingSubPages}
                data-prevent-progress
              >
                {isFetchingSubPages ? (
                  <Loader className="size-4 animate-spin" />
                ) : (
                  <ChevronRight
                    className={cn("size-4", {
                      "rotate-90": isExpanded,
                    })}
                    strokeWidth={2.5}
                  />
                )}
              </button>
            ) : (
              <span className="size-5" />
            )}
            <div className="grid size-6 flex-shrink-0 place-items-center">
              {logo_props?.in_use ? (
                <Logo logo={logo_props} size={16} type="lucide" />
              ) : (
                <PageIcon className="size-4 text-tertiary" />
              )}
            </div>
          </div>
        }
        actionableItems={<BlockItemAction page={page} parentRef={parentRef} storeType={storeType} />}
        isMobile={isMobile}
        parentRef={parentRef}
      />
    </div>
  );
});
