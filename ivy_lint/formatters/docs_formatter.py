import re
import ast
from typing import List
from ivy_lint.formatters import BaseFormatter

FILE_PATTERN = re.compile(r'\.py$')  # This matches Python files by their extension


class DocsFormatter(BaseFormatter):
    """Formatter for Python docstrings following the provided logic."""

    def _format_file(self, filename: str) -> bool:
        if FILE_PATTERN.match(filename) is None:
            return False

        try:
            with open(filename, "r", encoding="utf-8") as f:
                original_code = f.read()

            if not original_code.strip():
                return False

            formatted_code = self._apply_format_rules(original_code)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(formatted_code)

            return original_code != formatted_code

        except SyntaxError:
            print(
                f"Error: The provided file '{filename}' does not contain valid Python"
                " code."
            )
            return False

    def _apply_format_rules(self, content: str) -> str:
        # 1. Replace 'Functional Examples' with 'Examples'
        content = content.replace('Functional Examples', 'Examples')

        # 2. Fix spaces in examples for sphinx
        example_pattern = re.compile(r'(Examples\n-{2,}\n)([^`]*?)(\n\n|\Z)', re.DOTALL)

        def fix_example_spacing(match):
            example = match.group(2)
            # Replace multiple blank lines with a single blank line
            example = re.sub(r'\n{3,}', '\n\n', example)
            # Ensure only one blank line before and after each example
            example = re.sub(r'\n(?=[^ \n])', '\n\n', example)
            example = re.sub(r'(?<=[^ \n])\n', '\n\n', example)
            return 'Examples\n--------\n' + example + match.group(3)

        content = example_pattern.sub(fix_example_spacing, content)

        # 3. Remove backticks from examples
        def remove_backticks(match):
            example = match.group(2)
            # Remove backticks from the matched example
            example = example.replace('```', '')
            return 'Examples\n--------\n' + example + match.group(3)

        content = example_pattern.sub(remove_backticks, content)

        return content