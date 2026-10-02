"""Tenant registry (change 0004, 6.2, D4).

Platform-level table, owned by the migrator. The app role gets SELECT on
``id``, ``name`` and ``status`` only, and RLS (enabled, not forced) shows it only
the current tenant's row. Reversible.
"""

import uuid

import django.db.models.functions.text
import django.db.models.lookups
from django.db import migrations, models

from rms.tenancy.data.rls import EnableRegistryRLS, RestrictToColumnRead


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("rms_core", "0001_lock_down_migrations"),
    ]

    operations = [
        migrations.CreateModel(
            name="Restaurant",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("closed", "Closed"),
                        ],
                        db_default="active",
                        default="active",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "tenancy_restaurant",
                "base_manager_name": "objects",
                "default_manager_name": "objects",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("status__in", ["active", "suspended", "closed"])),
                        name="tenancy_restaurant_status_valid",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            django.db.models.lookups.Exact(
                                django.db.models.functions.text.Trim("name"), ""
                            ),
                            _negated=True,
                        ),
                        name="tenancy_restaurant_name_not_blank",
                    ),
                ],
            },
        ),
        RestrictToColumnRead("Restaurant", ["id", "name", "status"]),
        EnableRegistryRLS(),
    ]
