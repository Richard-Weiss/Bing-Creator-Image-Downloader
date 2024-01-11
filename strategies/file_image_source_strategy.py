import asyncio
import logging
from asyncio import Semaphore
from datetime import timezone
from typing import List
from urllib.parse import unquote

import aiohttp
from dateutil import parser as dateutil_parser

from models.image import Image
from strategies.image_source_strategy import ImageSourceStrategy
from utilities.image_utility import ImageUtility
from utilities.network_utility import NetworkUtility


class FileImageSourceStrategy(ImageSourceStrategy):
    """
    Concrete strategy class for getting images from the images_clipboard.txt file.
    """

    async def get_images(self) -> List[Image]:
        logging.info(f"Fetching metadata of images...")
        image_id_list = await FileImageSourceStrategy.__get_image_ids_from_file()
        semaphore = Semaphore(250)
        tasks = [
            FileImageSourceStrategy.get_image_data(image_ids, semaphore, index)
            for index, image_ids
            in enumerate(image_id_list)
        ]
        images = await asyncio.gather(*tasks)
        images = [image for image in images if image is not None]

        return images

    @staticmethod
    async def get_image_data(image_ids, semaphore, index) -> Image:
        image_set_id = image_ids['image_set_id']
        image_id = image_ids['image_id']
        request_url = f"https://www.bing.com/images/create/detail/async/{image_set_id}/?imageId={image_id}"

        async with semaphore:
            async with aiohttp.ClientSession() as session:
                async with NetworkUtility.create_retry_client(session).get(request_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'value' in data and data['value'] is not None:
                            images = data['value']
                            unquoted_image_id = unquote(image_id)
                            response_image_list = [img for img in images if img['imageId'] == unquoted_image_id]
                            response_image = images[0] if len(response_image_list) == 0 else response_image_list[0]
                            image_urls = [
                                (1, response_image['contentUrl']),
                                (2, response_image['thumbnailUrl'])
                            ]
                            prompt = response_image['imageAltText']
                            page_url = response_image['hostPageUrl']
                            creation_date_string = response_image['datePublished']
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
                    else:
                        logging.error(f"Failed to get detailed information for image: {image_ids}"
                                      f" for Reason: {response.status}: {response.reason}.")

    @staticmethod
    async def __get_image_ids_from_file() -> List[dict]:
        with open("images_clipboard.txt", "r", encoding='utf8') as f:
            content = f.read().splitlines()
        image_url_list = [line for line in content if line.startswith("https://www.bing.com/images/create")]
        image_ids = [await ImageUtility.extract_set_and_image_id(url) for url in image_url_list]

        return image_ids
