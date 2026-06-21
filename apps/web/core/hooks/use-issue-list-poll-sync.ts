/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef } from "react";

export const ISSUE_LIST_POLL_INTERVAL_MS = 5000;

type UseIssueListPollSyncOptions = {
  enabled: boolean;
  onPoll: () => void | Promise<void>;
  intervalMs?: number;
};

export function useIssueListPollSync({
  enabled,
  onPoll,
  intervalMs = ISSUE_LIST_POLL_INTERVAL_MS,
}: UseIssueListPollSyncOptions) {
  const onPollRef = useRef(onPoll);
  onPollRef.current = onPoll;
  const inFlightRef = useRef(false);

  useEffect(() => {
    if (!enabled) return;

    const tick = async () => {
      if (document.visibilityState !== "visible" || inFlightRef.current) return;

      inFlightRef.current = true;
      try {
        await onPollRef.current();
      } catch {
        // ignore polling errors
      } finally {
        inFlightRef.current = false;
      }
    };

    void tick();
    const interval = setInterval(() => {
      void tick();
    }, intervalMs);
    const onVisibility = () => {
      if (document.visibilityState === "visible") void tick();
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [enabled, intervalMs]);
}
