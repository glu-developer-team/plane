# Generated manually for GitHub PR connector webhook logs

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("db", "0125_github_pr_connector"),
    ]

    operations = [
        migrations.CreateModel(
            name="GithubWebhookLog",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("delivery_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("event_name", models.CharField(db_index=True, max_length=64)),
                ("action", models.CharField(blank=True, default="", max_length=64)),
                ("repo_owner", models.CharField(blank=True, default="", max_length=255)),
                ("repo_name", models.CharField(blank=True, default="", max_length=255)),
                ("handled", models.BooleanField(default=False)),
                ("result", models.JSONField(default=dict)),
                ("error", models.TextField(blank=True, default="")),
                ("payload_summary", models.JSONField(default=dict)),
            ],
            options={
                "verbose_name": "Github Webhook Log",
                "verbose_name_plural": "Github Webhook Logs",
                "db_table": "github_webhook_logs",
                "ordering": ("-created_at",),
            },
        ),
    ]
