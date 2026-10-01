"""Session-level test DB setup (change 0003, 6.5, SC-24, SC-25).

``django_db_setup`` is overridden so that both aliases are always set up.
Django applies ``TEST["MIRROR"]`` even when the mirror target was not set up
(``django/test/utils.py`` ``setup_databases``, verified on 5.2.17); pytest-django
would only set up the aliases tests declare (``default``), leaving ``default``
pointed at the dev DB. Tests declare only ``default``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.db import connections
from django.test.utils import setup_databases, teardown_databases
from pytest_django.plugin import DjangoDbBlocker

from config.tests.db_guards import (
    SETUP_ALIASES,
    database_guard_failures,
    lock_down_test_database,
)


@pytest.fixture(scope="session")
def django_db_setup(
    request: pytest.FixtureRequest,
    django_test_environment: None,
    django_db_blocker: DjangoDbBlocker,
) -> Iterator[None]:
    verbosity = request.config.option.verbose
    with django_db_blocker.unblock():
        db_cfg = setup_databases(
            verbosity=verbosity,
            interactive=False,
            # Runtime only tests membership; dict.fromkeys also satisfies the stub's Mapping.
            aliases=dict.fromkeys(SETUP_ALIASES),
        )
        lock_down_test_database()
    yield
    with django_db_blocker.unblock():
        # DROP DATABASE fails while any alias (mirror included) is still connected.
        for connection in connections.all():
            connection.close()
        teardown_databases(db_cfg, verbosity=verbosity)


@pytest.fixture(scope="session", autouse=True)
def _database_guards(django_db_setup: None, django_db_blocker: DjangoDbBlocker) -> None:
    """Abort the whole run, before any test, if the DB setup is unsafe (SC-25b)."""
    with django_db_blocker.unblock():
        failures = database_guard_failures()
    if failures:
        pytest.exit("test database guard failed: " + "; ".join(failures), returncode=3)
