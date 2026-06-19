# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import BacklogProjectSync
from plane.utils.backlog.client import BacklogAPIError, BacklogClient, normalize_space_host
from plane.utils.backlog.locale_map import DEFAULT_JA_TO_EN, looks_like_partial_translation, resolve_status_english, translate_status_name
from plane.utils.backlog.sync import DEFAULT_SYNC_MODE, SYNC_MODE_BIDIRECTIONAL, SYNC_MODE_BACKLOG_TO_PLANE, get_sync_mode
from plane.utils.encryption import decrypt_value, encrypt_value, mask_api_key


class BacklogLocaleEntrySerializer(serializers.Serializer):
    japanese = serializers.CharField(max_length=500, required=False, allow_blank=True)
    english = serializers.CharField(max_length=500)


class BacklogStatusLocaleWriteSerializer(serializers.Serializer):
    backlog_status_id = serializers.CharField(max_length=64)
    english = serializers.CharField(max_length=500)


class BacklogProjectSyncSerializer(serializers.ModelSerializer):
    enabled = serializers.SerializerMethodField()
    api_key_set = serializers.SerializerMethodField()
    api_key_masked = serializers.SerializerMethodField()
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    default_locale_entries = serializers.SerializerMethodField()
    custom_locale_entries = serializers.SerializerMethodField()
    status_locale_entries = serializers.SerializerMethodField()
    sync_mode = serializers.SerializerMethodField()

    class Meta:
        model = BacklogProjectSync
        fields = [
            "id",
            "enabled",
            "space_host",
            "backlog_project_key",
            "backlog_project_id",
            "is_enabled",
            "sync_mode",
            "api_key_set",
            "api_key_masked",
            "api_key",
            "last_pulled_at",
            "last_sync_completed_at",
            "default_locale_entries",
            "custom_locale_entries",
            "status_locale_entries",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "backlog_project_id",
            "last_pulled_at",
            "last_sync_completed_at",
            "created_at",
            "updated_at",
        ]

    def get_enabled(self, obj: BacklogProjectSync) -> bool:
        return bool(
            obj.is_enabled and obj.space_host and obj.api_key_encrypted and obj.backlog_project_key
        )

    def get_api_key_set(self, obj: BacklogProjectSync) -> bool:
        return bool(obj.api_key_encrypted)

    def get_api_key_masked(self, obj: BacklogProjectSync) -> str:
        if not obj.api_key_encrypted:
            return ""
        try:
            return mask_api_key(decrypt_value(obj.api_key_encrypted))
        except Exception:
            return "****"

    def validate_space_host(self, value: str) -> str:
        return normalize_space_host(value)

    def get_sync_mode(self, obj: BacklogProjectSync) -> str:
        if obj is None:
            return DEFAULT_SYNC_MODE
        return get_sync_mode(obj)

    def get_default_locale_entries(self, obj: BacklogProjectSync) -> list[dict[str, str]]:
        return [{"japanese": ja, "english": en} for ja, en in DEFAULT_JA_TO_EN.items()]

    def get_custom_locale_entries(self, obj: BacklogProjectSync) -> list[dict[str, str]]:
        locale_map = (obj.config or {}).get("locale_map") or {}
        ja_to_en = locale_map.get("ja_to_en") or {}
        return [{"japanese": ja, "english": en} for ja, en in ja_to_en.items()]

    def get_status_locale_entries(self, obj: BacklogProjectSync) -> list[dict[str, str]]:
        config = obj.config or {}
        labels = config.get("backlog_status_labels") or {}
        order = config.get("backlog_status_order") or list(labels.keys())
        entries: list[dict[str, str]] = []
        for status_id in order:
            label = labels.get(status_id)
            if not label:
                continue
            ja_name = label.get("ja") or ""
            entries.append(
                {
                    "backlog_status_id": status_id,
                    "japanese": ja_name,
                    "english": resolve_status_english(obj, ja_name, status_id=status_id),
                }
            )
        return entries


