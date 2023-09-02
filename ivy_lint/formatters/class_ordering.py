import re
import ast
import networkx as nx
from typing import Tuple, List

from ivy_lint.formatters import BaseFormatter

FILE_PATTERN = re.compile(
    r"(ivy/functional/frontends/(?!.*(?:config\.py|__init__\.py)$).*"
    r"|ivy_tests/test_ivy/(?!.*(?:__init__\.py|conftest\.py|helpers/.*|test_frontends/config/.*$)).*)"
)


def extract_names_from_assignment_inside_class(node: ast.Assign) -> List[str]:
    names = []

    def extract_names_from_node(node):
        if isinstance(node, ast.Name):
            names.append(node.id)
        for child in ast.iter_child_nodes(node):
            extract_names_from_node(child)

    extract_names_from_node(node.value)
    return names


def assignment_build_dependency_graph_for_class(class_node: ast.ClassDef):
    graph = nx.DiGraph()

    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    graph.add_node(target.id)

    for node in class_node.body:
        if isinstance(node, ast.Assign):
            right_side_names = extract_names_from_assignment_inside_class(node)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    for name in right_side_names:
                        if graph.has_node(name):
                            graph.add_edge(name, target.id)

    return graph


def has_property_decorators(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(decorator, ast.Attribute) and (
            decorator.attr.endswith(".setter") or decorator.attr.endswith(".getter") or decorator.attr == "property"
        )
        for decorator in node.decorator_list
    )


class ClassFunctionOrderingFormatter(BaseFormatter):

    def _extract_all_nodes_within_class(self, class_node: ast.ClassDef) -> List[ast.AST]:
        return class_node.body

    def _rearrange_functions_and_classes(self, source_code: str) -> str:
        tree = ast.parse(source_code)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                nodes_within_class = self._extract_all_nodes_within_class(node)

                # Dependency graph for assignments inside class
                assignment_dependency_graph_for_class = assignment_build_dependency_graph_for_class(node)
                dependent_assignments = set(assignment_dependency_graph_for_class.nodes()) - set(
                    assignment_dependency_graph_for_class.edges())
                independent_assignments = set(assignment_dependency_graph_for_class.nodes()) - dependent_assignments

                reordered_nodes = []

                # 1. Add independent assignments
                for inner_node in nodes_within_class:
                    if (isinstance(inner_node, ast.Assign)
                            and isinstance(inner_node.targets[0], ast.Name)
                            and inner_node.targets[0].id in independent_assignments):
                        reordered_nodes.append(inner_node)

                # 2. Add property-related functions
                reordered_nodes.append(ast.Expr(ast.Str(s="# Properties #\n# ---------- #")))
                for inner_node in nodes_within_class:
                    if isinstance(inner_node, ast.FunctionDef) and has_property_decorators(inner_node):
                        reordered_nodes.append(inner_node)

                # 3. Add other functions
                reordered_nodes.append(ast.Expr(ast.Str(s="# Instance Methods #\n# ---------------- #")))
                for inner_node in nodes_within_class:
                    if isinstance(inner_node, ast.FunctionDef) and not has_property_decorators(inner_node):
                        reordered_nodes.append(inner_node)

                # 4. Add dependent assignments
                for inner_node in nodes_within_class:
                    if (isinstance(inner_node, ast.Assign)
                            and isinstance(inner_node.targets[0], ast.Name)
                            and inner_node.targets[0].id in dependent_assignments):
                        reordered_nodes.append(inner_node)

                node.body = reordered_nodes

        return ast.unparse(tree)

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
