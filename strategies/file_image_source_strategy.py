import asyncio
import logging
from asyncio import Semaphore
from datetime import timezone
from typing import List, Dict

from dateutil import parser as dateutil_parser

from utilities.config import Config
from models.image import Image
from strategies.image_source_strategy import ImageSourceStrategy
from utilities.image_utility import ImageUtility


class FileImageSourceStrategy(ImageSourceStrategy):
    """
    Concrete strategy class for getting images from the images_clipboard.txt file.
    """

    async def get_images(self) -> List[Image]:
        logging.info(f"Fetching metadata of images...")
        image_id_list = await FileImageSourceStrategy.__get_image_ids_from_file()
        semaphore = Semaphore(250)
        images = await self.get_image_data_retry(image_id_list, semaphore, Config().detail_max_attempts())
        images = [image for image in images if image is not None]

        return images

    @staticmethod
    async def get_image_data_retry(image_id_list: List[Dict], semaphore: Semaphore, attempts: int) -> List[Image]:
        """
        Tries to get all image data until there are no None values or all attempts were used.
        :param image_id_list: List of dictionaries containing the image_set_id and image_id.
        :param semaphore: Used to regulate the maximum number of concurrent tasks.
        :param attempts: How many times to retry.
        :return: A list of :class:`Image` objects
        """
        current_images = await FileImageSourceStrategy.gather_images(image_id_list, semaphore)
        attempts_made = 1
        while None in current_images and attempts_made < attempts:
            logging.warning(f"Failed to get detailed information for some images."
                            f"Retrying ({attempts_made}) and merging...")
            new_images = await FileImageSourceStrategy.gather_images(image_id_list, semaphore)
            result = map(
                lambda current_image, new_image: current_image if current_image is not None else new_image,
                current_images,
                new_images
            )
            current_images = list(result)
            attempts_made += 1
        return current_images

    @staticmethod
    async def gather_images(image_id_list: List[Dict], semaphore: Semaphore) -> List[Image]:
        """
        Gathers all images from the image_id_list.
        :param image_id_list: List of dictionaries containing the image_set_id and image_id.
        :param semaphore: Used to regulate the maximum number of concurrent tasks.
        :return: List of :class:`Image` objects.
        """
        tasks = [
            FileImageSourceStrategy.get_image_data(image_ids, semaphore, index)
            for index, image_ids
            in enumerate(image_id_list)
        ]
        images = await asyncio.gather(*tasks)
        return list(images)

    @staticmethod
    async def get_image_data(image_ids, semaphore, index) -> Image | None:
        """
        Gathers all necessary data and creates an :class:`Image` object.
        :param image_ids: A dictionary containing the image_set_id and image_id.
        :param semaphore: Used to regulate the maximum number of concurrent tasks.
        :param index: Index the image should have.
        :return: An :class:`Image` object or None
        """
        image_set_id = image_ids['image_set_id']
        image_id = image_ids['image_id']
        detail_image = await ImageUtility.get_detail_image(image_set_id, image_id, semaphore)
        if detail_image is not None:
            image_urls = [
                (1, detail_image['contentUrl']),
                (2, detail_image['thumbnailUrl'])
            ]
            prompt = detail_image['imageAltText']
            page_url = detail_image['hostPageUrl']
            creation_date_string = detail_image['datePublished']
            creation_date_object = dateutil_parser.parse(creation_date_string).astimezone(timezone.utc)
            creation_date = creation_date_object.strftime('%Y-%m-%dT%H%MZ')
            return Image(
                image_urls=image_urls,
                prompt=prompt,
                index=str(index + 1).zfill(4),
                page_url=page_url,
                creation_date=creation_date
            )
        else:
            logging.error(f"Failed to get detailed information for image: {image_ids}"
                          f" for Reason: API response is missing data.")

    @staticmethod
    async def __get_image_ids_from_file() -> List[dict]:
        with open("images_clipboard.txt", "r", encoding='utf8') as f:
            content = f.read().splitlines()
        image_url_list = [line for line in content if line.startswith("https://www.bing.com/images/create")]
        image_ids = [await ImageUtility.extract_set_and_image_id(url) for url in reversed(image_url_list)]

        return image_ids
