import asyncio
import base64
import io
import json
import logging
import os
import re
import string
import sys
import time
import tomllib
import zipfile
from dataclasses import dataclass
from datetime import date
from datetime import timezone
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from typing import List, Tuple
from urllib.parse import unquote

import aiofiles
import aiofiles.tempfile
import aiohttp
import aiohttp.hdrs
import aiohttp_retry
import piexif
import requests
import unicodedata
from PIL import Image
from aiohttp_retry import ExponentialRetry
from aiohttp_retry import RetryClient
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from tabulate import tabulate
from urllib3 import Retry


@dataclass
class BingCreatorImage:
    """
    This class is used to represent a single image and its properties.
    """
    image_urls: List[Tuple[int, str]]
    index: str
    prompt: str
    collection_name: str
    page_url: str
    date_modified: str
    creation_date: str = None
    used_image_url: str = None
    file_name: str = None
    is_thumbnail: bool = False
    is_success: bool = False
    reason: str = None
    attempts: int = 0


class BingCreatorImageDownload:
    """
    This class is used to download all images from the supplied collections.
    It gathers all the necessary data from the collections and downloads the images from them.
    """

    def __init__(self):
        self.__images: List[BingCreatorImage] = []
        self.total_image_count = 0
        self.successful_image_count = 0

    @property
    def images(self):
        return self.__images

    async def run(self):
        """
        High level method that serves as the entry point.
        :return: None
        """
        self.__images = self.__gather_image_data()
        self.total_image_count = len(self.__images)
        await self.__set_additional_data()
        await self.__download_and_zip_images()

    @staticmethod
    def __gather_image_data() -> List[BingCreatorImage]:
        """
        Gathers all necessary data for each image from all collections.
        :return: A list containing :class:`BingCreatorImage` objects.
        :rtype: List[BingCreatorImage]
        """
        logging.info(f"Fetching metadata of collections...")
        header = {
            "Content-Type": "application/json",
            "cookie": os.getenv('COOKIE'),
            "sid": "0"
        }
        body = {
            "collectionItemType": "all",
            "maxItemsToFetch": 10000,
            "shouldFetchMetadata": True
        }
        response = BingCreatorNetworkUtility.create_session().post(
            url='https://www.bing.com/mysaves/collections/get?sid=0',
            headers=header,
            data=json.dumps(body)
        )
        if response.status_code == 200:
            collection_dict = response.json()
            if len(collection_dict['collections']) == 0:
                raise Exception('No collections were found for the given cookie.')
            gathered_image_data = []
            index = 1
            for collection in collection_dict['collections']:
                if BingCreatorImageValidator.should_add_collection_to_images(collection):
                    if config['debug']['debug']:
                        with open('collection_dict_dump_debug.json', 'w') as f:
                            f.write(json.dumps(collection))
                    for item in collection['collectionPage']['items']:
                        if BingCreatorImageValidator.should_add_item_to_images(item):
                            custom_data = json.loads(item['content']['customData'])
                            image_page_url = custom_data['PageUrl']
                            image_url = custom_data['MediaUrl']
                            image_prompt = custom_data['ToolTip']
                            date_modified = item['dateModified']
                            collection_name = collection['title']
                            image_urls = [(1, image_url)]
                            if 'thumbnails' in item['content']:
                                thumbnail_raw = item['content']['thumbnails'][0]['thumbnailUrl']
                                thumbnail_url = re.match('^[^&]+', thumbnail_raw).group(0)
                                image_urls.append((3, thumbnail_url))
                            pattern = r'Image \d of \d$'
                            image_prompt = re.sub(pattern, '', image_prompt)
                            image = BingCreatorImage(
                                image_urls=image_urls,
                                prompt=image_prompt,
                                collection_name=collection_name,
                                page_url=image_page_url,
                                index=str(index).zfill(4),
                                date_modified=date_modified
                            )
                            gathered_image_data.append(image)
                            index += 1
            return gathered_image_data
        else:
            raise Exception(f"Fetching collection failed with Error code "
                            f"{response.status_code}: {response.reason};{response.text}")

    async def __download_and_zip_images(self) -> None:
        """
        Downloads all images from the gathered image data and zips them.
        :return: None
        """
        logging.info(f"Starting download of {len(self.__images)} images.")
        with zipfile.ZipFile(f"bing_images_{date.today()}.zip", "w") as zip_file:
            async with aiofiles.tempfile.TemporaryDirectory('wb') as temp_dir:
                tasks = [
                    self.__download_and_save_image(image, temp_dir)
                    for image
                    in self.__images
                ]
                await asyncio.gather(*tasks)
                successful_images = [image for image in self.__images if image.is_success]
                self.successful_image_count = len(successful_images)
                for image in successful_images:
                    zip_file.write(
                        filename=image.file_name,
                        arcname=os.path.join(image.collection_name, os.path.basename(image.file_name))
                    )

    @staticmethod
    async def __download_and_save_image(
            image: BingCreatorImage,
            temp_dir: aiofiles.tempfile.TemporaryDirectory) -> None:
        """
        Downloads an image using the urls in the supplied image.
        :param image: :class:`BingCreatorImage` containing the necessary properties.
        :param temp_dir: The directory to save files to before zipping.
        :return: None
        """
        try:
            async with aiohttp.ClientSession() as session:
                for index, (_, url) in enumerate(image.image_urls):
                    async with BingCreatorNetworkUtility.create_retry_client(session).get(url) as response:
                        logging.info(f"Downloading image #{image.index} from: {url}")
                        image.attempts = image.attempts + 1
                        if response.status == 200:
                            filename_image_prompt = await BingCreatorImageUtility.slugify(image.prompt)
                            if config['filename']['use_local_time_zone']:
                                creation_date = dateutil_parser.parse(image.creation_date) \
                                    .astimezone() \
                                    .strftime('%Y-%m-%dT%H%M%z')
                            else:
                                creation_date = image.creation_date
                            file_name_substitute_dict = {
                                'date': creation_date,
                                'index': image.index,
                                'prompt': filename_image_prompt[:50],
                                'sep': '_'
                            }
                            template = string.Template(config['filename']['filename_pattern'])
                            file_name_formatted = template.safe_substitute(file_name_substitute_dict)
                            image_bytes = await response.read()
                            with Image.open(io.BytesIO(image_bytes)) as pil_image:
                                image_width = pil_image.width
                            if image_width < 1024:
                                file_name_formatted += '_T'
                                image.is_thumbnail = True
                            filename = f"{temp_dir}{os.sep}{file_name_formatted}.jpg"

                            async with aiofiles.open(filename, "wb") as f:
                                await f.write(image_bytes)

                            image.used_image_url = str(response.url)
                            image.file_name = filename
                            await BingCreatorImageUtility.add_exif_metadata(image)
                            logging.info(f"Successfully downloaded image #{image.index} from: {url}.")
                            image.is_success = True
                            image.reason = response.reason
                            return
                        else:
                            warning_output = (f"Image #{image.index}: Failed to download {url} "
                                              f"for Reason: {response.status}: {response.reason}")
                            if index != len(image.image_urls) - 1:
                                warning_output += " -> Retrying with next URL."
                            logging.warning(warning_output)
                    image.reason = response.reason
            logging.error(f"Image #{image.index}: Failed to download from any sources.")
        except Exception as e:
            logging.error(e)

    async def __set_additional_data(self) -> None:
        """
        Sets the creation date and adds additional fetch URLs for each image.
        :return: None
        """
        tasks = [
            BingCreatorImageUtility.set_additional_data(image)
            for image
            in self.__images
        ]
        await asyncio.gather(*tasks)


