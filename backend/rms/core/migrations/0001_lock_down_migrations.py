"""Make ``django_migrations`` read-only for the app role (change 0004, 6.7, T4-14).

The table does not exist when the DB is bootstrapped, so this cannot live in
``scripts/db/bootstrap.sh``. Reversible: the reverse restores the default
privileges. ``tenancy/0001`` depends on this migration.
"""

from django.db import migrations

from rms.tenancy.data.rls import LockDownMigrationTable


class Migration(migrations.Migration):
    dependencies = []

    operations = [LockDownMigrationTable()]
