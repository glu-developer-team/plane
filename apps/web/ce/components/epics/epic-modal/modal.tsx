/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";
import { CreateUpdateIssueModal } from "@/components/issues/issue-modal/modal";
import type { TIssue } from "@plane/types";
import { EIssuesStoreType } from "@plane/types";

export interface EpicModalProps {
  data?: Partial<TIssue>;
  isOpen: boolean;
  onClose: () => void;
  beforeFormSubmit?: () => Promise<void>;
  onSubmit?: (res: TIssue) => Promise<void>;
  fetchIssueDetails?: boolean;
  primaryButtonText?: {
    default: string;
    loading: string;
  };
  isProjectSelectionDisabled?: boolean;
}

export function CreateUpdateEpicModal(props: EpicModalProps) {
  const { t } = useTranslation();
  const {
    data,
    isOpen,
    onClose,
    beforeFormSubmit,
    onSubmit,
    fetchIssueDetails = true,
    primaryButtonText,
    isProjectSelectionDisabled = false,
  } = props;

  return (
    <CreateUpdateIssueModal
      data={data}
      isOpen={isOpen}
      onClose={onClose}
      beforeFormSubmit={beforeFormSubmit}
      onSubmit={onSubmit}
      fetchIssueDetails={fetchIssueDetails}
      storeType={EIssuesStoreType.EPIC}
      isProjectSelectionDisabled={isProjectSelectionDisabled}
      modalTitle={t("epic.new")}
      primaryButtonText={
        primaryButtonText ?? {
          default: t("epic.new"),
          loading: t("epic.adding"),
        }
      }
    />
  );
}
