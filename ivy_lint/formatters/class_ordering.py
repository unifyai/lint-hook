import ast
import networkx as nx
import astunparse
from ivy_lint.formatters import BaseFormatter
from typing import Union

class ClassFunctionOrderingFormatter(BaseFormatter):

    def build_dependency_graph_for_class(self, class_node: ast.ClassDef) -> nx.DiGraph:
        graph = nx.DiGraph()
        
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                graph.add_node(node.name)
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Attribute) and decorator.attr in ["getter", "setter"]:
                        graph.add_edge(node.name, node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        graph.add_node(target.id)

        return graph

    def is_property_method(self, node: ast.FunctionDef) -> bool:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Attribute) and decorator.attr in ["getter", "setter"]:
                return True
        return False

    def rearrange_class_functions(self, class_node: ast.ClassDef) -> ast.ClassDef:
        graph = self.build_dependency_graph_for_class(class_node)
        
        independent_assignments = [
            node for node in class_node.body 
            if isinstance(node, ast.Assign) and not graph.has_node(node.targets[0].id)
        ]

        property_methods = [
            node for node in class_node.body 
            if isinstance(node, ast.FunctionDef) and self.is_property_method(node)
        ]

        instance_methods = [
            node for node in class_node.body 
            if isinstance(node, ast.FunctionDef) and not self.is_property_method(node)
        ]

        dependent_assignments = [
            node for node in class_node.body 
            if isinstance(node, ast.Assign) and graph.has_node(node.targets[0].id)
        ]

        reordered_class_body = independent_assignments
        
        if property_methods:
            reordered_class_body.extend(property_methods)

        if instance_methods:
            reordered_class_body.extend(instance_methods)
        
        reordered_class_body.extend(dependent_assignments)

        return ast.ClassDef(
            name=class_node.name,
            bases=class_node.bases,
            keywords=class_node.keywords,
            body=reordered_class_body,
            decorator_list=class_node.decorator_list
        )

    def format_file(self, filename: str) -> bool:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                source_code = f.read()

            tree = ast.parse(source_code)

            for i, node in enumerate(tree.body):
                if isinstance(node, ast.ClassDef):
                    tree.body[i] = self.rearrange_class_functions(node)

            reformatted_code = astunparse.unparse(tree)  # Use astunparse to get source code

            with open(filename, "w", encoding="utf-8") as f:
                f.write(reformatted_code)

            return True
        except Exception as e:
            print(f"Error formatting {filename}. Reason: {e}")
            return False
