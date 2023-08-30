import re
import ast
import networkx as nx
from typing import Tuple, List
import sys

from ivy_lint.formatters import BaseFormatter

HEADER_PATTERN = re.compile(
    r"#\s?(-{0,3})\s?(Helpers|Main|API"
    r" Functions)\s?(-{0,3})\s?#\n#\s?(-{7,15})\s?#\n(?:\s*\n)*"
)
FILE_PATTERN = re.compile(
    r"(ivy/functional/frontends/(?!.*(?:config\.py|__init__\.py)$).*"
    r"|ivy_tests/test_ivy/(?!.*(?:__init__\.py|conftest\.py|helpers/.*|test_frontends/config/.*$)).*)"
)


def class_build_dependency_graph(nodes_with_comments):
    graph = nx.DiGraph()
    for _, node in nodes_with_comments:
        if isinstance(node, ast.ClassDef):
            graph.add_node(node.name)
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id not in graph:
                    graph.add_node(base.id)
                if isinstance(base, ast.Name):
                    graph.add_edge(base.id, node.name)
    return graph


def contains_any_name(code: str, names: List[str]) -> bool:
    return any(name in code for name in names)


def extract_names_from_assignment(node: ast.Assign) -> List[str]:
    names = []

    def extract_names(node):
        if isinstance(node, ast.Name):
            names.append(node.id)
        for child in ast.iter_child_nodes(node):
            extract_names(child)

    # Handle Python version differences
    if sys.version_info < (3, 8):
        values = node.values
    else:
        values = [node.value]

    for value in values:
        extract_names(value)

    return names


def assignment_build_dependency_graph(nodes_with_comments):
    graph = nx.DiGraph()

    for code, node in nodes_with_comments:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    graph.add_node(target.id)

    for code, node in nodes_with_comments:
        if isinstance(node, ast.Assign):
            right_side_names = extract_names_from_assignment(node)

            for target in node.targets:
                if isinstance(target, ast.Name):
                    for name in right_side_names:
                        if graph.has_node(name):

                            graph.add_edge(name, target.id)
    return graph

def has_st_composite_decorator(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(decorator, ast.Attribute) and decorator.attr == "composite"
        for decorator in node.decorator_list
    )
    
def related_helper_function(assignment_name, nodes_with_comments):
    for _, node in nodes_with_comments:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and hasattr(node, "name"):
            if node.name.startswith("_") and contains_any_name(ast.dump(node), [assignment_name]):
                return node.name
    return None

def has_property_related_decorator(node: ast.FunctionDef) -> Tuple[bool, str]:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Attribute):
            if decorator.attr in ["setter", "getter"]:
                return True, decorator.attr
        elif isinstance(decorator, ast.Name):
            if decorator.id == "property":
                return True, decorator.id
    return False, ""

def is_assignment_independent_of_class_methods(node: ast.Assign, class_methods: List[str]) -> bool:
    right_side_names = extract_names_from_assignment(node)
    return not any(name in right_side_names for name in class_methods)

def _sort_class_methods(class_node: ast.ClassDef, nodes_with_comments: List[Tuple[str, ast.AST]]) -> List[Tuple[str, ast.AST]]:
    properties = []
    methods = []
    independent_assignments = []
    dependent_assignments = []

    class_methods = [node.name for _, node in nodes_with_comments if isinstance(node, ast.FunctionDef) and node.name in [m.name for m in class_node.body if isinstance(m, ast.FunctionDef)]]
    
    for code, node in nodes_with_comments:
        if isinstance(node, ast.FunctionDef) and node.name in class_methods:
            has_property, property_type = has_property_related_decorator(node)
            if has_property:
                properties.append((code, node))
            else:
                methods.append((code, node))
        elif isinstance(node, ast.Assign):
            if is_assignment_independent_of_class_methods(node, class_methods):
                independent_assignments.append((code, node))
            else:
                dependent_assignments.append((code, node))
    
    properties = sorted(properties, key=lambda x: x[1].name)
    methods = sorted(methods, key=lambda x: x[1].name)
    
    result = independent_assignments + [("\n# Properties #\n# ---------- #", None)] + properties + [("\n# Instance Methods #\n# ---------------- #", None)] + methods + dependent_assignments
    return result


