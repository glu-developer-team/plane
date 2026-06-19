# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import traceback

from celery import shared_task
from django.utils import timezone

from plane.db.models import BacklogCommentSync, BacklogIssueSync, BacklogSyncJob, Issue, IssueComment
from plane.utils.backlog.client import BACKLOG_EXTERNAL_SOURCE, BacklogAPIError, is_backlog_no_change_error
from plane.utils.backlog.sync import (
    backlog_client_for_sync,
    clear_push_pending,
    default_issue_type_id,
    ensure_status_map,
    get_enabled_backlog_sync,
    html_to_markdown,
    is_backlog_push_enabled,
    parse_backlog_datetime,
    plane_issue_to_backlog_payload,
    set_skip_push,
    sync_backlog_comments,
    translate_text,
    upsert_plane_issue_from_backlog,
)
from plane.utils.exception_logger import log_exception


def _mark_job_running(job_id: str) -> BacklogSyncJob:
    job = BacklogSyncJob.objects.get(id=job_id)
    job.status = BacklogSyncJob.STATUS_RUNNING
    job.save(update_fields=["status", "updated_at"])
    return job


def _mark_job_completed(job: BacklogSyncJob, stats: dict) -> None:
    sync = get_enabled_backlog_sync(job.project_id)
    now = timezone.now()
    job.status = BacklogSyncJob.STATUS_COMPLETED
    job.stats = stats
    job.error = ""
    job.save(update_fields=["status", "stats", "error", "updated_at"])
    if sync:
        sync.last_pulled_at = now
        sync.last_sync_completed_at = now
        sync.save(update_fields=["last_pulled_at", "last_sync_completed_at", "updated_at"])


def _mark_job_failed(job_id: str, error: str) -> None:
    BacklogSyncJob.objects.filter(id=job_id).update(
        status=BacklogSyncJob.STATUS_FAILED,
        error=error[:4000],
    )


def _create_and_link_backlog_issue(issue: Issue, sync, client) -> bool:
    issue_type_id = default_issue_type_id(sync, client)
    if not issue_type_id:
        return False
    payload = plane_issue_to_backlog_payload(issue, sync, client)
    payload.update(
        {
            "projectId": sync.backlog_project_id,
            "issueTypeId": issue_type_id,
            "priorityId": payload.get("priorityId", 3),
        }
    )
    created = client.create_issue(payload)
    BacklogIssueSync.objects.create(
        project_id=sync.project_id,
        workspace_id=sync.workspace_id,
        issue=issue,
        backlog_issue_id=created["id"],
        backlog_issue_key=created["issueKey"],
        backlog_updated_at=parse_backlog_datetime(created.get("updated")) or timezone.now(),
        last_pushed_at=timezone.now(),
    )
    issue.external_source = BACKLOG_EXTERNAL_SOURCE
    issue.external_id = created["issueKey"]
    issue.save(update_fields=["external_source", "external_id", "updated_at"], disable_auto_set_user=True)
    return True


@shared_task
def backlog_push_issue_task(issue_id: str, action: str = "update") -> None:
    try:
        issue = Issue.objects.filter(id=issue_id, deleted_at__isnull=True, is_draft=False).first()
        if not issue:
            return
        sync = get_enabled_backlog_sync(issue.project_id)
        if not sync or not is_backlog_push_enabled(sync):
            return

        client = backlog_client_for_sync(sync)
        ensure_status_map(sync, client)
        issue_sync = BacklogIssueSync.objects.filter(issue_id=issue.id).first()

        if issue_sync:
            payload = plane_issue_to_backlog_payload(issue, sync, client)
            try:
                updated = client.update_issue(issue_sync.backlog_issue_key, payload)
            except BacklogAPIError as exc:
                if not is_backlog_no_change_error(exc):
                    raise
                updated = None
            issue_sync.last_pushed_at = timezone.now()
            if updated:
                issue_sync.backlog_updated_at = (
                    parse_backlog_datetime(updated.get("updated")) or issue_sync.last_pushed_at
                )
            issue_sync.save(update_fields=["last_pushed_at", "backlog_updated_at", "updated_at"])
        else:
            # Legacy Plane issues: first edit creates a linked Backlog issue (no pull merge).
            _create_and_link_backlog_issue(issue, sync, client)
    except Exception as exc:
        log_exception(exc)
        raise
    finally:
        clear_push_pending(issue_id)


