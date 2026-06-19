# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import F, Func, OuterRef
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers import IssueSerializer
from plane.api.views.issue import IssueDetailAPIEndpoint, IssueListCreateAPIEndpoint
from plane.app.permissions import ProjectEntityPermission
from plane.bgtasks.issue_activities_task import issue_activity
from plane.bgtasks.webhook_task import model_activity
from plane.db.models import Issue, Project
from plane.utils.epic import epic_queryset, get_or_create_epic_type, non_epic_filter
from plane.utils.host import base_host

from .base import BaseAPIView


class EpicListCreateAPIEndpoint(IssueListCreateAPIEndpoint):
    def get_queryset(self):
        return epic_queryset(
            Issue.issue_objects.annotate(
                sub_issues_count=Issue.issue_objects.filter(parent=OuterRef("id"))
                .order_by()
                .annotate(count=Func(F("id"), function="Count"))
                .values("count")
            )
            .filter(project_id=self.kwargs.get("project_id"))
            .filter(workspace__slug=self.kwargs.get("slug"))
            .select_related("project")
            .select_related("workspace")
            .select_related("state")
            .select_related("parent")
            .prefetch_related("assignees")
            .prefetch_related("labels")
            .order_by(self.kwargs.get("order_by", "-created_at"))
        ).distinct()

    def post(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id)
        epic_type = get_or_create_epic_type(project.workspace, project)

        data = request.data.copy()
        data["type_id"] = str(epic_type.id)

        serializer = IssueSerializer(
            data=data,
            context={
                "project_id": project_id,
                "workspace_id": project.workspace_id,
                "default_assignee_id": project.default_assignee_id,
            },
        )

        if serializer.is_valid():
            serializer.save(type=epic_type)
            issue = Issue.objects.filter(workspace__slug=slug, project_id=project_id, pk=serializer.data["id"]).first()
            issue_activity.delay(
                type="issue.activity.created",
                requested_data=json.dumps(self.request.data, cls=DjangoJSONEncoder),
                actor_id=str(request.user.id),
                issue_id=str(serializer.data.get("id", None)),
                project_id=str(project_id),
                current_instance=None,
                epoch=int(timezone.now().timestamp()),
            )
            model_activity.delay(
                model_name="issue",
                model_id=str(serializer.data["id"]),
                requested_data=request.data,
                current_instance=None,
                actor_id=request.user.id,
                slug=slug,
                origin=base_host(request=request, is_app=True),
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EpicDetailAPIEndpoint(IssueDetailAPIEndpoint):
    def get_queryset(self):
        return epic_queryset(
            Issue.issue_objects.annotate(
                sub_issues_count=Issue.issue_objects.filter(parent=OuterRef("id"))
                .order_by()
                .annotate(count=Func(F("id"), function="Count"))
                .values("count")
            )
            .filter(project_id=self.kwargs.get("project_id"))
            .filter(workspace__slug=self.kwargs.get("slug"))
            .select_related("project")
            .select_related("workspace")
            .select_related("state")
            .select_related("parent")
            .prefetch_related("assignees")
            .prefetch_related("labels")
            .order_by(self.kwargs.get("order_by", "-created_at"))
        ).distinct()


class EpicIssuesAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, epic_id):
        epic = Issue.issue_objects.filter(
            pk=epic_id,
            project_id=project_id,
            workspace__slug=slug,
            type__is_epic=True,
        ).first()
        if not epic:
            return Response({"error": "Epic not found"}, status=status.HTTP_404_NOT_FOUND)

        issues = (
            Issue.issue_objects.filter(parent_id=epic_id, project_id=project_id, workspace__slug=slug)
            .filter(non_epic_filter())
            .select_related("project", "workspace", "state", "parent")
            .prefetch_related("assignees", "labels")
        )
        serializer = IssueSerializer(issues, many=True, fields=self.fields, expand=self.expand)
        return Response({"results": serializer.data, "count": issues.count()}, status=status.HTTP_200_OK)

    def post(self, request, slug, project_id, epic_id):
        epic = Issue.issue_objects.filter(
            pk=epic_id,
            project_id=project_id,
            workspace__slug=slug,
            type__is_epic=True,
        ).first()
        if not epic:
            return Response({"error": "Epic not found"}, status=status.HTTP_404_NOT_FOUND)

        work_item_ids = request.data.get("work_item_ids", []) or request.data.get("sub_issue_ids", [])
        if not work_item_ids:
            return Response({"error": "work_item_ids are required"}, status=status.HTTP_400_BAD_REQUEST)

        sub_issues = Issue.issue_objects.filter(id__in=work_item_ids).filter(non_epic_filter())
        for sub_issue in sub_issues:
            sub_issue.parent = epic
        Issue.objects.bulk_update(sub_issues, ["parent"], batch_size=10)

        updated = Issue.issue_objects.filter(id__in=work_item_ids).annotate(state_group=F("state__group"))
        serializer = IssueSerializer(updated, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)


class ProjectFeaturesAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def _project_features(self, project):
        return {
            "epics": True,
            "modules": bool(project.module_view),
            "cycles": bool(project.cycle_view),
            "views": bool(project.issue_views_view),
            "pages": bool(project.page_view),
            "intakes": bool(project.inbox_view),
            "work_item_types": bool(project.is_issue_type_enabled),
            "workflows": False,
            "parallel_cycles": False,
            "project_updates": False,
        }

    def get(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        return Response(self._project_features(project), status=status.HTTP_200_OK)

    def patch(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        return Response(self._project_features(project), status=status.HTTP_200_OK)