class FunctionOrderingFormatter(BaseFormatter):
    def _remove_existing_headers(self, source_code: str) -> str:
        return HEADER_PATTERN.sub("", source_code)

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
        source_code = self._remove_existing_headers(source_code)

        tree = ast.parse(source_code)
        nodes_with_comments = self._extract_all_nodes_with_comments(tree, source_code)

        # Dependency graph for class inheritance
        class_dependency_graph = class_build_dependency_graph(nodes_with_comments)
        sorted_classes = list(nx.topological_sort(class_dependency_graph))

        # Dependency graph for assignments
        assignment_dependency_graph = assignment_build_dependency_graph(
            nodes_with_comments
        )
        dependent_assignments = set(assignment_dependency_graph.nodes()) - set(
            assignment_dependency_graph.edges()
        )
        all_assignments = {
            target.id
            for code, node in nodes_with_comments
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        all_assignments - dependent_assignments

        def _is_assignment_dependent_on_assignment(node):
            if isinstance(node, ast.Assign):
                right_side_names = extract_names_from_assignment(node)
                return any(name in right_side_names for name in all_assignments)
            return False

        def _is_assignment_dependent_on_function_or_class(node):
            if isinstance(node, ast.Assign):
                right_side_names = extract_names_from_assignment(node)
                function_and_class_names = [
                    node.name
                    for _, node in nodes_with_comments
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                ]
                return any(
                    name in right_side_names for name in function_and_class_names
                )
            return False

        def sort_key(item):
            node = item[1]

            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return (0, 0, getattr(node, "name", ""))

            # Handle the try-except blocks containing imports.
            if isinstance(node, ast.Try):
                for n in node.body:
                    if isinstance(n, (ast.Import, ast.ImportFrom)):
                        return (0, 1, getattr(n, "name", ""))

            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                target_str = ",".join(targets)
                
                related_function = related_helper_function(target_str, nodes_with_comments)
                if related_function:
                    function_position = [
                        i for i, (_, n) in enumerate(nodes_with_comments) 
                        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and hasattr(n, "name") and n.name == related_function
                    ][0]
                    return (6, function_position, target_str)
                
                if _is_assignment_dependent_on_assignment(node):
                    return (7, 0, target_str)
                elif _is_assignment_dependent_on_function_or_class(node):
                    return (6, 0, target_str)
                else:
                    return (1, 0, target_str)

            if isinstance(node, ast.ClassDef):
                class_content_sorted = _sort_class_methods(node, nodes_with_comments)
                class_index = sorted_classes.index(node.name)
                return (2, class_index, node.name), class_content_sorted

            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("_") or has_st_composite_decorator(node):
                    return (4, 0, node.name)
                else:
                    return (5, 0, node.name)

            return (8, 0, getattr(node, "name", ""))

        nodes_sorted = sorted(nodes_with_comments, key=sort_key)
        reordered_code_list = []

        # Check and add module-level docstring
        docstring_added = False
        if (
            isinstance(tree, ast.Module)
            and tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Str)
        ):
            docstring = ast.get_docstring(tree, clean=False)
            if docstring:
                reordered_code_list.append(f'"""{docstring}"""')
                docstring_added = True

        has_helper_functions = any(
            isinstance(node, ast.FunctionDef) and node.name.startswith("_")
            for _, node in nodes_sorted
        )

        prev_was_assignment = False
        last_function_type = None

        for code, node in nodes_sorted:
            # If the docstring was added at the beginning, skip the node
            if (
                docstring_added
                and isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Str)
            ):
                continue

            current_function_type = None
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("_") or has_st_composite_decorator(node):
                    current_function_type = "helper"
                    if last_function_type != "helper":
                        reordered_code_list.append(
                            "\n\n# --- Helpers --- #\n# --------------- #"
                        )
                else:
                    current_function_type = "api"
                    if last_function_type != "api" and has_helper_functions:
                        reordered_code_list.append(
                            "\n\n# --- Main --- #\n# ------------ #"
                        )

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
        if FILE_PATTERN.match(filename) is None:
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
            print(
                f"Error: The provided file '{filename}' does not contain valid Python"
                " code."
            )
            return False
