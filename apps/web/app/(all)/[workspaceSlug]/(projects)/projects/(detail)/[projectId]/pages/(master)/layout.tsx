/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Outlet, useParams } from "react-router";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { PagesMasterSidebar } from "@/components/pages/master/sidebar";
import { cn } from "@plane/utils";
import { usePlatformOS } from "@/hooks/use-platform-os";
import { EPageStoreType } from "@/plane-web/hooks/store";
import { PagesListHeader } from "../(list)/header";
import { PageDetailsHeader } from "../(detail)/header";

function ProjectPagesMasterLayout() {
  const { pageId } = useParams();
  const { isMobile } = usePlatformOS();
  const selectedPageId = pageId?.toString();
  const showMobileContent = Boolean(selectedPageId);

  return (
    <>
      <AppHeader header={selectedPageId ? <PageDetailsHeader /> : <PagesListHeader />} />
      <ContentWrapper>
        <div className="flex h-full w-full overflow-hidden bg-surface-1">
          <div
            className={cn(
              "h-full w-full shrink-0 border-r border-subtle lg:w-[340px] xl:w-[380px]",
              isMobile && showMobileContent && "hidden",
              isMobile && "absolute inset-0 z-10 lg:relative lg:z-auto"
            )}
          >
            <PagesMasterSidebar storeType={EPageStoreType.PROJECT} selectedPageId={selectedPageId} />
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
