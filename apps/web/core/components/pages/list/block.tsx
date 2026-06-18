/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

"use client";

import { useCallback, useRef, useState } from "react";
import { observer } from "mobx-react";
import { ChevronRight, Loader } from "lucide-react";
import { PageIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TPageNavigationTabs } from "@plane/types";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { cn, getPageName } from "@plane/utils";
import { ListItem } from "@/components/core/list";
import { BlockItemAction } from "@/components/pages/list/block-item-action";
import { useAppRouter } from "@/hooks/use-app-router";
import { usePlatformOS } from "@/hooks/use-platform-os";
import type { EPageStoreType } from "@/plane-web/hooks/store";
import { usePage } from "@/plane-web/hooks/store";

type TPageListBlock = {
  handleToggleExpanded: () => void;
  isExpanded: boolean;
  isSelected?: boolean;
  paddingLeft: number;
  pageId: string;
  storeType: EPageStoreType;
  pageType?: TPageNavigationTabs;
  variant?: "default" | "sidebar";
};

export const PageListBlock = observer(function PageListBlock(props: TPageListBlock) {
  const {
    handleToggleExpanded,
    isExpanded,
    isSelected = false,
    paddingLeft,
    pageId,
    storeType,
    variant = "default",
  } = props;
  const [isFetchingSubPages, setIsFetchingSubPages] = useState(false);
  const parentRef = useRef(null);
  const router = useAppRouter();
  const page = usePage({
    pageId,
    storeType,
  });
  const { isMobile } = usePlatformOS();
  const isSidebar = variant === "sidebar";

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
    <div ref={parentRef} className="relative px-1">
      <ListItem
        title={getPageName(name)}
        itemLink={getRedirectionLink()}
        onItemClick={() => router.push(getRedirectionLink())}
        leftElementClassName="gap-1.5"
        className={cn(
          "rounded-md border-b-0",
          isSidebar ? "min-h-[36px] py-1.5" : undefined,
          isSelected && "bg-layer-transparent-selected hover:bg-layer-transparent-selected"
        )}
        actionItemContainerClassName={cn(isSidebar && "opacity-0 transition-opacity group-hover:opacity-100")}
        prependTitleElement={
          <div
            className="flex flex-shrink-0 items-center gap-0.5"
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
                  <Loader className="size-3.5 animate-spin" />
                ) : (
                  <ChevronRight
                    className={cn("size-3.5", {
                      "rotate-90": isExpanded,
                    })}
                    strokeWidth={2.5}
                  />
                )}
              </button>
            ) : (
              <span className="size-5" />
            )}
            <div className="grid size-5 flex-shrink-0 place-items-center">
              {logo_props?.in_use ? (
                <Logo logo={logo_props} size={14} type="lucide" />
              ) : (
                <PageIcon className="size-3.5 text-tertiary" />
              )}
            </div>
          </div>
        }
        actionableItems={
          isSidebar ? undefined : <BlockItemAction page={page} parentRef={parentRef} storeType={storeType} />
        }
        isMobile={isMobile}
        parentRef={parentRef}
        isSidebarOpen={isSidebar}
      />
    </div>
  );
});
