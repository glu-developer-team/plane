/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IBacklogLocaleEntry, IBacklogStatusLocaleEntry, TBacklogSyncMode } from "@plane/types";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
import { PROJECT_BACKLOG_SYNC } from "@/constants/backlog-sync";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { backlogIntegrationService } from "@/services/integration/backlog.service";
import type { Route } from "./+types/page";
import { BacklogIntegrationProjectSettingsHeader } from "./header";
import {
  buildCustomOnlyEntries,
  buildDefaultEnglishOverrides,
  buildLocaleSavePayload,
  cloneStatusEntries,
} from "./locale-helpers";
import { LocaleMapEditor } from "./locale-map-editor";

function BacklogIntegrationSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { t } = useTranslation();
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { currentProjectDetails: projectDetails } = useProject();

  const { data: config, mutate } = useSWR(PROJECT_BACKLOG_SYNC(workspaceSlug, projectId), () =>
    backlogIntegrationService.getConfig(workspaceSlug, projectId)
  );

  const [spaceHost, setSpaceHost] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [projectKey, setProjectKey] = useState("");
  const [isEnabled, setIsEnabled] = useState(true);
  const [syncMode, setSyncMode] = useState<TBacklogSyncMode>("bidirectional");
  const [defaultEnglishOverrides, setDefaultEnglishOverrides] = useState<Record<string, string>>({});
  const [customLocaleEntries, setCustomLocaleEntries] = useState<IBacklogLocaleEntry[]>([]);
  const [statusLocaleEntries, setStatusLocaleEntries] = useState<IBacklogStatusLocaleEntry[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (!config || initialized) return;
    setSpaceHost(config.space_host || "");
    setProjectKey(config.backlog_project_key || "");
    setIsEnabled(config.is_enabled ?? true);
    setSyncMode(config.sync_mode === "backlog_to_plane" ? "backlog_to_plane" : "bidirectional");
    setDefaultEnglishOverrides(buildDefaultEnglishOverrides(config));
    setCustomLocaleEntries(buildCustomOnlyEntries(config));
    setStatusLocaleEntries(cloneStatusEntries(config.status_locale_entries));
    setInitialized(true);
  }, [config, initialized]);

  const canPerformProjectAdminActions = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT);
  const pageTitle = projectDetails?.name ? `${projectDetails?.name} - Backlog` : undefined;

  const handleDefaultEnglishChange = (japanese: string, english: string) => {
    setDefaultEnglishOverrides((current) => ({ ...current, [japanese]: english }));
  };

  const handleStatusEnglishChange = (backlogStatusId: string, english: string) => {
    setStatusLocaleEntries((current) =>
      current.map((entry) => (entry.backlog_status_id === backlogStatusId ? { ...entry, english } : entry))
    );
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const payload: Record<string, unknown> = {
        space_host: spaceHost,
        backlog_project_key: projectKey,
        is_enabled: isEnabled,
        sync_mode: syncMode,
        test_connection: true,
        custom_locale_entries: buildLocaleSavePayload(
          config?.default_locale_entries || [],
          defaultEnglishOverrides,
          customLocaleEntries
        ),
        status_locale_entries: statusLocaleEntries
          .filter((entry) => entry.backlog_status_id && entry.english.trim())
          .map((entry) => ({
            backlog_status_id: entry.backlog_status_id,
            english: entry.english.trim(),
          })),
      };
      if (apiKey) payload.api_key = apiKey;
      await backlogIntegrationService.saveConfig(workspaceSlug, projectId, payload);
      await mutate();
      setApiKey("");
      setInitialized(false);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("project_settings.integrations.backlog.saved"),
      });
    } catch (error: any) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error",
        message: error?.data?.detail || error?.data?.api_key?.[0] || "Failed to save Backlog settings",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await backlogIntegrationService.disconnect(workspaceSlug, projectId);
      await mutate();
      setSpaceHost("");
      setProjectKey("");
      setApiKey("");
      setDefaultEnglishOverrides({});
      setCustomLocaleEntries([]);
      setStatusLocaleEntries([]);
      setInitialized(false);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("project_settings.integrations.backlog.disconnected"),
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error",
        message: "Failed to disconnect Backlog",
      });
    }
  };

  if (workspaceUserInfo && !canPerformProjectAdminActions) {
    return <NotAuthorizedView section="settings" isProjectView className="h-auto" />;
  }

  return (
    <SettingsContentWrapper header={<BacklogIntegrationProjectSettingsHeader />} hugging>
      <PageHead title={pageTitle} />
      <section className="w-full max-w-2xl">
        <SettingsHeading
          title={t("project_settings.integrations.backlog.heading")}
          description={t("project_settings.integrations.backlog.description")}
        />
        <div className="mt-6 space-y-4">
          <div>
            <label className="text-sm font-medium text-secondary">
              {t("project_settings.integrations.backlog.space_host")}
            </label>
            <input
              className="text-sm mt-1 block w-full rounded-md border border-subtle bg-layer-1 px-3 py-2"
              placeholder={t("project_settings.integrations.backlog.space_host_placeholder")}
              value={spaceHost}
              onChange={(e) => setSpaceHost(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-secondary">
              {t("project_settings.integrations.backlog.api_key")}
            </label>
            <input
              type="password"
              className="text-sm mt-1 block w-full rounded-md border border-subtle bg-layer-1 px-3 py-2"
              placeholder={
                config?.api_key_masked
                  ? `${config.api_key_masked} (leave blank to keep)`
                  : t("project_settings.integrations.backlog.api_key_placeholder")
              }
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-secondary">
              {t("project_settings.integrations.backlog.project_key")}
            </label>
            <input
              className="text-sm mt-1 block w-full rounded-md border border-subtle bg-layer-1 px-3 py-2"
              placeholder={t("project_settings.integrations.backlog.project_key_placeholder")}
              value={projectKey}
              onChange={(e) => setProjectKey(e.target.value)}
            />
          </div>
          <label className="text-sm flex items-center gap-2">
            <input type="checkbox" checked={isEnabled} onChange={(e) => setIsEnabled(e.target.checked)} />
            {t("project_settings.integrations.backlog.enabled")}
          </label>

          <fieldset>
            <legend className="text-sm font-medium text-secondary">
              {t("project_settings.integrations.backlog.sync_mode")}
            </legend>
            <div className="mt-2 space-y-2">
              <div className="text-sm flex cursor-pointer items-start gap-2 rounded-md border border-subtle p-3">
                <input
                  type="radio"
                  id="backlog-sync-mode-pull"
                  name="backlog-sync-mode"
                  className="mt-0.5"
                  checked={syncMode === "backlog_to_plane"}
                  onChange={() => setSyncMode("backlog_to_plane")}
                />
                <label htmlFor="backlog-sync-mode-pull" className="cursor-pointer">
                  <span className="font-medium text-primary">
                    {t("project_settings.integrations.backlog.sync_mode_backlog_to_plane")}
                  </span>
                  <span className="mt-0.5 block text-secondary">
                    {t("project_settings.integrations.backlog.sync_mode_backlog_to_plane_hint")}
                  </span>
                </label>
              </div>
              <div className="text-sm flex cursor-pointer items-start gap-2 rounded-md border border-subtle p-3">
                <input
                  type="radio"
                  id="backlog-sync-mode-bidirectional"
                  name="backlog-sync-mode"
                  className="mt-0.5"
                  checked={syncMode === "bidirectional"}
                  onChange={() => setSyncMode("bidirectional")}
                />
                <label htmlFor="backlog-sync-mode-bidirectional" className="cursor-pointer">
                  <span className="font-medium text-primary">
                    {t("project_settings.integrations.backlog.sync_mode_bidirectional")}
                  </span>
                  <span className="mt-0.5 block text-secondary">
                    {t("project_settings.integrations.backlog.sync_mode_bidirectional_hint")}
                  </span>
                </label>
              </div>
            </div>
          </fieldset>

          <LocaleMapEditor
            customEntries={customLocaleEntries}
            defaultEntries={config?.default_locale_entries || []}
            defaultEnglishOverrides={defaultEnglishOverrides}
            statusEntries={statusLocaleEntries}
            onCustomEntriesChange={setCustomLocaleEntries}
            onDefaultEnglishChange={handleDefaultEnglishChange}
            onStatusEnglishChange={handleStatusEnglishChange}
          />

          <div className="flex items-center gap-3 border-t border-subtle pt-4">
            <button
              type="button"
              className="text-sm rounded-md bg-accent-primary px-4 py-2 font-medium text-on-color"
              disabled={isSaving || !spaceHost || !projectKey}
              onClick={handleSave}
            >
              {isSaving
                ? t("project_settings.integrations.backlog.saving")
                : t("project_settings.integrations.backlog.save")}
            </button>
            {config?.enabled && (
              <button
                type="button"
                className="text-sm rounded-md border border-subtle px-4 py-2"
                onClick={handleDisconnect}
              >
                {t("project_settings.integrations.backlog.disconnect")}
              </button>
            )}
          </div>
        </div>
      </section>
    </SettingsContentWrapper>
  );
}

export default observer(BacklogIntegrationSettingsPage);
