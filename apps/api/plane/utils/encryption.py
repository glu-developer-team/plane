# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_value(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str) -> str:
    if not value:
        return ""
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def mask_api_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"
