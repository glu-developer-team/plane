/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
// plane imports
import type { IIssueFilters, TWorkItemFilterExpression } from "@plane/types";
import type { EIssuesStoreType } from "@plane/types";
// local imports
import { useWorkItemFilters } from "./use-work-item-filters";

type TUseEnsureWorkItemFilterProps = {
  entityType: EIssuesStoreType;
  entityId: string | undefined;
  issueFilters: IIssueFilters | undefined;
  updateFilterExpression: (filters: TWorkItemFilterExpression) => Promise<void>;
};

/**
 * Ensures a work item filter instance exists as soon as issue filters are loaded.
 * The layout HOC reuses the same instance and registers filter configs.
 */
export const useEnsureWorkItemFilter = (props: TUseEnsureWorkItemFilterProps) => {
  const { entityType, entityId, issueFilters, updateFilterExpression } = props;
  const workItemFilterStore = useWorkItemFilters();
  const initialExpression = issueFilters?.richFilters;

  useMemo(() => {
    if (!entityId || !initialExpression) return;

    workItemFilterStore.getOrCreateFilter({
      entityType,
      entityId,
      initialExpression,
      onExpressionChange: updateFilterExpression,
    });
  }, [entityType, entityId, initialExpression, updateFilterExpression, workItemFilterStore]);
};
