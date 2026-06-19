# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers.github_pr import GithubProjectSyncSerializer, GithubProjectSyncWriteSerializer
from plane.app.views.base import BaseAPIView
from plane.bgtasks.github_pr_sync_task import dispatch_github_webhook
from plane.db.models import GithubProjectSync, GithubSyncJob, Project, Workspace
from plane.utils.github.pr_sync import (
    DEFAULT_SYNC_MODE,
    GITHUB_WEBHOOK_EVENTS,
    create_github_webhook_log,
    enqueue_github_resync,
    get_enabled_github_project_sync,
)
from plane.utils.github.webhook import verify_github_signature


class GithubProjectSyncEndpoint(BaseAPIView):
    def _get_sync(self, slug, project_id):
        return GithubProjectSync.objects.filter(
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
                    "is_enabled": False,
                    "sync_mode": DEFAULT_SYNC_MODE,
                },
                status=status.HTTP_200_OK,
            )
        data = GithubProjectSyncSerializer(sync).data
        return Response(data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="PROJECT")
    def post(self, request, slug, project_id):
        project = Project.objects.get(id=project_id, workspace__slug=slug)
        sync = self._get_sync(slug, project_id)
        serializer = GithubProjectSyncWriteSerializer(
            instance=sync,
            data=request.data,
            partial=bool(sync),
            context={"project": project, "workspace": project.workspace, "request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        saved = serializer.save()
        return Response(
            GithubProjectSyncSerializer(saved).data,
            status=status.HTTP_200_OK if sync else status.HTTP_201_CREATED,
        )

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="PROJECT")
    def delete(self, request, slug, project_id):
        sync = self._get_sync(slug, project_id)
        if sync:
            sync.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GithubResyncEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN], level="PROJECT")
    def post(self, request, slug, project_id):
        if not get_enabled_github_project_sync(project_id):
            return Response({"enabled": False}, status=status.HTTP_404_NOT_FOUND)

        job, deduplicated = enqueue_github_resync(project_id)
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


class GithubResyncStatusEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="PROJECT")
    def get(self, request, slug, project_id):
        job_id = request.query_params.get("job_id")
        if not job_id:
            return Response({"error": "job_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        job = GithubSyncJob.objects.filter(
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
                "stats": job.stats,
                "error": job.error,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class GithubWebhookEndpoint(BaseAPIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        event_name = request.headers.get("X-GitHub-Event", "")
        signature = request.headers.get("X-Hub-Signature-256")
        delivery_id = request.headers.get("X-GitHub-Delivery", "")

        if event_name == "ping":
            if not verify_github_signature(request.body, signature):
                return HttpResponse(status=401)
            return HttpResponse(status=200)

        if not verify_github_signature(request.body, signature):
            return HttpResponse(status=401)

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponse(status=400)

        if event_name in GITHUB_WEBHOOK_EVENTS:
            log = create_github_webhook_log(event_name, payload, delivery_id=delivery_id)
            dispatch_github_webhook(event_name, payload, str(log.id))

        return HttpResponse(status=200)


class GithubAppInstallEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        installation_id = request.data.get("installation_id")
        project_id = request.data.get("project_id")

        if not installation_id:
            return Response({"detail": "installation_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            installation_id = int(installation_id)
        except (TypeError, ValueError):
            return Response({"detail": "installation_id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        workspace = Workspace.objects.get(slug=slug)

        if project_id:
            sync = GithubProjectSync.objects.filter(
                project_id=project_id,
                project__workspace=workspace,
                deleted_at__isnull=True,
            ).first()
            if not sync:
                return Response({"detail": "GitHub PR sync not configured for this project"}, status=404)
            sync.installation_id = installation_id
            sync.save(update_fields=["installation_id", "updated_at"])
            return Response({"installation_id": installation_id, "project_id": str(project_id)})

        updated = GithubProjectSync.objects.filter(
            workspace=workspace,
            deleted_at__isnull=True,
        ).update(installation_id=installation_id)

        return Response({"installation_id": installation_id, "projects_updated": updated})
