# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import GithubPRSync, GithubProjectSync, Issue, IssueComment, IssueLink, Project, State, Workspace
from plane.utils.github.pr_sync import (
    derive_pr_state,
    handle_pull_request_event,
    parse_plane_issue_key,
    resolve_plane_issue,
)


@pytest.fixture
def workspace(create_user):
    return Workspace.objects.create(name="Test Workspace", slug="test-workspace", owner=create_user)


@pytest.fixture
def project(workspace, create_user):
    return Project.objects.create(
        name="Test Project",
        identifier="PLANE",
        workspace=workspace,
        created_by=create_user,
    )


@pytest.fixture
def state(project):
    return State.objects.create(name="Todo", project=project, group="backlog", default=True)


@pytest.fixture
def issue(workspace, project, state, create_user):
    return Issue.objects.create(
        name="Test Issue",
        workspace=workspace,
        project=project,
        state=state,
        sequence_id=123,
        created_by=create_user,
    )


@pytest.fixture
def github_sync(workspace, project, create_user):
    return GithubProjectSync.objects.create(
        workspace=workspace,
        project=project,
        repo_owner="glu-developer-team",
        repo_name="plane",
        installation_id=12345,
        is_enabled=True,
        created_by=create_user,
    )


def _pull_request_payload(*, action="opened", number=42, title="Fix bug [PLANE-123]", body="", merged=False, state="open"):
    return {
        "action": action,
        "repository": {
            "name": "plane",
            "owner": {"login": "glu-developer-team"},
        },
        "pull_request": {
            "number": number,
            "node_id": "PR_kwDO",
            "html_url": f"https://github.com/glu-developer-team/plane/pull/{number}",
            "title": title,
            "body": body,
            "state": state,
            "merged": merged,
            "updated_at": "2026-06-19T10:00:00Z",
            "head": {"ref": "feature/test"},
            "base": {"ref": "develop"},
        },
    }


@pytest.mark.unit
class TestParsePlaneIssueKey:
    def test_bracketed_key(self):
        assert parse_plane_issue_key("Fix [PLANE-123] now") == "PLANE-123"

    def test_bare_key(self):
        assert parse_plane_issue_key("See PLANE-456 for context") == "PLANE-456"

    def test_no_key(self):
        assert parse_plane_issue_key("No tag here") is None


@pytest.mark.unit
class TestResolvePlaneIssue:
    def test_resolves_matching_issue(self, project, issue):
        assert resolve_plane_issue(project, "PLANE-123") == issue

    def test_rejects_other_identifier(self, project, issue):
        assert resolve_plane_issue(project, "OTHER-123") is None


@pytest.mark.unit
class TestDerivePrState:
    def test_merged(self):
        assert derive_pr_state({"state": "closed", "merged": True}) == "merged"

    def test_closed(self):
        assert derive_pr_state({"state": "closed", "merged": False}) == "closed"


@pytest.mark.django_db
class TestHandlePullRequestEvent:
    def test_links_pr_with_tag(self, github_sync, issue):
        result = handle_pull_request_event(_pull_request_payload())

        assert result["handled"] is True
        assert result["issue_id"] == str(issue.id)
        assert result["created"] is True

        pr_sync = GithubPRSync.objects.get(project=github_sync.project, pr_number=42)
        assert pr_sync.issue_id == issue.id
        assert pr_sync.linked_issue_key == "PLANE-123"
        assert pr_sync.pr_state == "open"

        link = IssueLink.objects.get(issue=issue)
        assert "github.com" in link.url
        assert link.title.startswith("PR #42")

        comment = IssueComment.objects.get(issue=issue, external_source="github_pr")
        assert "Linked GitHub pull request" in comment.comment_html

    def test_ignores_untagged_pr(self, github_sync):
        payload = _pull_request_payload(title="Untagged PR")
        result = handle_pull_request_event(payload)

        assert result["handled"] is False
        assert result["reason"] == "no_issue_tag"
        assert GithubPRSync.objects.count() == 0

    def test_updates_state_on_close(self, github_sync, issue):
        handle_pull_request_event(_pull_request_payload())
        result = handle_pull_request_event(_pull_request_payload(action="closed", state="closed"))

        assert result["handled"] is True
        pr_sync = GithubPRSync.objects.get(project=github_sync.project, pr_number=42)
        assert pr_sync.pr_state == "closed"
        assert IssueComment.objects.filter(issue=issue, external_source="github_pr").count() == 2

    def test_tag_in_body(self, github_sync, issue):
        payload = _pull_request_payload(title="Untagged title", body="Refs PLANE-123")
        result = handle_pull_request_event(payload)

        assert result["handled"] is True
        assert GithubPRSync.objects.filter(issue=issue).exists()
