"""Resolve static Python dependencies for architecture boundary checks."""

import ast
from importlib.util import resolve_name

from tests.support.paths import REPO_ROOT


def imports(path):
    package = ".".join(path.relative_to(REPO_ROOT).parts[:-1])
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = resolve_name("." * node.level + module, package)
            yield module
            yield from (f"{module}.{alias.name}" for alias in node.names)
