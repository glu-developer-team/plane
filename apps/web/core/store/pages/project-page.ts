/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { computed, makeObservable, action, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
import { set } from "lodash-es";
// constants
import { EPageAccess, EUserPermissions } from "@plane/constants";
import type { TPage } from "@plane/types";
// plane web store
import type { RootStore } from "@/plane-web/store/root.store";
// helpers
import { getPageName } from "@plane/utils";
// services
import { ProjectPageService } from "@/services/page";
const projectPageService = new ProjectPageService();
// store
import { BasePage } from "./base-page";
import type { TPageInstance } from "./base-page";

export type TProjectPage = TPageInstance;

export class ProjectPage extends BasePage implements TProjectPage {
  constructor(store: RootStore, page: TPage) {
    // required fields for API calls
    const { workspaceSlug } = store.router;
    const projectId = page.project_ids?.[0];
    // initialize base instance
    super(store, page, {
      update: async (payload) => {
        if (!workspaceSlug || !projectId || !page.id) throw new Error("Missing required fields.");
        return await projectPageService.update(workspaceSlug, projectId, page.id, payload);
      },
      updateDescription: async (document) => {
        if (!workspaceSlug || !projectId || !page.id) throw new Error("Missing required fields.");
        await projectPageService.updateDescription(workspaceSlug, projectId, page.id, document);
      },
      updateAccess: async (payload) => {
        if (!workspaceSlug || !projectId || !page.id) throw new Error("Missing required fields.");
        await projectPageService.updateAccess(workspaceSlug, projectId, page.id, payload);
      },
      lock: async () => {
        if (!workspaceSlug || !projectId || !page.id) throw new Error("Missing required fields.");
        await projectPageService.lock(workspaceSlug, projectId, page.id);
      },
      unlock: async () => {
        if (!workspaceSlug || !projectId || !page.id) throw new Error("Missing required fields.");
        await projectPageService.unlock(workspaceSlug, projectId, page.id);
      },
      archive: async () => {
        if (!workspaceSlug || !projectId || !page.id) throw new Error("Missing required fields.");
        return await projectPageService.archive(workspaceSlug, projectId, page.id);
      },
      restore: async () => {
        if (!workspaceSlug || !projectId || !page.id) throw new Error("Missing required fields.");
        await projectPageService.restore(workspaceSlug, projectId, page.id);
      },
      duplicate: async () => {
        if (!workspaceSlug || !projectId || !page.id) throw new Error("Missing required fields.");
        return await projectPageService.duplicate(workspaceSlug, projectId, page.id);
      },
    });
    makeObservable(this, {
      // computed
      subPageIds: computed,
      parentPageIds: computed,
      canCurrentUserAccessPage: computed,
      canCurrentUserEditPage: computed,
      canCurrentUserDuplicatePage: computed,
      canCurrentUserLockPage: computed,
      canCurrentUserChangeAccess: computed,
      canCurrentUserArchivePage: computed,
      canCurrentUserDeletePage: computed,
      canCurrentUserFavoritePage: computed,
      canCurrentUserMovePage: computed,
      isContentEditable: computed,
      // actions
      fetchSubPages: action,
    });
  }

  get parentPageIds() {
    const immediateParent = this.parent_id;
    if (!immediateParent) return [];
    const parentPageIds = [immediateParent];
    let parent = this.rootStore.projectPages.getPageById(immediateParent);
    while (parent?.parent_id) {
      parentPageIds.push(parent.parent_id);
      parent = this.rootStore.projectPages.getPageById(parent.parent_id);
    }
    return parentPageIds.filter((id): id is string => id !== undefined);
  }

  get subPageIds() {
    const pages = Object.values(this.rootStore.projectPages.data);
    const filteredPages = pages.filter((page) => page.parent_id === this.id && !page.deleted_at);
    const sortedPages = filteredPages.toSorted((a, b) =>
      getPageName(a.name).toLowerCase().localeCompare(getPageName(b.name).toLowerCase())
    );
    return sortedPages.map((page) => page.id).filter((id): id is string => id !== undefined);
  }

  fetchSubPages = async () => {
    try {
      const { workspaceSlug } = this.rootStore.router ?? {};
      const projectId = this.project_ids?.[0];
      if (!workspaceSlug || !projectId || !this.id) throw new Error("Required fields not found");
      const subPages = await projectPageService.fetchSubPages(workspaceSlug, projectId, this.id);

      runInAction(() => {
        for (const page of subPages) {
          if (page?.id) {
            const pageInstance = this.rootStore.projectPages.getPageById(page.id);
            if (pageInstance) {
              pageInstance.mutateProperties(page);
            } else {
              set(this.rootStore.projectPages.data, [page.id], new ProjectPage(this.rootStore, page));
            }
          }
        }
      });
    } catch (error) {
      console.error("Error in fetching sub-pages", error);
      throw error;
    }
  };

  private getHighestRoleAcrossProjects = computedFn((): EUserPermissions | undefined => {
    const { workspaceSlug } = this.rootStore.router;
    if (!workspaceSlug || !this.project_ids?.length) return;
    let highestRole: EUserPermissions | undefined = undefined;
    this.project_ids.map((projectId) => {
      const currentUserProjectRole = this.rootStore.user.permission.getProjectRoleByWorkspaceSlugAndProjectId(
        workspaceSlug?.toString() || "",
        projectId?.toString() || ""
      );
      if (currentUserProjectRole) {
        if (!highestRole) highestRole = currentUserProjectRole;
        else if (currentUserProjectRole > highestRole) highestRole = currentUserProjectRole;
      }
    });
    return highestRole;
  });

  /**
   * @description returns true if the current logged in user can access the page
   */
  get canCurrentUserAccessPage() {
    const isPagePublic = this.access === EPageAccess.PUBLIC;
    return isPagePublic || this.isCurrentUserOwner;
  }

  /**
   * @description returns true if the current logged in user can edit the page
   */
  get canCurrentUserEditPage() {
    const highestRole = this.getHighestRoleAcrossProjects();
    const isPagePublic = this.access === EPageAccess.PUBLIC;
    return (
      (isPagePublic && !!highestRole && highestRole >= EUserPermissions.MEMBER) ||
      (!isPagePublic && this.isCurrentUserOwner)
    );
  }

  /**
   * @description returns true if the current logged in user can create a duplicate the page
   */
  get canCurrentUserDuplicatePage() {
    const highestRole = this.getHighestRoleAcrossProjects();
    return !!highestRole && highestRole >= EUserPermissions.MEMBER;
  }

  /**
   * @description returns true if the current logged in user can lock the page
   */
  get canCurrentUserLockPage() {
    const highestRole = this.getHighestRoleAcrossProjects();
    return this.isCurrentUserOwner || highestRole === EUserPermissions.ADMIN;
  }

  /**
   * @description returns true if the current logged in user can change the access of the page
   */
  get canCurrentUserChangeAccess() {
    const highestRole = this.getHighestRoleAcrossProjects();
    return this.isCurrentUserOwner || highestRole === EUserPermissions.ADMIN;
  }

  /**
   * @description returns true if the current logged in user can archive the page
   */
  get canCurrentUserArchivePage() {
    const highestRole = this.getHighestRoleAcrossProjects();
    return this.isCurrentUserOwner || highestRole === EUserPermissions.ADMIN;
  }

  /**
   * @description returns true if the current logged in user can delete the page
   */
  get canCurrentUserDeletePage() {
    const highestRole = this.getHighestRoleAcrossProjects();
    return this.isCurrentUserOwner || highestRole === EUserPermissions.ADMIN;
  }

  /**
   * @description returns true if the current logged in user can favorite the page
   */
  get canCurrentUserFavoritePage() {
    const highestRole = this.getHighestRoleAcrossProjects();
    return !!highestRole && highestRole >= EUserPermissions.MEMBER;
  }

  /**
   * @description returns true if the current logged in user can move the page
   */
  get canCurrentUserMovePage() {
    const highestRole = this.getHighestRoleAcrossProjects();
    return this.isCurrentUserOwner || highestRole === EUserPermissions.ADMIN;
  }

  /**
   * @description returns true if the page can be edited
   */
  get isContentEditable() {
    const highestRole = this.getHighestRoleAcrossProjects();
    const isOwner = this.isCurrentUserOwner;
    const isPublic = this.access === EPageAccess.PUBLIC;
    const isArchived = this.archived_at;
    const isLocked = this.is_locked;

    return (
      !isArchived && !isLocked && (isOwner || (isPublic && !!highestRole && highestRole >= EUserPermissions.MEMBER))
    );
  }

  getRedirectionLink = computedFn(() => {
    const { workspaceSlug } = this.rootStore.router;
    return `/${workspaceSlug}/projects/${this.project_ids?.[0]}/pages/${this.id}`;
  });
}
