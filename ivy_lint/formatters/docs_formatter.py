import re
from ivy_lint.formatters import BaseFormatter


class DocstringFormatter(BaseFormatter):
    """Formatter for correcting docstrings following ivy style."""
    
    # Patterns to identify and correct issues
    INCORRECT_EXAMPLES_PATTERN = re.compile(r'Functional Examples(?=:)', re.IGNORECASE)
    EXAMPLES_BLANK_SPACE_PATTERN = re.compile(r'(?<=Examples:)\n*?(>>>[^\n]*?\n[^\n]*?)\n*?(?=\w|$)', re.DOTALL)
    BACKTICKS_PATTERN = re.compile(r'(Examples:.*?)(```\s*?>>>.*?```)', re.DOTALL)
    
    def _fix_examples_title(self, content: str) -> str:
        return self.INCORRECT_EXAMPLES_PATTERN.sub("Examples", content)
    
    def _fix_examples_format_for_sphinx(self, content: str) -> str:
        def repl(match):
            example = match.group(1).strip()
            example = re.sub(r'\n+', '\n', example)  # Remove multiple newlines
            return f'\n\n{example}\n'
        
        return self.EXAMPLES_BLANK_SPACE_PATTERN.sub(repl, content)

    def _remove_backticks_from_examples(self, content: str) -> str:
        def repl(match):
            return match.group(1) + match.group(2).replace('```', '').strip()

        
        return self.BACKTICKS_PATTERN.sub(repl, content)

    def _format_file(self, filename: str) -> bool:
        with open(filename, 'r', encoding='utf-8') as f:
            original_content = f.read()

        formatted_content = self._fix_examples_title(original_content)
        formatted_content = self._fix_examples_format_for_sphinx(formatted_content)
        formatted_content = self._remove_backticks_from_examples(formatted_content)

        # Check if the file was changed
        if formatted_content != original_content:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            return True

        return False