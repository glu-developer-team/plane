# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers.backlog import (
    BacklogProjectSyncSerializer,
    BacklogProjectSyncWriteSerializer,
    BacklogPullRequestSerializer,
    BacklogSyncStateSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.db.models import BacklogProjectSync, BacklogSyncJob, Project
from plane.utils.backlog.sync import DEFAULT_SYNC_MODE, enqueue_backlog_pull, get_enabled_backlog_sync


class BacklogProjectSyncEndpoint(BaseAPIView):
    def _get_sync(self, slug, project_id):
        return BacklogProjectSync.objects.filter(
            project_id=project_id,
            project__workspace__slug=slug,
            deleted_at__isnull=True,
        ).first()

    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="PROJECT")
    def get(self, request, slug, project_id):
        sync = self._get_sync(slug, project_id)
        if not sync:
            return Response(
                {
                    "enabled": False,
                    "sync_mode": DEFAULT_SYNC_MODE,
                    "default_locale_entries": BacklogProjectSyncSerializer().get_default_locale_entries(None),
                    "custom_locale_entries": [],
                    "status_locale_entries": [],
                },
                status=status.HTTP_200_OK,
            )
        data = BacklogProjectSyncSerializer(sync).data
        return Response(data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="PROJECT")
    def post(self, request, slug, project_id):
        project = Project.objects.get(id=project_id, workspace__slug=slug)
        sync = self._get_sync(slug, project_id)
        serializer = BacklogProjectSyncWriteSerializer(
            instance=sync,
            data=request.data,
            partial=bool(sync),
            context={"project": project, "workspace": project.workspace, "request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        saved = serializer.save()
        return Response(
            BacklogProjectSyncSerializer(saved).data,
            status=status.HTTP_200_OK if sync else status.HTTP_201_CREATED,
        )

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="PROJECT")
    def delete(self, request, slug, project_id):
        sync = self._get_sync(slug, project_id)
        if sync:
            sync.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BacklogPullEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="PROJECT")
    def post(self, request, slug, project_id):
        if not get_enabled_backlog_sync(project_id):
            return Response({"enabled": False}, status=status.HTTP_404_NOT_FOUND)

        serializer = BacklogPullRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        scope = serializer.validated_data["scope"]
        issue_id = serializer.validated_data.get("issue_id")
        job, deduplicated = enqueue_backlog_pull(project_id, scope, issue_id)
        if not job:
            return Response({"enabled": False}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "job_id": str(job.id),
                "status": job.status,
                "deduplicated": deduplicated,
            },
            status=status.HTTP_200_OK,
        )


class BacklogSyncStatusEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="PROJECT")
    def get(self, request, slug, project_id):
        if not get_enabled_backlog_sync(project_id):
            return Response({"enabled": False}, status=status.HTTP_404_NOT_FOUND)

        job_id = request.query_params.get("job_id")
        if not job_id:
            return Response({"error": "job_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        job = BacklogSyncJob.objects.filter(
            id=job_id,
            project_id=project_id,
            project__workspace__slug=slug,
            deleted_at__isnull=True,
        ).first()
        if not job:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "id": str(job.id),
                "status": job.status,
                "scope": job.scope,
                "issue_id": str(job.issue_id) if job.issue_id else None,
                "stats": job.stats,
                "error": job.error,
            },
            status=status.HTTP_200_OK,
        )


class BacklogSyncStateEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="PROJECT")
    def get(self, request, slug, project_id):
        sync = get_enabled_backlog_sync(project_id)
        if not sync:
            return Response({"enabled": False}, status=status.HTTP_404_NOT_FOUND)

        active_job = (
            BacklogSyncJob.objects.filter(
                project_id=project_id,
                status__in=[BacklogSyncJob.STATUS_PENDING, BacklogSyncJob.STATUS_RUNNING],
                deleted_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )
        active_payload = None
        if active_job:
            active_payload = {
                "id": str(active_job.id),
                "status": active_job.status,
                "scope": active_job.scope,
                "issue_id": str(active_job.issue_id) if active_job.issue_id else None,
            }

        last_job = (
            BacklogSyncJob.objects.filter(
                project_id=project_id,
                status=BacklogSyncJob.STATUS_COMPLETED,
                deleted_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )

        payload = {
            "enabled": True,
            "last_sync_completed_at": sync.last_sync_completed_at,
            "last_pull_stats": last_job.stats if last_job else {},
            "active_job": active_payload,
        }
        return Response(BacklogSyncStateSerializer(payload).data, status=status.HTTP_200_OK)
