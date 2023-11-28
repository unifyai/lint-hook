import tokenize
from io import BytesIO
import re
import ast

from ivy_lint.formatters import BaseFormatter, BaseDocstringFormatter

class DocstringFormatter(BaseDocstringFormatter):
    def format_docstring(self, doc):
        """Formats a single docstring."""
        # Rename "Functional Examples" to "Examples" and format it without the extra newline
        doc = re.sub(r'(\s*)Functional Examples\n\1-*\n?', r'\1Examples\n\1--------\n', doc)
    
        # Ensure newline and correct indentation after "Examples" when it's already there
        doc = re.sub(r'(\s*)Examples\n\1--------\s*\n+([^\n])', r'\1Examples\n\1--------\n\2', doc)
        
        # Identify code blocks
        lines = doc.split('\n')
        is_codeblock = False
        codeblock_start_lines = set()  # This will store indices of lines which start a code block
        lines_to_modify = set()  # This will store the indices of indented lines not containing "..."
        
        for idx, line in enumerate(lines):
            stripped_line = line.strip()
    
            if not is_codeblock and stripped_line.startswith('>>>'):
                is_codeblock = True
                codeblock_start_lines.add(idx)
            elif stripped_line.startswith(('[', '(')) or stripped_line.endswith((')', ',', '\\', '(', '[', ']')):
                lines_to_modify.add(idx)
            elif is_codeblock and (not stripped_line or (not stripped_line.startswith(('>>>', '...', '[', '(')) and not stripped_line.endswith((')', ',', '\\', '(', '[', ']')))):
                is_codeblock = False
        
        # Add blank lines before code blocks
        formatted_lines = []
        skip = True
        for idx, line in enumerate(lines):
            if idx in codeblock_start_lines and formatted_lines and formatted_lines[-1].strip():  # Insert blank line before code block
                if skip:
                    skip = False
                    formatted_lines.append(line)
                    continue
                formatted_lines.append('')
            if idx in lines_to_modify:
                formatted_lines.append(line)
                formatted_lines[-1] += ' ...' + line.lstrip()
                continue
            formatted_lines.append(line)
                
        return '\n'.join(formatted_lines)

    def format_all_docstrings(self, python_code):
        """Extracts all docstrings from the given Python code, formats them, and replaces the original ones with the formatted versions."""
        replacements = {}
        # Tokenize the code
        tokens = tokenize.tokenize(BytesIO(python_code.encode('utf-8')).readline)
        for token in tokens:
            if token.type == tokenize.STRING:
                original_docstring = token.string
                modified_docstring = self.format_docstring(original_docstring)
                formatted_docstring = self._do_format_docstring(modified_docstring)
                if original_docstring != formatted_docstring:  # Only add if there are changes
                    replacements[original_docstring] = formatted_docstring

        for original, formatted in replacements.items():
                python_code = python_code.replace(original, formatted, 1)  # Only replace once to be safe
            
        return python_code
        
    def _format_file(self, filename: str) -> bool:
        with open(filename, 'r') as file:
            original_content = file.read()

        formatted_content = self.format_all_docstrings(original_content)

        if original_content != formatted_content:
            with open(filename, 'w') as file:
                file.write(formatted_content)
            return True

        return False
