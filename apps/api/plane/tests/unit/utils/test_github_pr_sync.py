# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from unittest.mock import MagicMock, patch

from plane.db.models import GithubPRCommentSync, GithubPRSync, GithubProjectSync, Issue, IssueComment, IssueLink, Project, State, Workspace
from plane.utils.github.pr_sync import (
    derive_pr_state,
    enqueue_github_push_comment,
    extract_issue_key_from_pull_request,
    github_comment_body_to_html,
    handle_issue_comment_event,
    handle_pull_request_event,
    handle_pull_request_review_event,
    parse_plane_issue_key,
    parse_plane_issue_key_from_branch,
    plane_comment_to_github_body,
    push_plane_comment_to_github_prs,
    resolve_plane_issue,
)


@pytest.fixture
def mock_redis():
    mock_redis_client = MagicMock()
    mock_redis_client.get.return_value = None
    with patch("plane.utils.github.pr_sync.redis_instance", return_value=mock_redis_client):
        yield mock_redis_client


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

    def test_branch_key(self):
        assert parse_plane_issue_key_from_branch("feature/PLANE-42-add-sync") == "PLANE-42"

    def test_extract_from_branch(self):
        pull_request = {"title": "Untagged", "body": "", "head": {"ref": "fix/PLANE-99-hotfix"}}
        assert extract_issue_key_from_pull_request(pull_request) == "PLANE-99"

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


def _issue_comment_payload(*, action="created", pr_number=42, comment_id=9001, body="Looks good to me"):
    return {
        "action": action,
        "repository": {
            "name": "plane",
            "owner": {"login": "glu-developer-team"},
        },
        "issue": {
            "number": pr_number,
            "pull_request": {"url": f"https://api.github.com/repos/glu-developer-team/plane/pulls/{pr_number}"},
        },
        "comment": {
            "id": comment_id,
            "body": body,
            "user": {"login": "octocat"},
            "html_url": f"https://github.com/glu-developer-team/plane/pull/{pr_number}#issuecomment-{comment_id}",
            "created_at": "2026-06-19T11:00:00Z",
            "updated_at": "2026-06-19T11:00:00Z",
        },
    }


@pytest.mark.unit
class TestGithubCommentBodyToHtml:
    def test_renders_markdown(self):
        html_output = github_comment_body_to_html("**bold** text")
        assert "<strong>bold</strong>" in html_output


@pytest.mark.django_db
class TestHandleIssueCommentEvent:
    def test_syncs_pr_comment(self, github_sync, issue, mock_redis):
        handle_pull_request_event(_pull_request_payload())
        result = handle_issue_comment_event(_issue_comment_payload())

        assert result["handled"] is True
        assert result["github_comment_id"] == 9001

        comment = IssueComment.objects.get(issue=issue, external_id="9001")
        assert "octocat" in comment.comment_html
        assert "Looks good to me" in comment.comment_html
        assert GithubPRCommentSync.objects.filter(github_comment_id=9001, comment=comment).exists()

    def test_ignores_unlinked_pr(self, github_sync, mock_redis):
        result = handle_issue_comment_event(_issue_comment_payload())
        assert result["handled"] is False
        assert result["reason"] == "pr_not_linked"

    def test_ignores_regular_issue_comment(self, github_sync, issue, mock_redis):
        handle_pull_request_event(_pull_request_payload())
        payload = _issue_comment_payload()
        payload["issue"] = {"number": 42}
        result = handle_issue_comment_event(payload)
        assert result["handled"] is False
        assert result["reason"] == "pr_not_linked"

    def test_edits_existing_comment(self, github_sync, issue, mock_redis):
        handle_pull_request_event(_pull_request_payload())
        handle_issue_comment_event(_issue_comment_payload())
        result = handle_issue_comment_event(_issue_comment_payload(action="edited", body="Updated review"))

        assert result["handled"] is True
        comment = IssueComment.objects.get(issue=issue, external_id="9001")
        assert "Updated review" in comment.comment_html

    def test_deletes_existing_comment(self, github_sync, issue, mock_redis):
        handle_pull_request_event(_pull_request_payload())
        handle_issue_comment_event(_issue_comment_payload())
        result = handle_issue_comment_event(_issue_comment_payload(action="deleted"))

        assert result["handled"] is True
        assert not IssueComment.objects.filter(issue=issue, external_id="9001", deleted_at__isnull=True).exists()
        assert not GithubPRCommentSync.objects.filter(github_comment_id=9001, deleted_at__isnull=True).exists()

    def test_skips_duplicate_created_comment(self, github_sync, issue, mock_redis):
        handle_pull_request_event(_pull_request_payload())
        first = handle_issue_comment_event(_issue_comment_payload())
        second = handle_issue_comment_event(_issue_comment_payload())

        assert first["handled"] is True
        assert second["handled"] is False
        assert second["reason"] == "comment_skipped"
        assert IssueComment.objects.filter(issue=issue, external_id="9001").count() == 1


