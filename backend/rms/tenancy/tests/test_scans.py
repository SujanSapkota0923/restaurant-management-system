"""Source scans that keep the tenancy controls closed (C-3, C-5(b), C-9; N-02, N-03, N-16).

Each scan has a self-test with a sample that must be flagged. Samples are built
by concatenation so that this file itself never matches a pattern.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

import config
import rms
from rms.tenancy.api.views import TenantAPIView

BACKEND = Path(__file__).resolve().parents[3]
REPO = BACKEND.parent


def backend_python_files() -> Iterator[tuple[str, str]]:
    """(path relative to backend/, text) for every backend .py file, hidden dirs excluded."""
    for path in sorted(BACKEND.rglob("*.py")):
        relative = path.relative_to(BACKEND)
        if any(part.startswith(".") for part in relative.parts):
            continue
        yield relative.as_posix(), path.read_text(encoding="utf-8")


def script_files() -> Iterator[tuple[str, str]]:
    for path in sorted((REPO / "scripts").rglob("*")):
        if path.is_file():
            yield (
                "scripts/" + path.relative_to(REPO / "scripts").as_posix(),
                path.read_text(encoding="utf-8", errors="replace"),
            )


def is_test_path(relative: str) -> bool:
    parts = relative.split("/")
    return "tests" in parts or relative == "conftest.py"


def matches(patterns: Iterable[re.Pattern[str]], text: str) -> list[str]:
    return [p.pattern for p in patterns if p.search(text)]


# --- C-3: only the entry point writes app.* settings ------------------------------------

CONTEXT_WRITE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"set_config\s*\(",
        r"\bset\s+(local\s+|session\s+)?app\.",
        r"\balter\s+(role|user|database)\b[^;]*\bset\s+app\.",
        r"-c\s*app\.",
    )
]
CONTEXT_WRITE_ALLOWED = frozenset(
    {
        "rms/tenancy/data/context.py",
        "rms/tenancy/data/rls.py",
        # The 0003 rollback probe writes its own rms.rollback_probe setting only.
        "rms/core/tests/views.py",
    }
)


def context_write_violations(files: Iterable[tuple[str, str]]) -> list[str]:
    return [
        f"{name}: {pattern}"
        for name, text in files
        if name not in CONTEXT_WRITE_ALLOWED
        for pattern in matches(CONTEXT_WRITE_PATTERNS, text)
    ]


def test_only_the_entry_point_writes_context_settings() -> None:
    files = [*backend_python_files(), *script_files()]
    assert len(files) > 50  # the scan really ran over the tree
    assert context_write_violations(files) == []


def test_rollback_probe_writes_no_app_setting() -> None:
    text = (BACKEND / "rms/core/tests/views.py").read_text(encoding="utf-8")
    assert "'app." not in text
    assert '"app.' not in text


@pytest.mark.parametrize(
    ("index", "sample"),
    [
        (0, "SELECT " + "set_" + "config('app.tenant_id', '1', true)"),
        (0, "select SET_" + "CONFIG ('app.user_id', '1', false)"),
        (1, "SET " + "LOCAL app.tenant_id = '1'"),
        (1, "set " + "app.user_id TO 'x'"),
        (1, "SET " + "SESSION app.tenant_id = '1'"),
        (2, "ALTER ROLE rms_app SET " + "app.tenant_id = 'x'"),
        (2, "alter database rms set " + "app.user_id = 'x'"),
        (3, "options='-c " + "app.tenant_id=1'"),
    ],
)
def test_context_write_scan_self_test(index: int, sample: str) -> None:
    assert CONTEXT_WRITE_PATTERNS[index].search(sample)
    assert context_write_violations([("rms/feature/services.py", sample)])


def test_context_write_scan_ignores_reads() -> None:
    assert not context_write_violations(
        [("rms/feature/services.py", "SELECT current_setting('app.tenant_id', true)")]
    )


# --- C-9(a): no raw SQL paths in application code -------------------------------------

APP_SQL_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\.raw\(",
        r"\.extra\(",
        r"\bRawSQL\(",
        r"\bQuerySet\(",
        r"\bconnection\.cursor\(",
        r"\bconnections\[[^\]]*\]\.cursor\(",
    )
]


def app_sql_allowed(name: str) -> bool:
    return (
        name == "rms/core/health.py"
        or re.fullmatch(r"rms/tenancy/data/[a-z_]+\.py", name) is not None
    )


def app_sql_violations(files: Iterable[tuple[str, str]]) -> list[str]:
    return [
        f"{name}: {pattern}"
        for name, text in files
        if name.startswith("rms/") and not is_test_path(name) and not app_sql_allowed(name)
        for pattern in matches(APP_SQL_PATTERNS, text)
    ]


def test_no_raw_sql_outside_the_data_layer() -> None:
    assert app_sql_violations(backend_python_files()) == []


@pytest.mark.parametrize(
    "sample",
    [
        "Order.objects" + ".raw('SELECT 1')",
        "Order.objects" + ".extra(where=['1=1'])",
        "Raw" + "SQL('SELECT 1', [])",
        "Query" + "Set(model=Order)",
        "connection" + ".cursor()",
        'connections["default"]' + ".cursor()",
    ],
)
def test_raw_sql_scan_self_test(sample: str) -> None:
    assert app_sql_violations([("rms/menu/services.py", sample)])
    assert not app_sql_violations([("rms/menu/tests/test_x.py", sample)])


# --- C-9(b): the migrator alias and factories stay in tests ------------------------------

MIGRATOR_PATTERN = re.compile(
    r"""(\.using\(|connections\[|db_manager\(|database\s*=)\s*["']migrator["']"""
)
FACTORY_IMPORT = re.compile(r"^\s*(import\s+factory\b|from\s+factory\b)", re.MULTILINE)


def test_only_harness_code_uses_the_migrator_alias_or_factories() -> None:
    assert migrator_violations(backend_python_files()) == []


def migrator_violations(files: Iterable[tuple[str, str]]) -> list[str]:
    return [
        f"{name}: {pattern.pattern}"
        for name, text in files
        if not is_test_path(name)
        for pattern in (MIGRATOR_PATTERN, FACTORY_IMPORT)
        if pattern.search(text)
    ]


@pytest.mark.parametrize(
    "sample",
    [
        "Restaurant.objects.using(" + "'migrator')",
        'connections["' + 'migrator"].cursor()',
        "Restaurant.objects.db_manager(" + '"migrator")',
        "call(database=" + '"migrator")',
        "import " + "factory",
        "from " + "factory.django import DjangoModelFactory",
    ],
)
def test_migrator_scan_self_test(sample: str) -> None:
    assert migrator_violations([("rms/menu/services.py", sample)])
    assert migrator_violations([("config/urls.py", sample)])
    assert not migrator_violations([("rms/menu/tests/factories.py", sample)])
    assert not migrator_violations([("config/tests/roundtrip.py", sample)])


# --- C-5(b): TenantAPIView's closed methods are never overridden outside tests -----------

FORBIDDEN_OVERRIDES = frozenset(
    {"dispatch", "initial", "resolve_active_tenant", "check_principal", "as_view"}
)
# Module prefixes allowed to override (reviewed). Empty in 0004; 0005 adds rms.access.api.
ALLOWED_OVERRIDES: frozenset[str] = frozenset()
TENANT_VIEW_MODULE = "rms/tenancy/api/views.py"
_NOT_IMPORTED = ("config.settings", "config.wsgi")


def import_all_modules() -> None:
    for package in (rms, config):
        for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            if module.name.startswith(_NOT_IMPORTED):
                continue  # settings modules validate the environment on import
            importlib.import_module(module.name)


def all_subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for sub in cls.__subclasses__():
        found |= {sub, *all_subclasses(sub)}
    return found


def _module_allowed(module: str) -> bool:
    return ".tests." in f".{module}." or module.startswith(tuple(ALLOWED_OVERRIDES))


def override_violations(classes: Iterable[type]) -> list[str]:
    return sorted(
        f"{cls.__module__}.{cls.__qualname__}: overrides {', '.join(sorted(defined))}"
        for cls in classes
        if not _module_allowed(cls.__module__)
        and (defined := FORBIDDEN_OVERRIDES.intersection(vars(cls)))
    )


def ast_override_violations(files: Iterable[tuple[str, str]]) -> list[str]:
    violations: list[str] = []
    for name, text in files:
        if is_test_path(name) or name == TENANT_VIEW_MODULE:
            continue
        if not (name.startswith("rms/") or name.startswith("config/")):
            continue
        module = name.removesuffix(".py").replace("/", ".")
        if _module_allowed(module):
            continue
        for node in ast.walk(ast.parse(text, filename=name)):
            if isinstance(node, ast.ClassDef):
                methods = {
                    item.name
                    for item in node.body
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                }
                for method in sorted(methods & FORBIDDEN_OVERRIDES):
                    violations.append(f"{name}: class {node.name} defines {method}")
    return violations


def test_no_tenant_view_overrides_the_closed_methods() -> None:
    import_all_modules()
    subclasses = all_subclasses(TenantAPIView)
    # Non-vacuous: the probe views were found, and one of them does override.
    names = {cls.__qualname__ for cls in subclasses}
    assert {"ProbeClosedView", "ProbeWriteView"} <= names
    assert override_violations(subclasses) == []
    assert ast_override_violations(backend_python_files()) == []


def test_override_check_flags_a_non_test_subclass() -> None:
    evil = type(
        "EvilView",
        (TenantAPIView,),
        {"__module__": "rms.evil.api", "check_principal": lambda self, request, tenant: None},
    )
    sneaky = type("SneakyView", (TenantAPIView,), {"__module__": "rms.evil.api", "initial": None})
    test_only = type(
        "TestView",
        (TenantAPIView,),
        {"__module__": "rms.evil.tests.views", "check_principal": lambda self, r, t: None},
    )
    assert override_violations([evil, sneaky, test_only]) == [
        "rms.evil.api.EvilView: overrides check_principal",
        "rms.evil.api.SneakyView: overrides initial",
    ]


def test_ast_check_flags_never_imported_modules() -> None:
    source = (
        "class Open(TenantAPIView):\n"
        "    def check_" + "principal(self, request, tenant):\n"
        "        return None\n"
        "    def dispatch(self, request, *args, **kwargs):\n"
        "        return None\n"
    )
    assert ast_override_violations([("rms/evil/api/views.py", source)]) == [
        "rms/evil/api/views.py: class Open defines check_principal",
        "rms/evil/api/views.py: class Open defines dispatch",
    ]
    assert ast_override_violations([("rms/evil/tests/views.py", source)]) == []
