"""String utilities for ivy_lint."""


def find_closing_parentheses(string: str, start: int) -> int:
    """
    Return the index of the closing parentheses.

    Parameters
    ----------
    string: str
        The string to search.

    start: int
        The index of the opening parentheses.

    Returns
    -------
    end: int
        The index of the closing parentheses.
    """
    count = 1
    for i in range(start + 1, len(string)):
        if string[i] == "(":
            count += 1
        elif string[i] == ")":
            count -= 1
            if count == 0:
                return i

    start_line = string.rfind("\n", 0, start)
    end_line = string.find("\n", start)
    if start_line == -1:
        start_line = 0
    if end_line == -1:
        end_line = len(string)
    raise ValueError(f"No closing parentheses found for {string[start_line:end_line]}")
