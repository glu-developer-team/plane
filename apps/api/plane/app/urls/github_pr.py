# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.integration.github_pr import (
    GithubAppInstallEndpoint,
    GithubProjectSyncEndpoint,
    GithubResyncEndpoint,
    GithubResyncStatusEndpoint,
    GithubWebhookEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/github-pr-sync/",
        GithubProjectSyncEndpoint.as_view(),
        name="github-pr-sync",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/github-pr-sync/resync/",
        GithubResyncEndpoint.as_view(),
        name="github-pr-sync-resync",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/github-pr-sync/resync/status/",
        GithubResyncStatusEndpoint.as_view(),
        name="github-pr-sync-resync-status",
    ),
    path(
        "workspaces/<str:slug>/github-app/install/",
        GithubAppInstallEndpoint.as_view(),
        name="github-app-install",
    ),
    path(
        "github/webhook/",
        GithubWebhookEndpoint.as_view(),
        name="github-webhook",
    ),
]
