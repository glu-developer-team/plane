/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set } from "lodash-es";
import { action, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// types
import type { TBaseIssue, TIssue } from "@plane/types";
import { EIssueServiceType } from "@plane/types";
// services
import { IssueService } from "@/services/issue/issue.service";
// store
import type { CoreRootStore } from "./root.store";

export interface IEpicStore {
  loader: boolean;
  fetchedMap: Record<string, boolean>;
  epicMap: Record<string, TIssue>;
  getEpicsFetchStatusByProjectId: (projectId: string) => boolean;
  getEpicById: (epicId: string) => TIssue | null;
  getProjectEpicIds: (projectId: string) => string[] | null;
  fetchEpics: (workspaceSlug: string, projectId: string) => Promise<TIssue[] | undefined>;
}

export class EpicStore implements IEpicStore {
  loader = false;
  fetchedMap: Record<string, boolean> = {};
  epicMap: Record<string, TIssue> = {};
  rootStore: CoreRootStore;
  epicService: IssueService;

  constructor(_rootStore: CoreRootStore) {
    makeObservable(this, {
      loader: observable.ref,
      fetchedMap: observable,
      epicMap: observable,
      fetchEpics: action,
    });
    this.rootStore = _rootStore;
    this.epicService = new IssueService(EIssueServiceType.EPICS);
  }

  getEpicsFetchStatusByProjectId = computedFn((projectId: string): boolean => this.fetchedMap[projectId] ?? false);

  getEpicById = computedFn((epicId: string): TIssue | null => this.epicMap[epicId] ?? null);

  getProjectEpicIds = computedFn((projectId: string): string[] | null => {
    if (!this.fetchedMap[projectId]) return null;

    const epicIds = Object.values(this.epicMap)
      .filter((epic) => epic.project_id === projectId)
      .map((epic) => epic.id);

    return epicIds.length > 0 ? epicIds : [];
  });

  private normalizeEpicList = (results: TBaseIssue[] | Record<string, unknown>): TIssue[] => {
    if (Array.isArray(results)) {
      return results.map((epic) => {
        const withEpicFlag = epic as TIssue;
        withEpicFlag.is_epic = true;
        return withEpicFlag;
      });
    }

    if (results && typeof results === "object") {
      const groupedEpics = Object.values(results).flatMap((group) => {
        if (Array.isArray(group)) return group;
        if (group && typeof group === "object" && "results" in group) {
          const nestedResults = (group as { results: TBaseIssue[] | Record<string, { results: TBaseIssue[] }> })
            .results;
          if (Array.isArray(nestedResults)) return nestedResults;
          return Object.values(nestedResults).flatMap((subGroup) => subGroup.results ?? []);
        }
        return [];
      });

      return groupedEpics.map((epic) => {
        const withEpicFlag = epic as TIssue;
        withEpicFlag.is_epic = true;
        return withEpicFlag;
      });
    }

    return [];
  };

  fetchEpics = async (workspaceSlug: string, projectId: string) => {
    try {
      this.loader = true;
      const response = await this.epicService.getIssues(workspaceSlug, projectId, {
        per_page: "250",
        cursor: "250:0:0",
      });
      const epics = this.normalizeEpicList(response.results);

      runInAction(() => {
        epics.forEach((epic) => {
          set(this.epicMap, [epic.id], { ...this.epicMap[epic.id], ...epic });
        });
        set(this.fetchedMap, projectId, true);
        this.loader = false;
      });

      return epics;
    } catch {
      runInAction(() => {
        this.loader = false;
      });
      return undefined;
    }
  };
}
