import re
import ast
import networkx as nx
from typing import Tuple, List
import sys

import black

from ivy_lint.formatters import BaseFormatter

HEADER_PATTERN = re.compile(
    r"#\s?(-{0,3})\s?(Helpers|Main|API"
    r" Functions)\s?(-{0,3})\s?#\n#\s?(-{7,15})\s?#\n(?:\s*\n)*"
)
FILE_PATTERN = re.compile(
    r"(ivy/functional/frontends/(?!.*(?:config\.py|__init__\.py)$).*"
    r"|ivy_tests/test_ivy/(?!.*(?:__init__\.py|conftest\.py|helpers/.*|test_frontends/config/.*$)).*)"
)

EXTENDED_FILE_PATTERN = re.compile(
    r"(ivy/functional/backends/(?!.*(?:config\.py|__init__\.py)$).*"
    r"|ivy/functional/stateful/(?!.*(?:config\.py|__init__\.py)$).*"
    r"|ivy/functional/ivy/(?!.*(?:config\.py|__init__\.py)$).*)"
)


def class_build_dependency_graph(nodes_with_comments: List[Tuple[str, ast.AST]]) -> nx.DiGraph:
    """
    Build a class dependency graph based on class inheritance relationships.

    This function constructs a directed graph to represent class dependencies
    in the code. It identifies classes and their inheritance relationships and
    ensures that the inheritance hierarchy is respected.

    Parameters
    ----------
    nodes_with_comments
        A list of code nodes extracted from the source code.

    Returns
    -------
    A directed graph representing class dependencies.
    """
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
    """
    Check if the given code contains any of the specified names.

    Parameters
    ----------
    code
        The code string to search for names in.
    names
        A list of names to search for within the code.

    Returns
    -------
    True if any of the names are found in the code; otherwise, False.
    """
    return any(name in code for name in names)


def extract_names_from_assignment(node: ast.Assign) -> List[str]:
    """
    Extract variable names from an assignment node in an Abstract Syntax Tree (AST).

    This function takes an AST assignment node as input and recursively extracts
    variable names (identifiers) assigned within it. The function returns a list
    of the extracted variable names.

    Parameters
    ----------
    node
        The assignment node from the AST.

    Returns
    -------
    A list of variable names extracted from the assignment node.
    """
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


def assignment_build_dependency_graph(nodes_with_comments: List[Tuple[str, ast.AST]]) -> nx.DiGraph:
    """
    Build a directed graph to represent dependencies between variables in assignment statements.

    This function processes a list of nodes with comments and analyzes assignment statements to create a directed graph.
    The graph represents dependencies between variables, where an edge from variable A to variable B means
    that variable A is assigned a value that depends on variable B.

    Parameters
    ----------
    nodes_with_comments
        A list of tuples containing source code and corresponding AST nodes.

    Returns
    -------
    A directed graph (NetworkX DiGraph) that captures variable dependencies.
    """
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
    """
    Check if a given function definition has a 'composite' decorator.

    This function examines the decorator list of a function definition node to determine if it contains a decorator
    with the name 'composite'.

    Parameters
    ----------
    node
        An Abstract Syntax Tree (AST) node representing a function definition.

    Returns
    -------
    True if the 'composite' decorator is found in the decorator list; otherwise, False.
    """
    return any(
        isinstance(decorator, ast.Attribute) and decorator.attr == "composite"
        for decorator in node.decorator_list
    )


def related_helper_function(assignment_name: str, nodes_with_comments: List[Tuple[str, ast.AST]]) -> str:
    """
    Find a related helper function or class based on the provided assignment_name.

    This function iterates through a list of nodes with comments (as returned by
    `_extract_all_nodes_with_comments` function) to find a related helper function or class
    based on the provided `assignment_name`.

    Parameters
    ----------
    assignment_name
        The name of the assignment that you want to find a related helper function for.
    nodes_with_comments
        A list of tuples, where each tuple contains a string of code and the corresponding AST node with comments.

    Returns
    -------
    The name of the related helper function or class if found, or None if none is found.
    """
    for _, node in nodes_with_comments:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and hasattr(node, "name"):
            if node.name.startswith("_") and contains_any_name(
                    ast.dump(node), [assignment_name]
            ):
                return node.name
    return None


