from typing import List

from tabulate import tabulate

from models.image import Image


class Statistics:
    def __init__(self, images: List[Image]):
        self.__images = images

    def create_statistics(self) -> str:
        """
        Creates a table with statistics about the download in markdown.
        :return: A table with statistics about the download in markdown.
        """
        data = []
        for image in self.__images:
            data.append([
                image.index,
                image.prompt[:50],
                image.page_url,
                image.is_success,
                image.reason,
                image.attempts,
                image.is_thumbnail
            ])
        table_str = tabulate(
            data,
            headers=["Index", "Prompt", "Page URL", "Success", "Reason", "Attempts", "Thumbnail"],
            tablefmt='pipe'
        )
        return table_str
