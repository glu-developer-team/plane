/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { IBacklogProjectSync, IBacklogPullResponse, IBacklogSyncJobStatus, IBacklogSyncState } from "@plane/types";
import { APIService } from "@/services/api.service";

export class BacklogIntegrationService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getConfig(workspaceSlug: string, projectId: string): Promise<IBacklogProjectSync> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/backlog-sync/`)
      .then((response) => response?.data)
      .catch((error) => {
        if (error?.response?.status === 404) {
          return { enabled: false } as IBacklogProjectSync;
        }
        throw error?.response;
      });
  }

  async saveConfig(
    workspaceSlug: string,
    projectId: string,
    data: Partial<IBacklogProjectSync>
  ): Promise<IBacklogProjectSync> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/backlog-sync/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }

  async disconnect(workspaceSlug: string, projectId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/backlog-sync/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response;
      });
  }

  async pull(
    workspaceSlug: string,
    projectId: string,
    payload: { scope: "project" | "issue"; issue_id?: string }
  ): Promise<IBacklogPullResponse> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/backlog-sync/pull/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }

  async getJobStatus(workspaceSlug: string, projectId: string, jobId: string): Promise<IBacklogSyncJobStatus> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/backlog-sync/status/`, {
      params: { job_id: jobId },
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }

  async getSyncState(workspaceSlug: string, projectId: string): Promise<IBacklogSyncState> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/backlog-sync/sync-state/`)
      .then((response) => response?.data)
      .catch((error) => {
        if (error?.response?.status === 404) {
          return { enabled: false };
        }
        throw error?.response;
      });
  }
}

export const backlogIntegrationService = new BacklogIntegrationService();
