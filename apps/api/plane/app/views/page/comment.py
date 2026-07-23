# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ProjectPagePermission
from plane.app.serializers import PageCommentSerializer
from plane.db.models import Page, PageComment

from ..base import BaseViewSet


class PageCommentViewSet(BaseViewSet):
    serializer_class = PageCommentSerializer
    model = PageComment
    permission_classes = [ProjectPagePermission]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
                page_id=self.kwargs.get("page_id"),
                page__project_pages__project_id=self.kwargs.get("project_id"),
                page__project_pages__deleted_at__isnull=True,
            )
            .select_related("actor", "page", "project", "workspace")
            .distinct()
        )

    def create(self, request, slug, project_id, page_id):
        page = Page.objects.filter(
            pk=page_id,
            workspace__slug=slug,
            project_pages__project_id=project_id,
            project_pages__deleted_at__isnull=True,
        ).first()
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PageCommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                project_id=project_id,
                page_id=page_id,
                actor=request.user,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
