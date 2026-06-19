# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from plane.db.models import GithubPRSync, GithubProjectSync, Issue, IssueComment, IssueLink

logger = logging.getLogger(__name__)

GITHUB_PR_EXTERNAL_SOURCE = "github_pr"

SYNC_MODE_GITHUB_TO_PLANE = "github_to_plane"
SYNC_MODE_BIDIRECTIONAL = "bidirectional"
DEFAULT_SYNC_MODE = SYNC_MODE_BIDIRECTIONAL

BRACKETED_ISSUE_KEY = re.compile(r"\[(?P<identifier>[A-Za-z][A-Za-z0-9]*)-(?P<sequence>\d+)\]")
BARE_ISSUE_KEY = re.compile(
    r"(?<![\w/\[])(?P<identifier>[A-Za-z][A-Za-z0-9]*)-(?P<sequence>\d+)(?![\w/\]])"
)

PR_STATE_ACTIONS = frozenset({"opened", "edited", "closed", "reopened", "synchronize"})


def get_sync_mode(sync) -> str:
    mode = (sync.config or {}).get("sync_mode")
    if mode in (SYNC_MODE_GITHUB_TO_PLANE, SYNC_MODE_BIDIRECTIONAL):
        return mode
    return DEFAULT_SYNC_MODE


def is_github_push_enabled(sync) -> bool:
    return get_sync_mode(sync) == SYNC_MODE_BIDIRECTIONAL


def get_enabled_github_project_sync(project_id):
    sync = GithubProjectSync.objects.filter(
        project_id=project_id,
        deleted_at__isnull=True,
        is_enabled=True,
    ).first()
    if not sync or not sync.repo_owner or not sync.repo_name:
        return None
    return sync


def get_github_project_sync_by_repo(repo_owner: str, repo_name: str) -> GithubProjectSync | None:
    if not repo_owner or not repo_name:
        return None
    return (
        GithubProjectSync.objects.filter(
            repo_owner__iexact=repo_owner.strip(),
            repo_name__iexact=repo_name.strip(),
            deleted_at__isnull=True,
            is_enabled=True,
        )
        .select_related("project")
        .first()
    )


def parse_plane_issue_key(text: str | None) -> str | None:
    """Extract the first Plane issue key from text, e.g. PLANE-123 or [PLANE-123]."""
    if not text:
        return None

    match = BRACKETED_ISSUE_KEY.search(text)
    if not match:
        match = BARE_ISSUE_KEY.search(text)
    if not match:
        return None

    identifier = match.group("identifier").upper()
    sequence = match.group("sequence")
    return f"{identifier}-{sequence}"


def resolve_plane_issue(project, issue_key: str) -> Issue | None:
    """Resolve a Plane issue key within the configured project."""
    if not issue_key or "-" not in issue_key:
        return None

    identifier, _, sequence_raw = issue_key.partition("-")
    if identifier.upper() != (project.identifier or "").upper():
        return None

    try:
        sequence_id = int(sequence_raw)
    except (TypeError, ValueError):
        return None

    return Issue.objects.filter(
        project_id=project.id,
        sequence_id=sequence_id,
        deleted_at__isnull=True,
    ).first()


def parse_github_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    parsed = parse_datetime(normalized)
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=timezone.utc)
    return parsed


def derive_pr_state(pull_request: dict[str, Any]) -> str:
    if pull_request.get("merged"):
        return "merged"
    state = (pull_request.get("state") or "open").lower()
    return state if state in {"open", "closed"} else "open"


def _pr_link_title(pull_request: dict[str, Any]) -> str:
    number = pull_request.get("number")
    title = (pull_request.get("title") or "").strip()
    label = f"PR #{number}"
    if title:
        label = f"{label}: {title}"
    return label[:255]


