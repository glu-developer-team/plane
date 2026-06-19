# Generated manually for Backlog connector

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("db", "0121_alter_estimate_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="BacklogProjectSync",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("space_host", models.CharField(max_length=255)),
                ("api_key_encrypted", models.TextField(blank=True, default="")),
                ("backlog_project_id", models.PositiveIntegerField(blank=True, null=True)),
                ("backlog_project_key", models.CharField(max_length=100)),
                ("is_enabled", models.BooleanField(default=True)),
                ("last_pulled_at", models.DateTimeField(blank=True, null=True)),
                ("last_sync_completed_at", models.DateTimeField(blank=True, null=True)),
                ("config", models.JSONField(default=dict)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_%(class)s",
                        to="db.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workspace_%(class)s",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Backlog Project Sync",
                "verbose_name_plural": "Backlog Project Syncs",
                "db_table": "backlog_project_syncs",
                "ordering": ("-created_at",),
                "unique_together": {("project",)},
            },
        ),
        migrations.CreateModel(
            name="BacklogIssueSync",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("backlog_issue_id", models.PositiveIntegerField()),
                ("backlog_issue_key", models.CharField(max_length=100)),
                ("backlog_updated_at", models.DateTimeField(blank=True, null=True)),
                ("last_pushed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "issue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="backlog_syncs",
                        to="db.issue",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_%(class)s",
                        to="db.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workspace_%(class)s",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Backlog Issue Sync",
                "verbose_name_plural": "Backlog Issue Syncs",
                "db_table": "backlog_issue_syncs",
                "ordering": ("-created_at",),
                "unique_together": {("project", "issue")},
            },
        ),
        migrations.CreateModel(
            name="BacklogSyncJob",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "scope",
                    models.CharField(
                        choices=[("project", "Project"), ("issue", "Issue")], max_length=20
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("celery_task_id", models.CharField(blank=True, default="", max_length=255)),
                ("stats", models.JSONField(default=dict)),
                ("error", models.TextField(blank=True, default="")),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "issue",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="backlog_sync_jobs",
                        to="db.issue",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_%(class)s",
                        to="db.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workspace_%(class)s",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Backlog Sync Job",
                "verbose_name_plural": "Backlog Sync Jobs",
                "db_table": "backlog_sync_jobs",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="BacklogCommentSync",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("backlog_comment_id", models.PositiveIntegerField()),
                (
                    "comment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="backlog_syncs",
                        to="db.issuecomment",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "issue_sync",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comment_syncs",
                        to="db.backlogissuesync",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_%(class)s",
                        to="db.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workspace_%(class)s",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Backlog Comment Sync",
                "verbose_name_plural": "Backlog Comment Syncs",
                "db_table": "backlog_comment_syncs",
                "ordering": ("-created_at",),
                "unique_together": {("issue_sync", "comment")},
            },
        ),
    ]
