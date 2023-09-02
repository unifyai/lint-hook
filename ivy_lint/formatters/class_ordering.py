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

    def rearrange_class_functions(self, class_node: ast.ClassDef) -> str:
        graph = build_dependency_graph_for_class(class_node)
        
        independent_assignments = [
            code for code, node in class_node.body 
            if isinstance(node, ast.Assign) and node.targets[0].id not in graph
        ]

        property_methods = [
            code for code, node in class_node.body 
            if isinstance(node, ast.FunctionDef) 
            and any(
                is_property_decorator(d) 
                or PROPERTY_DECORATORS["getter"].match(ast.dump(d)) 
                or PROPERTY_DECORATORS["setter"].match(ast.dump(d))
                for d in node.decorator_list
            )
        ]

        instance_methods = [
            code for code, node in class_node.body 
            if isinstance(node, ast.FunctionDef) 
            and node not in property_methods
        ]

        dependent_assignments = [
            code for code, node in class_node.body 
            if isinstance(node, ast.Assign) and node.targets[0].id in graph
        ]

        reordered_class_body = independent_assignments
        if property_methods:
            reordered_class_body.append("# Properties #")
            reordered_class_body.append("# ---------- #")
            reordered_class_body.extend(sorted(property_methods, key=lambda x: x.name))
        
        if instance_methods:
            reordered_class_body.append("# Instance Methods #")
            reordered_class_body.append("# ---------------- #")
            reordered_class_body.extend(sorted(instance_methods, key=lambda x: x.name))
        
        reordered_class_body.extend(dependent_assignments)

        return ast.ClassDef(
            name=class_node.name,
            bases=class_node.bases,
            keywords=class_node.keywords,
            body=reordered_class_body,
            decorator_list=class_node.decorator_list
        )

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
        