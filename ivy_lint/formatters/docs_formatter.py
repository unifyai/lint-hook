import re
import ast
from typing import List
from ivy_lint.formatters import BaseFormatter

EXAMPLES_PATTERN = re.compile(r"(Examples\n[-]{2,}\n\n)(.*?)(\n\n|$)", re.DOTALL)

class DocsFormatter(BaseFormatter):
    """Formatter for docstrings."""

    @staticmethod
    def correct_docstring(docstring: str) -> str:
        docstring = re.sub(r'Functional Examples\n-{3,}', 'Examples\n--------', docstring)
        docstring = EXAMPLES_PATTERN.sub(DocsFormatter._fix_examples_section, docstring)
        return docstring

    @staticmethod
    def _fix_examples_section(match):
        """Reformat the Examples section of a docstring."""
        examples_section = match.group(2)
        lines = examples_section.split('\n')
        
        in_code_block = False
        new_lines = []

        for line in lines:
            # Remove backticks from examples
            line = line.replace('```', '')
            
            if line.strip().startswith(">>>"):
                if not in_code_block:
                    new_lines.append("")
                    in_code_block = True
            elif in_code_block and not line.strip():
                in_code_block = False
                new_lines.append(line)
                continue

            new_lines.append(line)

        if in_code_block:
            new_lines.append("")

        return match.group(1) + '\n'.join(new_lines) + "\n"

    def _extract_docstrings(self, tree: ast.AST) -> List[str]:
        """Extract all docstrings from an AST tree."""
        docstrings = []

        for node in ast.walk(tree):
            # Check if the node is one of the constructs that can have a docstring
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node)
                if docstring:
                    docstrings.append(docstring)
        
        return docstrings

    def _replace_docstrings(self, source_code: str) -> str:
        """Replace docstrings in the provided source code with corrected versions."""
        tree = ast.parse(source_code)
        docstring_replacements = []

        # For each node, if it has a docstring, get its exact span
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node, clean=False)
                if docstring:
                    # Calculate the start of the docstring
                    start_byte_offset = node.body[0].col_offset
                    
                    # We include the node's col_offset to handle nested structures
                    start_index = source_code.rfind(docstring, 0, node.body[0].end_col_offset + node.col_offset)
                    
                    docstring_replacements.append((start_index, start_index + len(docstring), docstring))
                    
        # Apply replacements in reverse order to avoid shifting positions
        for start, end, doc in reversed(docstring_replacements):
            corrected = DocsFormatter.correct_docstring(doc)
            source_code = source_code[:start] + corrected + source_code[end:]

        return source_code

    def _format_file(self, filename: str) -> bool:
        """Format the file by correcting its docstrings."""
        with open(filename, 'r', encoding='utf-8') as f:
            original_code = f.read()

        corrected_code = self._replace_docstrings(original_code)

        if corrected_code != original_code:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(corrected_code)
            return True

        return False
