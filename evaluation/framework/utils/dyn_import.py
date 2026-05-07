"""Dynamic import helpers for Rollouts/Judges that adapt external repos.

Typical use: an external benchmark ships a Python module at a known path.
We want to `import` it at setup time, wire up its entry-point callable, and
let the Rollout/Judge invoke it in-process.

This avoids per-benchmark boilerplate for sys.path manipulation and module
reloading.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from types import ModuleType


def add_to_syspath(path: str) -> None:
    """Idempotently prepend `path` to sys.path."""
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise FileNotFoundError(f"sys.path candidate does not exist: {path}")
    if path not in sys.path:
        sys.path.insert(0, path)


def import_from_path(module_name: str, file_path: str) -> ModuleType:
    """Load a Python file as `module_name` without registering it globally
    (except under that name in sys.modules, so relative imports inside the
    file still work)."""
    file_path = os.path.abspath(file_path)
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def import_from_repo(repo_root: str, dotted: str) -> ModuleType:
    """Add `repo_root` to sys.path, then import `dotted` as a regular module."""
    add_to_syspath(repo_root)
    return importlib.import_module(dotted)


def resolve_attr(module: ModuleType, dotted_attr: str):
    """Resolve `a.b.c` against an imported module."""
    obj = module
    for part in dotted_attr.split("."):
        obj = getattr(obj, part)
    return obj
