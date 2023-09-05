import re
import ast
from typing import List
from ivy_lint.formatters import BaseFormatter

FILE_PATTERN = re.compile(
    r"(ivy/functional/frontends/(?!.*(?:config\.py|__init__\.py)$).*"
    r"|ivy_tests/test_ivy/(?!.*(?:__init__\.py|conftest\.py|helpers/.*|test_frontends/config/.*$)).*)"
)

EXAMPLES_PATTERN = re.compile(
    r"(Examples\n[-]{2,}\n\n)(.*?)(\n\n|$)", re.DOTALL
)
MULTI_EXAMPLE_PATTERN = re.compile(
    r"(>>>[^\n]+?\n)([^\n]+?)(\n\n|>>>|$)", re.DOTALL
)

class DocsFormatter(BaseFormatter):

    @staticmethod
    def correct_docstring(docstring: str) -> str:
        """Apply corrections to the given docstring."""

        # Replace 'Functional Examples' with 'Examples' and adjust the dashes
        docstring = re.sub(r'Functional Examples\n-{3,}', 'Examples\n--------', docstring)

        # Correcting the entire Examples section
        def fix_examples_section(match):
            examples_section = match.group(2)

            # Ensure correct spacing between examples
            examples_section = MULTI_EXAMPLE_PATTERN.sub(
                lambda m: m.group(1) + "\n" + m.group(2) + "\n", examples_section)
            
            return match.group(1) + examples_section + "\n"

        # Adjust the examples section
        docstring = EXAMPLES_PATTERN.sub(fix_examples_section, docstring)

        return docstring

    def _extract_docstrings_from_tree(self, tree: ast.AST) -> List[ast.Str]:
        """Extract all docstrings from an AST tree."""
        return [node.value for node in ast.walk(tree) if isinstance(node, ast.Expr) and isinstance(node.value, ast.Str)]

    def _correct_docstrings(self, source_code: str) -> str:
        """Correct docstrings in the provided source code."""
        tree = ast.parse(source_code)
        docstrings = self._extract_docstrings_from_tree(tree)
        
        for doc in docstrings:
            corrected = self.correct_docstring(doc.s)
            source_code = source_code.replace(doc.s, corrected)
        
        return source_code

    def _format_file(self, filename: str) -> bool:
        """Format the file by correcting its docstrings."""
        # if FILE_PATTERN.match(filename) is None:
        #     return False

        with open(filename, 'r', encoding='utf-8') as f:
            original_code = f.read()

        corrected_code = self._correct_docstrings(original_code)

        # Check if any changes have been made.
        if corrected_code == original_code:
            return False

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(corrected_code)

        return True
