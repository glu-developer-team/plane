/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
import { Outlet, useParams } from "react-router";
import { useLocalStorage } from "@plane/hooks";
import { cn } from "@plane/utils";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { PagesMasterSidebar } from "@/components/pages/master/sidebar";
import { usePlatformOS } from "@/hooks/use-platform-os";
import { EPageStoreType } from "@/plane-web/hooks/store";
import { PagesListHeader } from "../(list)/header";
import { PageDetailsHeader } from "../(detail)/header";

const PAGES_SIDEBAR_WIDTH_KEY = "pages_master_sidebar_width";
const DEFAULT_PAGES_SIDEBAR_WIDTH = 380;
const MIN_PAGES_SIDEBAR_WIDTH = 360;
const MAX_PAGES_SIDEBAR_WIDTH = 520;

function ProjectPagesMasterLayout() {
  const { pageId } = useParams();
  const { isMobile } = usePlatformOS();
  const selectedPageId = pageId?.toString();
  const showMobileContent = Boolean(selectedPageId);

  const { storedValue, setValue } = useLocalStorage(PAGES_SIDEBAR_WIDTH_KEY, DEFAULT_PAGES_SIDEBAR_WIDTH);
  const [sidebarWidth, setSidebarWidth] = useState(storedValue ?? DEFAULT_PAGES_SIDEBAR_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const sidebarWidthRef = useRef(sidebarWidth);
  const initialWidthRef = useRef(0);
  const initialMouseXRef = useRef(0);

  sidebarWidthRef.current = sidebarWidth;

  const startResizing = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsResizing(true);
      initialWidthRef.current = sidebarWidth;
      initialMouseXRef.current = e.clientX;
    },
    [sidebarWidth]
  );

  const handleResize = useCallback((e: MouseEvent) => {
    const deltaX = e.clientX - initialMouseXRef.current;
    const nextWidth = Math.min(
      Math.max(initialWidthRef.current + deltaX, MIN_PAGES_SIDEBAR_WIDTH),
      MAX_PAGES_SIDEBAR_WIDTH
    );
    setSidebarWidth(nextWidth);
  }, []);

  const stopResizing = useCallback(() => {
    setIsResizing(false);
    setValue(sidebarWidthRef.current);
  }, [setValue]);

  useEffect(() => {
    if (!isResizing) return;

    document.addEventListener("mousemove", handleResize);
    document.addEventListener("mouseup", stopResizing);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    return () => {
      document.removeEventListener("mousemove", handleResize);
      document.removeEventListener("mouseup", stopResizing);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizing, handleResize, stopResizing]);

  return (
    <>
      <AppHeader header={selectedPageId ? <PageDetailsHeader /> : <PagesListHeader />} />
      <ContentWrapper>
        <div className="flex h-full w-full overflow-hidden bg-surface-1">
          <div
            className={cn(
              "relative h-full w-full shrink-0 border-r border-subtle",
              isMobile && showMobileContent && "hidden",
              isMobile && "absolute inset-0 z-10 lg:relative lg:z-auto",
              !isMobile && !isResizing && "transition-[width] duration-150 ease-out"
            )}
            style={!isMobile ? { width: `${sidebarWidth}px`, minWidth: `${sidebarWidth}px` } : undefined}
          >
            <PagesMasterSidebar storeType={EPageStoreType.PROJECT} selectedPageId={selectedPageId} />
            {!isMobile && (
              <div
                className={cn(
                  "absolute top-0 right-0 z-10 h-full w-1 cursor-ew-resize transition-all duration-200",
                  !isResizing && "hover:bg-surface-2",
                  isResizing && "w-1.5 bg-layer-1"
                )}
                onMouseDown={startResizing}
                role="separator"
                aria-orientation="vertical"
                aria-label="Resize pages list"
              />
            )}
          </div>
          <div
            className={cn(
              "relative flex min-w-0 flex-1 flex-col overflow-hidden",
              isMobile && !showMobileContent && "hidden lg:flex"
            )}
          >
            <Outlet />
          </div>
        </div>
      </ContentWrapper>
    </>
  );
}

export default observer(ProjectPagesMasterLayout);
