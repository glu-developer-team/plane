# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import json
import logging

from celery import shared_task

from plane.utils.exception_logger import log_exception
from plane.utils.github.pr_sync import handle_pull_request_event

logger = logging.getLogger(__name__)


@shared_task
def github_webhook_event_task(event_name: str, payload: dict) -> dict:
    """Process GitHub webhook events for PR linking and comment sync."""
    try:
        action = payload.get("action")
        logger.info("github webhook event=%s action=%s", event_name, action)

        if event_name == "pull_request":
            result = handle_pull_request_event(payload)
            return {"event": event_name, **result}

        return {"event": event_name, "action": action, "handled": False, "reason": "unsupported_event"}
    except Exception as exc:
        log_exception(exc)
        raise


def dispatch_github_webhook(event_name: str, payload: dict) -> None:
    github_webhook_event_task.delay(event_name, json.loads(json.dumps(payload)))
