# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import html as html_module
from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.html import strip_tags

from plane.db.models import (
    BacklogActivitySync,
    BacklogCommentSync,
    BacklogIssueSync,
    BacklogProjectSync,
    BacklogSyncJob,
    Issue,
    IssueActivity,
    IssueAssignee,
    IssueComment,
    State,
    StateGroup,
    User,
)
from plane.settings.redis import redis_instance
from plane.utils.backlog.client import (
    BACKLOG_EXTERNAL_SOURCE,
    BACKLOG_PULL_DEBOUNCE_SECONDS,
    BACKLOG_PUSH_PENDING_TTL,
    BACKLOG_SKIP_PULL_NOTIFY_TTL,
    BACKLOG_SKIP_PUSH_TTL,
    BacklogClient,
    BacklogAPIError,
)
from plane.utils.backlog.locale_map import (
    looks_like_partial_translation,
    resolve_status_english,
    translate_status_name,
    translate_text,
)
from plane.utils.encryption import decrypt_value

PLANE_PRIORITY_TO_BACKLOG = {
    "urgent": 2,
    "high": 2,
    "medium": 3,
    "low": 4,
    "none": 3,
}

BACKLOG_PRIORITY_TO_PLANE = {
    2: "high",
    3: "medium",
    4: "low",
}

BACKLOG_PRIORITY_LABELS = {
    2: "High",
    3: "Medium",
    4: "Low",
}

CHANGELOG_FIELD_TO_PLANE = {
    "status": "state",
    "assignee": "assignees",
    "assigner": "assignees",
    "priority": "priority",
    "summary": "name",
    "description": "description",
    "dueDate": "target_date",
    "startDate": "start_date",
}

SYNC_MODE_BACKLOG_TO_PLANE = "backlog_to_plane"
SYNC_MODE_BIDIRECTIONAL = "bidirectional"
SYNC_MODE_CHOICES = (SYNC_MODE_BACKLOG_TO_PLANE, SYNC_MODE_BIDIRECTIONAL)
DEFAULT_SYNC_MODE = SYNC_MODE_BIDIRECTIONAL
BACKLOG_SYNC_JOB_TIMEOUT = timedelta(minutes=30)
BACKLOG_SYNC_JOB_TIMEOUT_ERROR = "Backlog sync job timed out before completion"


def get_sync_mode(sync: BacklogProjectSync) -> str:
    mode = (sync.config or {}).get("sync_mode")
    if mode in SYNC_MODE_CHOICES:
        return mode
    return DEFAULT_SYNC_MODE


def is_backlog_push_enabled(sync: BacklogProjectSync) -> bool:
    return get_sync_mode(sync) == SYNC_MODE_BIDIRECTIONAL


def get_enabled_backlog_sync(project_id) -> BacklogProjectSync | None:
    try:
        sync = BacklogProjectSync.objects.get(project_id=project_id, deleted_at__isnull=True)
    except BacklogProjectSync.DoesNotExist:
        return None
    if not sync.is_enabled:
        return None
    if not sync.space_host or not sync.api_key_encrypted or not sync.backlog_project_key:
        return None
    return sync


def backlog_client_for_sync(sync: BacklogProjectSync) -> BacklogClient:
    return BacklogClient(sync.space_host, decrypt_value(sync.api_key_encrypted))


def set_skip_push(issue_id: str, ttl: int = BACKLOG_SKIP_PUSH_TTL) -> None:
    redis_instance().set(f"backlog_skip_push:{issue_id}", "1", ex=ttl)


def should_skip_push(issue_id: str) -> bool:
    return bool(redis_instance().get(f"backlog_skip_push:{issue_id}"))


def set_skip_pull_notify(issue_id: str, ttl: int = BACKLOG_SKIP_PULL_NOTIFY_TTL) -> None:
    redis_instance().set(f"backlog_skip_pull_notify:{issue_id}", "1", ex=ttl)


def should_skip_pull_notify(issue_id: str) -> bool:
    return bool(redis_instance().get(f"backlog_skip_pull_notify:{issue_id}"))


def set_push_pending(issue_id: str, ttl: int = BACKLOG_PUSH_PENDING_TTL) -> None:
    redis_instance().set(f"backlog_push_pending:{issue_id}", "1", ex=ttl)


