/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IBacklogLocaleEntry, IBacklogProjectSync, IBacklogStatusLocaleEntry } from "@plane/types";

export function buildDefaultEnglishOverrides(config: IBacklogProjectSync | undefined): Record<string, string> {
  const defaults = config?.default_locale_entries || [];
  const custom = config?.custom_locale_entries || [];
  const overrides: Record<string, string> = {};

  for (const entry of defaults) {
    const customMatch = custom.find((item) => item.japanese === entry.japanese);
    overrides[entry.japanese] = customMatch?.english ?? entry.english;
  }

  return overrides;
}

export function buildCustomOnlyEntries(config: IBacklogProjectSync | undefined): IBacklogLocaleEntry[] {
  const defaults = config?.default_locale_entries || [];
  const custom = config?.custom_locale_entries || [];
  const defaultJapanese = new Set(defaults.map((entry) => entry.japanese));
  const entries: IBacklogLocaleEntry[] = [];

  for (const entry of custom) {
    if (defaultJapanese.has(entry.japanese)) continue;
    entries.push({
      japanese: entry.japanese,
      english: entry.english,
      client_key: entry.client_key ?? crypto.randomUUID(),
    });
  }

  return entries;
}

export function buildLocaleSavePayload(
  defaults: IBacklogLocaleEntry[],
  defaultEnglishOverrides: Record<string, string>,
  customOnlyEntries: IBacklogLocaleEntry[]
): IBacklogLocaleEntry[] {
  const entries: IBacklogLocaleEntry[] = [];

  for (const entry of defaults) {
    const japanese = entry.japanese.trim();
    const english = (defaultEnglishOverrides[entry.japanese] ?? entry.english).trim();
    if (japanese && english) {
      entries.push({ japanese, english });
    }
  }

  for (const entry of customOnlyEntries) {
    const japanese = entry.japanese.trim();
    const english = entry.english.trim();
    if (japanese && english) {
      entries.push({ japanese, english });
    }
  }

  return entries;
}

export function cloneStatusEntries(entries: IBacklogStatusLocaleEntry[] = []): IBacklogStatusLocaleEntry[] {
  return entries.map((entry) => ({ ...entry }));
}