@pytest.mark.django_db
class TestPlaneCommentPushToGithub:
    def test_plane_comment_to_github_body_includes_actor(self, issue, create_user):
        comment = IssueComment.objects.create(
            issue=issue,
            project=issue.project,
            workspace=issue.workspace,
            actor=create_user,
            comment_html="<p>Ship it</p>",
            created_by=create_user,
        )
        body = plane_comment_to_github_body(comment)
        assert "Plane" in body
        assert "Ship it" in body

    def test_skips_when_sync_mode_is_github_to_plane(self, github_sync, issue, create_user, mock_redis):
        github_sync.config = {"sync_mode": "github_to_plane"}
        github_sync.save()
        handle_pull_request_event(_pull_request_payload())

        comment = IssueComment.objects.create(
            issue=issue,
            project=issue.project,
            workspace=issue.workspace,
            actor=create_user,
            comment_html="<p>Local only</p>",
            created_by=create_user,
        )

        with patch("plane.bgtasks.github_pr_sync_task.github_push_comment_task.delay") as mock_delay:
            enqueue_github_push_comment(str(comment.id))
            mock_delay.assert_not_called()

    def test_pushes_comment_to_linked_pr(self, github_sync, issue, create_user, mock_redis):
        handle_pull_request_event(_pull_request_payload())
        comment = IssueComment.objects.create(
            issue=issue,
            project=issue.project,
            workspace=issue.workspace,
            actor=create_user,
            comment_html="<p>Please review</p>",
            created_by=create_user,
        )

        mock_client = MagicMock()
        mock_client.post_issue_comment.return_value = {"id": 7777}

        with patch("plane.utils.github.client.GitHubClient", return_value=mock_client):
            pushed = push_plane_comment_to_github_prs(comment, github_sync)

        assert len(pushed) == 1
        assert pushed[0].github_comment_id == 7777
        mock_client.post_issue_comment.assert_called_once_with(
            github_sync.repo_owner,
            github_sync.repo_name,
            42,
            plane_comment_to_github_body(comment),
        )

    def test_enqueue_dispatches_task(self, github_sync, issue, create_user, mock_redis):
        handle_pull_request_event(_pull_request_payload())
        comment = IssueComment.objects.create(
            issue=issue,
            project=issue.project,
            workspace=issue.workspace,
            actor=create_user,
            comment_html="<p>Queued</p>",
            created_by=create_user,
        )

        with patch("plane.bgtasks.github_pr_sync_task.github_push_comment_task.delay") as mock_delay:
            enqueue_github_push_comment(str(comment.id))
            mock_delay.assert_called_once_with(str(comment.id))


@pytest.mark.django_db
class TestGithubEnhancements:
    def test_merged_pr_moves_issue_to_completed_state(self, github_sync, issue, mock_redis):
        completed = State.objects.create(name="Done", project=issue.project, group="completed", sequence=2000)
        handle_pull_request_event(_pull_request_payload())
        result = handle_pull_request_event(
            _pull_request_payload(action="closed", state="closed", merged=True)
        )

        assert result["handled"] is True
        issue.refresh_from_db()
        assert issue.state_id == completed.id

    def test_review_posts_activity_comment(self, github_sync, issue, mock_redis):
        handle_pull_request_event(_pull_request_payload())
        payload = {
            "action": "submitted",
            "repository": {"name": "plane", "owner": {"login": "glu-developer-team"}},
            "pull_request": {
                "number": 42,
                "html_url": "https://github.com/glu-developer-team/plane/pull/42",
            },
            "review": {"id": 555, "state": "approved", "user": {"login": "reviewer"}},
        }
        result = handle_pull_request_review_event(payload)

        assert result["handled"] is True
        comment = IssueComment.objects.get(issue=issue, external_id="pr-review-42-555-submitted")
        assert "approved" in comment.comment_html
        assert "reviewer" in comment.comment_html