def is_push_pending(issue_id: str) -> bool:
    return bool(redis_instance().get(f"backlog_push_pending:{issue_id}"))


def clear_push_pending(issue_id: str) -> None:
    redis_instance().delete(f"backlog_push_pending:{issue_id}")


def should_skip_pull_overwrite(issue: Issue, issue_sync: BacklogIssueSync, backlog_updated) -> bool:
    issue_id = str(issue.id)
    if should_skip_pull_notify(issue_id) or is_push_pending(issue_id):
        return True
    if backlog_updated and issue_sync.backlog_updated_at and backlog_updated > issue_sync.backlog_updated_at:
        return False
    if issue_sync.last_pushed_at is None or issue.updated_at > issue_sync.last_pushed_at:
        return True
    return False


def _pull_window_key(scope: str, project_id: str, issue_id: str | None) -> str:
    if scope == BacklogSyncJob.SCOPE_ISSUE and issue_id:
        return f"backlog_pull:window:issue:{issue_id}"
    return f"backlog_pull:window:project:{project_id}"


def expire_stale_backlog_sync_jobs(project_id, *, scope: str | None = None, issue_id=None) -> int:
    """Fail orphaned jobs so they cannot block future pull requests indefinitely."""
    now = timezone.now()
    stale_jobs = BacklogSyncJob.objects.filter(
        project_id=project_id,
        status__in=[BacklogSyncJob.STATUS_PENDING, BacklogSyncJob.STATUS_RUNNING],
        updated_at__lt=now - BACKLOG_SYNC_JOB_TIMEOUT,
        deleted_at__isnull=True,
    )
    if scope:
        stale_jobs = stale_jobs.filter(scope=scope)
    if issue_id:
        stale_jobs = stale_jobs.filter(issue_id=issue_id)

    return stale_jobs.update(
        status=BacklogSyncJob.STATUS_FAILED,
        error=BACKLOG_SYNC_JOB_TIMEOUT_ERROR,
        updated_at=now,
    )


def enqueue_backlog_pull(project_id, scope: str, issue_id=None) -> tuple[BacklogSyncJob | None, bool]:
    sync = get_enabled_backlog_sync(project_id)
    if not sync:
        return None, False

    issue = None
    if scope == BacklogSyncJob.SCOPE_ISSUE:
        if not issue_id:
            return None, False
        issue = Issue.objects.filter(id=issue_id, project_id=project_id).first()
        if not issue:
            return None, False

    expire_stale_backlog_sync_jobs(project_id, scope=scope, issue_id=issue_id)

    active_qs = BacklogSyncJob.objects.filter(
        project_id=project_id,
        scope=scope,
        status__in=[BacklogSyncJob.STATUS_PENDING, BacklogSyncJob.STATUS_RUNNING],
        deleted_at__isnull=True,
    )
    if scope == BacklogSyncJob.SCOPE_ISSUE:
        active_qs = active_qs.filter(issue_id=issue_id)
    else:
        active_qs = active_qs.filter(issue__isnull=True)

    active = active_qs.order_by("-created_at").first()
    if active:
        return active, True

    redis = redis_instance()
    window_key = _pull_window_key(scope, str(project_id), str(issue_id) if issue_id else None)
    cached_job_id = redis.get(window_key)
    if cached_job_id:
        cached = BacklogSyncJob.objects.filter(id=cached_job_id.decode(), deleted_at__isnull=True).first()
        if cached and cached.status != BacklogSyncJob.STATUS_FAILED:
            return cached, True

    job = BacklogSyncJob.objects.create(
        project_id=project_id,
        workspace_id=sync.workspace_id,
        scope=scope,
        issue=issue,
        status=BacklogSyncJob.STATUS_PENDING,
    )
    redis.setex(window_key, BACKLOG_PULL_DEBOUNCE_SECONDS, str(job.id))

    from plane.bgtasks.backlog_sync_task import backlog_pull_issue_task, backlog_pull_project_task

    if scope == BacklogSyncJob.SCOPE_ISSUE:
        result = backlog_pull_issue_task.delay(str(project_id), str(issue_id), str(job.id))
    else:
        result = backlog_pull_project_task.delay(str(project_id), str(job.id))
    job.celery_task_id = result.id or ""
    job.save(update_fields=["celery_task_id", "updated_at"])
    return job, False


