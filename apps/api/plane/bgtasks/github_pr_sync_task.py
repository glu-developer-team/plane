# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import json
import logging

from celery import shared_task

from plane.utils.exception_logger import log_exception
from plane.utils.github.pr_sync import (
    handle_issue_comment_event,
    handle_pull_request_event,
    push_plane_comment_to_github_prs,
)

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

        if event_name == "issue_comment":
            result = handle_issue_comment_event(payload)
            return {"event": event_name, **result}

        return {"event": event_name, "action": action, "handled": False, "reason": "unsupported_event"}
    except Exception as exc:
        log_exception(exc)
        raise


def dispatch_github_webhook(event_name: str, payload: dict) -> None:
    github_webhook_event_task.delay(event_name, json.loads(json.dumps(payload)))


@shared_task
def github_push_comment_task(comment_id: str) -> dict:
    """Push a Plane task comment to linked GitHub pull requests."""
    try:
        from plane.db.models import IssueComment

        comment = IssueComment.objects.filter(id=comment_id, deleted_at__isnull=True).select_related(
            "issue", "actor"
        ).first()
        if not comment:
            return {"handled": False, "reason": "comment_not_found"}

        from plane.utils.github.pr_sync import (
            GITHUB_PR_EXTERNAL_SOURCE,
            get_enabled_github_project_sync,
            is_github_push_enabled,
        )

        if comment.external_source == GITHUB_PR_EXTERNAL_SOURCE:
            return {"handled": False, "reason": "external_comment"}

        sync = get_enabled_github_project_sync(comment.project_id)
        if not sync or not is_github_push_enabled(sync):
            return {"handled": False, "reason": "push_disabled"}

        pushed = push_plane_comment_to_github_prs(comment, sync)
        return {
            "handled": bool(pushed),
            "comment_id": str(comment_id),
            "pushed_count": len(pushed),
            "github_comment_ids": [record.github_comment_id for record in pushed],
        }
    except Exception as exc:
        log_exception(exc)
        raise
