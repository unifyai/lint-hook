"""Formatter for function ordering."""

import re
import ast
from typing import Tuple, List

from ivy_lint.formatters import BaseFormatter


class FunctionOrderingFormatter(BaseFormatter):
    """Formatter for function ordering."""

    def _extract_node_with_leading_comments(
        self, node: ast.AST, source_code: str
    ) -> Tuple[str, ast.AST]:
        """
        Extract the source code of a node along with its leading comments,
        decorators, and whitespaces.
        """
        if hasattr(node, "decorator_list"):
            start_line = (
                node.decorator_list[0].lineno if node.decorator_list else node.lineno
            )
        else:
            start_line = node.lineno

        end_line = getattr(node, "end_lineno", node.lineno)

        lines = source_code.splitlines()
        extracted_lines = []

        # Get the actual code for the node
        for line_num in range(start_line - 1, end_line):
            extracted_lines.append(lines[line_num])

        # Get the leading comments and whitespaces
        for line_num in range(start_line - 2, -1, -1):
            stripped = lines[line_num].strip()
            if not stripped or stripped.startswith("#"):
                extracted_lines.insert(0, lines[line_num])
            else:
                break

        # Remove duplicate headers
        extracted_lines = [line for line in extracted_lines if line not in ["# Helpers #", "# ------- #", "# API Functions #", "# ------------- #"]]

        return "\n".join(extracted_lines), node

    def _extract_all_nodes_with_comments(
        self, tree: ast.AST, source_code: str
    ) -> List[Tuple[str, ast.AST]]:
        """
        Extract all the nodes in the AST with their associated comments and
        whitespaces.
        """
        return [
            self._extract_node_with_leading_comments(node, source_code)
            for node in tree.body
        ]

    def _rearrange_functions_and_classes(self, source_code: str) -> str:
        """
        Rearrange classes and functions in source code alphabetically with
        comments.
        """
        tree = ast.parse(source_code)

        # Rearrange methods inside each class in ascending order
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                node.body.sort(key=lambda n: n.name if isinstance(n, ast.FunctionDef) else "")

        nodes_with_comments = self._extract_all_nodes_with_comments(tree, source_code)

        # Define a helper function to determine sorting precedence
        def sort_key(item):
            node = item[1]
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return (0, 0, getattr(node, "name", ""))
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                return (1, 0, ",".join(targets))
            if isinstance(node, ast.ClassDef):
                return (2, 0, node.name)
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("_"):
                    return (3, 0, node.name)
                return (4, 0, node.name)
            return (5, 0, getattr(node, "name", ""))

        nodes_sorted = sorted(nodes_with_comments, key=sort_key)

        reordered_code_list = []
        prev_was_assignment = False
        added_helpers_header = False
        added_api_header = False

        for code, node in nodes_sorted:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("_") and not added_helpers_header:
                reordered_code_list.append("# Helpers #")
                reordered_code_list.append("# ------- #")
                added_helpers_header = True
            elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_") and not added_api_header:
                reordered_code_list.append("# API Functions #")
                reordered_code_list.append("# ------------- #")
                added_api_header = True

            if isinstance(node, ast.Assign):
                if prev_was_assignment:
                    # If the previous node was also an assignment, skip one newline
                    reordered_code_list.append(code.strip())
                else:
                    reordered_code_list.append(code)
                prev_was_assignment = True
            else:
                reordered_code_list.append(code)
                prev_was_assignment = False

        reordered_code = "\n".join(reordered_code_list).strip()

        # Ensure there's a newline at the end of the file
        if not reordered_code.endswith("\n"):
            reordered_code += "\n"

        return reordered_code

    def _format_file(self, filename: str) -> bool:
        # Only include ivy frontend files
        if (
            re.match(
                r"ivy/functional/frontends/(?!.*(?:config\.py|__init__\.py)$).*", 
                filename,
            )
            is None
        ):
            return False

        try:
            with open(filename, "r", encoding="utf-8") as f:
                original_code = f.read()

            # Ignore the file if it's empty or contains only whitespace
            if not original_code.strip():
                return False

            reordered_code = self._rearrange_functions_and_classes(original_code)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(reordered_code)

        except SyntaxError:
            print(
                f"Error: The provided file '{filename}' does not contain valid Python "
                "code."
            )
            return False
