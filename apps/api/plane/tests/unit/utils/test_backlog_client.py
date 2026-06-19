# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from unittest.mock import patch

from plane.utils.backlog.client import BacklogAPIError, BacklogClient, is_backlog_no_change_error


@pytest.mark.unit
class TestBacklogNoChangeError:
    def test_detects_code_7(self):
        exc = BacklogAPIError(
            "failed",
            status_code=400,
            body='{"errors":[{"message":"No comment content.","code":7,"moreInfo":""}]}',
        )
        assert is_backlog_no_change_error(exc) is True

    def test_ignores_other_errors(self):
        exc = BacklogAPIError("failed", status_code=400, body='{"errors":[{"message":"bad","code":1}]}')
        assert is_backlog_no_change_error(exc) is False

    def test_ignores_non_400(self):
        exc = BacklogAPIError("failed", status_code=404, body='{"errors":[{"code":7}]}')
        assert is_backlog_no_change_error(exc) is False


@pytest.mark.unit
class TestBacklogClientComments:
    def test_list_comments_does_not_send_offset(self):
        client = BacklogClient("example.backlog.com", "test-key")
        with patch.object(client, "_request", return_value=[]) as mock_request:
            client.list_comments("PROJ-1", count=50, min_id=100)

        mock_request.assert_called_once_with(
            "GET",
            "issues/PROJ-1/comments",
            params={"count": 50, "order": "asc", "minId": 100},
        )

    def test_list_all_comments_paginates_with_min_id(self):
        client = BacklogClient("example.backlog.com", "test-key")
        batches = [
            [{"id": 1}, {"id": 2}],
            [{"id": 3}],
        ]

        with patch.object(client, "list_comments", side_effect=batches) as mock_list:
            comments = client.list_all_comments("PROJ-1", count=2)

        assert comments == [{"id": 1}, {"id": 2}, {"id": 3}]
        assert mock_list.call_count == 2
        assert mock_list.call_args_list[0].kwargs == {"count": 2, "order": "asc", "min_id": None}
        assert mock_list.call_args_list[1].kwargs == {"count": 2, "order": "asc", "min_id": 3}
