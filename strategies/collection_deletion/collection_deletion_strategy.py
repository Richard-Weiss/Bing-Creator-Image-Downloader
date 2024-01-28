import abc
from typing import List

from models.image import Image


class CollectionDeletionStrategy(abc.ABC):
    """
    Abstract base class for deleting collections.
    """

    @abc.abstractmethod
    def delete_collection(self, images: List[Image]) -> None:
        """
        Abstract method for deleting collections.
        """