def _is_assignment_target_an_attribute(node: ast.Assign) -> bool:
    """
    This function determines whether the assignment target in an assignment statement
    is an attribute of an object. It is used to distinguish between simple variable
    assignments and assignments to object attributes.

    Parameters
    ----------
    node
        The assignment node being analyzed.

    Returns
    -------
    True if the assignment target is an attribute, False otherwise.
    """
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                return True
    return False


class FunctionOrderingFormatter(BaseFormatter):
    def _remove_existing_headers(self, source_code: str) -> str:
        """
        Removes any existing header patterns from the provided source code.

        Parameters
        ----------
        source_code
            The original source code containing headers.

        Returns
        -------
        The source code with existing headers removed.
        """
        return HEADER_PATTERN.sub("", source_code)

    def _extract_node_with_leading_comments(
            self, node: ast.AST, source_code: str
    ) -> Tuple[str, ast.AST]:
        """
        Extracts the portion of the source code containing the leading comments of the provided node.
        It preserves the structure and leading comments for the specified node.

        Parameters
        ----------
        node
            The node for which the leading comments need to be extracted.
        source_code
            The complete source code containing the specified node and comments.

        Returns
        -------
        A tuple containing the extracted source code with leading comments
        and the corresponding node.

        Notes
        -----
        This function scans the source code to find the region of code that immediately precedes
        the provided node and captures the comments associated with it. It identifies the start and
        end lines of the comments and the node, then collects the lines with comments, if present,
        providing the extracted content for further processing.
        """
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
        """
        Extracts all nodes with their leading comments from the provided AST tree.

        This function calls `_extract_node_with_leading_comments` for each node in the tree.

        Parameters
        ----------
        tree
            The Abstract Syntax Tree (AST) representing the parsed source code.
        source_code
            The complete source code containing the nodes and their comments.

        Returns
        -------
        A list of tuples containing extracted source code with leading comments
        and their corresponding AST nodes.
        """
        return [
            self._extract_node_with_leading_comments(node, source_code)
            for node in tree.body
        ]

    def _rearrange_functions_and_classes(self, original_source_code: str, extended: bool) -> str:
        """
        Rearranges functions and classes in the provided source code following a specific order.

        This method utilizes multiple helper functions and custom sorting criteria to reorder the code
        based on class inheritance and dependencies.

        Parameters
        ----------
        original_source_code
            The source code to be reordered.

        extended
            To call the extended rearrange method

        Returns
        -------
        The reordered source code.
        """
        source_code = self._remove_existing_headers(original_source_code)

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

        def _is_assignment_dependent_on_assignment(node: ast.Assign) -> bool:
            """
            Checks if an assignment node is dependent on other assignments within the same scope.

            Parameters
            ----------
            node
                The assignment node to be checked.

            Returns
            -------
            True if the assignment depends on other assignments; otherwise, False.
            """
            if isinstance(node, ast.Assign):
                right_side_names = extract_names_from_assignment(node)
                return any(name in right_side_names for name in all_assignments)
            return False

        def _is_assignment_dependent_on_function_or_class(node: ast.Assign) -> bool:
            """
            Checks if an assignment node is dependent on functions or classes within the same scope.

            Parameters
            ----------
            node
                The assignment node to be checked.

            Returns
            -------
            True if the assignment depends on functions or classes; otherwise, False.
            """
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

        def sort_key(item: Tuple[str, ast.AST]) -> Tuple[float, int, str]:
            """
            Custom sorting key function for nodes.

            This function defines the sorting criteria for the nodes in the code. Nodes are sorted
            based on their characteristics to ensure a structured and organized code layout.

            Parameters
            ----------
            item
                The item containing source code and the associated AST node.

            Returns
            -------
            A tuple containing sorting criteria to determine the order of the nodes.
            - If the node represents an import statement, it receives the highest priority (0).
            - For try-except blocks containing imports, they are considered next (0, 1).
            - Assignments are sorted based on their dependencies and target names. The priority is
            determined as follows:
                - If the assignment is related to a helper function or class, it is given priority (6).
                - If the assignment involves attributes, it has slightly lower priority (5.5).
                - Assignments dependent on other assignments are ranked accordingly (7).
                - Assignments dependent on functions or classes are ranked below (6).
                - Other assignments follow with a priority of (1).
            - Class definitions are sorted based on the order of inheritance. Classes are prioritized based
            on their inheritance hierarchy.
            - Function definitions are categorized into "helper" and "api" functions. Helper functions or
            those with a "composite" decorator receive a higher priority (4), while main API functions
            receive slightly lower priority (5).
            - If a node does not match any of the above categories, it is sorted with the lowest priority (8).
            """
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
                            "\n\n# --- Helpers --- #\n# --------------- #\n"
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

        reordered_code = black.format_str(reordered_code, mode=black.Mode())

        if extended:
            return self._extended_rearrange_functions_and_classes(original_source_code, reordered_code, sort_key)
        return reordered_code

    def _extended_rearrange_functions_and_classes(self, original_source_code: str, reordered_code: str, sort_key) -> str:
        """
        Extends the _rearrange_functions_and_classes function to cater to both ivy and stateful files.

        This method utilizes the reordered code from _rearrange_functions_and_classes ensuring that classes, helpers and
        assignment ordering is maintained, however it reorders the main functions keeping the organizational structure
        typically found in ivy and stateful files.

        Parameters
        ----------
        original_source_code
            The original source code to be reordered.

        reordered_code
            The reordered_code from _rearrange_functions_and_classes.

        sort_key: the sort function from _rearrange_functions_and_classes

        Returns
        -------
        The reordered source code.
        """
        section_headers = [
            "# Array API Standard",
            "# Autograd",
            "# Optimizer Steps",
            "# Optimizer Updates",
            "# Array Printing",
            "# Device Queries",
            "# Retrieval",
            "# Conversions",
            "# Memory",
            "# Utilization",
            "# Availability",
            "# Default Device",
            "# Device Allocation",
            "# Function Splitting",
            "# Profiler",
        ]

        tree = ast.parse(original_source_code)
        nodes_with_comments = self._extract_all_nodes_with_comments(tree, original_source_code)

        sorted_sections = {}
        current_section = []
        current_header = ""
        for code, node in nodes_with_comments:
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("_") or has_st_composite_decorator(node):
                    continue
                for header in section_headers:
                    if code.strip().startswith(header):
                        current_header = header
                        current_section = []
                        break
                current_section.append((code, node))
                sorted_sections[current_header] = current_section

        for header, section in sorted_sections.items():
            sorted_section = sorted(section, key=sort_key)
            sorted_sections[header] = sorted_section

        reordered_code_list_main = []
        for header, section in sorted_sections.items():
            if header == "":
                reordered_code_list_main.extend(code for code, _ in section)
            else:
                header = header.strip("#")
                reordered_code_list_main.append(f"#{header}")
                pattern = re.compile(rf"\s?#{re.escape(header)}\s?#?")
                reordered_code_list_main.extend(pattern.sub("", code) for code, _ in section)

        tree = ast.parse(reordered_code)
        nodes_with_comments = self._extract_all_nodes_with_comments(tree, reordered_code)

        reordered_code_list_before = []
        reordered_code_list_after = []
        previous_was_main = False
        prev_was_assignment = False
        for code, node in nodes_with_comments:
            if isinstance(node, ast.Assign):
                if prev_was_assignment:
                    code = code.strip()
                if previous_was_main:
                    reordered_code_list_after.append(code)
                else:
                    reordered_code_list_before.append(code)
                prev_was_assignment = True
            elif isinstance(node, ast.FunctionDef):
                if node.name.startswith("_") or has_st_composite_decorator(node):
                    reordered_code_list_before.append(code)
                    continue
                if code.strip().startswith("# --- Main"):
                    previous_was_main = True
            else:
                reordered_code_list_before.append(code)

        reordered_code_list_before.extend(reordered_code_list_main)
        reordered_code_list_before.extend(reordered_code_list_after)
        reordered_code = "\n".join(reordered_code_list_before).strip()
        if not reordered_code.endswith("\n"):
            reordered_code += "\n"

        reordered_code = black.format_str(reordered_code, mode=black.Mode())
        return reordered_code

    def _format_file(self, filename: str) -> bool:
        """
        Formats the content of a Python file by reordering functions and classes.

        Parameters
        ----------
        filename
            The path to the Python file to be formatted.

        Returns
        -------
        True if formatting is successful, False otherwise.
        """
        if FILE_PATTERN.match(filename) or EXTENDED_FILE_PATTERN.match(filename):
            extended = True if EXTENDED_FILE_PATTERN.match(filename) else False
        else:
            return False
        try:
            with open(filename, "r", encoding="utf-8") as f:
                original_code = f.read()

            if not original_code.strip():
                return False

            reordered_code = self._rearrange_functions_and_classes(original_code, extended)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(reordered_code)

        except SyntaxError:
            print(
                f"Error: The provided file '{filename}' does not contain valid Python"
                " code."
            )
            return False