def enqueue_backlog_push_issue(issue_id: str, action: str = "update") -> None:
    project_id = Issue.objects.filter(id=issue_id).values_list("project_id", flat=True).first()
    if not project_id:
        return
    sync = get_enabled_backlog_sync(project_id)
    if not sync or not is_backlog_push_enabled(sync):
        return
    if should_skip_push(str(issue_id)):
        return
    from plane.bgtasks.backlog_sync_task import backlog_push_issue_task

    set_skip_pull_notify(str(issue_id))
    set_push_pending(str(issue_id))
    backlog_push_issue_task.delay(str(issue_id), action)


def enqueue_backlog_push_comment(comment_id: str) -> None:
    comment = IssueComment.objects.filter(id=comment_id).select_related("issue").first()
    if not comment:
        return
    sync = get_enabled_backlog_sync(comment.project_id)
    if not sync or not is_backlog_push_enabled(sync):
        return
    if comment.external_source == BACKLOG_EXTERNAL_SOURCE:
        return
    if BacklogCommentSync.objects.filter(comment_id=comment_id).exists():
        return
    if should_skip_push(str(comment.issue_id)):
        return
    from plane.bgtasks.backlog_sync_task import backlog_push_comment_task

    set_skip_pull_notify(str(comment.issue_id))
    set_push_pending(str(comment.issue_id))
    backlog_push_comment_task.delay(str(comment_id))


def ensure_status_map(sync: BacklogProjectSync, client: BacklogClient) -> dict[str, str]:
    """Backlog statuses are canonical — mirror them onto Plane states before every sync."""
    return sync_backlog_statuses_to_plane(sync, client)


def backlog_status_to_plane_group(name: str, index: int, total: int) -> str:
    lower = (name or "").lower()
    if index == 0:
        return StateGroup.BACKLOG.value
    if index == total - 1:
        return StateGroup.COMPLETED.value
    if any(token in lower for token in ("progress", "処理中", "doing", "進行")):
        return StateGroup.STARTED.value
    if any(token in lower for token in ("resolved", "処理済", "review", "レビュー")):
        return StateGroup.STARTED.value
    if "cancel" in lower:
        return StateGroup.CANCELLED.value
    if any(token in lower for token in ("close", "完了", "done")):
        return StateGroup.COMPLETED.value
    return StateGroup.UNSTARTED.value


def sync_backlog_statuses_to_plane(sync: BacklogProjectSync, client: BacklogClient) -> dict[str, str]:
    try:
        statuses = client.get_statuses(sync.backlog_project_key)
    except BacklogAPIError:
        config = sync.config or {}
        return config.get("status_map") or {}

    statuses = sorted(statuses, key=lambda entry: entry.get("displayOrder", 0))
    status_map: dict[str, str] = {}
    backlog_status_ids: dict[str, int] = {}
    backlog_status_order: list[str] = []
    backlog_status_labels: dict[str, dict[str, str]] = {}
    total = len(statuses)

    config = sync.config or {}
    status_en_overrides = dict(config.get("status_en_overrides") or {})

    for index, status in enumerate(statuses):
        sid = str(status["id"])
        backlog_status_ids[sid] = status["id"]
        backlog_status_order.append(sid)
        ja_name = (status.get("name") or sid).strip()
        override = status_en_overrides.get(sid)
        if override and looks_like_partial_translation(override):
            status_en_overrides.pop(sid, None)
            override = None
        en_name = override or translate_status_name(sync, ja_name)
        backlog_status_labels[sid] = {"ja": ja_name, "en": en_name}
        group = backlog_status_to_plane_group(ja_name, index, total)
        state_defaults = {
            "name": en_name[:255],
            "color": status.get("color") or "#60646C",
            "sequence": float(status.get("displayOrder", (index + 1) * 1000)),
            "group": group,
            "external_source": BACKLOG_EXTERNAL_SOURCE,
            "external_id": sid,
        }

        state = State.all_state_objects.filter(
            project_id=sync.project_id,
            external_source=BACKLOG_EXTERNAL_SOURCE,
            external_id=sid,
            deleted_at__isnull=True,
        ).first()

        if not state:
            state = State.all_state_objects.filter(
                project_id=sync.project_id,
                name=en_name,
                deleted_at__isnull=True,
            ).exclude(external_source=BACKLOG_EXTERNAL_SOURCE).first()
        if not state and ja_name != en_name:
            state = State.all_state_objects.filter(
                project_id=sync.project_id,
                name=ja_name,
                deleted_at__isnull=True,
            ).exclude(external_source=BACKLOG_EXTERNAL_SOURCE).first()

        if state:
            for field, value in state_defaults.items():
                setattr(state, field, value)
            state.default = index == 0
            state.save(
                update_fields=[
                    "name",
                    "color",
                    "sequence",
                    "group",
                    "external_source",
                    "external_id",
                    "default",
                    "updated_at",
                ],
                disable_auto_set_user=True,
            )
        else:
            state = State(
                project_id=sync.project_id,
                workspace_id=sync.workspace_id,
                default=index == 0,
                created_by_id=sync.created_by_id,
                **state_defaults,
            )
            state.save(created_by_id=sync.created_by_id, disable_auto_set_user=True)

        status_map[sid] = str(state.id)

    if statuses:
        State.objects.filter(project_id=sync.project_id, default=True).exclude(
            external_source=BACKLOG_EXTERNAL_SOURCE
        ).update(default=False)
        first_state_id = status_map.get(str(statuses[0]["id"]))
        if first_state_id:
            State.objects.filter(project_id=sync.project_id, default=True).update(default=False)
            State.objects.filter(id=first_state_id).update(default=True)

    config = sync.config or {}
    config["status_map"] = status_map
    config["backlog_status_ids"] = backlog_status_ids
    config["backlog_status_order"] = backlog_status_order
    config["backlog_status_labels"] = backlog_status_labels
    config["status_en_overrides"] = status_en_overrides
    sync.config = config
    sync.save(update_fields=["config", "updated_at"])
    return status_map


