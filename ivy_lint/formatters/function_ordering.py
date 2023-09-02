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
def inside_class_dependency_graph(class_node):
    graph = nx.DiGraph()
    function_names = [
        f.name for f in class_node.body if isinstance(f, ast.FunctionDef)
    ]

    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    graph.add_node(target.id)
                    right_side_names = extract_names_from_assignment(node)
                    for name in right_side_names:
                        if name in function_names:
                            graph.add_edge(name, target.id)
        elif isinstance(node, ast.FunctionDef):
            graph.add_node(node.name)
    return graph

def sort_inside_class_nodes(class_node):
    # Extract nodes
    assigns = [node for node in class_node.body if isinstance(node, ast.Assign)]
    functions = [node for node in class_node.body if isinstance(node, ast.FunctionDef)]

    # Dependency graph
    dependency_graph = inside_class_dependency_graph(class_node)
    dependent_assignments = set(dependency_graph.nodes()) - set(
        dependency_graph.edges()
    )

    def sort_key(node):
        if isinstance(node, ast.Assign):
            if node in dependent_assignments:
                return (4, 0)
            else:
                return (1, 0)
        if isinstance(node, ast.FunctionDef):
            if any(isinstance(dec, ast.Attribute) and dec.attr in ("setter", "getter") for dec in node.decorator_list):
                return (2, node.name)
            elif any(isinstance(dec, ast.Name) and dec.id == "property" for dec in node.decorator_list):
                return (2, node.name)
            else:
                return (3, node.name)
        return (5, 0)

    sorted_nodes = sorted(class_node.body, key=sort_key)
    
    # Add headers
    sorted_body_with_headers = []

    # Properties header
    properties_nodes = [n for n in sorted_nodes if sort_key(n)[0] == 2]
    if properties_nodes:
        sorted_body_with_headers.append("# Properties #")
        sorted_body_with_headers.append("# ---------- #")
        sorted_body_with_headers.extend(properties_nodes)

    # Instance methods header
    instance_methods_nodes = [n for n in sorted_nodes if sort_key(n)[0] == 3]
    if instance_methods_nodes:
        sorted_body_with_headers.append("# Instance Methods #")
        sorted_body_with_headers.append("# ---------------- #")
        sorted_body_with_headers.extend(instance_methods_nodes)

    # Remaining nodes
    other_nodes = [n for n in sorted_nodes if n not in properties_nodes + instance_methods_nodes]
    sorted_body_with_headers.extend(other_nodes)

    return sorted_body_with_headers


def class_assignment_build_dependency_graph(class_node):
    graph = nx.DiGraph()
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    graph.add_node(target.id)

    for node in class_node.body:
        if isinstance(node, ast.Assign):
            right_side_names = extract_names_from_assignment(node)

            for target in node.targets:
                if isinstance(target, ast.Name):
                    for name in right_side_names:
                        if any(isinstance(n, ast.FunctionDef) and n.name == name for n in class_node.body):
                            graph.add_edge(name, target.id)
    return graph

def is_property_related(node):
    return any(isinstance(decorator, ast.Attribute) and decorator.attr in ['setter', 'getter']
               for decorator in node.decorator_list) or \
           any(isinstance(decorator, ast.Name) and decorator.id == 'property'
               for decorator in node.decorator_list)

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
        
        for _, node in nodes_with_comments:
            if isinstance(node, ast.ClassDef):
                sorted_body = sort_inside_class_nodes(node)
                node.body = sorted_body

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
                # Dependency graph for assignments in class
                class_assignment_dependency_graph = class_assignment_build_dependency_graph(node)
                independent_assignments = set(class_assignment_dependency_graph.nodes()) - \
                                          set(class_assignment_dependency_graph.edges())

                # Sort class content
                class_content_order = {}
                for inner_node in node.body:
                    if isinstance(inner_node, ast.FunctionDef):
                        if is_property_related(inner_node):
                            class_content_order[inner_node.name] = 2
                        else:
                            class_content_order[inner_node.name] = 3
                    elif isinstance(inner_node, ast.Assign):
                        if inner_node.targets[0].id in independent_assignments:
                            class_content_order[inner_node.targets[0].id] = 1
                        else:
                            class_content_order[inner_node.targets[0].id] = 4

                def class_inner_sort_key(inner_name):
                    if inner_name in class_content_order:
                        return class_content_order[inner_name], inner_name
                    return 5, inner_name

                # Sort and reformat class content
                class_body_sorted = sorted(node.body, key=lambda x: class_inner_sort_key(getattr(x, 'name', 'unknown')))
                class_body_with_comments = self._extract_all_nodes_with_comments(class_node, source_code)
                class_body_sorted = sorted(class_body_with_comments, key=class_sort_key)
                class_code = [code for code, _ in class_body_sorted]

                
                # Insert property and method headers
                i = 0
                while i < len(class_code):
                    if class_content_order.get(getattr(class_body_sorted[i], 'name', 'unknown')) == 2:
                        class_code.insert(i, "# Properties #\n# ---------- #")
                        while i < len(class_code) and class_content_order.get(getattr(class_body_sorted[i], 'name', 'unknown')) == 2:
                            i += 1
                    elif class_content_order.get(getattr(class_body_sorted[i], 'name', 'unknown')) == 3:
                        class_code.insert(i, "# Instance Methods #\n# ---------------- #")
                        while i < len(class_code) and class_content_order.get(getattr(class_body_sorted[i], 'name', 'unknown')) == 3:
                            i += 1
                    else:
                        i += 1

                return (2, sorted_classes.index(node.name), "\n".join(class_code))


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
