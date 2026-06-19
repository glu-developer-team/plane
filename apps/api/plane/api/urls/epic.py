# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.api.views.epic import (
    EpicDetailAPIEndpoint,
    EpicIssuesAPIEndpoint,
    EpicListCreateAPIEndpoint,
    ProjectFeaturesAPIEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/",
        EpicListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="epic",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/<uuid:pk>/",
        EpicDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="epic",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/<uuid:epic_id>/issues/",
        EpicIssuesAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="epic-issues",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/features/",
        ProjectFeaturesAPIEndpoint.as_view(http_method_names=["get", "patch"]),
        name="project-features",
    ),
]
