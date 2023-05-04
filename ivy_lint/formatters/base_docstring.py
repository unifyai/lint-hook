"""Base Ivy docstring formatter."""

from abc import ABC
import tokenize
from typing import List, Tuple
import re

import untokenize


class BaseDocstringFormatter(ABC):
    """Docstring formatter for ivy docstring style."""

    STR_QUOTE_TYPES = (
        '"""',
        "'''",
    )
    RAW_QUOTE_TYPES = (
        'r"""',
        'R"""',
        "r'''",
        "R'''",
    )
    UCODE_QUOTE_TYPES = (
        'u"""',
        'U"""',
        "u'''",
        "U'''",
    )
    QUOTE_TYPES = STR_QUOTE_TYPES + RAW_QUOTE_TYPES + UCODE_QUOTE_TYPES

    def __init__(self, filenames: List[str]):
        self.filenames = filenames

    def format(self) -> bool:
        """
        Format docstrings in files.

        Returns
        -------
        changed
            True if any file was changed, False otherwise.
        """
        changed = False

        for filename in self.filenames:
            changed = self._format_file(filename) or changed

        return changed

    def _format_file(self, filename: str) -> bool:
        """
        Format individual file.

        Returns
        -------
        ret
            True if file was changed, False otherwise.
        """
        file = open(filename, "r", encoding="utf-8")

        modified_tokens = []

        previous_token_type = None
        only_comments_so_far = True
        changed = False

        try:
            for (
                token_type,
                token_string,
                start,
                end,
                line,
            ) in tokenize.generate_tokens(file.readline):
                new_token_string = token_string
                try:
                    if (
                        token_type == tokenize.STRING
                        and token_string.startswith(self.QUOTE_TYPES)
                        and (
                            previous_token_type == tokenize.INDENT
                            or previous_token_type == tokenize.NEWLINE
                            or only_comments_so_far
                        )
                    ):
                        indentation = " " * (len(line) - len(line.lstrip()))
                        new_token_string = self._do_format_docstring_node(
                            indentation,
                            token_string,
                        )
                        if not changed and new_token_string != token_string:
                            changed = True
                except Exception as e:
                    print(
                        "Error formatting docstring in"
                        f" {filename}:{start[0]}:{start[1]}: {e}"
                    )
                    new_token_string = token_string
                    changed = True

                if token_type not in [
                    tokenize.COMMENT,
                    tokenize.NEWLINE,
                    tokenize.NL,
                ]:
                    only_comments_so_far = False

                previous_token_type = token_type
                modified_tokens.append((token_type, new_token_string, start, end, line))

            file.close()

            if changed:
                formatted_code = untokenize.untokenize(modified_tokens)

                with open(filename, "w", encoding="utf-8") as file:
                    file.write(formatted_code)

        except tokenize.TokenError:
            file.close()

        return changed

    def _do_format_docstring_node(self, indentation: str, token_string: str) -> str:
        """
        Format docstring node.

        Parameters
        ----------
        indentation: str
            The indentation of the docstring.
        token_string: str
            The docstring itself.

        Returns
        -------
        token_string_formatted: str
            The docstring formatted.
        """
        contents, open_quote = self._do_strip_docstring(len(indentation), token_string)

        # Skip if there are nested triple double quotes
        if contents.count(self.QUOTE_TYPES[0]):
            return token_string

        contents = self._do_format_docstring(contents)

        # If the docstring is only contains summary format it as a single line
        if (
            len(contents.split("\n\n")) == 1
            and len(self._do_split_sections(contents)) == 1
        ):
            contents = contents.replace("\n", f"\n{indentation}").strip()
            return f"{open_quote}{contents}{open_quote}"

        contents = indentation + contents.replace("\n", f"\n{indentation}")

        # Strip trailing whitespace for every line
        contents = "\n".join([line.rstrip() for line in contents.split("\n")])

        return f'{open_quote}\n{contents}\n{indentation}"""'

    def _do_strip_docstring(self, indentation: int, docstring: str) -> Tuple[str, str]:
        """
        Return contents of docstring and opening quote type.

        Strips the docstring of its triple quotes, trailing white space,
        and line returns. Determines type of docstring quote (either string,
        raw, or unicode) and returns the opening quotes, including the type
        identifier, with single quotes replaced by double quotes.

        Parameters
        ----------
        docstring: str
            The docstring, including the opening and closing triple quotes.

        indentation: int
            The indentation of the docstring to be removed.

        Returns
        -------
        (docstring, open_quote) : tuple
            The docstring with the triple quotes removed.
            The opening quote type with single quotes replaced by double
            quotes.
        """
        docstring = docstring.strip()

        for quote in self.QUOTE_TYPES:
            if quote in self.RAW_QUOTE_TYPES + self.UCODE_QUOTE_TYPES and (
                docstring.startswith(quote) and docstring.endswith(quote[1:])
            ):
                return docstring.split(quote, 1)[1].rsplit(quote[1:], 1)[
                    0
                ].strip().replace("\n" + indentation * " ", "\n"), quote.replace(
                    "'", '"'
                )
            elif docstring.startswith(quote) and docstring.endswith(quote):
                return docstring.split(quote, 1)[1].rsplit(quote, 1)[0].strip().replace(
                    "\n" + indentation * " ", "\n"
                ), quote.replace("'", '"')

        raise ValueError(
            "docformatter only handles triple-quoted (single or double) strings"
        )

    def _do_split_sections(self, docstring: str) -> List[Tuple[str, str]]:
        """
        Return the docstring split into sections.

        Parameters
        ----------
        docstring: str
            The cleaned docstring.

        Returns
        -------
        docstring_sections: List[Tuple[str, str]]
            The docstring split into sections.

            Each section is a tuple of the form (title, contents).
        """
        # Find section titles and split the docstring into sections
        # Section titles are lines followed by a line of dashes
        sections = re.split(r"(^.+\n-+\n)", docstring, flags=re.MULTILINE)

        # Because of how re.split works, there will be an empty string after every
        # section title if the section is actually empty (i.e. no special cases)
        sections = [""] + sections  # Empty title for first section

        return [(sections[i], sections[i + 1]) for i in range(0, len(sections), 2)]

    def _get_section_title(self, section: str) -> str:
        """
        Return the title of the section.

        Parameters
        ----------
        section: str
            The section.

        Returns
        -------
        title: str
            The title of the section.
        """
        return section.split("\n", 1)[0].strip()

    def _do_format_docstring(self, docstring: str) -> str:
        """
        Return formatted version of docstring.

        Parameters
        ----------
        docstring: str
            The cleaned docstring.

        Returns
        -------
        docstring_formatted: str
            The docstring formatted.
        """
        # If it's needed, we can implement a method for splitting summary and
        # description
        sections = self._do_split_sections(docstring)

        formatted_sections = [self._do_format_summary_and_description(sections[0][1])]
        formatted_sections.extend(
            [
                self._do_format_section(title + section)
                for title, section in sections[1:]
            ]
        )

        return "".join(formatted_sections)

    def _do_format_section(self, section: str) -> str:
        """
        Return formatted version of section.

        Parameters
        ----------
        section: str
            The section.

        Returns
        -------
        section_formatted: str
            The section formatted.
        """
        return section

    def _do_format_summary_and_description(self, summary_description: str) -> str:
        """
        Return formatted version of summary and description.

        Parameters
        ----------
        summary_description: str
            The summary and description.

        Returns
        -------
        summary_description_formatted: str
            The summary and description formatted.
        """
        return summary_description
