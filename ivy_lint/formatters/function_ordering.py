import re
import ast
from typing import Tuple, List

from ivy_lint.formatters import BaseFormatter


class FunctionOrderingFormatter(BaseFormatter):
    """Formatter for function ordering."""

    def _extract_node_with_leading_comments(
        self, node: ast.AST, source_code: str
    ) -> Tuple[str, ast.AST]:
        if hasattr(node, "decorator_list"):
            start_line = (
                node.decorator_list[0].lineno if node.decorator_list else node.lineno
            )
        else:
            start_line = node.lineno

        end_line = getattr(node, "end_lineno", node.lineno)
        lines = source_code.splitlines()
        extracted_lines = []

        for line_num in range(start_line - 1, end_line):
            extracted_lines.append(lines[line_num])

        for line_num in range(start_line - 2, -1, -1):
            stripped = lines[line_num].strip()
            if not stripped or stripped.startswith("#"):
                extracted_lines.insert(0, lines[line_num])
            else:
                break

        return "\n".join(extracted_lines), node

    def _extract_all_nodes_with_comments(
        self, tree: ast.AST, source_code: str
    ) -> List[Tuple[str, ast.AST]]:
        return [
            self._extract_node_with_leading_comments(node, source_code)
            for node in tree.body
        ]

    def _rearrange_functions_and_classes(self, source_code: str) -> str:
        tree = ast.parse(source_code)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                node.body.sort(key=lambda n: n.name if isinstance(n, ast.FunctionDef) else "")

        nodes_with_comments = self._extract_all_nodes_with_comments(tree, source_code)

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
        last_function_type = None

        for code, node in nodes_sorted:
            current_function_type = None
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("_"):
                    current_function_type = "helper"
                    if last_function_type != "helper":
                        reordered_code_list.append("# Helpers #")
                        reordered_code_list.append("# ------- #")
                else:
                    current_function_type = "api"
                    if last_function_type != "api":
                        reordered_code_list.append("# API Functions #")
                        reordered_code_list.append("# ------------- #")

            last_function_type = current_function_type or last_function_type

            if isinstance(node, ast.Assign):
                if prev_was_assignment:
                    reordered_code_list.append(code.strip())
                else:
                    reordered_code_list.append(code)
                prev_was_assignment = True
            else:
                reordered_code_list.append(code)
                prev_was_assignment = False

        reordered_code = "\n".join(reordered_code_list).strip()
        if not reordered_code.endswith("\n"):
            reordered_code += "\n"

        return reordered_code

    def _format_file(self, filename: str) -> bool:
        if re.match(r"ivy/functional/frontends/(?!.*(?:config\.py|__init__\.py)$).*", filename) is None:
            return False

        try:
            with open(filename, "r", encoding="utf-8") as f:
                original_code = f.read()

            if not original_code.strip():
                return False

            reordered_code = self._rearrange_functions_and_classes(original_code)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(reordered_code)

        except SyntaxError:
            print(f"Error: The provided file '{filename}' does not contain valid Python code.")
            return False