@shared_task
def backlog_push_comment_task(comment_id: str) -> None:
    issue_id = None
    delegated_to_issue_push = False
    try:
        comment = IssueComment.objects.filter(id=comment_id, deleted_at__isnull=True).select_related("issue").first()
        if not comment:
            return
        if comment.external_source == BACKLOG_EXTERNAL_SOURCE:
            return
        if BacklogCommentSync.objects.filter(comment_id=comment_id).exists():
            return
        issue_id = str(comment.issue_id)
        sync = get_enabled_backlog_sync(comment.project_id)
        if not sync or not is_backlog_push_enabled(sync):
            return
        issue_sync = BacklogIssueSync.objects.filter(issue_id=comment.issue_id).first()
        client = backlog_client_for_sync(sync)
        ensure_status_map(sync, client)
        if not issue_sync:
            delegated_to_issue_push = True
            if not _create_and_link_backlog_issue(comment.issue, sync, client):
                return
            issue_sync = BacklogIssueSync.objects.filter(issue_id=comment.issue_id).first()
            if not issue_sync:
                return

        content = html_to_markdown(comment.comment_html)
        if not content:
            content = "(empty comment)"
        content = translate_text(sync, content, direction="to_backlog")
        created = client.create_comment(issue_sync.backlog_issue_key, content)
        BacklogCommentSync.objects.create(
            project_id=sync.project_id,
            workspace_id=sync.workspace_id,
            comment=comment,
            issue_sync=issue_sync,
            backlog_comment_id=created["id"],
        )
    except Exception as exc:
        log_exception(exc)
        raise
    finally:
        if issue_id and not delegated_to_issue_push:
            clear_push_pending(issue_id)


@shared_task
def backlog_pull_project_task(project_id: str, job_id: str) -> None:
    job = None
    try:
        job = _mark_job_running(job_id)
        sync = get_enabled_backlog_sync(project_id)
        if not sync:
            _mark_job_failed(job_id, "Backlog sync not configured")
            return

        client = backlog_client_for_sync(sync)
        if not sync.backlog_project_id:
            project = client.get_project(sync.backlog_project_key)
            sync.backlog_project_id = project["id"]
            sync.save(update_fields=["backlog_project_id", "updated_at"])

        ensure_status_map(sync, client)
        updated_since = None
        if sync.last_pulled_at:
            updated_since = sync.last_pulled_at.strftime("%Y-%m-%d")

        stats = {"created": 0, "updated": 0, "comments_created": 0, "activities_created": 0, "updated_issue_ids": []}
        offset = 0
        while True:
            issues = client.list_issues(
                project_id=sync.backlog_project_id,
                updated_since=updated_since,
                offset=offset,
                count=100,
            )
            if not issues:
                break
            for backlog_issue in issues:
                issue = upsert_plane_issue_from_backlog(sync, backlog_issue, stats=stats)
                issue_sync = BacklogIssueSync.objects.filter(issue_id=issue.id).first()
                if issue_sync:
                    sync_backlog_comments(sync, client, issue_sync, stats)
            if len(issues) < 100:
                break
            offset += 100

        _mark_job_completed(job, stats)
    except Exception as exc:
        log_exception(exc)
        _mark_job_failed(job_id, traceback.format_exc())
        raise


@shared_task
def backlog_pull_issue_task(project_id: str, issue_id: str, job_id: str) -> None:
    job = None
    try:
        job = _mark_job_running(job_id)
        sync = get_enabled_backlog_sync(project_id)
        if not sync:
            _mark_job_failed(job_id, "Backlog sync not configured")
            return

        client = backlog_client_for_sync(sync)
        ensure_status_map(sync, client)
        issue_sync = BacklogIssueSync.objects.filter(issue_id=issue_id, project_id=project_id).first()

        stats = {"created": 0, "updated": 0, "comments_created": 0, "activities_created": 0, "updated_issue_ids": []}
        if issue_sync:
            backlog_issue = client.get_issue(issue_sync.backlog_issue_key)
        else:
            plane_issue = Issue.objects.filter(id=issue_id, project_id=project_id).first()
            if plane_issue and plane_issue.external_id and plane_issue.external_source == BACKLOG_EXTERNAL_SOURCE:
                backlog_issue = client.get_issue(plane_issue.external_id)
            else:
                _mark_job_completed(job, stats)
                return

        upsert_plane_issue_from_backlog(sync, backlog_issue, stats=stats)
        issue_sync = BacklogIssueSync.objects.filter(issue_id=issue_id, project_id=project_id).first()
        if issue_sync:
            sync_backlog_comments(sync, client, issue_sync, stats)

        _mark_job_completed(job, stats)
    except Exception as exc:
        log_exception(exc)
        _mark_job_failed(job_id, traceback.format_exc())
        raise
