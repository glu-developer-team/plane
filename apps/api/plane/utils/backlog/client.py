# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlencode, urljoin

import requests

BACKLOG_EXTERNAL_SOURCE = "backlog"
BACKLOG_PULL_DEBOUNCE_SECONDS = 5
BACKLOG_SKIP_PUSH_TTL = 60
BACKLOG_SKIP_PULL_NOTIFY_TTL = 60
BACKLOG_PUSH_PENDING_TTL = 120


class BacklogAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def is_backlog_no_change_error(exc: BacklogAPIError) -> bool:
    """Backlog returns code 7 when PATCH would not change any issue field."""
    if exc.status_code != 400:
        return False
    try:
        data = json.loads(exc.body or "{}")
        errors = data.get("errors") or []
        return any(error.get("code") == 7 for error in errors)
    except (json.JSONDecodeError, TypeError, AttributeError):
        return "No comment content" in (exc.body or "")


class BacklogClient:
    def __init__(self, space_host: str, api_key: str, timeout: int = 30):
        host = space_host.strip().rstrip("/")
        if host.startswith("http://") or host.startswith("https://"):
            base = host
        else:
            base = f"https://{host}"
        self.base_url = urljoin(base + "/", "api/v2/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        query = dict(params or {})
        query["apiKey"] = self.api_key
        url = urljoin(self.base_url, path.lstrip("/"))
        if query:
            url = f"{url}?{urlencode(query, doseq=True)}"

        for attempt in range(5):
            response = self._session.request(method, url, data=data, timeout=self.timeout)
            if response.status_code == 429:
                reset = response.headers.get("X-RateLimit-Reset")
                if reset and reset.isdigit():
                    wait = max(1, int(reset) - int(time.time()))
                else:
                    wait = min(60, 2**attempt)
                time.sleep(wait)
                continue
            if response.status_code >= 400:
                raise BacklogAPIError(
                    f"Backlog API {method} {path} failed ({response.status_code})",
                    status_code=response.status_code,
                    body=response.text,
                )
            if not response.text:
                return None
            return response.json()
        raise BacklogAPIError(f"Backlog API rate limited after retries: {method} {path}", status_code=429)

    def test_connection(self, project_key: str) -> dict[str, Any]:
        space = self._request("GET", "space")
        project = self._request("GET", f"projects/{project_key}")
        return {"space": space, "project": project}

    def get_project(self, project_key: str) -> dict[str, Any]:
        return self._request("GET", f"projects/{project_key}")

    def get_statuses(self, project_key: str) -> list[dict[str, Any]]:
        return self._request("GET", f"projects/{project_key}/statuses")

    def get_issue_types(self, project_key: str) -> list[dict[str, Any]]:
        return self._request("GET", f"projects/{project_key}/issueTypes")

    def get_priorities(self) -> list[dict[str, Any]]:
        return self._request("GET", "priorities")

    def list_issues(
        self,
        *,
        project_id: int,
        updated_since: str | None = None,
        offset: int = 0,
        count: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "projectId[]": project_id,
            "offset": offset,
            "count": count,
            "order": "asc",
            "sort": "updated",
        }
        if updated_since:
            params["updatedSince"] = updated_since
        return self._request("GET", "issues", params=params)

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        return self._request("GET", f"issues/{issue_key}")

    def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "issues", data=payload)

    def update_issue(self, issue_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"issues/{issue_key}", data=payload)

    def list_comments(
        self,
        issue_key: str,
        *,
        count: int = 100,
        order: str = "asc",
        min_id: int | None = None,
        max_id: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"count": count, "order": order}
        if min_id is not None:
            params["minId"] = min_id
        if max_id is not None:
            params["maxId"] = max_id
        return self._request("GET", f"issues/{issue_key}/comments", params=params)

    def list_all_comments(self, issue_key: str, count: int = 100) -> list[dict[str, Any]]:
        all_comments: list[dict[str, Any]] = []
        min_id: int | None = None
        while True:
            batch = self.list_comments(issue_key, count=count, order="asc", min_id=min_id)
            if not batch:
                break
            all_comments.extend(batch)
            if len(batch) < count:
                break
            last_id = batch[-1].get("id")
            if last_id is None:
                break
            min_id = int(last_id) + 1
        return all_comments

    def create_comment(self, issue_key: str, content: str) -> dict[str, Any]:
        return self._request("POST", f"issues/{issue_key}/comments", data={"content": content})

    def list_users(self) -> list[dict[str, Any]]:
        return self._request("GET", "users")


def normalize_space_host(space_host: str) -> str:
    host = space_host.strip().rstrip("/")
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    return host.split("/")[0]