def default_backlog_plane_state_id(sync: BacklogProjectSync) -> str | None:
    config = sync.config or {}
    status_map: dict[str, str] = config.get("status_map") or {}
    if not status_map:
        return None
    ordered = config.get("backlog_status_order") or list(status_map.keys())
    if not ordered:
        return next(iter(status_map.values()), None)
    return status_map.get(str(ordered[0]))


def backlog_status_id_for_plane_state(sync: BacklogProjectSync, state_id) -> int | None:
    state = State.all_state_objects.filter(id=state_id, deleted_at__isnull=True).first()
    if state and state.external_source == BACKLOG_EXTERNAL_SOURCE and state.external_id:
        return int(state.external_id)

    config = sync.config or {}
    status_map: dict[str, str] = config.get("status_map") or {}
    for backlog_id, plane_state_id in status_map.items():
        if str(plane_state_id) == str(state_id):
            return int(backlog_id)
    return None


def plane_state_id_for_backlog_status(sync: BacklogProjectSync, status_id: int | None) -> str | None:
    if status_id is None:
        return default_backlog_plane_state_id(sync)

    state = State.all_state_objects.filter(
        project_id=sync.project_id,
        external_source=BACKLOG_EXTERNAL_SOURCE,
        external_id=str(status_id),
        deleted_at__isnull=True,
    ).first()
    if state:
        return str(state.id)

    config = sync.config or {}
    status_map: dict[str, str] = config.get("status_map") or {}
    return status_map.get(str(status_id))


def default_issue_type_id(sync: BacklogProjectSync, client: BacklogClient) -> int | None:
    config = sync.config or {}
    if config.get("default_issue_type_id"):
        return int(config["default_issue_type_id"])
    try:
        types = client.get_issue_types(sync.backlog_project_key)
    except BacklogAPIError:
        return None
    if not types:
        return None
    type_id = types[0]["id"]
    config["default_issue_type_id"] = type_id
    sync.config = config
    sync.save(update_fields=["config", "updated_at"])
    return type_id


def resolve_backlog_assignee_id(client: BacklogClient, user: User | None) -> int | None:
    if not user or not user.email:
        return None
    users = client.list_users()
    email = user.email.lower()
    for entry in users:
        if (entry.get("mailAddress") or "").lower() == email:
            return entry.get("id")
    return None


def parse_backlog_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(value.replace("Z", "+00:00"))
    return parsed


def parse_backlog_date(value: str | None):
    if not value:
        return None
    return parse_date(value.split("T")[0])