def upsert_issue_link(
    issue: Issue,
    pull_request: dict[str, Any],
    *,
    sync: GithubProjectSync,
) -> IssueLink:
    pr_url = pull_request["html_url"]
    title = _pr_link_title(pull_request)
    metadata = {
        "source": GITHUB_PR_EXTERNAL_SOURCE,
        "pr_number": pull_request.get("number"),
        "pr_node_id": pull_request.get("node_id") or "",
    }

    link = IssueLink.objects.filter(issue_id=issue.id, url=pr_url, deleted_at__isnull=True).first()
    if link:
        changed = False
        if link.title != title:
            link.title = title
            changed = True
        if link.metadata != metadata:
            link.metadata = metadata
            changed = True
        if changed:
            link.save(update_fields=["title", "metadata", "updated_at"], disable_auto_set_user=True)
        return link

    return IssueLink.objects.create(
        issue_id=issue.id,
        project_id=issue.project_id,
        workspace_id=issue.workspace_id,
        url=pr_url,
        title=title,
        metadata=metadata,
        created_by_id=sync.created_by_id,
    )


def _remove_issue_link(issue: Issue, pr_url: str) -> None:
    IssueLink.objects.filter(issue_id=issue.id, url=pr_url, deleted_at__isnull=True).delete()


def post_pr_activity_comment(
    issue: Issue,
    *,
    sync: GithubProjectSync,
    message_html: str,
    external_id: str,
) -> IssueComment | None:
    if IssueComment.objects.filter(
        issue_id=issue.id,
        external_source=GITHUB_PR_EXTERNAL_SOURCE,
        external_id=external_id,
        deleted_at__isnull=True,
    ).exists():
        return None

    return IssueComment.objects.create(
        issue_id=issue.id,
        project_id=issue.project_id,
        workspace_id=issue.workspace_id,
        comment_html=message_html,
        access="EXTERNAL",
        external_source=GITHUB_PR_EXTERNAL_SOURCE,
        external_id=external_id,
        actor_id=sync.created_by_id,
        created_by_id=sync.created_by_id,
    )


def _linked_comment_html(pull_request: dict[str, Any]) -> str:
    number = pull_request.get("number")
    title = html.escape((pull_request.get("title") or "").strip())
    url = html.escape(pull_request.get("html_url") or "")
    title_suffix = f": {title}" if title else ""
    return (
        f'<p>Linked GitHub pull request '
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">#{number}</a>'
        f"{title_suffix}.</p>"
    )


def _state_change_comment_html(pull_request: dict[str, Any], pr_state: str) -> str:
    number = pull_request.get("number")
    url = html.escape(pull_request.get("html_url") or "")
    if pr_state == "merged":
        action = "was merged"
    elif pr_state == "closed":
        action = "was closed"
    elif pr_state == "open":
        action = "was reopened"
    else:
        action = f"is now {pr_state}"
    return (
        f'<p>GitHub pull request '
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">#{number}</a> '
        f"{action}.</p>"
    )


def upsert_github_pr_sync(
    sync: GithubProjectSync,
    issue: Issue,
    pull_request: dict[str, Any],
    *,
    linked_issue_key: str,
) -> tuple[GithubPRSync, bool, Issue | None]:
    """Create or update GithubPRSync. Returns (record, created, previous_issue)."""
    pr_number = pull_request["number"]
    previous_issue: Issue | None = None

    pr_sync = GithubPRSync.objects.filter(
        project_id=sync.project_id,
        pr_number=pr_number,
        deleted_at__isnull=True,
    ).first()

    defaults = {
        "issue_id": issue.id,
        "pr_node_id": pull_request.get("node_id") or "",
        "pr_url": pull_request["html_url"],
        "head_branch": (pull_request.get("head") or {}).get("ref") or "",
        "base_branch": (pull_request.get("base") or {}).get("ref") or "",
        "pr_state": derive_pr_state(pull_request),
        "linked_issue_key": linked_issue_key,
        "last_github_updated_at": parse_github_datetime(pull_request.get("updated_at")),
    }

    if pr_sync:
        previous_issue_id = pr_sync.issue_id
        for field, value in defaults.items():
            setattr(pr_sync, field, value)
        pr_sync.save(disable_auto_set_user=True)
        if previous_issue_id and previous_issue_id != issue.id:
            previous_issue = Issue.objects.filter(id=previous_issue_id).first()
        return pr_sync, False, previous_issue

    pr_sync = GithubPRSync.objects.create(
        project_id=sync.project_id,
        workspace_id=sync.workspace_id,
        created_by_id=sync.created_by_id,
        **defaults,
    )
    return pr_sync, True, None


