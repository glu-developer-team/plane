# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timezone as dt_timezone
from unittest.mock import MagicMock, patch

import pytest

from plane.db.models import BacklogActivitySync, BacklogIssueSync, BacklogProjectSync, Issue, IssueActivity, State
from plane.utils.backlog.sync import (
    _changelog_activity_comment,
    _format_changelog_value,
    backlog_comment_to_html,
    backlog_text_to_html,
    html_to_markdown,
    html_to_plain,
    plane_issue_to_backlog_payload,
    should_skip_pull_overwrite,
    sync_backlog_changelog_to_activities,
    upsert_plane_issue_from_backlog,
)


@pytest.mark.unit
class TestHtmlToMarkdown:
    def test_paragraph(self):
        assert html_to_markdown("<p>Hello</p>") == "Hello"

    def test_bold_and_list(self):
        html = "<p><strong>Title</strong></p><ul><li>one</li><li>two</li></ul>"
        md = html_to_markdown(html)
        assert "**Title**" in md
        assert "- one" in md or "* one" in md
        assert "<p>" not in md
        assert "<strong>" not in md

    def test_link(self):
        md = html_to_markdown('<p><a href="https://example.com">link</a></p>')
        assert "https://example.com" in md
        assert "link" in md
        assert "<a" not in md

    def test_empty_editor(self):
        assert html_to_markdown("<p></p>") == ""
        assert html_to_markdown("<p><br></p>") == ""
        assert html_to_markdown("") == ""
        assert html_to_markdown(None) == ""

    def test_fallback_on_converter_error(self):
        html = "<p>fallback text</p>"
        with patch("markdownify.markdownify", side_effect=RuntimeError("fail")):
            assert html_to_markdown(html) == html_to_plain(html)


@pytest.mark.unit
class TestPlaneIssueToBacklogPayload:
    def test_description_is_markdown_not_html(self):
        issue = MagicMock()
        issue.id = "00000000-0000-0000-0000-000000000001"
        issue.name = "Test issue"
        issue.description_html = "<p><strong>bold</strong></p><ul><li>item</li></ul>"
        issue.state_id = None
        issue.priority = "none"
        issue.target_date = None
        issue.start_date = None

        sync = MagicMock()
        sync.config = {}

        client = MagicMock()

        with patch("plane.utils.backlog.sync.translate_text", side_effect=lambda _s, text, **_: text):
            with patch("plane.utils.backlog.sync.backlog_status_id_for_plane_state", return_value=None):
                with patch("plane.utils.backlog.sync.IssueAssignee") as mock_assignee:
                    mock_assignee.objects.filter.return_value.select_related.return_value.first.return_value = None
                    payload = plane_issue_to_backlog_payload(issue, sync, client)

        assert "<p>" not in payload["description"]
        assert "<strong>" not in payload["description"]
        assert "**bold**" in payload["description"]
        assert "item" in payload["description"]


from plane.utils.backlog.sync import (
    DEFAULT_SYNC_MODE,
    SYNC_MODE_BACKLOG_TO_PLANE,
    SYNC_MODE_BIDIRECTIONAL,
    get_sync_mode,
    is_backlog_push_enabled,
)


@pytest.mark.unit
class TestBacklogSyncMode:
    def test_default_sync_mode(self):
        sync = MagicMock()
        sync.config = {}
        assert get_sync_mode(sync) == DEFAULT_SYNC_MODE
        assert is_backlog_push_enabled(sync) is True

    def test_backlog_to_plane_disables_push(self):
        sync = MagicMock()
        sync.config = {"sync_mode": SYNC_MODE_BACKLOG_TO_PLANE}
        assert get_sync_mode(sync) == SYNC_MODE_BACKLOG_TO_PLANE
        assert is_backlog_push_enabled(sync) is False

    def test_bidirectional_enables_push(self):
        sync = MagicMock()
        sync.config = {"sync_mode": SYNC_MODE_BIDIRECTIONAL}
        assert is_backlog_push_enabled(sync) is True


