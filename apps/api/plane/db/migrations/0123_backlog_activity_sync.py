# Generated manually for Backlog activity dedup

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("db", "0122_backlog_connector"),
    ]

    operations = [
        migrations.CreateModel(
            name="BacklogActivitySync",
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
                ("change_field", models.CharField(max_length=64)),
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
                        related_name="activity_syncs",
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
                "verbose_name": "Backlog Activity Sync",
                "verbose_name_plural": "Backlog Activity Syncs",
                "db_table": "backlog_activity_syncs",
                "ordering": ("-created_at",),
                "unique_together": {("issue_sync", "backlog_comment_id", "change_field")},
            },
        ),
    ]