def html_to_plain(html: str | None) -> str:
    if not html:
        return ""
    return strip_tags(html).strip()


def html_to_markdown(html: str | None) -> str:
    if not html:
        return ""
    stripped = strip_tags(html).strip()
    if not stripped:
        return ""
    try:
        from markdownify import markdownify as md_convert

        return md_convert(html, heading_style="ATX", bullets="-").strip()
    except Exception:
        return html_to_plain(html)


def resolve_backlog_actor_id(entry: dict[str, Any], sync: BacklogProjectSync, fallback_id) -> str | None:
    user_data = entry.get("createdUser") or {}
    email = (user_data.get("mailAddress") or "").strip().lower()
    if email:
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            return str(user.id)
    if fallback_id:
        return str(fallback_id)
    if sync.created_by_id:
        return str(sync.created_by_id)
    return None


def backlog_text_to_html(text: str) -> str:
    if not text:
        return ""
    paragraphs = text.split("\n\n")
    parts: list[str] = []
    for paragraph in paragraphs:
        stripped = paragraph.strip()
        if not stripped:
            continue
        escaped = html_module.escape(stripped)
        parts.append(f"<p>{escaped.replace(chr(10), '<br>')}</p>")
    return "".join(parts) or ""


def backlog_comment_to_html(sync: BacklogProjectSync, entry: dict[str, Any]) -> str | None:
    content = translate_text(sync, (entry.get("content") or "").strip(), direction="to_plane")
    if not content:
        return None
    html = backlog_text_to_html(content)
    return html or None


def _format_changelog_value(sync: BacklogProjectSync, field: str, value: str | None) -> str:
    if not value:
        return ""
    if field == "status":
        return resolve_status_english(sync, value)
    if field == "priority":
        return BACKLOG_PRIORITY_LABELS.get(int(value), value) if value.isdigit() else value
    if field in ("summary", "description"):
        return translate_text(sync, value, direction="to_plane")
    return value


def _changelog_activity_comment(field: str, old_value: str, new_value: str) -> str:
    plane_field = CHANGELOG_FIELD_TO_PLANE.get(field, field)
    if plane_field == "state":
        return "updated the state to"
    if plane_field == "assignees":
        if old_value and not new_value:
            return "removed assignee "
        if new_value and not old_value:
            return "added assignee "
        return "updated assignee"
    if plane_field == "priority":
        return "updated the priority to"
    if plane_field == "name":
        return "updated the title to"
    if plane_field == "description":
        return "updated the description"
    if plane_field == "target_date":
        return "updated the due date to"
    if plane_field == "start_date":
        return "updated the start date to"
    return f"updated {field}"


def record_backlog_state_activity(
    issue: Issue,
    old_state_id,
    new_state_id,
    *,
    actor_id,
    created_at: datetime | None = None,
) -> bool:
    if not new_state_id or str(old_state_id or "") == str(new_state_id):
        return False
    old_state = State.objects.filter(id=old_state_id).first() if old_state_id else None
    new_state = State.objects.filter(id=new_state_id).first()
    if not new_state:
        return False
    when = created_at or timezone.now()
    epoch = when.timestamp()
    IssueActivity.objects.create(
        issue_id=issue.id,
        project_id=issue.project_id,
        workspace_id=issue.workspace_id,
        actor_id=actor_id,
        verb="updated",
        field="state",
        old_value=old_state.name if old_state else None,
        new_value=new_state.name,
        comment="updated the state to",
        old_identifier=old_state.id if old_state else None,
        new_identifier=new_state.id,
        epoch=epoch,
        created_by_id=actor_id,
        created_at=when,
        updated_at=when,
    )
    return True


