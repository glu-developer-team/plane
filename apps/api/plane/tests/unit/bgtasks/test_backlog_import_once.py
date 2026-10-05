# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from plane.app.serializers.backlog import BacklogProjectSyncWriteSerializer
from plane.bgtasks.backlog_sync_task import (
    backlog_pull_issue_task,
    backlog_pull_project_task,
    backlog_push_comment_task,
)
from plane.db.models import (
    BacklogIssueSync,
    BacklogProjectSync,
    BacklogSyncJob,
    Issue,
    IssueActivity,
    IssueComment,
    Project,
    State,
    Workspace,
)
from plane.utils.backlog.sync import (
    get_sync_mode,
    import_backlog_issue_once,
    is_backlog_push_enabled,
    sync_backlog_comments,
    sync_backlog_statuses_to_plane,
    upsert_plane_issue_from_backlog,
)
from plane.utils.encryption import encrypt_value


@pytest.fixture
def import_setup(create_user, monkeypatch):
    monkeypatch.setattr("celery.app.task.Task.delay", MagicMock())
    workspace = Workspace.objects.create(name="Import", slug="import", owner=create_user)
    project = Project.objects.create(name="Import", identifier="IMP", workspace=workspace, created_by=create_user)
    state = State.objects.create(name="Open", project=project, group="backlog", default=True, color="#123456")
    sync = BacklogProjectSync.objects.create(
        project=project,
        workspace=workspace,
        space_host="example.backlog.com",
        backlog_project_key="IMP",
        backlog_project_id=99,
        api_key_encrypted=encrypt_value("test-key"),
        created_by=create_user,
        config={"sync_mode": "import_once", "status_map": {"1": str(state.id)}},
    )
    client = MagicMock()
    client.get_statuses.return_value = [{"id": 1, "name": "Open", "color": "#ffffff", "displayOrder": 1}]
    client.list_all_comments.return_value = [
        {
            "id": 10,
            "content": "Initial comment",
            "created": "2026-10-01T00:00:00Z",
            "changeLog": [{"field": "summary", "originalValue": "Old", "newValue": "Imported"}],
        },
    ]
    backlog_issue = {
        "id": 100,
        "issueKey": "IMP-1",
        "summary": "Imported",
        "description": "Initial description",
        "status": {"id": 1},
        "priority": {"id": 3},
        "updated": "2026-10-01T00:00:00Z",
    }
    return sync, client, backlog_issue, state


