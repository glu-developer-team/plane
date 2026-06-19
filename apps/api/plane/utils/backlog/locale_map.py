# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import re
from typing import Literal

from plane.db.models import BacklogProjectSync

# Default Backlog (JA) → Plane (EN) labels. Override per project via sync.config["locale_map"].
DEFAULT_JA_TO_EN: dict[str, str] = {
    # Workflow statuses
    "未対応": "Open",
    "未着手": "Todo",
    "処理中": "In Progress",
    "対応中": "In Progress",
    "作業中": "In Progress",
    "処理済み": "Resolved",
    "完了": "Closed",
    "クローズ": "Closed",
    "確認待ち": "Waiting for Review",
    "レビュー中": "In Review",
    "保留": "On Hold",
    "キャンセル": "Cancelled",
    # Priority
    "高": "High",
    "中": "Medium",
    "低": "Low",
    # Common issue phrases
    "要望": "Request",
    "不具合": "Bug",
    "タスク": "Task",
    "課題": "Issue",
    "新規": "New",
    "更新": "Update",
    "修正": "Fix",
    "調査": "Investigation",
    "設計": "Design",
    "実装": "Implementation",
    "テスト": "Test",
    "リリース": "Release",
}

TranslateDirection = Literal["to_plane", "to_backlog"]


def _locale_config(sync: BacklogProjectSync) -> dict:
    config = sync.config or {}
    return config.get("locale_map") or {}


def ja_to_en_map(sync: BacklogProjectSync) -> dict[str, str]:
    custom = _locale_config(sync).get("ja_to_en") or {}
    return {**DEFAULT_JA_TO_EN, **custom}


def en_to_ja_map(sync: BacklogProjectSync) -> dict[str, str]:
    custom = _locale_config(sync).get("en_to_ja") or {}
    derived = {english: japanese for japanese, english in ja_to_en_map(sync).items()}
    return {**derived, **custom}


def _apply_ja_to_en(text: str, mapping: dict[str, str]) -> str:
    result = text
    for source, target in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if source in result:
            result = result.replace(source, target)
    return result


def translate_text(
    sync: BacklogProjectSync,
    text: str | None,
    *,
    direction: TranslateDirection,
    allow_substring: bool = True,
) -> str:
    if not text:
        return ""

    mapping = ja_to_en_map(sync) if direction == "to_plane" else en_to_ja_map(sync)
    stripped = text.strip()
    if not stripped:
        return text

    if stripped in mapping:
        if stripped == text:
            return mapping[stripped]
        leading = text[: len(text) - len(text.lstrip())]
        trailing = text[len(text.rstrip()) :]
        return f"{leading}{mapping[stripped]}{trailing}"

    if direction == "to_plane" and allow_substring:
        return _apply_ja_to_en(text, mapping)
    return text


def translate_status_name(sync: BacklogProjectSync, ja_name: str | None) -> str:
    """Map Backlog status labels using whole-string matches only."""
    if not ja_name:
        return ""
    stripped = ja_name.strip()
    if not stripped:
        return ja_name
    return ja_to_en_map(sync).get(stripped, stripped)


def looks_like_partial_translation(text: str) -> bool:
    """True when text mixes Japanese script with Latin letters (broken substring translation)."""
    has_ja = bool(re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]", text))
    has_en = bool(re.search(r"[A-Za-z]", text))
    return has_ja and has_en


def resolve_status_english(sync: BacklogProjectSync, ja_name: str, *, status_id: str | None = None) -> str:
    config = sync.config or {}
    overrides = config.get("status_en_overrides") or {}
    auto_en = translate_status_name(sync, ja_name)

    if status_id:
        override = overrides.get(status_id)
        if override and not looks_like_partial_translation(override):
            return override

    return auto_en
