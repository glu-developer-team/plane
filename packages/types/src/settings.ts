/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// local imports
import type { EUserProjectRoles } from ".";
import type { EUserWorkspaceRoles } from "./workspace";

export type TProfileSettingsTabs = "general" | "preferences" | "activity" | "notifications" | "security" | "api-tokens";

export type TWorkspaceSettingsTabs = "general" | "members" | "billing-and-plans" | "export" | "webhooks";
export type TWorkspaceSettingsItem = {
  key: TWorkspaceSettingsTabs;
  i18n_label: string;
  href: string;
  access: EUserWorkspaceRoles[];
  highlight: (pathname: string, baseUrl: string) => boolean;
};

export type TProjectSettingsTabs =
  | "general"
  | "members"
  | "features_cycles"
  | "features_modules"
  | "features_views"
  | "features_pages"
  | "features_intake"
  | "states"
  | "labels"
  | "estimates"
  | "automations"
  | "integrations_backlog";

export interface IBacklogLocaleEntry {
  japanese: string;
  english: string;
  /** Client-only stable key for editable locale rows */
  client_key?: string;
}

export interface IBacklogStatusLocaleEntry {
  backlog_status_id: string;
  japanese: string;
  english: string;
}

export type TBacklogSyncMode = "backlog_to_plane" | "bidirectional";

export interface IBacklogProjectSync {
  id?: string;
  enabled: boolean;
  space_host: string;
  backlog_project_key: string;
  backlog_project_id?: number | null;
  is_enabled: boolean;
  sync_mode?: TBacklogSyncMode;
  api_key_set?: boolean;
  api_key_masked?: string;
  api_key?: string;
  last_pulled_at?: string | null;
  last_sync_completed_at?: string | null;
  default_locale_entries?: IBacklogLocaleEntry[];
  custom_locale_entries?: IBacklogLocaleEntry[];
  status_locale_entries?: IBacklogStatusLocaleEntry[];
}

export interface IBacklogPullResponse {
  job_id: string;
  status: string;
  deduplicated: boolean;
}

export interface IBacklogSyncState {
  enabled: boolean;
  last_sync_completed_at?: string | null;
  last_pull_stats?: Record<string, unknown>;
  active_job?: {
    id: string;
    status: string;
    scope: string;
    issue_id?: string | null;
  } | null;
}

export interface IBacklogSyncJobStatus {
  id: string;
  status: string;
  scope: string;
  issue_id?: string | null;
  stats: Record<string, unknown>;
  error?: string;
}
export type TProjectSettingsItem = {
  key: TProjectSettingsTabs;
  i18n_label: string;
  href: string;
  access: EUserProjectRoles[];
  highlight: (pathname: string, baseUrl: string) => boolean;
};
