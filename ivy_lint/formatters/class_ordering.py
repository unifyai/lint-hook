import ast
import re
import networkx as nx

FILE_PATTERN = re.compile(
    r"(ivy/functional/frontends/(?!.*(?:config\.py|__init__\.py)$).*"
    r"|ivy_tests/test_ivy/(?!.*(?:__init__\.py|conftest\.py|helpers/.*|test_frontends/config/.*$)).*)"
)

def has_property_decorators(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(decorator, ast.Attribute) and (
            decorator.attr.endswith(".setter") or decorator.attr.endswith(".getter") or decorator.attr == "property"
        )
        for decorator in node.decorator_list
    )

def assignment_build_dependency_graph_for_class(class_node: ast.ClassDef):
    graph = nx.DiGraph()

    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    graph.add_node(target.id)
                    for name in [n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)]:
                        if name != target.id:  # Avoid self-dependencies
                            graph.add_node(name)
                            graph.add_edge(target.id, name)
    return graph

class ClassFunctionOrderingFormatter:

    def rearrange_functions_within_class(self, class_node: ast.ClassDef) -> ast.ClassDef:

        dependency_graph = assignment_build_dependency_graph_for_class(class_node)

        # Split nodes into various categories
        independent_assignments, dependent_assignments, properties, methods = [], [], [], []

        for inner_node in class_node.body:
            if isinstance(inner_node, ast.Assign) and isinstance(inner_node.targets[0], ast.Name):
                if not list(dependency_graph.predecessors(inner_node.targets[0].id)):
                    independent_assignments.append(inner_node)
                else:
                    dependent_assignments.append(inner_node)
            elif isinstance(inner_node, ast.FunctionDef):
                if has_property_decorators(inner_node):
                    properties.append(inner_node)
                else:
                    methods.append(inner_node)

        # Construct reordered body
        class_node.body = [
            *independent_assignments,
            ast.Expr(ast.Str(s="# Properties #\n# ---------- #")),
            *properties,
            ast.Expr(ast.Str(s="# Instance Methods #\n# ---------------- #")),
            *methods,
            *dependent_assignments
        ]
        
        return class_node

    def rearrange_class_in_source(self, source_code: str) -> str:
        tree = ast.parse(source_code)
        reordered_nodes = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                reordered_nodes.append(self.rearrange_functions_within_class(node))
            else:
                reordered_nodes.append(node)

        tree.body = reordered_nodes
        return ast.unparse(tree)

    def format_file(self, filename: str) -> bool:
        if FILE_PATTERN.match(filename) is None:
            return False

        try:
            with open(filename, "r", encoding="utf-8") as f:
                original_code = f.read()

            if not original_code.strip():
                return False

            reordered_code = self.rearrange_class_in_source(original_code)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(reordered_code)
            return True

        except SyntaxError:
            print(f"Error: The provided file '{filename}' does not contain valid Python code.")
            return False
