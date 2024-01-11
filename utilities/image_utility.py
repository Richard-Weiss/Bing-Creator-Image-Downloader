import json
import re

import piexif
import unicodedata

from strategies.image_source_strategy import ImageSourceStrategy
from models.image import Image


class ImageUtility:
    """
    Contains functions that don't need a class instance.
    """

    @staticmethod
    async def extract_set_and_image_id(url: str) -> dict:
        """
        Extracts the image set and image id from the image page url.
        :param url: The image page url i.e. https://www.bing.com/images/create/$prompt/$imageSetId?id=$imageId.
        :return: A dictionary containing the image_set_id and image_id.
        """
        pattern = r"(?P<image_set_id>(?<=\/)(?:\d\-)?[a-f0-9]{32})(?:\?id=)(?P<image_id>(?<=\?id=)[^&]+)"
        result = re.search(pattern, url)
        image_set_id = result.group('image_set_id')
        image_id = result.group('image_id')
        id_dict = {'image_set_id': image_set_id, 'image_id': image_id}

        return id_dict

    @staticmethod
    def get_image_source_strategy(setting: str) -> ImageSourceStrategy:
        """
        Returns the correct image source strategy based on the supplied method.
        :param setting: The method to get images from.
        :return: The correct image source strategy.
        """
        if setting == 'api':
            from strategies.api_image_source_strategy import APIImageSourceStrategy
            return APIImageSourceStrategy()
        elif setting == 'file':
            from strategies.file_image_source_strategy import FileImageSourceStrategy
            return FileImageSourceStrategy()
        else:
            raise Exception(f"Invalid image source setting: {setting}")

    @staticmethod
    async def add_exif_metadata(image: Image) -> None:
        """
        Adds the prompt, image url and creation date to the image as EXIF metadata in JSON format.
        :param image: :class:`BingCreatorImage` object containing the properties to save.
        :return: None
        """
        with open(image.file_name, 'rb') as f:
            exif_dict = piexif.load(f.read())
            user_comment = {
                'prompt': image.prompt,
                'image_url': image.used_image_url,
                'creation_date': image.creation_date
            }
            user_comment_utf_8 = json.dumps(user_comment, ensure_ascii=False).encode("utf-8")
            exif_dict['Exif'][piexif.ExifIFD.UserComment] = user_comment_utf_8
            user_comment_utf_16le = json.dumps(user_comment, ensure_ascii=False).encode('utf-16le')
            exif_dict['0th'][piexif.ImageIFD.XPComment] = user_comment_utf_16le
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, image.file_name)

    @staticmethod
    async def slugify(text: str) -> str:
        """
        Convert spaces or repeated dashes to single dashes. Remove characters that aren't alphanumerics,
        underscores, or hyphens. Convert to lowercase. Also strip leading and
        trailing whitespace, dashes, and underscores.
        Source: https://github.com/django/django/blob/main/django/utils/text.py
        :param text: The text that should be slugged.
        :return: The slugged text.
        """
        text = (
            unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        )
        text = re.sub(r"[^\w\s-]", "", text.lower())
        return re.sub(r"[-\s]+", "-", text).strip("-_")
