import abc
from typing import List

from models.image import Image


class ImageSourceStrategy(abc.ABC):
    """
    Abstract base class for image source strategies.
    """

    @abc.abstractmethod
    async def get_images(self) -> List[Image]:
        """
        Abstract method for getting images.
        :return: A list containing :class:`Image` objects.
        :rtype: List[Image]
        """
