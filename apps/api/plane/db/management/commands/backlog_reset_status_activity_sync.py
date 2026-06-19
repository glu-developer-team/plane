# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand

from plane.db.models import BacklogActivitySync


class Command(BaseCommand):
    help = (
        "Clear Backlog status activity dedup markers so the next issue pull can "
        "create IssueActivity rows for status changeLog entries."
    )

    def handle(self, *args, **options):
        deleted = BacklogActivitySync.objects.filter(change_field="status").delete()
        if isinstance(deleted, tuple):
            deleted = deleted[0]
        self.stdout.write(
            self.style.SUCCESS(
                f"Cleared {deleted} status activity sync marker(s). "
                "Re-open issues in Plane (or wait for pull sync) to backfill activities."
            )
        )
