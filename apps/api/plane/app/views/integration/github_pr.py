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
from plane.app.views.base import BaseAPIView
from plane.bgtasks.github_pr_sync_task import dispatch_github_webhook
from plane.db.models import GithubProjectSync, Workspace
from plane.utils.github.webhook import verify_github_signature


@method_decorator(csrf_exempt, name="dispatch")
class GithubWebhookEndpoint(BaseAPIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        event_name = request.headers.get("X-GitHub-Event", "")
        signature = request.headers.get("X-Hub-Signature-256")

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

        if event_name in ("pull_request", "issue_comment"):
            dispatch_github_webhook(event_name, payload)

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
