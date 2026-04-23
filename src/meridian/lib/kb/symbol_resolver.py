"""Symbol resolution for source code files.

Uses Python's ast module to extract top-level symbol definitions.
Designed with a Protocol interface for extensibility to other languages.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Protocol


class SymbolResolver(Protocol):
    """Protocol for language-specific symbol resolution."""

    def can_handle(self, path: Path) -> bool:
        """Return True if this resolver can handle the given file."""
        ...

    def resolve(self, path: Path) -> list[tuple[str, int]]:
        """Extract symbols from a file.

        Returns:
            List of (symbol_name, line_number) tuples.
            Returns empty list on parse errors.
        """
        ...


class PythonSymbolResolver:
    """Python symbol resolver using stdlib ast."""

    def can_handle(self, path: Path) -> bool:
        """Return True for .py files."""
        return path.suffix == ".py"

    def resolve(self, path: Path) -> list[tuple[str, int]]:
        """Extract top-level function and class definitions from a Python file.

        Returns:
            List of (symbol_name, line_number) tuples.
            Returns empty list on syntax errors.
        """
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            return []
        except OSError:
            return []

        symbols: list[tuple[str, int]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                symbols.append((node.name, node.lineno))

        return symbols


__all__ = [
    "PythonSymbolResolver",
    "SymbolResolver",
]
