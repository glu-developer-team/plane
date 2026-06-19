# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import GithubProjectSync
from plane.utils.github.pr_sync import (
    DEFAULT_SYNC_MODE,
    SYNC_MODE_BIDIRECTIONAL,
    SYNC_MODE_GITHUB_TO_PLANE,
    get_sync_mode,
)


class GithubProjectSyncSerializer(serializers.ModelSerializer):
    enabled = serializers.SerializerMethodField()
    sync_mode = serializers.SerializerMethodField()

    class Meta:
        model = GithubProjectSync
        fields = [
            "id",
            "enabled",
            "repo_owner",
            "repo_name",
            "installation_id",
            "is_enabled",
            "sync_mode",
            "last_webhook_at",
            "last_sync_completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "last_webhook_at",
            "last_sync_completed_at",
            "created_at",
            "updated_at",
        ]

    def get_enabled(self, obj: GithubProjectSync) -> bool:
        return bool(obj.is_enabled and obj.repo_owner and obj.repo_name)

    def get_sync_mode(self, obj: GithubProjectSync) -> str:
        if obj is None:
            return DEFAULT_SYNC_MODE
        return get_sync_mode(obj)


class GithubProjectSyncWriteSerializer(GithubProjectSyncSerializer):
    sync_mode = serializers.ChoiceField(
        choices=[SYNC_MODE_GITHUB_TO_PLANE, SYNC_MODE_BIDIRECTIONAL],
        required=False,
        write_only=True,
    )

    class Meta(GithubProjectSyncSerializer.Meta):
        fields = GithubProjectSyncSerializer.Meta.fields + ["sync_mode"]

    def create(self, validated_data):
        return self._save_sync(validated_data)

    def update(self, instance, validated_data):
        return self._save_sync(validated_data, instance)

    def _save_sync(self, validated_data, instance=None):
        sync_mode = validated_data.pop("sync_mode", None)
        project = self.context["project"]
        workspace = self.context["workspace"]

        if instance is None:
            instance = GithubProjectSync(project=project, workspace=workspace)

        for field in ("repo_owner", "repo_name", "installation_id", "is_enabled"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        if sync_mode is not None:
            config = dict(instance.config or {})
            config["sync_mode"] = sync_mode
            instance.config = config

        instance.repo_owner = (instance.repo_owner or "").strip()
        instance.repo_name = (instance.repo_name or "").strip()

        if not instance.repo_owner or not instance.repo_name:
            raise serializers.ValidationError({"detail": "repo_owner and repo_name are required"})

        instance.save()
        return instance