def sync_backlog_changelog_to_activities(
    sync: BacklogProjectSync,
    issue_sync: BacklogIssueSync,
    entry: dict[str, Any],
    *,
    stats: dict[str, Any],
) -> None:
    change_log = entry.get("changeLog") or []
    if not change_log:
        return

    cid = entry.get("id")
    if not cid:
        return

    actor_id = resolve_backlog_actor_id(entry, sync, issue_sync.issue.created_by_id)
    created_at = parse_backlog_datetime(entry.get("created")) or timezone.now()
    epoch = created_at.timestamp()

    existing_fields = set(
        BacklogActivitySync.objects.filter(issue_sync=issue_sync, backlog_comment_id=cid).values_list(
            "change_field", flat=True
        )
    )

    for change in change_log:
        field = (change.get("field") or "").strip()
        if not field or field in existing_fields:
            continue

        plane_field = CHANGELOG_FIELD_TO_PLANE.get(field, field)
        old_value = _format_changelog_value(sync, field, (change.get("originalValue") or "").strip())
        new_value = _format_changelog_value(sync, field, (change.get("newValue") or "").strip())
        comment = _changelog_activity_comment(field, old_value, new_value)

        activity_kwargs: dict[str, Any] = {
            "issue_id": issue_sync.issue_id,
            "project_id": sync.project_id,
            "workspace_id": sync.workspace_id,
            "actor_id": actor_id,
            "verb": "updated",
            "field": plane_field,
            "old_value": old_value or None,
            "new_value": new_value or None,
            "comment": comment,
            "epoch": epoch,
            "created_by_id": actor_id or sync.created_by_id,
            "created_at": created_at,
            "updated_at": created_at,
        }

        if field == "status" and new_value:
            new_state = State.objects.filter(
                project_id=sync.project_id, name=new_value, deleted_at__isnull=True
            ).first()
            old_state = (
                State.objects.filter(project_id=sync.project_id, name=old_value, deleted_at__isnull=True).first()
                if old_value
                else None
            )
            if new_state:
                activity_kwargs["new_identifier"] = new_state.id
            if old_state:
                activity_kwargs["old_identifier"] = old_state.id

        IssueActivity.objects.create(**activity_kwargs)
        BacklogActivitySync.objects.create(
            project_id=sync.project_id,
            workspace_id=sync.workspace_id,
            issue_sync=issue_sync,
            backlog_comment_id=cid,
            change_field=field,
            created_by_id=sync.created_by_id,
        )
        existing_fields.add(field)
        stats["activities_created"] = stats.get("activities_created", 0) + 1


def plane_issue_to_backlog_payload(issue: Issue, sync: BacklogProjectSync, client: BacklogClient) -> dict[str, Any]:
    description_md = html_to_markdown(issue.description_html)
    payload: dict[str, Any] = {
        "summary": translate_text(sync, issue.name[:255], direction="to_backlog"),
        "description": translate_text(sync, description_md, direction="to_backlog"),
    }
    status_id = backlog_status_id_for_plane_state(sync, issue.state_id)
    if status_id:
        payload["statusId"] = status_id
    priority_id = PLANE_PRIORITY_TO_BACKLOG.get(issue.priority or "none", 3)
    payload["priorityId"] = priority_id
    if issue.target_date:
        payload["dueDate"] = issue.target_date.isoformat()
    if issue.start_date:
        payload["startDate"] = issue.start_date.isoformat()
    assignee = (
        IssueAssignee.objects.filter(issue_id=issue.id, deleted_at__isnull=True)
        .select_related("assignee")
        .first()
    )
    if assignee and assignee.assignee:
        assignee_id = resolve_backlog_assignee_id(client, assignee.assignee)
        if assignee_id:
            payload["assigneeId"] = assignee_id
    return payload


