# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import MagicMock, patch

import pytest

from plane.bgtasks.backlog_sync_task import backlog_push_issue_task
from plane.db.models import BacklogIssueSync, BacklogProjectSync, Issue, State
from plane.utils.backlog.client import BACKLOG_EXTERNAL_SOURCE


@pytest.mark.django_db
class TestBacklogPushIssueTask:
    @pytest.fixture
    def backlog_setup(self, create_user):
        from plane.db.models import Project, Workspace

        workspace = Workspace.objects.create(name="WS Push", slug="ws-push", owner=create_user)
        project = Project.objects.create(name="Proj Push", identifier="PUSH", workspace=workspace, created_by=create_user)
        state = State.objects.create(name="Open", project=project, group="backlog", default=True, created_by=create_user)
        issue = Issue.objects.create(
            name="Legacy issue",
            description_html="<p>Hello</p>",
            workspace=workspace,
            project=project,
            state=state,
            created_by=create_user,
        )
        sync = BacklogProjectSync.objects.create(
            workspace=workspace,
            project=project,
            space_host="example.backlog.com",
            backlog_project_key="PUSH",
            backlog_project_id=99,
            api_key_encrypted="enc",
            created_by=create_user,
        )
        return sync, issue

    def test_legacy_issue_update_creates_backlog_link(self, backlog_setup):
        sync, issue = backlog_setup
        mock_client = MagicMock()
        mock_client.create_issue.return_value = {
            "id": 501,
            "issueKey": "PUSH-10",
            "updated": "2025-06-19T00:00:00Z",
        }

        with patch("plane.bgtasks.backlog_sync_task.get_enabled_backlog_sync", return_value=sync):
            with patch("plane.bgtasks.backlog_sync_task.backlog_client_for_sync", return_value=mock_client):
                with patch("plane.bgtasks.backlog_sync_task.ensure_status_map"):
                    with patch("plane.bgtasks.backlog_sync_task.default_issue_type_id", return_value=1):
                        backlog_push_issue_task(str(issue.id), action="update")

        issue.refresh_from_db()
        issue_sync = BacklogIssueSync.objects.get(issue_id=issue.id)
        assert issue_sync.backlog_issue_key == "PUSH-10"
        assert issue.external_source == BACKLOG_EXTERNAL_SOURCE
        assert issue.external_id == "PUSH-10"
        mock_client.create_issue.assert_called_once()
        mock_client.update_issue.assert_not_called()

    def test_legacy_issue_update_skipped_when_one_way_sync(self, backlog_setup):
        sync, issue = backlog_setup
        sync.config = {"sync_mode": "backlog_to_plane"}
        sync.save(update_fields=["config", "updated_at"])
        mock_client = MagicMock()

        with patch("plane.bgtasks.backlog_sync_task.get_enabled_backlog_sync", return_value=sync):
            with patch("plane.bgtasks.backlog_sync_task.backlog_client_for_sync", return_value=mock_client):
                with patch("plane.bgtasks.backlog_sync_task.ensure_status_map"):
                    backlog_push_issue_task(str(issue.id), action="update")

        assert BacklogIssueSync.objects.filter(issue_id=issue.id).exists() is False
        mock_client.create_issue.assert_not_called()
        mock_client.update_issue.assert_not_called()

    def test_linked_issue_update_patches_backlog(self, backlog_setup):
        sync, issue = backlog_setup
        BacklogIssueSync.objects.create(
            workspace=sync.workspace,
            project=sync.project,
            issue=issue,
            backlog_issue_id=500,
            backlog_issue_key="PUSH-9",
            created_by=sync.created_by,
        )
        mock_client = MagicMock()
        mock_client.update_issue.return_value = {"updated": "2025-06-19T00:00:00Z"}

        with patch("plane.bgtasks.backlog_sync_task.get_enabled_backlog_sync", return_value=sync):
            with patch("plane.bgtasks.backlog_sync_task.backlog_client_for_sync", return_value=mock_client):
                with patch("plane.bgtasks.backlog_sync_task.ensure_status_map"):
                    backlog_push_issue_task(str(issue.id), action="update")

        mock_client.update_issue.assert_called_once_with("PUSH-9", mock_client.update_issue.call_args[0][1])
        mock_client.create_issue.assert_not_called()
