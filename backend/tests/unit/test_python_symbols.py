from __future__ import annotations

from app.services.ingestion.python_symbols import extract_python_symbols

SAMPLE = '''"""Module docstring."""


def top_level_function(x: int) -> int:
    """Doubles x."""
    return x * 2


class Widget:
    """A widget."""

    def render(self) -> str:
        return "<widget/>"

    async def render_async(self) -> str:
        return "<widget/>"


async def top_level_async() -> None:
    ...
'''


def test_extracts_module_level_function():
    symbols = extract_python_symbols(SAMPLE, module_qualified_prefix="pkg.mod")
    fn = next(s for s in symbols if s.name == "top_level_function")
    assert fn.kind == "function"
    assert fn.qualified_name == "pkg.mod.top_level_function"
    assert fn.start_line == 4
    assert fn.docstring == "Doubles x."


def test_extracts_class_and_methods():
    symbols = extract_python_symbols(SAMPLE, module_qualified_prefix="pkg.mod")
    cls = next(s for s in symbols if s.name == "Widget")
    assert cls.kind == "class"
    assert cls.qualified_name == "pkg.mod.Widget"

    method = next(s for s in symbols if s.name == "render")
    assert method.kind == "method"
    assert method.qualified_name == "pkg.mod.Widget.render"

    async_method = next(s for s in symbols if s.name == "render_async")
    assert async_method.kind == "method"


def test_extracts_async_top_level_function():
    symbols = extract_python_symbols(SAMPLE, module_qualified_prefix="pkg.mod")
    fn = next(s for s in symbols if s.name == "top_level_async")
    assert fn.kind == "function"


def test_syntax_error_returns_empty_list_not_raises():
    assert extract_python_symbols("def broken(:\n", module_qualified_prefix="pkg") == []


def test_empty_source_returns_empty_list():
    assert extract_python_symbols("", module_qualified_prefix="pkg") == []
