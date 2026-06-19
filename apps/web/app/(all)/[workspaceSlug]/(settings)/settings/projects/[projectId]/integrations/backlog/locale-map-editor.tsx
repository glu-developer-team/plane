/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IBacklogLocaleEntry, IBacklogStatusLocaleEntry } from "@plane/types";
import { useTranslation } from "@plane/i18n";

type LocaleMapEditorProps = {
  customEntries: IBacklogLocaleEntry[];
  defaultEntries: IBacklogLocaleEntry[];
  defaultEnglishOverrides: Record<string, string>;
  statusEntries: IBacklogStatusLocaleEntry[];
  onCustomEntriesChange: (entries: IBacklogLocaleEntry[]) => void;
  onDefaultEnglishChange: (japanese: string, english: string) => void;
  onStatusEnglishChange: (backlogStatusId: string, english: string) => void;
};

const inputClassName =
  "w-full rounded-md border border-subtle bg-layer-1 px-2 py-1.5 text-sm text-primary focus:border-accent-primary focus:outline-none";

export function LocaleMapEditor({
  customEntries,
  defaultEntries,
  defaultEnglishOverrides,
  statusEntries,
  onCustomEntriesChange,
  onDefaultEnglishChange,
  onStatusEnglishChange,
}: LocaleMapEditorProps) {
  const { t } = useTranslation();

  const handleCustomChange = (index: number, field: "japanese" | "english", value: string) => {
    const next = customEntries.map((entry, i) => (i === index ? { ...entry, [field]: value } : entry));
    onCustomEntriesChange(next);
  };

  const handleAddCustom = () => {
    onCustomEntriesChange([...customEntries, { japanese: "", english: "", client_key: crypto.randomUUID() }]);
  };

  const handleRemoveCustom = (index: number) => {
    onCustomEntriesChange(customEntries.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-6 border-t border-subtle pt-6">
      <div>
        <h3 className="text-sm font-semibold text-primary">
          {t("project_settings.integrations.backlog.locale_heading")}
        </h3>
        <p className="text-sm mt-1 text-tertiary">{t("project_settings.integrations.backlog.locale_description")}</p>
        <p className="text-xs mt-1 text-tertiary">{t("project_settings.integrations.backlog.locale_save_hint")}</p>
      </div>

      <div>
        <h4 className="text-sm mb-1 font-medium text-secondary">
          {t("project_settings.integrations.backlog.locale_default_heading")}
        </h4>
        <p className="text-xs mb-2 text-tertiary">{t("project_settings.integrations.backlog.locale_default_hint")}</p>
        <div className="overflow-hidden rounded-md border border-subtle">
          <table className="text-sm w-full">
            <thead className="bg-layer-2 text-left text-tertiary">
              <tr>
                <th className="px-3 py-2 font-medium">{t("project_settings.integrations.backlog.locale_japanese")}</th>
                <th className="px-3 py-2 font-medium">{t("project_settings.integrations.backlog.locale_english")}</th>
              </tr>
            </thead>
            <tbody>
              {defaultEntries.map((entry) => (
                <tr key={entry.japanese} className="border-t border-subtle">
                  <td className="px-3 py-2 text-secondary">{entry.japanese}</td>
                  <td className="px-3 py-2">
                    <input
                      className={inputClassName}
                      value={defaultEnglishOverrides[entry.japanese] ?? entry.english}
                      onChange={(e) => onDefaultEnglishChange(entry.japanese, e.target.value)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <div>
            <h4 className="text-sm font-medium text-secondary">
              {t("project_settings.integrations.backlog.locale_custom_heading")}
            </h4>
            <p className="text-xs text-tertiary">{t("project_settings.integrations.backlog.locale_custom_hint")}</p>
          </div>
          <button
            type="button"
            className="text-sm shrink-0 rounded-md border border-subtle bg-layer-1 px-3 py-1.5 font-medium hover:bg-layer-2"
            onClick={handleAddCustom}
          >
            {t("project_settings.integrations.backlog.locale_add_row")}
          </button>
        </div>
        {customEntries.length === 0 ? (
          <button
            type="button"
            className="text-sm hover:border-accent-primary w-full rounded-md border border-dashed border-subtle px-4 py-6 text-tertiary hover:text-secondary"
            onClick={handleAddCustom}
          >
            {t("project_settings.integrations.backlog.locale_add_first")}
          </button>
        ) : (
          <div className="overflow-hidden rounded-md border border-subtle">
            <table className="text-sm w-full">
              <thead className="bg-layer-2 text-left text-tertiary">
                <tr>
                  <th className="px-3 py-2 font-medium">
                    {t("project_settings.integrations.backlog.locale_japanese")}
                  </th>
                  <th className="px-3 py-2 font-medium">{t("project_settings.integrations.backlog.locale_english")}</th>
                  <th className="w-20 px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {customEntries.map((entry, index) => (
                  <tr
                    key={entry.client_key ?? `${entry.japanese}::${entry.english}`}
                    className="border-t border-subtle"
                  >
                    <td className="px-3 py-2">
                      <input
                        className={inputClassName}
                        placeholder={t("project_settings.integrations.backlog.locale_japanese_placeholder")}
                        value={entry.japanese}
                        onChange={(e) => handleCustomChange(index, "japanese", e.target.value)}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        className={inputClassName}
                        placeholder={t("project_settings.integrations.backlog.locale_english_placeholder")}
                        value={entry.english}
                        onChange={(e) => handleCustomChange(index, "english", e.target.value)}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        className="text-xs hover:text-danger text-tertiary"
                        onClick={() => handleRemoveCustom(index)}
                      >
                        {t("project_settings.integrations.backlog.locale_remove_row")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <h4 className="text-sm mb-1 font-medium text-secondary">
          {t("project_settings.integrations.backlog.locale_status_heading")}
        </h4>
        <p className="text-xs mb-2 text-tertiary">{t("project_settings.integrations.backlog.locale_status_hint")}</p>
        {statusEntries.length === 0 ? (
          <p className="text-sm text-tertiary">{t("project_settings.integrations.backlog.locale_no_status")}</p>
        ) : (
          <div className="overflow-hidden rounded-md border border-subtle">
            <table className="text-sm w-full">
              <thead className="bg-layer-2 text-left text-tertiary">
                <tr>
                  <th className="px-3 py-2 font-medium">
                    {t("project_settings.integrations.backlog.locale_japanese")}
                  </th>
                  <th className="px-3 py-2 font-medium">{t("project_settings.integrations.backlog.locale_english")}</th>
                </tr>
              </thead>
              <tbody>
                {statusEntries.map((entry) => (
                  <tr key={entry.backlog_status_id} className="border-t border-subtle">
                    <td className="px-3 py-2 text-secondary">{entry.japanese}</td>
                    <td className="px-3 py-2">
                      <input
                        className={inputClassName}
                        value={entry.english}
                        onChange={(e) => onStatusEnglishChange(entry.backlog_status_id, e.target.value)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
