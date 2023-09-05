import re
from ivy_lint.formatters import BaseFormatter

EXAMPLES_PATTERN = re.compile(
    r"(Examples\n[-]{2,}\n\n)(.*?)(\n\n|$)", re.DOTALL
)

class DocsFormatter(BaseFormatter):
    """Formatter for docstrings."""

    @staticmethod
    def correct_docstring(docstring: str) -> str:
        """Apply corrections to the given docstring."""
        docstring = re.sub(r'Functional Examples\n-{3,}', 'Examples\n--------', docstring)
        docstring = EXAMPLES_PATTERN.sub(DocsFormatter._fix_examples_section, docstring)
        return docstring

    @staticmethod
    def _fix_examples_section(match):
        """Reformat the Examples section of a docstring."""
        examples_section = match.group(2)
        lines = examples_section.split('\n')
        
        in_code_block = False
        new_lines = []

        for line in lines:
            if line.strip().startswith(">>>"):
                if not in_code_block:
                    new_lines.append("")
                    in_code_block = True
            elif in_code_block and not line.strip():
                in_code_block = False
                new_lines.append(line)
                continue

            new_lines.append(line)

        if in_code_block:
            new_lines.append("")

        return match.group(1) + '\n'.join(new_lines) + "\n"

    def _format_file(self, filename: str) -> bool:
        """Format the file by correcting its docstrings."""
        with open(filename, 'r', encoding='utf-8') as f:
            original_code = f.read()

        corrected_code = re.sub(r'(?P<doc>""".*?""")', lambda m: self.correct_docstring(m.group('doc')), original_code, flags=re.DOTALL)

        if corrected_code != original_code:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(corrected_code)
            return True

        return False
