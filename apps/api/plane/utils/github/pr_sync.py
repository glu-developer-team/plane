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

from plane.db.models import GithubPRCommentSync, GithubPRSync, GithubProjectSync, Issue, IssueComment, IssueLink
from plane.settings.redis import redis_instance
from plane.utils.backlog.sync import html_to_markdown
from plane.utils.markdown import markdown

logger = logging.getLogger(__name__)

GITHUB_PR_EXTERNAL_SOURCE = "github_pr"
GITHUB_SKIP_PUSH_TTL = 60

SYNC_MODE_GITHUB_TO_PLANE = "github_to_plane"
SYNC_MODE_BIDIRECTIONAL = "bidirectional"
DEFAULT_SYNC_MODE = SYNC_MODE_BIDIRECTIONAL

BRACKETED_ISSUE_KEY = re.compile(r"\[(?P<identifier>[A-Za-z][A-Za-z0-9]*)-(?P<sequence>\d+)\]")
BARE_ISSUE_KEY = re.compile(
    r"(?<![\w/\[])(?P<identifier>[A-Za-z][A-Za-z0-9]*)-(?P<sequence>\d+)(?![\w/\]])"
)

PR_STATE_ACTIONS = frozenset({"opened", "edited", "closed", "reopened", "synchronize"})
ISSUE_COMMENT_ACTIONS = frozenset({"created", "edited", "deleted"})


def set_github_skip_push(issue_id: str, ttl: int = GITHUB_SKIP_PUSH_TTL) -> None:
    redis_instance().set(f"github_skip_push:{issue_id}", "1", ex=ttl)


