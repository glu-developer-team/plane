# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import os
import time

import jwt
import requests
from django.core.cache import cache

from plane.license.utils.instance_value import get_configuration_value


class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _github_app_config() -> tuple[str, str]:
    app_id, private_key = get_configuration_value([
        {"key": "GITHUB_APP_ID", "default": os.environ.get("GITHUB_APP_ID", "")},
        {"key": "GITHUB_APP_PRIVATE_KEY", "default": os.environ.get("GITHUB_APP_PRIVATE_KEY", "")},
    ])
    if not app_id or not private_key:
        raise GitHubAPIError("GitHub App is not configured (GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY)")
    private_key = private_key.replace("\\n", "\n")
    return str(app_id), private_key


def create_app_jwt() -> str:
    app_id, private_key = _github_app_config()
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def get_installation_access_token(installation_id: int) -> str:
    cache_key = f"github_installation_token:{installation_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    app_jwt = create_app_jwt()
    response = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise GitHubAPIError(
            f"Failed to get installation token: HTTP {response.status_code}",
            status_code=response.status_code,
            body=response.text,
        )
    data = response.json()
    token = data.get("token")
    if not token:
        raise GitHubAPIError("GitHub installation token response missing token field")

    expires_at = data.get("expires_at")
    timeout = 3000
    if expires_at:
        try:
            from django.utils.dateparse import parse_datetime

            expires_dt = parse_datetime(expires_at)
            if expires_dt:
                timeout = max(60, int((expires_dt.timestamp() - time.time()) - 120))
        except Exception:
            pass
    cache.set(cache_key, token, timeout=timeout)
    return token


class GitHubClient:
    def __init__(self, installation_id: int):
        self.installation_id = installation_id

    def _headers(self) -> dict[str, str]:
        token = get_installation_access_token(self.installation_id)
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"https://api.github.com{path}"
        response = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        if response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub API error: HTTP {response.status_code}",
                status_code=response.status_code,
                body=response.text,
            )
        return response

    def post_issue_comment(self, owner: str, repo: str, issue_number: int, body: str) -> dict:
        response = self.request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        return response.json()

    def list_pulls(self, owner: str, repo: str, *, state: str = "open", per_page: int = 100) -> list[dict]:
        pulls: list[dict] = []
        page = 1
        while True:
            response = self.request(
                "GET",
                f"/repos/{owner}/{repo}/pulls",
                params={"state": state, "per_page": per_page, "page": page},
            )
            batch = response.json()
            if not batch:
                break
            pulls.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        return pulls
