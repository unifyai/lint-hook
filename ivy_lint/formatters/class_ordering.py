import ast
import re
import networkx as nx
import sys
from typing import List

from ivy_lint.formatters import BaseFormatter

FILE_PATTERN = re.compile(
    r"(ivy/functional/frontends/(?!.*(?:config\.py|__init__\.py)$).*"
    r"|ivy_tests/test_ivy/(?!.*(?:__init__\.py|conftest\.py|helpers/.*|test_frontends/config/.*$)).*)"
)

PROPERTIES_HEADER = "\n# Properties #\n# ---------- #\n"
METHODS_HEADER = "\n# Instance Methods #\n# ---------------- #\n"

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

class ClassFunctionOrderingFormatter(BaseFormatter):

    def _build_intra_class_dependency_graph(self, class_body):
        graph = nx.DiGraph()
        
        # Add nodes
        for node in class_body:
            if isinstance(node, ast.FunctionDef):
                graph.add_node(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        graph.add_node(target.id)

        # Add edges
        for node in class_body:
            if isinstance(node, ast.Assign):
                right_side_names = extract_names_from_assignment(node)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        for name in right_side_names:
                            if graph.has_node(name):
                                graph.add_edge(name, target.id)

        return graph

    def _rearrange_class_content(self, class_node: ast.ClassDef) -> List[ast.AST]:
        graph = self._build_intra_class_dependency_graph(class_node.body)
        
        dependent_assignments = set(graph.nodes()) - set(graph.edges())
        non_dependent_assignments = [
            node for node in class_node.body if isinstance(node, ast.Assign) and all(
                isinstance(target, ast.Name) and target.id not in dependent_assignments
                for target in node.targets
            )
        ]

        properties = [
            node for node in class_node.body if any(
                isinstance(decorator, ast.Attribute) and decorator.attr in ["setter", "getter", "property"]
                for decorator in node.decorator_list
            )
        ]
        properties = sorted(properties, key=lambda x: x.name)

        other_methods = [
            node for node in class_node.body if isinstance(node, ast.FunctionDef)
            and node not in properties
        ]
        other_methods = sorted(other_methods, key=lambda x: x.name)

        # Reconstruct class content
        new_body = non_dependent_assignments
        if properties:
            new_body.extend([ast.parse(PROPERTIES_HEADER).body[0]])
            new_body.extend(properties)
        if other_methods:
            new_body.extend([ast.parse(METHODS_HEADER).body[0]])
            new_body.extend(other_methods)
        new_body.extend([node for node in class_node.body if node not in (non_dependent_assignments + properties + other_methods)])
        
        return new_body

    def _format_file(self, filename: str) -> bool:
        if FILE_PATTERN.match(filename) is None:
            return False

        try:
            with open(filename, "r", encoding="utf-8") as f:
                original_code = f.read()

            tree = ast.parse(original_code)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    node.body = self._rearrange_class_content(node)

            new_code = ast.unparse(tree)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(new_code)

        except SyntaxError:
            print(
                f"Error: The provided file '{filename}' does not contain valid Python"
                " code."
            )
            return False

        return True
