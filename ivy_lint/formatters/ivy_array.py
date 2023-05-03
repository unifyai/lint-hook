"""Docstring formatter for fixing ivy.array output style."""

from ivy_lint.formatters import BaseDocstringFormatter


class IvyArrayDocstringFormatter(BaseDocstringFormatter):
    """
    Docstring formatter for fixing ivy.array output style.

    It checks for code examples that have `ivy.array` as it's output and
    formats its content to be more readable.
    """

    def _do_format_docstring(self, docstring: str) -> str:
        raise NotImplementedError()
