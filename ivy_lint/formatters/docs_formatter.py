import re
from ivy_lint.formatters import BaseFormatter

EXAMPLE_HEADER_PATTERN = re.compile(r'Functional Examples\n-{2,}')
BACKTICKS_PATTERN = re.compile(r'```')
EXAMPLES_SPACING_PATTERN = re.compile(r'(Examples\n-{2,}\n)([^`]*?)(\n\n|\Z)', re.DOTALL)

class DocsFormatter(BaseFormatter):
    
    def _format_examples_header(self, source_code: str) -> str:
        return EXAMPLE_HEADER_PATTERN.sub('Examples\n--------', source_code)

    def _format_examples_spacing(self, source_code: str) -> str:
        def fix_spacing(match):
            example = match.group(2)
            example = re.sub(r'\n{3,}', '\n\n', example)
            example = re.sub(r'\n(?=[^ \n])', '\n\n', example)
            example = re.sub(r'(?<=[^ \n])\n', '\n\n', example)
            return 'Examples\n--------\n' + example + match.group(3)

        return EXAMPLES_SPACING_PATTERN.sub(fix_spacing, source_code)

    def _format_remove_backticks(self, source_code: str) -> str:
        def remove_ticks(match):
            example = match.group(2)
            example = BACKTICKS_PATTERN.sub('', example)
            return 'Examples\n--------\n' + example + match.group(3)

        return EXAMPLES_SPACING_PATTERN.sub(remove_ticks, source_code)
        
    def _format_file(self, filename: str) -> bool:
        try:
            with open(filename, 'r', encoding="utf-8") as f:
                source_code = f.read()

            if not source_code.strip():
                return False

            source_code = self._format_examples_header(source_code)
            source_code = self._format_examples_spacing(source_code)
            source_code = self._format_remove_backticks(source_code)

            with open(filename, 'w', encoding="utf-8") as f:
                f.write(source_code)

        except Exception as e:
            print(f"Error while formatting '{filename}': {e}")
            return False
        return True

    def format(self) -> bool:
        changed = False
        for filename in self.filenames:
            changed = self._format_file(filename) or changed
        return changed