class BingCreatorImageUtility:
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
    async def set_additional_data(image: BingCreatorImage) -> None:
        """
        Fetches and sets additional data from the detail API.
        :param image: :class:`BingCreatorImage` object to set the `creation_date` value for.
        :return: None
        """
        extracted_ids = await BingCreatorImageUtility.extract_set_and_image_id(image.page_url)
        image_set_id = extracted_ids['image_set_id']
        image_id = extracted_ids['image_id']
        request_url = f"https://www.bing.com/images/create/detail/async/{image_set_id}/?imageId={image_id}"

        async with aiohttp.ClientSession() as session:
            async with BingCreatorNetworkUtility.create_retry_client(session).get(request_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'value' in data:
                        images = data['value']
                        decoded_image_id = unquote(image_id)
                        response_image_list = [img for img in images if img['imageId'] == decoded_image_id]
                        response_image = images[0] if len(response_image_list) == 0 else response_image_list[0]
                        creation_date_string = response_image['datePublished']
                        if not any(response_image['contentUrl'] == url for _, url in image.image_urls):
                            image.image_urls.append((2, response_image['contentUrl']))
                        if not any(response_image['thumbnailUrl'] == url for _, url in image.image_urls):
                            image.image_urls.append((4, response_image['thumbnailUrl']))
                        image.image_urls = sorted(image.image_urls, key=lambda url: url[0])
                    else:
                        creation_date_string = image.date_modified
                    creation_date_object = dateutil_parser.parse(creation_date_string).astimezone(timezone.utc)
                    creation_date_string_formatted = creation_date_object.strftime('%Y-%m-%dT%H%MZ')
                    image.creation_date = creation_date_string_formatted
                else:
                    logging.error(f"Failed to get detailed information for image: {image.page_url} "
                                  f"for Reason: {response.status}: {response.reason}.")
                    image.creation_date = dateutil_parser.parse(date.today().isoformat()) \
                        .astimezone() \
                        .strftime('%Y-%m-%dT%H%M%z')

    @staticmethod
    async def add_exif_metadata(image: BingCreatorImage) -> None:
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
        :param text: The text that should be normalized.
        :return: The normalized text.
        """
        text = (
            unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        )
        text = re.sub(r"[^\w\s-]", "", text.lower())
        return re.sub(r"[-\s]+", "-", text).strip("-_")


class BingCreatorNetworkUtility:
    """
    Different request related functions.
    """

    @staticmethod
    def create_session() -> requests.Session:
        """
        Create a new request.Session with retry.
        :return: A new request.Session with retry.
        """
        session = requests.session()
        statuses = {x for x in range(100, 600) if x != 200}
        retries = Retry(total=5, backoff_factor=1, status_forcelist=statuses)
        session.mount('http://', HTTPAdapter(max_retries=retries))

        return session

    @staticmethod
    def create_retry_client(session: aiohttp.ClientSession) -> aiohttp_retry.RetryClient:
        """
        Creates a retry client used for making requests to the different APIs.
        :param session: Session to use in the retry client.
        :return: The created retry client.
        """
        statuses = {x for x in range(100, 600) if x != 200}
        retry_options = ExponentialRetry(statuses=statuses)
        retry_client = RetryClient(client_session=session, retry_options=retry_options)

        return retry_client

    @staticmethod
    async def should_retry_add_collection(response: aiohttp.ClientResponse) -> bool:
        """
        Callback functions for the collections API for retrying.
        :param response: The response to evaluate.
        :return: Whether the request should be retried or not.
        """
        invalid_response = response.content_type != 'application/json'
        if not invalid_response:
            response_json = await response.json()
            invalid_response = not response_json['isSuccess']
        if invalid_response:
            pass
        return invalid_response


class BingCreatorImageValidator:
    """
    Used to evaluate if different data should be considered for download.
    """

    @staticmethod
    def should_add_collection_to_images(_collection: dict) -> bool:
        """
        Checks if a collection should be considered for download
        by checking the included collections and necessary keys.
        :param _collection: Collection to determine for download.
        :return: Whether the collection should be added or not.
        """
        if 'collectionPage' in _collection and 'items' in _collection['collectionPage']:
            collections_to_include = config['collection']['collections_to_include']
            if len(collections_to_include) == 0:
                return True
            else:
                return (('knownCollectionType' in _collection and 'Saved Images' in collections_to_include)
                        or _collection['title'] in collections_to_include)
        else:
            return False

    @staticmethod
    def should_add_item_to_images(_item: dict) -> bool:
        """
        Checks for the necessary keys in the item and returns whether they are present.
        :param _item: Item to consider for download.
        :return: Whether the item dictionary is valid for download.
        """
        valid_item_root = 'content' in _item and 'customData' in _item['content']
        if valid_item_root:
            custom_data = _item['content']['customData']
            valid_custom_data = 'MediaUrl' in custom_data and 'ToolTip' in custom_data
            return valid_custom_data
        else:
            return False


class BingCreatorCollectionImport:
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
        semaphore = asyncio.Semaphore(10)
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
                retry_client = BingCreatorNetworkUtility.create_retry_client(session)
                retry_client.retry_options.evaluate_response_callback = \
                    BingCreatorNetworkUtility.should_retry_add_collection
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
        tasks = [BingCreatorCollectionImport.__convert_item_to_request_format(item['content'])
                 for collection in self.__collection_dict['collections']
                 if BingCreatorImageValidator.should_add_collection_to_images(collection)
                 for item in collection['collectionPage']['items']
                 if BingCreatorImageValidator.should_add_item_to_images(item)]
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
        thumbnail_base64 = await BingCreatorCollectionImport.__get_thumbnail_base64(thumbnail_url)

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
            async with BingCreatorNetworkUtility.create_retry_client(session).get(thumbnail_url) as response:
                thumbnail_content = await response.read()
                img = Image.open(io.BytesIO(thumbnail_content))
                img.thumbnail((468, 468))
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG")
                thumbnail_base64 = str(base64.b64encode(buffered.getvalue()).decode('utf-8'))

        return thumbnail_base64


async def main() -> None:
    """
    Entry point for the program. Calls all high level functionality.
    :return: None
    """
    start = time.time()
    cookie = os.getenv('COOKIE')
    if bool(cookie):
        logging.debug(f"Loaded cookie ending with: {cookie[-16:]}")
    else:
        raise Exception("No cookie was found in the .env file.")
    image_download = BingCreatorImageDownload()
    await image_download.run()
    end = time.time()
    elapsed = end - start
    logging.info(f"Successfully downloaded {image_download.successful_image_count}"
                 f" of {image_download.total_image_count} images in"
                 f" {round(elapsed, 2)} seconds.\n")
    if config['debug']['detailed_statistics']:
        output_statistics(image_download.images)


def output_statistics(images: List[BingCreatorImage]) -> None:
    """
    Outputs statistics about the downloaded images in the console and a file.
    :param images: All images that were attempted to download.
    :return: None
    """
    print("Detailed statistics:")
    data = []
    for image in images:
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
    with open('detailed_statistics.md', 'w') as f:
        f.write(table_str)
    print(table_str)


def init_logging() -> None:
    """
    Initializes logging for the program.
    :return: None
    """
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aiohttp_retry").setLevel(logging.WARNING)

    log_level = logging.DEBUG if config['debug']['debug'] else logging.INFO
    log_format = "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(
        format=log_format,
        level=log_level,
        handlers=[StreamHandler(sys.stdout)]
    )

    if config['debug']['use_log_file']:
        file_handler = RotatingFileHandler(
            config['debug']['debug_filename'],
            maxBytes=1000000,
            backupCount=1)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)


if __name__ == "__main__":
    load_dotenv()
    with open('config.toml', 'rb') as cfg_file:
        config = tomllib.load(cfg_file)
    init_logging()
    asyncio.run(main())
