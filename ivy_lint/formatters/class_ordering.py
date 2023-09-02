import ast
import networkx as nx
import re
from typing import List, Tuple
from ivy_lint.formatters import BaseFormatter

PROPERTY_DECORATORS = {
    "getter": re.compile(r"@(.+)\.getter"),
    "setter": re.compile(r"@(.+)\.setter"),
}

def is_property_decorator(decorator: ast.decorator) -> bool:
    if isinstance(decorator, ast.Attribute):
        return decorator.attr == "property"
    return False

def extract_names_from_assignment(node: ast.Assign) -> List[str]:
    names = []

    def extract_names(node):
        if isinstance(node, ast.Name):
            names.append(node.id)
        for child in ast.iter_child_nodes(node):
            extract_names(child)

    extract_names(node.value)
    return names

def build_dependency_graph_for_class(class_node: ast.ClassDef) -> nx.DiGraph:
    graph = nx.DiGraph()
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef):
            graph.add_node(node.name)
            for decorator in node.decorator_list:
                match_getter = PROPERTY_DECORATORS["getter"].match(ast.dump(decorator))
                match_setter = PROPERTY_DECORATORS["setter"].match(ast.dump(decorator))
                if match_getter or match_setter or is_property_decorator(decorator):
                    graph.add_edge(node.name, node.name)
            for sub_node in ast.walk(node):
                if isinstance(sub_node, ast.Name) and sub_node.id in graph:
                    graph.add_edge(sub_node.id, node.name)

        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    graph.add_node(target.id)
                    for name in extract_names_from_assignment(node):
                        if graph.has_node(name):
                            graph.add_edge(name, target.id)
    return graph

class ClassFunctionOrderingFormatter(BaseFormatter):

    def _rearrange_inside_class(self, class_node: ast.ClassDef, source_code: str) -> str:
        nodes_with_comments = self._extract_all_nodes_with_comments(class_node, source_code)

        assignment_dependency_graph = assignment_build_dependency_graph(nodes_with_comments)

        independent_assignments = [
            code for code, node in nodes_with_comments if isinstance(node, ast.Assign) and not _is_assignment_dependent_on_assignment(node)
        ]

        property_functions = [
            code for code, node in nodes_with_comments if isinstance(node, ast.FunctionDef) and any(
                isinstance(decorator, ast.Attribute) and decorator.attr in ["setter", "getter"]
                for decorator in node.decorator_list
            )
        ]

        other_functions = [
            code for code, node in nodes_with_comments if isinstance(node, ast.FunctionDef) and not any(
                isinstance(decorator, ast.Attribute) and decorator.attr in ["setter", "getter"]
                for decorator in node.decorator_list
            )
        ]

        dependent_assignments = [
            code for code, node in nodes_with_comments if isinstance(node, ast.Assign) and _is_assignment_dependent_on_assignment(node)
        ]

        return '\n'.join(
            independent_assignments +
            ["\n# Properties #", "# ---------- #"] + property_functions +
            ["\n# Instance Methods #", "# ---------------- #"] + other_functions +
            dependent_assignments
        )

    def _rearrange_functions_and_classes(self, source_code: str) -> str:
        tree = ast.parse(source_code)
        reordered_code_list = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_code = self._rearrange_inside_class(node, source_code)
                reordered_code_list.append(class_code)
            else:
                reordered_code_list.append(self._extract_node_with_leading_comments(node, source_code)[0])

        reordered_code = '\n'.join(reordered_code_list).strip()
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
                f"Error: The provided file '{filename}' does not contain valid Python code."
            )
            return False
            