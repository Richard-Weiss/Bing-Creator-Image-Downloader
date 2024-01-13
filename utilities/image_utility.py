import asyncio
import json
import logging
import re
from urllib.parse import unquote

import aiohttp
import piexif
import unicodedata

from utilities.network_utility import NetworkUtility
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
    async def get_detail_image(image_set_id: str, image_id: str, semaphore: asyncio.Semaphore) -> dict | None:
        """
        Fetches the detailed information for an image from the detail API.
        :param image_set_id: Supplied image set id to use in URL.
        :param image_id: Supplied image id to use in URL.
        :param semaphore: Semaphore to limit concurrency.
        :return: Dictionary containing relevant data or None if the request failed.
        """
        request_url = f"https://www.bing.com/images/create/detail/async/{image_set_id}/?imageId={image_id}"

        async with semaphore:
            async with aiohttp.ClientSession() as session:
                retry_client = NetworkUtility.create_retry_client(session, attempts=8, max_timeout=128)
                retry_client.retry_options.evaluate_response_callback = \
                    NetworkUtility.should_retry_get_detail_image
                async with retry_client.get(request_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'value' in data and data['value'] is not None:
                            images = data['value']
                            decoded_image_id = unquote(image_id)
                            detail_image_list = [img for img in images if img['imageId'] == decoded_image_id]
                            detail_image = images[0] if len(detail_image_list) == 0 else detail_image_list[0]
                            return detail_image
                    else:
                        logging.error(f"Failed to get detailed information for image: {image_set_id}/{image_id} "
                                      f"for Reason: {response.status}: {response.reason}.")

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
