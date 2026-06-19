# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand
from django.utils.html import strip_tags

from plane.db.models import BacklogCommentSync, IssueComment


class Command(BaseCommand):
    help = "Remove empty Plane comments imported from Backlog (legacy sync artifacts)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print how many comments would be deleted without deleting.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        qs = IssueComment.objects.filter(
            backlog_syncs__isnull=False,
            deleted_at__isnull=True,
        ).distinct()

        comment_ids: list = []
        for comment in qs.iterator():
            stripped = strip_tags(comment.comment_html or "").strip()
            if not stripped:
                comment_ids.append(comment.id)

        count = len(comment_ids)
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Would delete {count} empty Backlog-imported comment(s)."))
            return

        if not comment_ids:
            self.stdout.write(self.style.SUCCESS("No empty Backlog-imported comments to delete."))
            return

        BacklogCommentSync.objects.filter(comment_id__in=comment_ids).delete()
        # Hard delete via all_objects — avoids Celery soft-delete tasks (no broker required).
        _, deleted_map = IssueComment.all_objects.filter(id__in=comment_ids).delete()
        deleted = deleted_map.get(IssueComment._meta.label, count)

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} empty Backlog-imported comment(s)."))
