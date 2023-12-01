import tokenize
from io import BytesIO
import re
import ast

from ivy_lint.formatters import BaseFormatter, BaseDocstringFormatter

class DocstringFormatter(BaseDocstringFormatter):
    def validate_section_name(self, section_name, VALID_SECTION_NAMES):
        if section_name not in VALID_SECTION_NAMES:
            raise ValueError(f"Invalid section name: {section_name}. Valid section names are {VALID_SECTION_NAMES}")
        
    def format_docstring(self, doc):
        """Formats a single docstring."""
        # Rename "Functional Examples" to "Examples" and format it without the extra newline
        doc = re.sub(r'(\s*)Functional Examples\n\1-*\n?', r'\1Examples\n\1--------\n', doc)
    
        # Ensure newline and correct indentation after "Examples" when it's already there
        doc = re.sub(r'(\s*)Examples\n\1--------\s*\n+([^\n])', r'\1Examples\n\1--------\n\2', doc)
        
        VALID_SECTION_NAMES = ["Args", "Arguments", "Attention", "Attributes", "Caution", "Danger", "Error", "Example", "Examples", "Hint", "Important", 
                               "Keyword Args", "Keyword Arguments", "Methods", "Note", "Notes", "Other Parameters", "Parameters", "Return", "Returns", 
                               "Raise", "Raises", "References", "See Also", "Tip", "Todo", "Warning", "Warnings", "Warn", "Warns", "Yield", "Yields"]
        
        # Identify code blocks
        lines = doc.split('\n')
        is_codeblock = False
        codeblock_start_lines = set()  # This will store indices of lines which start a code block
        lines_to_modify = set()  # This will store the indices of indented lines not containing "..."
        incorrect_sections = set()
        prev_line = ""
        is_codeblock_cont = False
        lb = 0
        rb = 0
        
        for idx, line in enumerate(lines):
            stripped_line = line.strip()
            
            if stripped_line.startswith('-') and stripped_line.endswith('-'):
                section_title = prev_line
                try:
                    self.validate_section_name(section_title, VALID_SECTION_NAMES)
                except ValueError as e:
                    incorrect_sections.add(idx)
                    
            if not is_codeblock and stripped_line.startswith('>>>'):
                is_codeblock = True
                codeblock_start_lines.add(idx)
            elif is_codeblock and not is_codeblock_cont and (not stripped_line or (not stripped_line.startswith(('>>>', '...')))):
                is_codeblock = False
                
            if is_codeblock:
                if stripped_line.startswith(('>>>')):
                    lb = rb = 0
                lb += line.count('(')
                rb += line.count(')')
                if rb >= lb:
                    rb = 0
                    lb = 0
                    is_codeblock_cont = False
                else:
                    lb = lb - rb
                    rb = 0
                    is_codeblock_cont = True
                if not stripped_line.startswith(('>>>', '...')):
                        lines_to_modify.add(idx) 
            prev_line = stripped_line
        
        # Add blank lines before code blocks
        formatted_lines = []
        skip = True
        indentation = 0
        for idx, line in enumerate(lines):
            if idx in codeblock_start_lines and formatted_lines and formatted_lines[-1].strip():  # Insert blank line before code block
                if not formatted_lines[-1].strip().startswith("-"):
                    skip = False
                elif skip:
                    skip = False
                    formatted_lines.append(line)
                    continue
                formatted_lines.append('')
            if idx in lines_to_modify:
                formatted_lines.append(line)
                indentation = len(formatted_lines[-2]) - len(formatted_lines[-2].lstrip())
                formatted_lines[-1] = (indentation * ' ') + '...' + line[indentation:]
                continue
            if idx in incorrect_sections:
                formatted_lines[-1] = "INCORRECT"
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
