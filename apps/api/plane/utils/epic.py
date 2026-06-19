# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db.models import Q

from plane.db.models import IssueType, Project, Workspace
from plane.db.models.issue_type import ProjectIssueType


def non_epic_filter() -> Q:
    return Q(type__isnull=True) | Q(type__is_epic=False)


def epic_filter() -> Q:
    return Q(type__is_epic=True)


def epic_queryset(queryset):
    return queryset.filter(epic_filter())


def non_epic_queryset(queryset):
    return queryset.filter(non_epic_filter())


def get_or_create_epic_type(workspace: Workspace, project: Project) -> IssueType:
    epic_type = IssueType.objects.filter(workspace=workspace, is_epic=True, is_active=True).first()
    if not epic_type:
        epic_type = IssueType.objects.create(
            workspace=workspace,
            name="Epic",
            description="Epic work item type",
            is_epic=True,
            is_default=False,
            is_active=True,
            level=0,
        )

    ProjectIssueType.objects.get_or_create(
        project=project,
        issue_type=epic_type,
        workspace=project.workspace,
        defaults={"level": 0, "is_default": False},
    )
    return epic_type


def seed_epic_type_for_project(project: Project) -> IssueType:
    return get_or_create_epic_type(project.workspace, project)