def should_github_skip_push(issue_id: str) -> bool:
    return bool(redis_instance().get(f"github_skip_push:{issue_id}"))


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

    comment = IssueComment.objects.create(
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
    set_github_skip_push(str(issue.id))
    return comment


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


def github_comment_body_to_html(body: str | None) -> str:
    text = (body or "").strip()
    if not text:
        return "<p></p>"
    rendered = markdown(text)
    if rendered and rendered.strip():
        return rendered.strip()
    return f"<p>{html.escape(text)}</p>"


def github_comment_to_html(body: str | None, user: dict[str, Any] | None) -> str:
    login = html.escape((user or {}).get("login") or "github-user")
    content = github_comment_body_to_html(body)
    return f'<p><strong>@{login}</strong> (GitHub):</p>{content}'


def _get_pr_sync_for_issue_comment(
    sync: GithubProjectSync,
    issue_payload: dict[str, Any],
) -> GithubPRSync | None:
    if not issue_payload.get("pull_request"):
        return None

    pr_number = issue_payload.get("number")
    if not pr_number:
        return None

    return (
        GithubPRSync.objects.filter(
            project_id=sync.project_id,
            pr_number=pr_number,
            deleted_at__isnull=True,
        )
        .select_related("issue")
        .first()
    )


def _find_github_comment_sync(pr_sync: GithubPRSync, github_comment_id: int) -> GithubPRCommentSync | None:
    return (
        GithubPRCommentSync.objects.filter(
            pr_sync=pr_sync,
            github_comment_id=github_comment_id,
            deleted_at__isnull=True,
        )
        .select_related("comment")
        .first()
    )


def sync_github_comment_created(
    sync: GithubProjectSync,
    pr_sync: GithubPRSync,
    comment_payload: dict[str, Any],
) -> IssueComment | None:
    github_comment_id = comment_payload.get("id")
    if not github_comment_id:
        return None

    if _find_github_comment_sync(pr_sync, github_comment_id):
        return None

    if IssueComment.objects.filter(
        external_source=GITHUB_PR_EXTERNAL_SOURCE,
        external_id=str(github_comment_id),
        deleted_at__isnull=True,
    ).exists():
        return None

    if should_github_skip_push(str(pr_sync.issue_id)):
        return None

    comment_html = github_comment_to_html(comment_payload.get("body"), comment_payload.get("user"))
    created_at = parse_github_datetime(comment_payload.get("created_at")) or timezone.now()

    set_github_skip_push(str(pr_sync.issue_id))
    comment = IssueComment(
        project_id=sync.project_id,
        workspace_id=sync.workspace_id,
        issue_id=pr_sync.issue_id,
        actor_id=sync.created_by_id,
        comment_html=comment_html,
        access="EXTERNAL",
        external_source=GITHUB_PR_EXTERNAL_SOURCE,
        external_id=str(github_comment_id),
        created_by_id=sync.created_by_id,
        created_at=created_at,
        updated_at=created_at,
    )
    comment.save()

    GithubPRCommentSync.objects.create(
        project_id=sync.project_id,
        workspace_id=sync.workspace_id,
        comment=comment,
        pr_sync=pr_sync,
        github_comment_id=github_comment_id,
        created_by_id=sync.created_by_id,
    )
    return comment


def sync_github_comment_edited(
    pr_sync: GithubPRSync,
    comment_payload: dict[str, Any],
) -> IssueComment | None:
    github_comment_id = comment_payload.get("id")
    if not github_comment_id:
        return None

    comment_sync = _find_github_comment_sync(pr_sync, github_comment_id)
    if not comment_sync or not comment_sync.comment:
        return None

    comment = comment_sync.comment
    comment_html = github_comment_to_html(comment_payload.get("body"), comment_payload.get("user"))
    updated_at = parse_github_datetime(comment_payload.get("updated_at")) or timezone.now()

    set_github_skip_push(str(pr_sync.issue_id))
    comment.comment_html = comment_html
    comment.updated_at = updated_at
    comment.save(update_fields=["comment_html", "updated_at"])
    return comment


def sync_github_comment_deleted(pr_sync: GithubPRSync, comment_payload: dict[str, Any]) -> bool:
    github_comment_id = comment_payload.get("id")
    if not github_comment_id:
        return False

    comment_sync = _find_github_comment_sync(pr_sync, github_comment_id)
    if not comment_sync:
        return False

    set_github_skip_push(str(pr_sync.issue_id))
    if comment_sync.comment:
        comment_sync.comment.delete()
    comment_sync.delete()
    return True


def handle_issue_comment_event(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action") or ""
    if action not in ISSUE_COMMENT_ACTIONS:
        return {"handled": False, "reason": "unsupported_action", "action": action}

    repository = payload.get("repository") or {}
    owner = ((repository.get("owner") or {}).get("login") or "").strip()
    repo_name = (repository.get("name") or "").strip()
    sync = get_github_project_sync_by_repo(owner, repo_name)
    if not sync:
        return {"handled": False, "reason": "repo_not_configured", "action": action}

    issue_payload = payload.get("issue") or {}
    pr_sync = _get_pr_sync_for_issue_comment(sync, issue_payload)
    if not pr_sync:
        return {"handled": False, "reason": "pr_not_linked", "action": action}

    comment_payload = payload.get("comment") or {}
    github_comment_id = comment_payload.get("id")
    if not github_comment_id:
        return {"handled": False, "reason": "invalid_payload", "action": action}

    sync.last_webhook_at = timezone.now()
    sync.save(update_fields=["last_webhook_at", "updated_at"], disable_auto_set_user=True)

    if action == "created":
        comment = sync_github_comment_created(sync, pr_sync, comment_payload)
        if not comment:
            return {
                "handled": False,
                "reason": "comment_skipped",
                "action": action,
                "github_comment_id": github_comment_id,
            }
        return {
            "handled": True,
            "action": action,
            "github_comment_id": github_comment_id,
            "comment_id": str(comment.id),
            "issue_id": str(pr_sync.issue_id),
            "pr_number": pr_sync.pr_number,
        }

    if action == "edited":
        comment = sync_github_comment_edited(pr_sync, comment_payload)
        if not comment:
            return {
                "handled": False,
                "reason": "comment_not_found",
                "action": action,
                "github_comment_id": github_comment_id,
            }
        return {
            "handled": True,
            "action": action,
            "github_comment_id": github_comment_id,
            "comment_id": str(comment.id),
            "issue_id": str(pr_sync.issue_id),
            "pr_number": pr_sync.pr_number,
        }

    deleted = sync_github_comment_deleted(pr_sync, comment_payload)
    return {
        "handled": deleted,
        "action": action,
        "github_comment_id": github_comment_id,
        "issue_id": str(pr_sync.issue_id),
        "pr_number": pr_sync.pr_number,
        "reason": None if deleted else "comment_not_found",
    }


def plane_comment_to_github_body(comment: IssueComment) -> str:
    content = html_to_markdown(comment.comment_html)
    if not content:
        content = "(empty comment)"

    actor = comment.actor
    if actor:
        label = (getattr(actor, "display_name", None) or actor.email or "Plane user").strip()
        if label:
            return f"**{label}** (Plane):\n\n{content}"
    return content


def get_linked_github_prs_for_issue(issue_id, project_id) -> list[GithubPRSync]:
    return list(
        GithubPRSync.objects.filter(
            issue_id=issue_id,
            project_id=project_id,
            deleted_at__isnull=True,
        ).order_by("-updated_at")
    )


def push_plane_comment_to_github(
    comment: IssueComment,
    sync: GithubProjectSync,
    pr_sync: GithubPRSync,
    *,
    client,
) -> GithubPRCommentSync | None:
    if GithubPRCommentSync.objects.filter(
        comment_id=comment.id,
        pr_sync_id=pr_sync.id,
        deleted_at__isnull=True,
    ).exists():
        return None

    if not sync.installation_id:
        logger.info("github pr sync: missing installation_id for project %s", sync.project_id)
        return None

    body = plane_comment_to_github_body(comment)
    set_github_skip_push(str(comment.issue_id))

    created = client.post_issue_comment(
        sync.repo_owner,
        sync.repo_name,
        pr_sync.pr_number,
        body,
    )
    github_comment_id = created.get("id")
    if not github_comment_id:
        raise ValueError("GitHub comment response missing id")

    return GithubPRCommentSync.objects.create(
        project_id=sync.project_id,
        workspace_id=sync.workspace_id,
        comment=comment,
        pr_sync=pr_sync,
        github_comment_id=github_comment_id,
        created_by_id=sync.created_by_id,
    )


def push_plane_comment_to_github_prs(comment: IssueComment, sync: GithubProjectSync) -> list[GithubPRCommentSync]:
    from plane.utils.github.client import GitHubClient

    if not is_github_push_enabled(sync):
        return []
    if not sync.installation_id:
        return []

    pr_syncs = get_linked_github_prs_for_issue(comment.issue_id, comment.project_id)
    if not pr_syncs:
        return []

    client = GitHubClient(sync.installation_id)
    pushed: list[GithubPRCommentSync] = []
    for pr_sync in pr_syncs:
        try:
            record = push_plane_comment_to_github(comment, sync, pr_sync, client=client)
            if record:
                pushed.append(record)
        except Exception as exc:
            logger.exception(
                "github pr sync: failed to push comment %s to PR #%s: %s",
                comment.id,
                pr_sync.pr_number,
                exc,
            )
    return pushed


def enqueue_github_push_comment(comment_id: str) -> None:
    comment = IssueComment.objects.filter(id=comment_id, deleted_at__isnull=True).select_related("issue", "actor").first()
    if not comment:
        return

    sync = get_enabled_github_project_sync(comment.project_id)
    if not sync or not is_github_push_enabled(sync):
        return
    if comment.external_source == GITHUB_PR_EXTERNAL_SOURCE:
        return
    if should_github_skip_push(str(comment.issue_id)):
        return
    if not get_linked_github_prs_for_issue(comment.issue_id, comment.project_id):
        return

    from plane.bgtasks.github_pr_sync_task import github_push_comment_task

    github_push_comment_task.delay(str(comment_id))
