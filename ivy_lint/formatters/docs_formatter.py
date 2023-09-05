import re
import ast
from typing import List
from ivy_lint.formatters import BaseFormatter

EXAMPLES_PATTERN = re.compile(
    r"(Examples\n[-]{2,}\n\n)(.*?)(\n\n|$)", re.DOTALL
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
            
            # Split the section into lines
            lines = examples_section.split('\n')
            in_code_block = False
            new_lines = []

            for line in lines:
                # Detect the start or continuation of a code block
                if line.strip().startswith(">>>"):
                    if not in_code_block:
                        new_lines.append("")  # Add blank line before starting a new block
                        in_code_block = True
                # Detect the end of a code block
                elif in_code_block and not line.strip():
                    in_code_block = False
                    new_lines.append(line)  # Keep the existing blank line
                    continue

                new_lines.append(line)

            # If it ends while still in a code block, ensure it finishes with a blank line
            if in_code_block:
                new_lines.append("")

            return match.group(1) + '\n'.join(new_lines) + "\n"

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
            print(doc.s)
            corrected = self.correct_docstring(doc.s)
            source_code = source_code.replace(doc.s, corrected)
        
        return source_code

    def _format_file(self, filename: str) -> bool:
        """Format the file by correcting its docstrings."""

        with open(filename, 'r', encoding='utf-8') as f:
            original_code = f.read()

        corrected_code = self._correct_docstrings(original_code)

        # Check if any changes have been made.
        if corrected_code == original_code:
            print(f'No changes made to {filename}')
            return False

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(corrected_code)

        return True
