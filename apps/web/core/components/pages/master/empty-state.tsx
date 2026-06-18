/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { EmptyStateCompact } from "@plane/propel/empty-state";

export const PagesMasterEmptyState = observer(function PagesMasterEmptyState() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-surface-1">
      <EmptyStateCompact
        assetKey="page"
        title="Select a page"
        description="Choose a page from the sidebar to view and edit its content."
        assetClassName="size-20"
      />
    </div>
  );
});
