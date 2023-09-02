import re
import ast
import networkx as nx
from typing import Tuple, List, Union
from ivy_lint.formatters import BaseFormatter

PROPERTY_PATTERN = re.compile(r"@([a-zA-Z_]\w*)\.(setter|getter|deleter)")

def class_function_dependency_graph(class_node: ast.ClassDef) -> nx.DiGraph:
    graph = nx.DiGraph()

    for node in class_node.body:
        if isinstance(node, ast.FunctionDef):
            graph.add_node(node.name)
            if any(isinstance(dec, ast.Attribute) and dec.attr in ['setter', 'getter', 'deleter'] for dec in node.decorator_list):
                base_func_name = node.name.split("_")[0]
                graph.add_edge(base_func_name, node.name)

    return graph

def assignment_function_dependency_graph(class_node: ast.ClassDef) -> nx.DiGraph:
    graph = nx.DiGraph()

    def extract_names_from_node(node):
        if isinstance(node, ast.Name):
            return [node.id]
        return [name.id for child in ast.iter_child_nodes(node) for name in extract_names_from_node(child)]

    for node in class_node.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            for target in targets:
                graph.add_node(target)
            dependencies = extract_names_from_node(node.value)
            for dep in dependencies:
                if graph.has_node(dep):
                    for target in targets:
                        graph.add_edge(dep, target)
    return graph

class ClassFunctionOrderingFormatter(BaseFormatter):

    def _extract_node_with_leading_comments(self, node: ast.AST, source_code: str) -> Tuple[str, ast.AST]:
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        lines = source_code.splitlines()
        extracted_lines = lines[start_line - 1:end_line]

        return "\n".join(extracted_lines), node

    def _rearrange_functions_within_class(self, class_node: ast.ClassDef, source_code: str) -> str:
        nodes_with_comments = [
            self._extract_node_with_leading_comments(node, source_code)
            for node in class_node.body
        ]

        func_dependency_graph = class_function_dependency_graph(class_node)
        assign_dependency_graph = assignment_function_dependency_graph(class_node)

        # Sort functions alphabetically
        func_nodes = sorted([
            node for node in nodes_with_comments if isinstance(node[1], ast.FunctionDef)
        ], key=lambda x: x[1].name)

        assign_nodes = [
            node for node in nodes_with_comments if isinstance(node[1], ast.Assign)
        ]

        independent_assignments = [
            node for node in assign_nodes if node[1].targets[0].id not in assign_dependency_graph
        ]

        dependent_assignments = [
            node for node in assign_nodes if node[1].targets[0].id in assign_dependency_graph
        ]

        properties = [
            node for node in func_nodes if PROPERTY_PATTERN.match(self._extract_node_with_leading_comments(node[1], source_code)[0])
        ]

        other_funcs = [
            node for node in func_nodes if node not in properties
        ]

        reordered_code = []

        # Add assignments that don't depend on functions
        for code, _ in independent_assignments:
            reordered_code.append(code)

        # Add properties
        if properties:
            reordered_code.append("# Properties #")
            reordered_code.append("# ---------- #")
            reordered_code.extend([code for code, _ in properties])

        # Add other functions
        if other_funcs:
            reordered_code.append("# Instance Methods #")
            reordered_code.append("# ---------------- #")
            reordered_code.extend([code for code, _ in other_funcs])

        # Add dependent assignments
        for code, _ in dependent_assignments:
            reordered_code.append(code)

        return "\n".join(reordered_code)

    def _format_file(self, filename: str) -> bool:
        with open(filename, "r", encoding="utf-8") as f:
            original_code = f.read()

        if not original_code.strip():
            return False

        tree = ast.parse(original_code)
        modified_classes = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                reordered_class = self._rearrange_functions_within_class(node, original_code)
                modified_classes.append(reordered_class)

        if modified_classes:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n\n".join(modified_classes))

            return True
        return False
