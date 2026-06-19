# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

GITHUB_PR_EXTERNAL_SOURCE = "github_pr"

SYNC_MODE_GITHUB_TO_PLANE = "github_to_plane"
SYNC_MODE_BIDIRECTIONAL = "bidirectional"
DEFAULT_SYNC_MODE = SYNC_MODE_BIDIRECTIONAL


def get_sync_mode(sync) -> str:
    mode = (sync.config or {}).get("sync_mode")
    if mode in (SYNC_MODE_GITHUB_TO_PLANE, SYNC_MODE_BIDIRECTIONAL):
        return mode
    return DEFAULT_SYNC_MODE


def is_github_push_enabled(sync) -> bool:
    return get_sync_mode(sync) == SYNC_MODE_BIDIRECTIONAL


def get_enabled_github_project_sync(project_id):
    from plane.db.models import GithubProjectSync

    sync = GithubProjectSync.objects.filter(
        project_id=project_id,
        deleted_at__isnull=True,
        is_enabled=True,
    ).first()
    if not sync or not sync.repo_owner or not sync.repo_name:
        return None
    return sync
