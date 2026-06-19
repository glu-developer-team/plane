/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { IGithubProjectSync } from "@plane/types";
import { APIService } from "@/services/api.service";

export class GithubPRIntegrationService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getConfig(workspaceSlug: string, projectId: string): Promise<IGithubProjectSync> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/github-pr-sync/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }

  async saveConfig(
    workspaceSlug: string,
    projectId: string,
    data: Partial<IGithubProjectSync>
  ): Promise<IGithubProjectSync> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/github-pr-sync/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }

  async disconnect(workspaceSlug: string, projectId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/github-pr-sync/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response;
      });
  }

  async registerInstallation(
    workspaceSlug: string,
    data: { installation_id: number; project_id?: string }
  ): Promise<{ installation_id: number }> {
    return this.post(`/api/workspaces/${workspaceSlug}/github-app/install/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }

  async resync(
    workspaceSlug: string,
    projectId: string
  ): Promise<{ job_id: string; status: string; deduplicated: boolean }> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/github-pr-sync/resync/`, {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }

  async getResyncStatus(
    workspaceSlug: string,
    projectId: string,
    jobId: string
  ): Promise<{ id: string; status: string; stats: Record<string, number>; error: string }> {
    return this.get(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/github-pr-sync/resync/status/?job_id=${jobId}`
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }
}

export const githubPRIntegrationService = new GithubPRIntegrationService();
