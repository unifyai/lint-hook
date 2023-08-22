import re
import ast
from typing import Tuple, List
from ivy_lint.formatters import BaseFormatter

HEADER_PATTERN = re.compile(r"# ?[-]+ ?(?:Helpers|Main|API Functions)? ?[-]+ ?#")

class FunctionOrderingFormatter(BaseFormatter):
    """Formatter for function ordering."""

    @staticmethod
    def _remove_existing_headers(source_code: str) -> str:
        return HEADER_PATTERN.sub("", source_code)

    @staticmethod
    def _sort_key(item) -> Tuple[int, str]:
        node = item[1]
        order = {
            ast.Import: 0,
            ast.ImportFrom: 0,
            ast.Assign: 1,
            ast.ClassDef: 2,
            ast.FunctionDef: 3 if node.name.startswith("_") else 4,
        }
        node_type = type(node)
        if node_type in order:
            return (order[node_type], getattr(node, "name", ""))
        return (5, "")

    def _extract_node_with_leading_comments(self, node: ast.AST, source_code: str) -> Tuple[str, ast.AST]:
        if hasattr(node, "decorator_list"):
            start_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
        else:
            start_line = node.lineno

        end_line = getattr(node, "end_lineno", node.lineno)
        lines = source_code.splitlines()
        extracted_lines = [lines[line_num] for line_num in range(start_line - 1, end_line)]
        
        for line_num in range(start_line - 2, -1, -1):
            stripped = lines[line_num].strip()
            if not stripped or stripped.startswith("#"):
                extracted_lines.insert(0, lines[line_num])
            else:
                break

        return "\n".join(extracted_lines), node

    def _extract_all_nodes_with_comments(self, tree: ast.AST, source_code: str) -> List[Tuple[str, ast.AST]]:
        return [self._extract_node_with_leading_comments(node, source_code) for node in tree.body]

    def _rearrange_functions_and_classes(self, source_code: str) -> str:
        source_code = self._remove_existing_headers(source_code.strip())

        tree = ast.parse(source_code)
        nodes_with_comments = self._extract_all_nodes_with_comments(tree, source_code)
        nodes_sorted = sorted(nodes_with_comments, key=self._sort_key)

        segments = {
            "imports": [],
            "assignments": [],
            "helpers": ["\n\n# --- Helpers --- #", "# --------------- #"],
            "apis": ["\n\n# --- Main --- #", "# ------------ #"]
        }

        for code, node in nodes_sorted:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                segments["imports"].append(code)
            elif isinstance(node, ast.Assign):
                segments["assignments"].append(code)
            elif isinstance(node, ast.FunctionDef):
                if node.names.startswith("_"):
                    segments["helpers"].append(code)
                else:
                    segments["apis"].append(code)

        reordered_code = "\n".join(segments["imports"] + segments["assignments"] + segments["helpers"] + segments["apis"])
        return reordered_code + "\n" if not reordered_code.endswith("\n") else reordered_code

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

        return True  # indicate successful formatting