def upsert_plane_issue_from_backlog(
    sync: BacklogProjectSync,
    backlog_issue: dict[str, Any],
    *,
    stats: dict[str, Any],
) -> Issue:
    issue_key = backlog_issue["issueKey"]
    issue_sync = (
        BacklogIssueSync.objects.filter(project_id=sync.project_id, backlog_issue_key=issue_key)
        .select_related("issue")
        .first()
    )

    state_id = plane_state_id_for_backlog_status(sync, backlog_issue.get("status", {}).get("id"))
    if not state_id:
        state_id = default_backlog_plane_state_id(sync)
    if not state_id:
        default_state = State.objects.filter(project_id=sync.project_id, default=True).first()
        state_id = str(default_state.id) if default_state else None

    priority = BACKLOG_PRIORITY_TO_PLANE.get(backlog_issue.get("priority", {}).get("id"), "none")
    name = translate_text(sync, backlog_issue.get("summary") or issue_key, direction="to_plane")
    description = translate_text(sync, backlog_issue.get("description") or "", direction="to_plane")
    due = parse_backlog_date(backlog_issue.get("dueDate"))
    start = parse_backlog_date(backlog_issue.get("startDate"))
    updated = parse_backlog_datetime(backlog_issue.get("updated"))

    if issue_sync:
        issue = issue_sync.issue
        skip_content = should_skip_pull_overwrite(issue, issue_sync, updated)
        update_fields: list[str] = []

        if not skip_content:
            issue.name = name[:255]
            issue.description_html = description
            issue.priority = priority
            issue.target_date = due or None
            issue.start_date = start or None
            update_fields.extend(["name", "description_html", "priority", "target_date", "start_date"])

        if state_id and str(issue.state_id) != str(state_id):
            issue.state_id = state_id
            update_fields.append("state_id")

        issue.external_source = BACKLOG_EXTERNAL_SOURCE
        issue.external_id = issue_key
        update_fields.extend(["external_source", "external_id", "updated_at"])

        changed = bool(set(update_fields) - {"external_source", "external_id", "updated_at"})
        if update_fields:
            set_skip_push(str(issue.id))
            issue.save(update_fields=update_fields, disable_auto_set_user=True)

        issue_sync.backlog_issue_id = backlog_issue["id"]
        issue_sync.backlog_updated_at = updated
        issue_sync.save(update_fields=["backlog_issue_id", "backlog_updated_at", "updated_at"])

        if changed:
            stats["updated"] = stats.get("updated", 0) + 1
            stats.setdefault("updated_issue_ids", []).append(str(issue.id))
        elif skip_content:
            stats["skipped"] = stats.get("skipped", 0) + 1
        return issue

    if not state_id:
        default_state = State.objects.filter(project_id=sync.project_id, default=True).first()
        if not default_state:
            raise BacklogAPIError("Project has no default state for Backlog import")
        state_id = str(default_state.id)

    issue = Issue.objects.create(
        project_id=sync.project_id,
        workspace_id=sync.workspace_id,
        name=name[:255],
        description_html=description,
        state_id=state_id,
        priority=priority,
        target_date=due or None,
        start_date=start or None,
        external_source=BACKLOG_EXTERNAL_SOURCE,
        external_id=issue_key,
    )
    set_skip_push(str(issue.id))
    BacklogIssueSync.objects.create(
        project_id=sync.project_id,
        workspace_id=sync.workspace_id,
        issue=issue,
        backlog_issue_id=backlog_issue["id"],
        backlog_issue_key=issue_key,
        backlog_updated_at=updated,
    )
    stats["created"] = stats.get("created", 0) + 1
    stats.setdefault("updated_issue_ids", []).append(str(issue.id))
    return issue


def sync_backlog_comments(
    sync: BacklogProjectSync,
    client: BacklogClient,
    issue_sync: BacklogIssueSync,
    stats: dict[str, Any],
) -> None:
    comments = client.list_all_comments(issue_sync.backlog_issue_key)
    existing_comments = set(
        BacklogCommentSync.objects.filter(issue_sync=issue_sync).values_list("backlog_comment_id", flat=True)
    )

    for entry in comments:
        cid = entry.get("id")
        if not cid:
            continue

        sync_backlog_changelog_to_activities(sync, issue_sync, entry, stats=stats)

        if cid in existing_comments:
            continue

        comment_html = backlog_comment_to_html(sync, entry)
        if not comment_html:
            continue

        set_skip_push(str(issue_sync.issue_id))
        actor_id = resolve_backlog_actor_id(entry, sync, issue_sync.issue.created_by_id)
        created_at = parse_backlog_datetime(entry.get("created")) or timezone.now()

        comment = IssueComment(
            project_id=sync.project_id,
            workspace_id=sync.workspace_id,
            issue_id=issue_sync.issue_id,
            actor_id=actor_id,
            comment_html=comment_html,
            external_source=BACKLOG_EXTERNAL_SOURCE,
            external_id=str(cid),
            created_by_id=actor_id or sync.created_by_id,
            created_at=created_at,
            updated_at=created_at,
        )
        comment.save()
        BacklogCommentSync.objects.create(
            project_id=sync.project_id,
            workspace_id=sync.workspace_id,
            comment=comment,
            issue_sync=issue_sync,
            backlog_comment_id=cid,
            created_by_id=sync.created_by_id,
        )
        existing_comments.add(cid)
        stats["comments_created"] = stats.get("comments_created", 0) + 1
