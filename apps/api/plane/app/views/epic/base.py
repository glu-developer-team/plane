# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from copy import deepcopy
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import IssueCreateSerializer, IssueSerializer, ProjectUserPropertySerializer
from plane.app.views.issue.base import (
    IssueDetailEndpoint,
    IssuePaginatedViewSet,
    IssueViewSet,
)
from plane.bgtasks.issue_activities_task import issue_activity
from plane.bgtasks.webhook_task import model_activity
from plane.db.models import Issue, Project, ProjectUserProperty
from plane.utils.epic import epic_queryset, get_or_create_epic_type, non_epic_filter
from plane.utils.grouper import issue_queryset_grouper
from plane.utils.host import base_host
from plane.utils.timezone_converter import user_timezone_converter

from .. import BaseAPIView


class EpicViewSet(IssueViewSet):
    work_item_scope = "epics"

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id)
        epic_type = get_or_create_epic_type(project.workspace, project)

        data = request.data.copy()
        data["type_id"] = str(epic_type.id)

        serializer = IssueCreateSerializer(
            data=data,
            context={
                "project_id": project_id,
                "workspace_id": project.workspace_id,
                "default_assignee_id": project.default_assignee_id,
            },
        )

        if serializer.is_valid():
            serializer.save(type=epic_type)

            issue_activity.delay(
                type="issue.activity.created",
                requested_data=json.dumps(request.data, cls=DjangoJSONEncoder),
                actor_id=str(request.user.id),
                issue_id=str(serializer.data.get("id", None)),
                project_id=str(project_id),
                current_instance=None,
                epoch=int(timezone.now().timestamp()),
                notification=True,
                origin=base_host(request=request, is_app=True),
            )
            queryset = self.get_queryset()
            queryset = self.apply_annotations(queryset)
            issue = (
                issue_queryset_grouper(
                    queryset=queryset.filter(pk=serializer.data["id"]),
                    group_by=None,
                    sub_group_by=None,
                )
                .values(
                    "id",
                    "name",
                    "state_id",
                    "sort_order",
                    "completed_at",
                    "estimate_point",
                    "priority",
                    "start_date",
                    "target_date",
                    "sequence_id",
                    "project_id",
                    "parent_id",
                    "cycle_id",
                    "module_ids",
                    "label_ids",
                    "assignee_ids",
                    "sub_issues_count",
                    "created_at",
                    "updated_at",
                    "created_by",
                    "updated_by",
                    "attachment_count",
                    "link_count",
                    "is_draft",
                    "archived_at",
                    "deleted_at",
                )
                .first()
            )
            datetime_fields = ["created_at", "updated_at"]
            issue = user_timezone_converter(issue, datetime_fields, request.user.user_timezone)
            model_activity.delay(
                model_name="issue",
                model_id=str(serializer.data["id"]),
                requested_data=request.data,
                current_instance=None,
                actor_id=request.user.id,
                slug=slug,
                origin=base_host(request=request, is_app=True),
            )
            return Response(issue, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EpicPaginatedViewSet(IssuePaginatedViewSet):
    work_item_scope = "epics"


class EpicDetailEndpoint(IssueDetailEndpoint):
    work_item_scope = "epics"


class EpicUserDisplayPropertyEndpoint(BaseAPIView):
    EPIC_PREFERENCES_KEY = "epics"

    def _get_epic_preferences(self, issue_property):
        preferences = issue_property.preferences or {}
        epic_prefs = preferences.get(self.EPIC_PREFERENCES_KEY, {})
        if not epic_prefs:
            return {
                "filters": issue_property.filters,
                "display_filters": issue_property.display_filters,
                "display_properties": issue_property.display_properties,
                "rich_filters": issue_property.rich_filters,
            }
        return epic_prefs

    def _set_epic_preferences(self, issue_property, data):
        preferences = deepcopy(issue_property.preferences or {})
        current = preferences.get(self.EPIC_PREFERENCES_KEY, {})
        for key in ("filters", "display_filters", "display_properties", "rich_filters"):
            if key in data:
                current[key] = data[key]
        preferences[self.EPIC_PREFERENCES_KEY] = current
        issue_property.preferences = preferences
        issue_property.save(update_fields=["preferences"])
        return current

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def patch(self, request, slug, project_id):
        try:
            issue_property = ProjectUserProperty.objects.get(user=request.user, project_id=project_id)
        except ProjectUserProperty.DoesNotExist:
            issue_property = ProjectUserProperty.objects.create(user=request.user, project_id=project_id)

        epic_data = self._set_epic_preferences(issue_property, request.data)
        return Response(epic_data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        issue_property, _ = ProjectUserProperty.objects.get_or_create(user=request.user, project_id=project_id)
        return Response(self._get_epic_preferences(issue_property), status=status.HTTP_200_OK)


class EpicIssuesEndpoint(BaseAPIView):
    """List and assign work items under an epic (mirrors SubIssuesEndpoint)."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        from plane.app.views.issue.sub_issue import SubIssuesEndpoint

        epic = Issue.issue_objects.filter(
            pk=issue_id,
            project_id=project_id,
            workspace__slug=slug,
            type__is_epic=True,
        ).first()
        if not epic:
            return Response({"error": "Epic not found"}, status=status.HTTP_404_NOT_FOUND)
        return SubIssuesEndpoint().get(request, slug, project_id, issue_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, issue_id):
        parent_issue = Issue.issue_objects.filter(
            pk=issue_id,
            project_id=project_id,
            workspace__slug=slug,
            type__is_epic=True,
        ).first()
        if not parent_issue:
            return Response({"error": "Epic not found"}, status=status.HTTP_404_NOT_FOUND)

        sub_issue_ids = request.data.get("sub_issue_ids", []) or request.data.get("work_item_ids", [])

        if not len(sub_issue_ids):
            return Response({"error": "Sub Issue IDs are required"}, status=status.HTTP_400_BAD_REQUEST)

        sub_issues = Issue.issue_objects.filter(id__in=sub_issue_ids).filter(non_epic_filter())

        for sub_issue in sub_issues:
            sub_issue.parent = parent_issue

        Issue.objects.bulk_update(sub_issues, ["parent"], batch_size=10)

        from collections import defaultdict

        from django.db.models import F

        updated_sub_issues = Issue.issue_objects.filter(id__in=sub_issue_ids).annotate(state_group=F("state__group"))

        _ = [
            issue_activity.delay(
                type="issue.activity.updated",
                requested_data=json.dumps({"parent": str(issue_id)}),
                actor_id=str(request.user.id),
                issue_id=str(sub_issue_id),
                project_id=str(project_id),
                current_instance=json.dumps({"parent": str(sub_issue_id)}),
                epoch=int(timezone.now().timestamp()),
                notification=True,
                origin=base_host(request=request, is_app=True),
            )
            for sub_issue_id in sub_issue_ids
        ]

        result = defaultdict(list)
        for sub_issue in updated_sub_issues:
            result[sub_issue.state_group].append(str(sub_issue.id))

        serializer = IssueSerializer(updated_sub_issues, many=True)
        return Response({"sub_issues": serializer.data, "state_distribution": result}, status=status.HTTP_200_OK)
