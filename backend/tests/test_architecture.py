"""Enforce the backend's layering so it doesn't drift again:

    routes/  ->  services/  ->  repositories/  ->  db.py
                    |
                    v
                 logic/  (pure functions)

- routes may not import repositories or db (no SQL in HTTP handlers);
- services may not import flask (they get the user id passed in);
- repositories may not import services, routes or flask;
- only repositories (and db.py itself) may call the SQL helpers;
- logic stays pure: no flask, no db.
"""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
SQL_HELPERS = {"query", "query_one", "execute"}


def imports(path):
    """Module names imported by a file (relative imports resolved inside app)."""
    tree = ast.parse(path.read_text())
    names, sql_calls = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: resolve against the file's package
                package = path.parent.relative_to(APP).parts[: len(path.parent.relative_to(APP).parts) - (node.level - 1)]
                base = ".".join(("app", *package, node.module or "")).rstrip(".")
            else:
                base = node.module or ""
            names.add(base)
            names.update(f"{base}.{a.name}" for a in node.names)
            if base == "app.db":
                sql_calls.update(a.name for a in node.names if a.name in SQL_HELPERS)
    return names, sql_calls


def files(layer):
    return sorted((APP / layer).glob("*.py"))


def layer_imports(layer):
    return [(f.name, *imports(f)) for f in files(layer)]


def bad(names, prefixes):
    return sorted(n for n in names if any(n == p or n.startswith(p + ".") for p in prefixes))


@pytest.mark.parametrize("name,names,sql", layer_imports("routes"))
def test_routes_do_not_touch_the_database(name, names, sql):
    assert not bad(names, ["app.repositories", "app.db", "pymysql"]), name
    assert not sql, name


@pytest.mark.parametrize("name,names,sql", layer_imports("services"))
def test_services_do_not_use_flask_or_sql(name, names, sql):
    assert not bad(names, ["flask", "app.routes"]), name
    assert not sql, f"{name} runs SQL itself; move it to a repository"


@pytest.mark.parametrize("name,names,sql", layer_imports("repositories"))
def test_repositories_are_only_data_access(name, names, sql):
    assert not bad(names, ["flask", "app.services", "app.routes", "app.logic"]), name


@pytest.mark.parametrize("name,names,sql", layer_imports("logic"))
def test_logic_is_pure(name, names, sql):
    assert not bad(names, ["flask", "app.db", "app.repositories", "app.services", "pymysql"]), name


def test_no_feature_modules_left_at_the_top_level():
    allowed = {"__init__.py", "config.py", "db.py", "errors.py"}
    assert {p.name for p in APP.glob("*.py")} == allowed
