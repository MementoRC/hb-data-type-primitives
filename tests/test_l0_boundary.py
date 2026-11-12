"""AST guard: data_type_primitives is an L0 leaf and must not reference hummingbot."""

import ast
from pathlib import Path

import pytest

_PKG_DIR = Path(__file__).resolve().parent.parent / "data_type_primitives"
_FILES = sorted(_PKG_DIR.rglob("*.py"))
_DYNAMIC_IMPORTERS = {"import_module", "__import__"}


def _is_hummingbot(name: str) -> bool:
    return name == "hummingbot" or name.startswith("hummingbot.")


def _callee_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _find_violations(tree: ast.AST) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.extend(
                f"line {node.lineno}: import {a.name}" for a in node.names if _is_hummingbot(a.name)
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and _is_hummingbot(node.module):
                violations.append(f"line {node.lineno}: from {node.module} import ...")
        elif (
            isinstance(node, ast.Call)
            and _callee_name(node.func) in _DYNAMIC_IMPORTERS
            and node.args
        ):
            first = node.args[0]
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and first.value.startswith("hummingbot")
            ):
                violations.append(f"line {node.lineno}: dynamic import of {first.value!r}")
    return violations


def test_package_files_discovered() -> None:
    assert _FILES, f"no python files found under {_PKG_DIR}"


@pytest.mark.unit
@pytest.mark.parametrize("path", _FILES, ids=lambda p: str(p.relative_to(_PKG_DIR)))
def test_no_hummingbot_references(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert _find_violations(tree) == []


@pytest.mark.unit
def test_guard_detects_violations() -> None:
    src = (
        "import hummingbot.core\n"
        "from hummingbot.x import y\n"
        "import importlib\n"
        "importlib.import_module('hummingbot.a')\n"
        "__import__('hummingbot')\n"
        "# import hummingbot\n"
        "'''from hummingbot import z'''\n"
        "importlib.import_module('os')\n"
    )
    assert len(_find_violations(ast.parse(src))) == 4
