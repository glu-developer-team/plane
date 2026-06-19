/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import type { TFilterProperty, TIssue } from "@plane/types";
import { EQUALITY_OPERATOR, COLLECTION_OPERATOR } from "@plane/types";
// local imports
import type { TCreateFilterConfigParams, IFilterIconConfig, TCreateFilterConfig } from "../../../rich-filters";
import { createFilterConfig, getMultiSelectConfig, createOperatorConfigEntry } from "../../../rich-filters";

/**
 * Epic (parent) filter specific params
 */
export type TCreateEpicFilterParams = TCreateFilterConfigParams &
  IFilterIconConfig<undefined> & {
    epics: TIssue[];
  };

/**
 * Helper to get the epic multi select config
 * @param params - The filter params
 * @returns The epic multi select config
 */
export const getEpicMultiSelectConfig = (params: TCreateEpicFilterParams) =>
  getMultiSelectConfig<TIssue, string, undefined>(
    {
      items: params.epics,
      getId: (epic) => epic.id,
      getLabel: (epic) => epic.name,
      getValue: (epic) => epic.id,
      getIconData: () => undefined,
    },
    {
      singleValueOperator: EQUALITY_OPERATOR.EXACT,
      ...params,
    },
    {
      ...params,
    }
  );

/**
 * Get the epic filter config
 * @template K - The filter key
 * @param key - The filter key to use
 * @returns A function that takes parameters and returns the epic filter config
 */
export const getEpicFilterConfig =
  <P extends TFilterProperty>(key: P): TCreateFilterConfig<P, TCreateEpicFilterParams> =>
  (params: TCreateEpicFilterParams) =>
    createFilterConfig<P>({
      id: key,
      label: "Epic",
      ...params,
      icon: params.filterIcon,
      supportedOperatorConfigsMap: new Map([
        createOperatorConfigEntry(COLLECTION_OPERATOR.IN, params, (updatedParams) =>
          getEpicMultiSelectConfig(updatedParams)
        ),
      ]),
    });
