# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0127_page_comment"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pagecomment",
            name="selected_text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="pagecomment",
            name="is_inline",
            field=models.BooleanField(default=False),
        ),
    ]
