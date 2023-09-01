import re
import ast
import networkx as nx
from typing import Tuple, List
import sys
from functools import partial

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
            if node.name.startswith("_") and contains_any_name(
                ast.dump(node), [assignment_name]
            ):
                return node.name
    return None


def _is_assignment_target_an_attribute(node):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                return True
    return False

def _is_property_related_decorator(decorator):
    """Check if a decorator corresponds to a property-like decorator."""
    if isinstance(decorator, ast.Attribute):
        attr = decorator.attr
        return attr in ["setter", "getter"] or decorator.value.id == "property"
    return False

def _class_node_sort_key(class_node, nodes_with_comments):
    """Sorting key for methods and assignments inside a class."""

    # Categorize by node type
    if isinstance(class_node, ast.FunctionDef):
        # Check if it's a property-related function
        if any(
            _is_property_related_decorator(decorator)
            for decorator in class_node.decorator_list
        ):
            return (2, class_node.name)  # properties
        else:
            return (3, class_node.name)  # instance methods
    elif isinstance(class_node, ast.Assign):
        # Check if the assignment depends on other methods in the class
        right_side_names = extract_names_from_assignment(class_node)
        method_names = [
            node.name for _, node in nodes_with_comments if isinstance(node, ast.FunctionDef)
        ]
        if any(name in right_side_names for name in method_names):
            return (4, class_node.name)  # assignments that depend on methods
        else:
            return (1, class_node.name)  # independent assignments
    return (5, "")  # anything else

def _rearrange_methods_and_assignments_within_class(class_code, class_node, nodes_with_comments):
    """Rearrange methods and assignments inside a class based on the criteria."""
    # Extract the body of the class
    class_body_with_comments = [
        (code, node) for code, node in nodes_with_comments if node in class_node.body
    ]

    # Sort based on the defined criteria
    class_body_sorted = sorted(
        class_body_with_comments, key=partial(_class_node_sort_key, nodes_with_comments=nodes_with_comments)
    )

    # Insert headers
    reordered_code_list = []
    last_category = None
    for code, node in class_body_sorted:
        current_category = _class_node_sort_key(node, nodes_with_comments)[0]
        if current_category != last_category:
            if current_category == 2:
                reordered_code_list.append("# Properties #\n# ---------- #")
            elif current_category == 3:
                reordered_code_list.append("# Instance Methods #\n# ---------------- #")
        reordered_code_list.append(code)
        last_category = current_category

    return "\n".join(reordered_code_list)


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
        
        # Extract class nodes
        class_nodes = [
            (code, node) for code, node in nodes_with_comments if isinstance(node, ast.ClassDef)
        ]
        for class_code, class_node in class_nodes:
            rearranged_class_content = _rearrange_methods_and_assignments_within_class(class_code, class_node, nodes_with_comments)
            source_code = source_code.replace(class_code, rearranged_class_content)

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

                related_function = related_helper_function(
                    target_str, nodes_with_comments
                )
                if related_function:
                    function_position = [
                        i
                        for i, (_, n) in enumerate(nodes_with_comments)
                        if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                        and hasattr(n, "name")
                        and n.name == related_function
                    ][0]
                    return (6, function_position, target_str)

                if _is_assignment_target_an_attribute(node):
                    return (5.5, 0, target_str)

                if _is_assignment_dependent_on_assignment(node):
                    return (7, 0, target_str)
                elif _is_assignment_dependent_on_function_or_class(node):
                    return (6, 0, target_str)
                else:
                    return (1, 0, target_str)

            if isinstance(node, ast.ClassDef):
                try:
                    return (2, sorted_classes.index(node.name), node.name)
                except ValueError:
                    return (2, len(sorted_classes), node.name)

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