@pytest.mark.unit
class TestBacklogCommentHelpers:
    def test_backlog_text_to_html_multiline(self):
        html = backlog_text_to_html("line one\nline two\n\nsecond paragraph")
        assert "<p>" in html
        assert "line one<br>line two" in html
        assert "second paragraph" in html

    def test_backlog_comment_to_html_returns_none_for_empty(self):
        sync = MagicMock()
        sync.config = {}
        assert backlog_comment_to_html(sync, {"content": ""}) is None
        assert backlog_comment_to_html(sync, {"content": None, "changeLog": [{"field": "status"}]}) is None

    def test_backlog_comment_to_html_translates_content(self):
        sync = MagicMock()
        sync.config = {"locale_map": {"ja_to_en": {"要望": "Request"}}}
        with patch("plane.utils.backlog.sync.translate_text", side_effect=lambda _s, text, **_: text.replace("要望", "Request")):
            html = backlog_comment_to_html(sync, {"content": "要望です"})
        assert html is not None
        assert "Request" in html


@pytest.mark.unit
class TestChangelogHelpers:
    def test_format_changelog_status_uses_english_resolver(self):
        sync = MagicMock()
        sync.config = {}
        with patch("plane.utils.backlog.sync.resolve_status_english", return_value="In Progress"):
            assert _format_changelog_value(sync, "status", "処理中") == "In Progress"

    def test_changelog_activity_comment_state(self):
        assert _changelog_activity_comment("status", "Open", "Closed") == "updated the state to"


@pytest.mark.unit
class TestShouldSkipPullOverwrite:
    def test_skip_when_local_edit_is_newer(self):
        issue = MagicMock()
        issue.id = "issue-1"
        issue.updated_at = datetime(2025, 6, 18, 12, 0, tzinfo=dt_timezone.utc)
        issue_sync = MagicMock()
        issue_sync.last_pushed_at = datetime(2025, 6, 18, 11, 0, tzinfo=dt_timezone.utc)
        issue_sync.backlog_updated_at = datetime(2025, 6, 18, 10, 0, tzinfo=dt_timezone.utc)
        backlog_updated = datetime(2025, 6, 18, 9, 0, tzinfo=dt_timezone.utc)

        with patch("plane.utils.backlog.sync.should_skip_pull_notify", return_value=False):
            with patch("plane.utils.backlog.sync.is_push_pending", return_value=False):
                assert should_skip_pull_overwrite(issue, issue_sync, backlog_updated) is True


@pytest.mark.django_db
class TestFieldLevelMerge:
    @pytest.fixture
    def backlog_setup(self, create_user):
        from plane.db.models import Project, Workspace

        workspace = Workspace.objects.create(name="WS", slug="ws", owner=create_user)
        project = Project.objects.create(name="Proj", identifier="PRJ", workspace=workspace, created_by=create_user)
        open_state = State.objects.create(name="Open", project=project, group="backlog", default=True, created_by=create_user)
        closed_state = State.objects.create(
            name="Closed", project=project, group="completed", default=False, created_by=create_user
        )
        issue = Issue.objects.create(
            name="Local title",
            workspace=workspace,
            project=project,
            state=open_state,
            created_by=create_user,
        )
        sync = BacklogProjectSync.objects.create(
            workspace=workspace,
            project=project,
            space_host="example.backlog.com",
            backlog_project_key="PRJ",
            api_key_encrypted="enc",
            config={
                "status_map": {"1": str(open_state.id), "2": str(closed_state.id)},
                "backlog_status_order": ["1", "2"],
            },
            created_by=create_user,
        )
        issue_sync = BacklogIssueSync.objects.create(
            workspace=workspace,
            project=project,
            issue=issue,
            backlog_issue_id=100,
            backlog_issue_key="PRJ-1",
            last_pushed_at=issue.updated_at,
            created_by=create_user,
        )
        return sync, issue_sync, issue, open_state, closed_state

    def test_status_always_updates_when_content_skipped(self, backlog_setup, create_user):
        sync, issue_sync, issue, open_state, closed_state = backlog_setup
        issue.name = "Edited locally"
        issue.save(update_fields=["name", "updated_at"])

        backlog_issue = {
            "id": 100,
            "issueKey": "PRJ-1",
            "summary": "Backlog title",
            "description": "",
            "status": {"id": 2},
            "priority": {"id": 3},
            "updated": "2025-06-18T08:00:00Z",
        }
        stats: dict = {}

        with patch("plane.utils.backlog.sync.translate_text", side_effect=lambda _s, text, **_: text):
            result = upsert_plane_issue_from_backlog(sync, backlog_issue, stats=stats)

        result.refresh_from_db()
        assert result.name == "Edited locally"
        assert str(result.state_id) == str(closed_state.id)