@pytest.mark.django_db
class TestBacklogImportOnce:
    def test_repeated_import_keeps_all_plane_data(self, import_setup):
        sync, client, data, state = import_setup
        stats = {}
        import_backlog_issue_once(sync, client, data, stats)
        issue = Issue.objects.get(external_id="IMP-1")
        assert stats["created"] == 1
        assert IssueComment.objects.filter(issue=issue).count() == 1
        assert IssueActivity.objects.filter(issue=issue).count() == 1

        local_state = State.objects.create(name="Plane review", group="started", project=sync.project)
        issue.name = "Plane title"
        issue.description_html = "<p>Plane content</p>"
        issue.state = local_state
        issue.priority = "urgent"
        issue.save()
        saved_at = issue.updated_at
        data.update(summary="Remote title", description="Remote content", priority={"id": 4})
        client.list_all_comments.reset_mock()

        import_backlog_issue_once(sync, client, data, stats)
        # The lower-level entry points must also leave existing imports alone.
        upsert_plane_issue_from_backlog(sync, data, stats=stats)
        sync_backlog_comments(sync, client, BacklogIssueSync.objects.get(issue=issue), stats)
        issue.refresh_from_db()
        assert (issue.name, issue.description_html, issue.state_id, issue.priority, issue.updated_at) == (
            "Plane title",
            "<p>Plane content</p>",
            local_state.id,
            "urgent",
            saved_at,
        )
        assert IssueComment.objects.filter(issue=issue).count() == 1
        assert IssueActivity.objects.filter(issue=issue).count() == 1
        client.list_all_comments.assert_not_called()

    def test_switching_existing_sync_does_not_reimport(self, import_setup):
        sync, client, data, state = import_setup
        issue = Issue.objects.create(project=sync.project, workspace=sync.workspace, state=state, name="Keep me")
        BacklogIssueSync.objects.create(
            project=sync.project,
            workspace=sync.workspace,
            issue=issue,
            backlog_issue_id=100,
            backlog_issue_key="IMP-1",
        )
        import_backlog_issue_once(sync, client, data, {})
        issue.refresh_from_db()
        assert issue.name == "Keep me"
        client.list_all_comments.assert_not_called()

    def test_deleted_task_is_not_resurrected(self, import_setup):
        sync, client, data, state = import_setup
        import_backlog_issue_once(sync, client, data, {})
        issue = Issue.objects.get(external_id="IMP-1")
        Issue.all_objects.filter(id=issue.id).update(deleted_at=timezone.now())
        client.list_all_comments.reset_mock()
        import_backlog_issue_once(sync, client, data, {})
        assert Issue.all_objects.filter(project=sync.project).count() == 1
        assert not Issue.objects.filter(id=issue.id).exists()
        client.list_all_comments.assert_not_called()

    def test_legacy_external_task_without_link_is_not_duplicated(self, import_setup):
        sync, client, data, state = import_setup
        issue = Issue.objects.create(
            project=sync.project,
            workspace=sync.workspace,
            state=state,
            name="Legacy",
            external_source="backlog",
            external_id="IMP-1",
        )
        import_backlog_issue_once(sync, client, data, {})
        assert Issue.objects.filter(project=sync.project).count() == 1
        issue.refresh_from_db()
        assert issue.name == "Legacy"
        client.list_all_comments.assert_not_called()

    def test_purged_task_and_link_are_not_reimported(self, import_setup):
        sync, client, data, state = import_setup
        import_backlog_issue_once(sync, client, data, {})
        IssueActivity.all_objects.filter(issue__external_id="IMP-1").delete()
        Issue.all_objects.filter(external_id="IMP-1").delete()
        assert not BacklogIssueSync.all_objects.filter(project=sync.project).exists()
        client.list_all_comments.reset_mock()
        import_backlog_issue_once(sync, client, data, {})
        assert not Issue.all_objects.filter(project=sync.project).exists()
        client.list_all_comments.assert_not_called()

    def test_status_refresh_retains_import_markers_from_other_worker(self, import_setup):
        sync, client, data, state = import_setup
        stale_sync = BacklogProjectSync.objects.get(id=sync.id)
        import_backlog_issue_once(sync, client, data, {})
        sync_backlog_statuses_to_plane(stale_sync, client)
        sync.refresh_from_db()
        assert sync.config["imported_issue_keys"] == {"IMP-1": True}

    def test_failed_initial_comments_roll_back_and_can_retry(self, import_setup):
        sync, client, data, state = import_setup
        client.list_all_comments.side_effect = RuntimeError("Backlog unavailable")
        with pytest.raises(RuntimeError):
            import_backlog_issue_once(sync, client, data, {})
        assert not BacklogIssueSync.objects.filter(project=sync.project).exists()
        assert not Issue.objects.filter(project=sync.project).exists()
        client.list_all_comments.side_effect = None
        import_backlog_issue_once(sync, client, data, {})
        assert Issue.objects.filter(project=sync.project).count() == 1
        assert IssueComment.objects.filter(project=sync.project).count() == 1

    def test_status_import_preserves_plane_edits_and_default(self, import_setup):
        sync, client, data, state = import_setup
        state.name = "Plane workflow"
        state.group = "started"
        state.sequence = 42
        state.save()
        client.get_statuses.return_value.append(
            {"id": 2, "name": "Closed", "color": "#000000", "displayOrder": 2},
        )
        mapping = sync_backlog_statuses_to_plane(sync, client)
        state.refresh_from_db()
        assert (state.name, state.color, state.group, state.sequence, state.default) == (
            "Plane workflow",
            "#123456",
            "started",
            42,
            True,
        )
        assert mapping["1"] == str(state.id)
        assert State.objects.get(id=mapping["2"]).name == "Closed"
        assert State.objects.filter(project=sync.project, default=True).count() == 1

    def test_deleted_plane_state_is_not_recreated(self, import_setup):
        sync, client, data, state = import_setup
        State.all_objects.filter(id=state.id).update(deleted_at=timezone.now())
        mapping = sync_backlog_statuses_to_plane(sync, client)
        assert "1" not in mapping
        sync_backlog_statuses_to_plane(sync, client)
        assert State.all_objects.filter(project=sync.project).count() == 1

    def test_saving_import_mode_preserves_state_labels(self, import_setup):
        sync, client, data, state = import_setup
        sync.config["sync_mode"] = "backlog_to_plane"
        sync.config["backlog_status_labels"] = {"1": {"ja": "Open", "en": "Open"}}
        sync.save()
        serializer = BacklogProjectSyncWriteSerializer(
            instance=sync,
            partial=True,
            data={
                "space_host": sync.space_host,
                "sync_mode": "import_once",
                "test_connection": False,
                "status_locale_entries": [{"backlog_status_id": "1", "english": "Remote label"}],
            },
            context={"project": sync.project, "workspace": sync.workspace},
        )
        assert serializer.is_valid(), serializer.errors
        with patch("plane.app.serializers.backlog.BacklogClient", return_value=client):
            serializer.save()
        sync.refresh_from_db()
        state.refresh_from_db()
        assert get_sync_mode(sync) == "import_once"
        assert state.name == "Open"

    def test_project_pull_only_imports_unseen_tasks(self, import_setup):
        sync, client, data, state = import_setup
        import_backlog_issue_once(sync, client, data, {})
        sync.last_pulled_at = timezone.now()
        sync.save()
        new_issue = {**data, "id": 101, "issueKey": "IMP-2", "summary": "New task"}
        client.list_issues.return_value = [data, new_issue]
        client.list_all_comments.reset_mock()
        job = BacklogSyncJob.objects.create(project=sync.project, workspace=sync.workspace, scope="project")
        with patch("plane.bgtasks.backlog_sync_task.backlog_client_for_sync", return_value=client):
            backlog_pull_project_task(str(sync.project_id), str(job.id))
        job.refresh_from_db()
        assert job.status == "completed"
        assert job.stats["created"] == 1
        assert job.stats["skipped"] == 1
        assert Issue.objects.filter(project=sync.project).count() == 2
        client.list_all_comments.assert_called_once_with("IMP-2")
        assert client.list_issues.call_args.kwargs["updated_since"] is None

    def test_issue_pull_does_not_contact_backlog(self, import_setup):
        sync, client, data, state = import_setup
        import_backlog_issue_once(sync, client, data, {})
        issue = Issue.objects.get(external_id="IMP-1")
        job = BacklogSyncJob.objects.create(project=sync.project, workspace=sync.workspace, scope="issue", issue=issue)
        with patch("plane.bgtasks.backlog_sync_task.backlog_client_for_sync") as factory:
            backlog_pull_issue_task(str(sync.project_id), str(issue.id), str(job.id))
        factory.assert_not_called()
        job.refresh_from_db()
        assert job.status == "completed"

    def test_import_once_is_accepted_and_never_pushes_comments(self, import_setup):
        sync, client, data, state = import_setup
        serializer = BacklogProjectSyncWriteSerializer(data={"sync_mode": "import_once"}, partial=True)
        assert serializer.is_valid(), serializer.errors
        assert get_sync_mode(sync) == "import_once"
        assert not is_backlog_push_enabled(sync)
        import_backlog_issue_once(sync, client, data, {})
        issue = Issue.objects.get(external_id="IMP-1")
        comment = IssueComment.objects.create(
            project=sync.project,
            workspace=sync.workspace,
            issue=issue,
            actor=sync.created_by,
            comment_html="Plane comment",
        )
        with patch("plane.bgtasks.backlog_sync_task.backlog_client_for_sync") as factory:
            backlog_push_comment_task(str(comment.id))
        factory.assert_not_called()
