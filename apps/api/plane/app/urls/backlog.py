# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.integration.backlog import (
    BacklogProjectSyncEndpoint,
    BacklogPullEndpoint,
    BacklogSyncStateEndpoint,
    BacklogSyncStatusEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/backlog-sync/",
        BacklogProjectSyncEndpoint.as_view(),
        name="backlog-sync",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/backlog-sync/pull/",
        BacklogPullEndpoint.as_view(),
        name="backlog-sync-pull",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/backlog-sync/status/",
        BacklogSyncStatusEndpoint.as_view(),
        name="backlog-sync-status",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/backlog-sync/sync-state/",
        BacklogSyncStateEndpoint.as_view(),
        name="backlog-sync-state",
    ),
]
