"""
Abstract base class for data formats, defining interface for import/export.
"""
import pathlib
from abc import ABC, abstractmethod


class BaseDataFormat(ABC):
    """
    Abstract base class for data formats.
    Defines the interface for loading and saving data in specific formats.
    """

    @abstractmethod
    def load(self, file_path: str|pathlib.Path|None = None) -> int:
        """
        Load data from the source. 
        If file_path is None, use the default path set during initialization.
        Returns the number of records loaded.
        """
        pass

    @abstractmethod
    def save(self, file_path: str|pathlib.Path|None = None) -> int:
        """
        Save data to the destination.
        If file_path is None, use the default path set during initialization.
        Returns the number of records saved.
        """
        pass