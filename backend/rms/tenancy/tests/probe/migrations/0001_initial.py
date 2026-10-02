"""Probe tenant tables (test settings only, change 0004 D6).

Shows the required pattern: each tenant table's CreateModel is followed, in the
same migration, by ``enable_tenant_rls``, ``restrict_tenant_key_update`` and a
``composite_tenant_fk`` per tenant FK.
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models

from rms.tenancy.data.rls import composite_tenant_fk, enable_tenant_rls, restrict_tenant_key_update


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProbeParent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("code", models.CharField(max_length=32)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        db_index=False,
                        editable=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="tenancy.restaurant",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "base_manager_name": "objects",
                "default_manager_name": "objects",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "id"), name="tenancy_probe_probeparent_tenant_id_uniq"
                    ),
                    models.UniqueConstraint(
                        fields=("tenant", "code"), name="probe_parent_tenant_code_uniq"
                    ),
                ],
            },
        ),
        enable_tenant_rls("tenancy_probe_probeparent"),
        restrict_tenant_key_update("ProbeParent", ["code"]),
        migrations.CreateModel(
            name="ProbeChild",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("label", models.CharField(default="child", max_length=32)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        db_index=False,
                        editable=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="tenancy.restaurant",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        db_constraint=False,
                        db_index=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="tenancy_probe.probeparent",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "base_manager_name": "objects",
                "default_manager_name": "objects",
                "indexes": [
                    models.Index(fields=["tenant", "parent"], name="probe_child_tenant_parent_idx")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "id"), name="tenancy_probe_probechild_tenant_id_uniq"
                    ),
                ],
            },
        ),
        enable_tenant_rls("tenancy_probe_probechild"),
        restrict_tenant_key_update("ProbeChild", ["label", "parent"]),
        composite_tenant_fk("tenancy_probe_probechild", "parent_id", "tenancy_probe_probeparent"),
    ]
