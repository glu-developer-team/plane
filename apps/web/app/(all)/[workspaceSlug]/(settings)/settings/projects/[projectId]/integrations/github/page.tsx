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
import type { TGithubPRSyncMode } from "@plane/types";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
import { PROJECT_GITHUB_PR_SYNC } from "@/constants/github-pr-sync";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { githubPRIntegrationService } from "@/services/integration/github-pr.service";
import type { Route } from "./+types/page";
import { GithubIntegrationProjectSettingsHeader } from "./header";

function GithubIntegrationSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { t } = useTranslation();
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { currentProjectDetails: projectDetails } = useProject();
  const { config: instanceConfig } = useInstance();
  const { startAuth, isConnecting } = useIntegrationPopup({
    provider: "github",
    github_app_name: instanceConfig?.github_app_name || "",
  });

  const { data: config, mutate } = useSWR(PROJECT_GITHUB_PR_SYNC(workspaceSlug, projectId), () =>
    githubPRIntegrationService.getConfig(workspaceSlug, projectId)
  );

  const [repoOwner, setRepoOwner] = useState("");
  const [repoName, setRepoName] = useState("");
  const [installationId, setInstallationId] = useState("");
  const [isEnabled, setIsEnabled] = useState(true);
  const [syncMode, setSyncMode] = useState<TGithubPRSyncMode>("bidirectional");
  const [isSaving, setIsSaving] = useState(false);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (!config || initialized) return;
    setRepoOwner(config.repo_owner || "");
    setRepoName(config.repo_name || "");
    setInstallationId(config.installation_id ? String(config.installation_id) : "");
    setIsEnabled(config.is_enabled ?? true);
    setSyncMode(config.sync_mode === "github_to_plane" ? "github_to_plane" : "bidirectional");
    setInitialized(true);
  }, [config, initialized]);

  const canPerformProjectAdminActions = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT);
  const pageTitle = projectDetails?.name ? `${projectDetails?.name} - GitHub PR` : undefined;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const payload: Record<string, unknown> = {
        repo_owner: repoOwner.trim(),
        repo_name: repoName.trim(),
        is_enabled: isEnabled,
        sync_mode: syncMode,
      };
      if (installationId.trim()) {
        payload.installation_id = Number(installationId.trim());
      }
      await githubPRIntegrationService.saveConfig(workspaceSlug, projectId, payload);
      await mutate();
      setInitialized(false);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("project_settings.integrations.github.saved"),
      });
    } catch (error: any) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error",
        message: error?.data?.detail || "Failed to save GitHub PR settings",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await githubPRIntegrationService.disconnect(workspaceSlug, projectId);
      await mutate();
      setRepoOwner("");
      setRepoName("");
      setInstallationId("");
      setInitialized(false);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("project_settings.integrations.github.disconnected"),
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error",
        message: "Failed to disconnect GitHub PR sync",
      });
    }
  };

  if (workspaceUserInfo && !canPerformProjectAdminActions) {
    return <NotAuthorizedView section="settings" isProjectView className="h-auto" />;
  }

  return (
    <SettingsContentWrapper header={<GithubIntegrationProjectSettingsHeader />} hugging>
      <PageHead title={pageTitle} />
      <section className="w-full max-w-2xl">
        <SettingsHeading
          title={t("project_settings.integrations.github.heading")}
          description={t("project_settings.integrations.github.description")}
        />
        <div className="mt-6 space-y-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="text-sm rounded-md border border-subtle px-4 py-2 font-medium"
              disabled={isConnecting || !instanceConfig?.github_app_name}
              onClick={() => startAuth()}
            >
              {isConnecting
                ? t("project_settings.integrations.github.connecting")
                : t("project_settings.integrations.github.connect")}
            </button>
            {!instanceConfig?.github_app_name && (
              <p className="text-xs text-tertiary">{t("project_settings.integrations.github.connect_unconfigured")}</p>
            )}
          </div>
          <div>
            <label className="text-sm font-medium text-secondary">
              {t("project_settings.integrations.github.repo_owner")}
            </label>
            <input
              className="text-sm mt-1 block w-full rounded-md border border-subtle bg-layer-1 px-3 py-2"
              placeholder={t("project_settings.integrations.github.repo_owner_placeholder")}
              value={repoOwner}
              onChange={(e) => setRepoOwner(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-secondary">
              {t("project_settings.integrations.github.repo_name")}
            </label>
            <input
              className="text-sm mt-1 block w-full rounded-md border border-subtle bg-layer-1 px-3 py-2"
              placeholder={t("project_settings.integrations.github.repo_name_placeholder")}
              value={repoName}
              onChange={(e) => setRepoName(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-secondary">
              {t("project_settings.integrations.github.installation_id")}
            </label>
            <input
              className="text-sm mt-1 block w-full rounded-md border border-subtle bg-layer-1 px-3 py-2"
              placeholder={t("project_settings.integrations.github.installation_id_placeholder")}
              value={installationId}
              onChange={(e) => setInstallationId(e.target.value)}
            />
            <p className="text-xs mt-1 text-tertiary">
              {t("project_settings.integrations.github.installation_id_hint")}
            </p>
          </div>
          <label className="text-sm flex items-center gap-2">
            <input type="checkbox" checked={isEnabled} onChange={(e) => setIsEnabled(e.target.checked)} />
            {t("project_settings.integrations.github.enabled")}
          </label>

          <fieldset>
            <legend className="text-sm font-medium text-secondary">
              {t("project_settings.integrations.github.sync_mode")}
            </legend>
            <div className="mt-2 space-y-2">
              <div className="text-sm flex cursor-pointer items-start gap-2 rounded-md border border-subtle p-3">
                <input
                  type="radio"
                  id="github-sync-mode-pull"
                  name="github-sync-mode"
                  className="mt-0.5"
                  checked={syncMode === "github_to_plane"}
                  onChange={() => setSyncMode("github_to_plane")}
                />
                <label htmlFor="github-sync-mode-pull" className="cursor-pointer">
                  <span className="font-medium text-primary">
                    {t("project_settings.integrations.github.sync_mode_github_to_plane")}
                  </span>
                  <span className="mt-0.5 block text-secondary">
                    {t("project_settings.integrations.github.sync_mode_github_to_plane_hint")}
                  </span>
                </label>
              </div>
              <div className="text-sm flex cursor-pointer items-start gap-2 rounded-md border border-subtle p-3">
                <input
                  type="radio"
                  id="github-sync-mode-bidirectional"
                  name="github-sync-mode"
                  className="mt-0.5"
                  checked={syncMode === "bidirectional"}
                  onChange={() => setSyncMode("bidirectional")}
                />
                <label htmlFor="github-sync-mode-bidirectional" className="cursor-pointer">
                  <span className="font-medium text-primary">
                    {t("project_settings.integrations.github.sync_mode_bidirectional")}
                  </span>
                  <span className="mt-0.5 block text-secondary">
                    {t("project_settings.integrations.github.sync_mode_bidirectional_hint")}
                  </span>
                </label>
              </div>
            </div>
          </fieldset>

          <div className="flex items-center gap-3 border-t border-subtle pt-4">
            <button
              type="button"
              className="text-sm rounded-md bg-accent-primary px-4 py-2 font-medium text-on-color"
              disabled={isSaving || !repoOwner.trim() || !repoName.trim()}
              onClick={handleSave}
            >
              {isSaving
                ? t("project_settings.integrations.github.saving")
                : t("project_settings.integrations.github.save")}
            </button>
            {config?.enabled && (
              <button
                type="button"
                className="text-sm rounded-md border border-subtle px-4 py-2"
                onClick={handleDisconnect}
              >
                {t("project_settings.integrations.github.disconnect")}
              </button>
            )}
          </div>
        </div>
      </section>
    </SettingsContentWrapper>
  );
}

export default observer(GithubIntegrationSettingsPage);
