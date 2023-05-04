"""Docstring formatter for fixing ivy.array output style."""

import re

import black

from ivy_lint.formatters import BaseDocstringFormatter
from ivy_lint.strings import find_closing_parentheses


class IvyArrayDocstringFormatter(BaseDocstringFormatter):
    """
    Docstring formatter for fixing ivy.array output style.

    It checks for code examples that have `ivy.array` as it's output and
    formats its content to be more readable.
    """

    def _do_format_section(self, section: str) -> str:
        if not self._get_section_title(section).startswith("Example"):
            return super()._do_format_section(section)

        # Split on inputs
        partitions = re.split(r"(^>>> .*\n(\.\.\. .*\n)*)", section, flags=re.MULTILINE)

        # Partitions should looke like
        # [title block, input block, remaining input, output block, ...]
        del partitions[2::3]

        for i in range(2, len(partitions), 2):
            # ivy.array should exist somewhere in the output
            # The output is not seperated by a blank line from the input
            if partitions[i].startswith("\n"):
                continue

            output = partitions[i].split("\n\n", 1)[0]
            if "ivy.array(" not in output:
                continue

            new_output_parts = []
            pointer = 0
            while pointer < len(partitions[i]):
                found = partitions[i].find("ivy.array(", pointer)
                comment = partitions[i].find("\n\n", pointer)
                if found == -1 or (comment != -1 and found > comment):
                    new_output_parts.append(partitions[i][pointer:])
                    break
                new_output_parts.append(partitions[i][pointer:found])
                closing = find_closing_parentheses(partitions[i], found + 10)
                pointer = closing + 1

                code = black.format_str(
                    partitions[i][found : closing + 1], mode=black.Mode(line_length=50)
                ).strip()

                if "\n" in code:
                    # Find how many characters from the start of the line to found
                    # This is used to indent the code
                    indent = found - partitions[i].rfind("\n", 0, found) - 1
                    code = code.replace("\n", "\n" + indent * " ")

                new_output_parts.append(code)

            partitions[i] = "".join(new_output_parts)

        return "".join(partitions)
