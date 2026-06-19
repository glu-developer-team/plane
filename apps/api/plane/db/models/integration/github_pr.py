# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from plane.db.models.project import ProjectBaseModel


class GithubProjectSync(ProjectBaseModel):
    repo_owner = models.CharField(max_length=255)
    repo_name = models.CharField(max_length=255)
    installation_id = models.BigIntegerField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)
    last_webhook_at = models.DateTimeField(null=True, blank=True)
    last_sync_completed_at = models.DateTimeField(null=True, blank=True)
    config = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Github Project Sync"
        verbose_name_plural = "Github Project Syncs"
        db_table = "github_project_syncs"
        unique_together = ["project"]

    def __str__(self):
        return f"{self.project.name} <-> {self.repo_owner}/{self.repo_name}"


class GithubPRSync(ProjectBaseModel):
    issue = models.ForeignKey("db.Issue", related_name="github_pr_syncs", on_delete=models.CASCADE)
    pr_number = models.PositiveIntegerField()
    pr_node_id = models.CharField(max_length=64, blank=True, default="")
    pr_url = models.URLField()
    head_branch = models.CharField(max_length=500, blank=True, default="")
    base_branch = models.CharField(max_length=500, blank=True, default="")
    pr_state = models.CharField(max_length=32, blank=True, default="open")
    linked_issue_key = models.CharField(max_length=100)
    last_github_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Github PR Sync"
        verbose_name_plural = "Github PR Syncs"
        db_table = "github_pr_syncs"
        unique_together = [("project", "pr_number")]
        ordering = ("-created_at",)

    def __str__(self):
        return f"PR #{self.pr_number} <{self.linked_issue_key}>"


class GithubPRCommentSync(ProjectBaseModel):
    comment = models.ForeignKey("db.IssueComment", related_name="github_pr_syncs", on_delete=models.CASCADE)
    pr_sync = models.ForeignKey("db.GithubPRSync", related_name="comment_syncs", on_delete=models.CASCADE)
    github_comment_id = models.BigIntegerField()

    class Meta:
        verbose_name = "Github PR Comment Sync"
        verbose_name_plural = "Github PR Comment Syncs"
        db_table = "github_pr_comment_syncs"
        unique_together = [("pr_sync", "github_comment_id")]

    def __str__(self):
        return f"github-comment-{self.github_comment_id}"


class GithubSyncJob(ProjectBaseModel):
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
        "db.Issue", related_name="github_sync_jobs", on_delete=models.CASCADE, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    stats = models.JSONField(default=dict)
    error = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Github Sync Job"
        verbose_name_plural = "Github Sync Jobs"
        db_table = "github_sync_jobs"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.scope} sync {self.status}"
