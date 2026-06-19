# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models.project import ProjectBaseModel


class BacklogProjectSync(ProjectBaseModel):
    space_host = models.CharField(max_length=255)
    api_key_encrypted = models.TextField(blank=True, default="")
    backlog_project_id = models.PositiveIntegerField(null=True, blank=True)
    backlog_project_key = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=True)
    last_pulled_at = models.DateTimeField(null=True, blank=True)
    last_sync_completed_at = models.DateTimeField(null=True, blank=True)
    config = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Backlog Project Sync"
        verbose_name_plural = "Backlog Project Syncs"
        db_table = "backlog_project_syncs"
        unique_together = ["project"]

    def __str__(self):
        return f"{self.project.name} <-> {self.backlog_project_key}"


class BacklogIssueSync(ProjectBaseModel):
    issue = models.ForeignKey("db.Issue", related_name="backlog_syncs", on_delete=models.CASCADE)
    backlog_issue_id = models.PositiveIntegerField()
    backlog_issue_key = models.CharField(max_length=100)
    backlog_updated_at = models.DateTimeField(null=True, blank=True)
    last_pushed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Backlog Issue Sync"
        verbose_name_plural = "Backlog Issue Syncs"
        db_table = "backlog_issue_syncs"
        unique_together = ["project", "issue"]

    def __str__(self):
        return f"{self.backlog_issue_key} <{self.issue.name}>"


class BacklogCommentSync(ProjectBaseModel):
    comment = models.ForeignKey("db.IssueComment", related_name="backlog_syncs", on_delete=models.CASCADE)
    issue_sync = models.ForeignKey(
        "db.BacklogIssueSync", related_name="comment_syncs", on_delete=models.CASCADE
    )
    backlog_comment_id = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Backlog Comment Sync"
        verbose_name_plural = "Backlog Comment Syncs"
        db_table = "backlog_comment_syncs"
        unique_together = ["issue_sync", "comment"]

    def __str__(self):
        return f"backlog-comment-{self.backlog_comment_id}"


class BacklogActivitySync(ProjectBaseModel):
    issue_sync = models.ForeignKey(
        "db.BacklogIssueSync", related_name="activity_syncs", on_delete=models.CASCADE
    )
    backlog_comment_id = models.PositiveIntegerField()
    change_field = models.CharField(max_length=64)

    class Meta:
        verbose_name = "Backlog Activity Sync"
        verbose_name_plural = "Backlog Activity Syncs"
        db_table = "backlog_activity_syncs"
        unique_together = ["issue_sync", "backlog_comment_id", "change_field"]

    def __str__(self):
        return f"backlog-activity-{self.backlog_comment_id}:{self.change_field}"


class BacklogSyncJob(ProjectBaseModel):
    SCOPE_PROJECT = "project"
    SCOPE_ISSUE = "issue"
    SCOPE_CHOICES = (
        (SCOPE_PROJECT, "Project"),
        (SCOPE_ISSUE, "Issue"),
    )

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    )

    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    issue = models.ForeignKey(
        "db.Issue", related_name="backlog_sync_jobs", on_delete=models.CASCADE, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    stats = models.JSONField(default=dict)
    error = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Backlog Sync Job"
        verbose_name_plural = "Backlog Sync Jobs"
        db_table = "backlog_sync_jobs"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.scope} sync {self.status}"
