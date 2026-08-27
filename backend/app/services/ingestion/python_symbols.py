"""Symbol extraction for Python source using the standard library `ast` module.

Only Python gets real AST-based symbol extraction in this vertical slice;
other languages fall back to whole-file chunking without symbol rows (see
`docs/architecture.md` for the documented scope and how to extend this with
tree-sitter for additional languages).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedSymbol:
    kind: str  # "module" | "class" | "function" | "method"
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    docstring: str | None


def extract_python_symbols(source: str, *, module_qualified_prefix: str) -> list[ExtractedSymbol]:
    """Returns every module-level and class-level function/class definition in
    `source`. Returns an empty list (never raises) for unparseable source, so
    a single malformed file can't abort ingestion of an entire repository.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    symbols: list[ExtractedSymbol] = []

    def _end_line(node: ast.stmt) -> int:
        return int(node.end_lineno if node.end_lineno is not None else node.lineno)

    def _visit_class(node: ast.ClassDef, prefix: str) -> None:
        qualified = f"{prefix}.{node.name}" if prefix else node.name
        symbols.append(
            ExtractedSymbol(
                kind="class",
                name=node.name,
                qualified_name=qualified,
                start_line=node.lineno,
                end_line=_end_line(node),
                docstring=ast.get_docstring(node),
            )
        )
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(
                    ExtractedSymbol(
                        kind="method",
                        name=child.name,
                        qualified_name=f"{qualified}.{child.name}",
                        start_line=child.lineno,
                        end_line=_end_line(child),
                        docstring=ast.get_docstring(child),
                    )
                )

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            _visit_class(node, module_qualified_prefix)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified = f"{module_qualified_prefix}.{node.name}" if module_qualified_prefix else node.name
            symbols.append(
                ExtractedSymbol(
                    kind="function",
                    name=node.name,
                    qualified_name=qualified,
                    start_line=node.lineno,
                    end_line=_end_line(node),
                    docstring=ast.get_docstring(node),
                )
            )

    return symbols