def handle_pull_request_event(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action") or ""
    if action not in PR_STATE_ACTIONS:
        return {"handled": False, "reason": "unsupported_action", "action": action}

    repository = payload.get("repository") or {}
    owner = ((repository.get("owner") or {}).get("login") or "").strip()
    repo_name = (repository.get("name") or "").strip()
    sync = get_github_project_sync_by_repo(owner, repo_name)
    if not sync:
        return {"handled": False, "reason": "repo_not_configured", "action": action}

    pull_request = payload.get("pull_request") or {}
    pr_number = pull_request.get("number")
    if not pr_number or not pull_request.get("html_url"):
        return {"handled": False, "reason": "invalid_payload", "action": action}

    sync.last_webhook_at = timezone.now()
    sync.save(update_fields=["last_webhook_at", "updated_at"], disable_auto_set_user=True)

    existing_sync = GithubPRSync.objects.filter(
        project_id=sync.project_id,
        pr_number=pr_number,
        deleted_at__isnull=True,
    ).first()

    issue_key = parse_plane_issue_key(pull_request.get("title") or "")
    if not issue_key:
        issue_key = parse_plane_issue_key(pull_request.get("body") or "")

    if not issue_key and not existing_sync:
        return {"handled": False, "reason": "no_issue_tag", "action": action}

    issue = None
    if issue_key:
        issue = resolve_plane_issue(sync.project, issue_key)
        if not issue:
            logger.info(
                "github pr sync: issue key %s not found in project %s",
                issue_key,
                sync.project_id,
            )
            if not existing_sync:
                return {"handled": False, "reason": "issue_not_found", "action": action, "issue_key": issue_key}
    elif existing_sync:
        issue = existing_sync.issue

    if not issue:
        return {"handled": False, "reason": "issue_not_resolved", "action": action}

    previous_state = existing_sync.pr_state if existing_sync else None
    new_state = derive_pr_state(pull_request)

    with transaction.atomic():
        pr_sync, created, previous_issue = upsert_github_pr_sync(
            sync,
            issue,
            pull_request,
            linked_issue_key=issue_key or existing_sync.linked_issue_key,
        )
        upsert_issue_link(issue, pull_request, sync=sync)

        if previous_issue and previous_issue.id != issue.id:
            _remove_issue_link(previous_issue, pull_request["html_url"])

        if created:
            post_pr_activity_comment(
                issue,
                sync=sync,
                message_html=_linked_comment_html(pull_request),
                external_id=f"pr-linked-{pr_number}",
            )
        elif previous_issue and previous_issue.id != issue.id:
            post_pr_activity_comment(
                issue,
                sync=sync,
                message_html=_linked_comment_html(pull_request),
                external_id=f"pr-linked-{pr_number}",
            )
        elif action in {"closed", "reopened"} and previous_state != new_state:
            post_pr_activity_comment(
                issue,
                sync=sync,
                message_html=_state_change_comment_html(pull_request, new_state),
                external_id=f"pr-state-{pr_number}-{new_state}-{action}",
            )
        elif action == "closed" and new_state == "merged" and previous_state != "merged":
            post_pr_activity_comment(
                issue,
                sync=sync,
                message_html=_state_change_comment_html(pull_request, "merged"),
                external_id=f"pr-state-{pr_number}-merged-{action}",
            )

    return {
        "handled": True,
        "action": action,
        "pr_number": pr_number,
        "issue_id": str(issue.id),
        "issue_key": issue_key or pr_sync.linked_issue_key,
        "created": created,
        "pr_state": new_state,
    }
