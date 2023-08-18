"""Base Ivy formatter."""

from abc import ABC, abstractmethod
from typing import List


class BaseFormatter(ABC):
    """Base formatter for ivy style."""

    def __init__(self, filenames: List[str]) -> None:
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

    @abstractmethod
    def _format_file(self, filename: str) -> bool:
        """
        Format individual file.

        Returns
        -------
        ret
            True if file was changed, False otherwise.
        """
        raise NotImplementedError