@pytest.mark.django_db
class TestChangelogToActivity:
    def test_creates_activity_for_assignee_change(self, create_user):
        from plane.db.models import Project, Workspace

        workspace = Workspace.objects.create(name="WS2", slug="ws2", owner=create_user)
        project = Project.objects.create(name="Proj2", identifier="P2", workspace=workspace, created_by=create_user)
        state = State.objects.create(name="Todo", project=project, group="backlog", default=True, created_by=create_user)
        issue = Issue.objects.create(name="Issue", workspace=workspace, project=project, state=state, created_by=create_user)
        sync = BacklogProjectSync.objects.create(
            workspace=workspace,
            project=project,
            space_host="example.backlog.com",
            backlog_project_key="P2",
            api_key_encrypted="enc",
            created_by=create_user,
        )
        issue_sync = BacklogIssueSync.objects.create(
            workspace=workspace,
            project=project,
            issue=issue,
            backlog_issue_id=200,
            backlog_issue_key="P2-1",
            created_by=create_user,
        )
        entry = {
            "id": 999,
            "content": None,
            "changeLog": [
                {
                    "field": "assignee",
                    "originalValue": "",
                    "newValue": "Tanaka",
                }
            ],
            "created": "2025-06-18T10:00:00Z",
            "createdUser": {"mailAddress": create_user.email},
        }
        stats: dict = {}
        sync_backlog_changelog_to_activities(sync, issue_sync, entry, stats=stats)

        assert IssueActivity.objects.filter(issue=issue, field="assignees").count() == 1
        assert BacklogActivitySync.objects.filter(issue_sync=issue_sync, backlog_comment_id=999).count() == 1
        assert stats["activities_created"] == 1

    def test_creates_activity_for_status_change(self, create_user):
        from plane.db.models import Project, Workspace

        workspace = Workspace.objects.create(name="WS4", slug="ws4", owner=create_user)
        project = Project.objects.create(name="Proj4", identifier="P4", workspace=workspace, created_by=create_user)
        state = State.objects.create(name="Todo", project=project, group="backlog", default=True, created_by=create_user)
        issue = Issue.objects.create(name="Issue", workspace=workspace, project=project, state=state, created_by=create_user)
        sync = BacklogProjectSync.objects.create(
            workspace=workspace,
            project=project,
            space_host="example.backlog.com",
            backlog_project_key="P4",
            api_key_encrypted="enc",
            created_by=create_user,
        )
        issue_sync = BacklogIssueSync.objects.create(
            workspace=workspace,
            project=project,
            issue=issue,
            backlog_issue_id=400,
            backlog_issue_key="P4-1",
            created_by=create_user,
        )
        entry = {
            "id": 1001,
            "content": None,
            "changeLog": [{"field": "status", "originalValue": "未対応", "newValue": "処理中"}],
            "created": "2025-06-18T10:00:00Z",
        }
        stats: dict = {}
        with patch("plane.utils.backlog.sync.resolve_status_english", side_effect=lambda _s, v, **_: {"未対応": "Open", "処理中": "In Progress"}.get(v, v)):
            sync_backlog_changelog_to_activities(sync, issue_sync, entry, stats=stats)

        activity = IssueActivity.objects.get(issue=issue, field="state")
        assert activity.old_value == "Open"
        assert activity.new_value == "In Progress"
        assert stats["activities_created"] == 1

        from plane.db.models import Project, Workspace

        workspace = Workspace.objects.create(name="WS3", slug="ws3", owner=create_user)
        project = Project.objects.create(name="Proj3", identifier="P3", workspace=workspace, created_by=create_user)
        state = State.objects.create(name="Todo", project=project, group="backlog", default=True, created_by=create_user)
        issue = Issue.objects.create(name="Issue", workspace=workspace, project=project, state=state, created_by=create_user)
        sync = BacklogProjectSync.objects.create(
            workspace=workspace,
            project=project,
            space_host="example.backlog.com",
            backlog_project_key="P3",
            api_key_encrypted="enc",
            created_by=create_user,
        )
        issue_sync = BacklogIssueSync.objects.create(
            workspace=workspace,
            project=project,
            issue=issue,
            backlog_issue_id=300,
            backlog_issue_key="P3-1",
            created_by=create_user,
        )
        entry = {
            "id": 1000,
            "content": None,
            "changeLog": [{"field": "priority", "originalValue": "中", "newValue": "高"}],
            "created": "2025-06-18T10:00:00Z",
        }
        stats: dict = {}
        sync_backlog_changelog_to_activities(sync, issue_sync, entry, stats=stats)
        sync_backlog_changelog_to_activities(sync, issue_sync, entry, stats=stats)
        assert IssueActivity.objects.filter(issue=issue, field="priority").count() == 1
