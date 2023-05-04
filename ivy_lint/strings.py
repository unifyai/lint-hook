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
    raise ValueError("No closing parentheses found")
