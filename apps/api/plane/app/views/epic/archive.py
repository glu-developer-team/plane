# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.app.views.issue.archive import IssueArchiveViewSet
from plane.db.models import Issue


class EpicArchiveViewSet(IssueArchiveViewSet):
    def get_queryset(self):
        return (
            Issue.objects.filter(type__is_epic=True)
            .filter(archived_at__isnull=False)
            .filter(project_id=self.kwargs.get("project_id"))
            .filter(workspace__slug=self.kwargs.get("slug"))
        )
