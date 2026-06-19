/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createContext, useContext } from "react";
import type { TIssueServiceType } from "@plane/types";
import { EIssueServiceType } from "@plane/types";
// mobx store
import { StoreContext } from "@/lib/store-context";
// types
import type { IIssueDetail } from "@/plane-web/store/issue/issue-details/root.store";

export const IssueDetailStoreContext = createContext<IIssueDetail | null>(null);

export const useIssueDetail = (serviceType: TIssueServiceType = EIssueServiceType.ISSUES): IIssueDetail => {
  const context = useContext(StoreContext);
  if (context === undefined) throw new Error("useIssueDetail must be used within StoreProvider");
  if (serviceType === EIssueServiceType.EPICS) return context.issue.epicDetail;
  else return context.issue.issueDetail;
};

export const useWorkItemIssueDetail = (issueId?: string, issueServiceType?: TIssueServiceType): IIssueDetail => {
  const issueStore = useIssueDetail(EIssueServiceType.ISSUES);
  const epicStore = useIssueDetail(EIssueServiceType.EPICS);

  if (issueServiceType === EIssueServiceType.EPICS) return epicStore;
  if (issueServiceType === EIssueServiceType.ISSUES) return issueStore;

  if (!issueId) return issueStore;

  const issue = issueStore.issue.getIssueById(issueId) ?? epicStore.issue.getIssueById(issueId);
  return issue?.is_epic ? epicStore : issueStore;
};

/** Resolves issue vs epic detail store from IssueDetailStoreContext (activity panel) or falls back to issues store. */
export const useActiveIssueDetail = (): IIssueDetail => {
  const activeStore = useContext(IssueDetailStoreContext);
  if (activeStore) return activeStore;
  return useIssueDetail(EIssueServiceType.ISSUES);
};
