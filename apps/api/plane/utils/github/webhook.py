# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import hashlib
import hmac
import os

from plane.license.utils.instance_value import get_configuration_value


def get_webhook_secret() -> str:
    (secret,) = get_configuration_value([
        {"key": "GITHUB_WEBHOOK_SECRET", "default": os.environ.get("GITHUB_WEBHOOK_SECRET", "")},
    ])
    return secret or ""


def verify_github_signature(payload: bytes, signature_header: str | None) -> bool:
    secret = get_webhook_secret()
    if not secret:
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)
