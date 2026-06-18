# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import connection


def get_all_parent_ids(page_id):
    """Return ancestor page ids from top-most parent to immediate parent."""
    query = """
    WITH RECURSIVE page_hierarchy AS (
        SELECT id, parent_id
        FROM pages
        WHERE id = %s AND deleted_at IS NULL

        UNION ALL

        SELECT p.id, p.parent_id
        FROM pages p
        JOIN page_hierarchy ph ON ph.parent_id = p.id
        WHERE p.deleted_at IS NULL
    )
    SELECT id
    FROM page_hierarchy;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, [page_id])
        ids = [str(row[0]) for row in cursor.fetchall()]

    return ids[::-1]
