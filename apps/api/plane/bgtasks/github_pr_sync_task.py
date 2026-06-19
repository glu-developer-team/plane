# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import json
import logging
import traceback

from celery import shared_task

from plane.db.models import GithubSyncJob
from plane.utils.exception_logger import log_exception
from plane.utils.github.pr_sync import (
    finalize_github_webhook_log,
    get_enabled_github_project_sync,
    handle_issue_comment_event,
    handle_pull_request_event,
    handle_pull_request_review_event,
    push_plane_comment_to_github_prs,
    resync_open_tagged_pull_requests,
)

logger = logging.getLogger(__name__)


@shared_task
def github_webhook_event_task(event_name: str, payload: dict, log_id: str | None = None) -> dict:
    """Process GitHub webhook events for PR linking and comment sync."""
    result: dict = {"event": event_name, "handled": False, "reason": "unsupported_event"}
    try:
        action = payload.get("action")
        logger.info("github webhook event=%s action=%s", event_name, action)

        if event_name == "pull_request":
            result = {"event": event_name, **handle_pull_request_event(payload)}
        elif event_name == "issue_comment":
            result = {"event": event_name, **handle_issue_comment_event(payload)}
        elif event_name == "pull_request_review":
            result = {"event": event_name, **handle_pull_request_review_event(payload)}
        else:
            result = {"event": event_name, "action": action, "handled": False, "reason": "unsupported_event"}

        finalize_github_webhook_log(log_id, result)
        return result
    except Exception as exc:
        log_exception(exc)
        finalize_github_webhook_log(log_id, result, error=traceback.format_exc())
        raise


def dispatch_github_webhook(event_name: str, payload: dict, log_id: str | None = None) -> None:
    github_webhook_event_task.delay(event_name, json.loads(json.dumps(payload)), log_id)


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


@shared_task
def github_resync_project_task(project_id: str, job_id: str) -> dict:
    job = GithubSyncJob.objects.filter(id=job_id, deleted_at__isnull=True).first()
    try:
        if job:
            job.status = GithubSyncJob.STATUS_RUNNING
            job.save(update_fields=["status", "updated_at"])

        sync = get_enabled_github_project_sync(project_id)
        if not sync:
            if job:
                job.status = GithubSyncJob.STATUS_FAILED
                job.error = "GitHub PR sync not configured"
                job.save(update_fields=["status", "error", "updated_at"])
            return {"handled": False, "reason": "sync_not_configured"}

        stats = resync_open_tagged_pull_requests(sync)
        if job:
            job.status = GithubSyncJob.STATUS_COMPLETED
            job.stats = stats
            job.error = ""
            job.save(update_fields=["status", "stats", "error", "updated_at"])
        return {"handled": True, "stats": stats}
    except Exception as exc:
        log_exception(exc)
        if job:
            job.status = GithubSyncJob.STATUS_FAILED
            job.error = traceback.format_exc()
            job.save(update_fields=["status", "error", "updated_at"])
        raise
