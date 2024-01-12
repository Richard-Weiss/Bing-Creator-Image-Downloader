import asyncio
import base64
import io
import json
import logging
import os
import re
from asyncio import Semaphore

import aiohttp
import requests
from PIL import Image as PIL_Image

from utilities.image_validator import ImageValidator
from utilities.network_utility import NetworkUtility


class CollectionImport:
    """
    This class is still WIP, but is used in the future to allow imports of collections from the collection_dict.
    """

    def __init__(self, collection_dict_filename):
        with open(collection_dict_filename, 'r') as f:
            self.__collection_dict = json.load(f)

    async def gather_images_to_collection(self) -> None:
        """
        Adds images from the collection_dict to a specified collection.
        Semaphore to prevent issues from overloading API like getting no backend response.
        :return: None
        """
        logging.info("Creating thumbnails...")
        item_list = await self.__construct_item_list()
        logging.info(f"Adding {len(item_list)} items to the collection...")
        semaphore = Semaphore(10)
        tasks = [self.add_image_to_collection(item, semaphore) for item in item_list]
        await asyncio.gather(*tasks)

    @staticmethod
    async def add_image_to_collection(item: dict, semaphore: asyncio.locks.Semaphore) -> None:
        """
        Adds a single image to the specified collection. The specified collection is hardcoded for now.
        :param item: The image from the collection_dict formatted for this request.
        :param semaphore: Used to regulate the maximum number of concurrent tasks.
        :return: None
        """
        async with semaphore:
            header = {
                "content-type": "application/json",
                "cookie": os.getenv('COOKIE'),
                "sid": "0"
            }
            body = {
                "Items": [item],
                "TargetCollection": {
                    "CollectionId": "3a165902d3a64b6c8f05f52ea2b830ee"
                }
            }
            async with (aiohttp.ClientSession() as session):
                retry_client = NetworkUtility.create_retry_client(session)
                retry_client.retry_options.evaluate_response_callback = \
                    NetworkUtility.should_retry_add_collection
                async with retry_client.post(
                        url='https://www.bing.com/mysaves/collections/items/add?sid=0',
                        headers=header,
                        data=json.dumps(body)
                ) as response:
                    logging.info(f"Adding image {item['ClickThroughUrl']} to the collection.")
                    try:
                        response_json = await response.json()
                    except requests.JSONDecodeError:
                        raise Exception(f"The request to add the item to the collection was unsuccessful:"
                                        f"{response.status}")
                    if response.status != 200 or not response_json['isSuccess']:
                        raise Exception(f"Adding item to collection failed with following response:"
                                        f"{response_json} for item:{item['ClickThroughUrl']}")

    async def __construct_item_list(self) -> list[dict]:
        """
        Creates a list of the images that should be added to the new collection in the required format.
        :return: A list of item dictionaries.
        """
        tasks = [CollectionImport.__convert_item_to_request_format(item['content'])
                 for collection in self.__collection_dict['collections']
                 if ImageValidator.should_add_collection_to_images(collection)
                 for item in collection['collectionPage']['items']
                 if ImageValidator.should_add_item_to_images(item)]
        items = await asyncio.gather(*tasks)

        return list(items)

    @staticmethod
    async def __convert_item_to_request_format(item: dict) -> dict:
        """
        Formats the item to fit the request format by changing the keys and fetching the thumbnail.
        The thumbnail size is hardcoded for now, as larger resolutions led to issues.
        :param item: Original item dictionary from collection_dict.
        :return: A new item dictionary in the required format.
        """
        thumbnail_raw = item['thumbnails'][0]['thumbnailUrl']
        thumbnail_pattern = r"(?P<raw_url>^[^&]+)&w=(?P<width>\d+)&h=(?P<height>\d+)"
        thumbnail_groups = re.search(thumbnail_pattern, thumbnail_raw)
        thumbnail_url = thumbnail_groups.group('raw_url')
        thumbnail_base64 = await CollectionImport.__get_thumbnail_base64(thumbnail_url)

        pattern = r'Image \d of \d$'
        title = re.sub(pattern, '', item['title'])
        custom_data = json.loads(item['customData'])
        custom_data['ToolTip'] = re.sub(pattern, '', custom_data['ToolTip'])
        item_dict = {
            "Title": title,
            "ClickThroughUrl": item['url'],
            "ContentId": item['contentId'],
            "ItemTagPath": item['itemTagPath'],
            "ThumbnailInfo": [{
                "Thumbnail": f"data:image/jpeg;base64,{thumbnail_base64}",
                "Width": 468,
                "Height": 468
            }],
            "CustomData": json.dumps(custom_data)
        }

        return item_dict

    @staticmethod
    async def __get_thumbnail_base64(thumbnail_url: str) -> str:
        """
        Gets the thumbnail from the url, resizes it and converts it to base64 for later usage.
        :param thumbnail_url: Url to fetch thumbnail from.
        :return: The fetched and resized thumbnail in base64.
        """
        async with aiohttp.ClientSession() as session:
            async with NetworkUtility.create_retry_client(session).get(thumbnail_url) as response:
                thumbnail_content = await response.read()
                img = PIL_Image.open(io.BytesIO(thumbnail_content))
                img.thumbnail((468, 468))
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG")
                thumbnail_base64 = str(base64.b64encode(buffered.getvalue()).decode('utf-8'))

        return thumbnail_base64