class BacklogProjectSyncWriteSerializer(BacklogProjectSyncSerializer):
    test_connection = serializers.BooleanField(default=True, write_only=True)
    sync_mode = serializers.ChoiceField(
        choices=[SYNC_MODE_BACKLOG_TO_PLANE, SYNC_MODE_BIDIRECTIONAL],
        required=False,
        write_only=True,
    )
    custom_locale_entries = serializers.ListField(
        child=BacklogLocaleEntrySerializer(),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    status_locale_entries = serializers.ListField(
        child=BacklogStatusLocaleWriteSerializer(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta(BacklogProjectSyncSerializer.Meta):
        fields = BacklogProjectSyncSerializer.Meta.fields + ["test_connection"]

    def create(self, validated_data):
        return self._save_sync(validated_data)

    def update(self, instance, validated_data):
        return self._save_sync(validated_data, instance)

    def _save_sync(self, validated_data, instance=None):
        from plane.db.models import State

        api_key = validated_data.pop("api_key", None)
        test_connection = validated_data.pop("test_connection", True)
        sync_mode = validated_data.pop("sync_mode", None)
        custom_locale_entries = validated_data.pop("custom_locale_entries", None)
        status_locale_entries = validated_data.pop("status_locale_entries", None)
        validated_data["space_host"] = normalize_space_host(validated_data["space_host"])

        project = self.context["project"]
        workspace = self.context["workspace"]

        if instance is None:
            instance = BacklogProjectSync(project=project, workspace=workspace)

        for field in ("space_host", "backlog_project_key", "is_enabled"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        if sync_mode is not None:
            config = dict(instance.config or {})
            config["sync_mode"] = sync_mode
            instance.config = config

        if custom_locale_entries is not None:
            config = dict(instance.config or {})
            ja_to_en: dict[str, str] = {}
            en_to_ja: dict[str, str] = {}
            for entry in custom_locale_entries:
                japanese = (entry.get("japanese") or "").strip()
                english = (entry.get("english") or "").strip()
                if not japanese or not english:
                    continue
                if japanese in DEFAULT_JA_TO_EN and english == DEFAULT_JA_TO_EN[japanese]:
                    continue
                ja_to_en[japanese] = english
                en_to_ja[english] = japanese
            locale_map = dict(config.get("locale_map") or {})
            locale_map["ja_to_en"] = ja_to_en
            locale_map["en_to_ja"] = en_to_ja
            config["locale_map"] = locale_map
            instance.config = config

        if status_locale_entries is not None:
            config = dict(instance.config or {})
            overrides = dict(config.get("status_en_overrides") or {})
            labels = dict(config.get("backlog_status_labels") or {})
            status_map = config.get("status_map") or {}
            for entry in status_locale_entries:
                status_id = str(entry.get("backlog_status_id") or "").strip()
                english = (entry.get("english") or "").strip()
                if not status_id or not english or looks_like_partial_translation(english):
                    continue
                ja_name = (labels.get(status_id) or {}).get("ja") or ""
                auto_en = translate_status_name(instance, ja_name)
                if english == auto_en:
                    overrides.pop(status_id, None)
                else:
                    overrides[status_id] = english
                if status_id in labels:
                    labels[status_id] = {**labels[status_id], "en": english}
                state_id = status_map.get(status_id)
                if state_id:
                    State.objects.filter(id=state_id, project_id=instance.project_id).update(name=english[:255])
            config["status_en_overrides"] = overrides
            config["backlog_status_labels"] = labels
            instance.config = config

        if api_key:
            instance.api_key_encrypted = encrypt_value(api_key)
        elif not instance.api_key_encrypted:
            raise serializers.ValidationError({"api_key": "API key is required"})

        if test_connection:
            client = BacklogClient(instance.space_host, decrypt_value(instance.api_key_encrypted))
            try:
                result = client.test_connection(instance.backlog_project_key)
                instance.backlog_project_id = result["project"]["id"]
            except BacklogAPIError as exc:
                raise serializers.ValidationError({"detail": str(exc), "body": exc.body}) from exc

        instance.save()

        if instance.is_enabled and instance.backlog_project_key and instance.api_key_encrypted:
            from plane.utils.backlog.sync import sync_backlog_statuses_to_plane

            client = BacklogClient(instance.space_host, decrypt_value(instance.api_key_encrypted))
            sync_backlog_statuses_to_plane(instance, client)

        return instance


class BacklogPullRequestSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=["project", "issue"])
    issue_id = serializers.UUIDField(required=False, allow_null=True)


class BacklogSyncJobStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    scope = serializers.CharField()
    issue_id = serializers.UUIDField(allow_null=True)
    stats = serializers.JSONField()
    error = serializers.CharField()
    deduplicated = serializers.BooleanField(required=False)


class BacklogSyncStateSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    last_sync_completed_at = serializers.DateTimeField(allow_null=True)
    last_pull_stats = serializers.JSONField(required=False)
    active_job = serializers.DictField(allow_null=True)
