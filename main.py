import asyncio
import base64
import json
import logging
import os
import re
import string
import sys
import time
import tomllib
import zipfile
from datetime import date
from datetime import timezone
from urllib.parse import unquote

import aiofiles
import aiofiles.tempfile
import aiohttp
import piexif as piexif
import requests
import unicodedata
from aiohttp_retry import ExponentialRetry
from aiohttp_retry import RetryClient
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3 import Retry

with open('config.toml', 'rb') as cfg_file:
    config = tomllib.load(cfg_file)


def gather_image_data() -> list:
    """
    Gathers all necessary data for each image from all collections.
    :return: A list containing dictionaries containing the interesting data for each image.
    """
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
    session = requests.session()
    statuses = {x for x in range(100, 600) if x != 200}
    retries = Retry(total=5, backoff_factor=1, status_forcelist=statuses)
    session.mount('http://', HTTPAdapter(max_retries=retries))
    response = session.post(
        url='https://www.bing.com/mysaves/collections/get?sid=0',
        headers=header,
        data=json.dumps(body)
    )
    if response.status_code == 200:
        collection_dict = response.json()
        if len(collection_dict) == 0:
            raise Exception('No collections were found for the given cookie.')
        gathered_image_data = []
        for collection in collection_dict['collections']:
            if should_add_collection_to_images(collection):
                for index, item in enumerate(collection['collectionPage']['items']):
                    if should_add_item_to_images(item):
                        custom_data = json.loads(item['content']['customData'])
                        image_page_url = custom_data['PageUrl']
                        image_link = custom_data['MediaUrl']
                        image_prompt = custom_data['ToolTip']
                        collection_name = collection['title']
                        thumbnail_raw = item['content']['thumbnails'][0]['thumbnailUrl']
                        thumbnail_link = re.match('^[^&]+', thumbnail_raw).group(0)
                        pattern = r'Image \d of \d$'
                        image_prompt = re.sub(pattern, '', image_prompt)
                        image_dict = {
                            'image_link': image_link,
                            'image_prompt': image_prompt,
                            'collection_name': collection_name,
                            'thumbnail_link': thumbnail_link,
                            'image_page_url': image_page_url,
                            'index': str((index + 1)).zfill(4)
                        }
                        gathered_image_data.append(image_dict)
        return gathered_image_data
    else:
        raise Exception(f"Fetching collection failed with Error code"
                        f"{response.status_code}: {response.reason};{response.text}")


def should_add_collection_to_images(_collection: dict) -> bool:
    """
    Checks if a collection should be considered for download by checking the included collections and necessary keys.
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


async def download_and_zip_images(image_data: list) -> None:
    """
    Downloads all images supplied in the image_tuples list and zips them.
    :param image_data: List of dictionary containing the link, description and collection of the images.
    :return: None
    """
    with zipfile.ZipFile(f"bing_images_{date.today()}.zip", "w") as zip_file:
        async with aiofiles.tempfile.TemporaryDirectory('wb') as temp_dir:
            async with aiohttp.ClientSession() as session:
                tasks = [
                    download_and_save_image(session, image_dict, index, temp_dir)
                    for index, image_dict
                    in enumerate(image_data)
                ]
                file_names = await asyncio.gather(*tasks)
                file_names = [file_name for file_name in file_names if not None]
                for file_name, collection_name in file_names:
                    file_name: str
                    zip_file.write(file_name, arcname=os.path.join(collection_name, os.path.basename(file_name)))


async def download_and_save_image(
        session: aiohttp.ClientSession,
        image_dict: dict,
        index: int,
        temp_dir: aiofiles.tempfile.TemporaryDirectory) -> tuple:
    """
    Downloads an image using the src and the existing session.
    :param session: The ClientSession to use for the request.
    :param image_dict: Dictionary containing link, prompt collection name and thumbnail link of an image.
    :param index: An index that gets added to the filename. Only used to prevent duplicate names.
    :param temp_dir: The directory to save files to before zipping.
    :return: The filename and collection name of the downloaded file.
    """
    try:
        statuses = {x for x in range(100, 600) if x != 200}
        retry_options = ExponentialRetry(attempts=5, statuses=statuses)
        retry_client = RetryClient(client_session=session, retry_options=retry_options)
        async with retry_client.get(image_dict['image_link']) as response:
            logging.info(f"Downloading image from: {image_dict['image_link']}")
            if response.status == 200:
                filename_image_prompt = await slugify(image_dict['image_prompt'])
                file_name_substitute_dict = {
                    'date': image_dict['creation_date'],
                    'index': image_dict['index'],
                    'prompt': filename_image_prompt[:50],
                    'sep': '_'
                }
                template = string.Template(config['filename']['filename_pattern'])
                file_name_formatted = template.safe_substitute(file_name_substitute_dict)
                filename = f"{temp_dir}{os.sep}{file_name_formatted}.jpg"

                async with aiofiles.open(filename, "wb") as f:
                    await f.write(await response.read())

                await add_exif_metadata(image_dict, filename)

                return filename, image_dict['collection_name']
            else:
                logging.warning(f"Failed to download {image_dict['image_link']} "
                                f"for Reason: {response.status}: {response.reason}-> "
                                f"Retrying with thumbnail {image_dict['thumbnail_link']}")
                async with retry_client.get(image_dict['thumbnail_link']) as thumbnail_response:
                    if thumbnail_response.status == 200:
                        filename_image_prompt = await slugify(image_dict['image_prompt'])
                        file_name_substitute_dict = {
                            'date': image_dict['creation_date'],
                            'index': image_dict['index'],
                            'prompt': filename_image_prompt[:50],
                            'sep': '_'
                        }
                        template = string.Template(config['filename']['filename_pattern'])
                        file_name_formatted = template.safe_substitute(file_name_substitute_dict)
                        filename = f"{temp_dir}{os.sep}{file_name_formatted}_T.jpg"

                        async with aiofiles.open(filename, "wb") as f:
                            await f.write(await thumbnail_response.read())

                        await add_exif_metadata(image_dict, filename)

                        return filename, image_dict['collection_name']
                    else:
                        logging.warning(f"Failed to download {image_dict['thumbnail_link']} "
                                        f"for Reason: {thumbnail_response.status}: {thumbnail_response.reason}")
    except Exception as e:
        logging.exception(e)


async def add_exif_metadata(image_dict: dict, filename: str) -> None:
    """
    Adds the prompt, image link,thumbnail link and creation date to the image as EXIF metadata.
    :param image_dict: Dictionary containing metadata of the image.
    :param filename: The name of the file containing the image.
    :return: None
    """
    with open(filename, 'rb') as img:
        exif_dict = piexif.load(img.read())
        user_comment = {
            'prompt': image_dict['image_prompt'],
            'image_link': image_dict['image_link'],
            'thumbnail_link': image_dict['thumbnail_link'],
            'creation_date': image_dict['creation_date']
        }
        user_comment_bytes = json.dumps(user_comment, ensure_ascii=False).encode("utf-8")
        exif_dict['Exif'][piexif.ExifIFD.UserComment] = user_comment_bytes
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, filename)


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


async def set_creation_dates(image_data: list) -> None:
    async with aiohttp.ClientSession() as session:
        tasks = [
            _set_creation_date(session, image)
            for image
            in image_data
        ]
        await asyncio.gather(*tasks)


async def _set_creation_date(session: aiohttp.ClientSession, image: dict) -> None:
    extracted_ids = await _extract_set_and_image_id(image['image_page_url'])
    image_set_id = extracted_ids['image_set_id']
    image_id = extracted_ids['image_id']
    request_url = f"https://www.bing.com/images/create/detail/async/{image_set_id}/?imageId={image_id}"

    statuses = {x for x in range(100, 600) if x != 200}
    retry_options = ExponentialRetry(attempts=5, statuses=statuses)
    retry_client = RetryClient(client_session=session, retry_options=retry_options)
    async with retry_client.get(request_url) as response:
        if response.status == 200:
            data = await response.json()
            images = data['value']
            decoded_image_id = unquote(image_id)
            resp_image_arr = [img for img in images if img['imageId'] == decoded_image_id]
            resp_image = images[0] if len(resp_image_arr) < 1 else resp_image_arr[0]
            creation_date_string = resp_image['datePublished']
            creation_date_object = dateutil_parser.parse(creation_date_string).astimezone(timezone.utc)
            creation_date_string_formatted = creation_date_object.strftime('%Y-%m-%dT%H%MZ')
            image['creation_date'] = creation_date_string_formatted
        else:
            logging.error(f"Failed to get detailed information for image: {image['image_page_url']} "
                          f"for Reason: {response.status}: {response.reason}-> ")


async def _extract_set_and_image_id(url: str) -> dict:
    """
    Extracts the image set and image id from the image page url.
    :param url: The image page url i.e. https://www.bing.com/images/create/$prompt/$imageSetId?id=$imageId.
    :return: A dictionary containing the image_set_id and image_id.
    """
    logging.info(f"Extracting image set id and image id from url: {url}")
    pattern = r"(?P<image_set_id>(?<=\/)(?:\d\-)?[a-f0-9]{32})(?:\?id=)(?P<image_id>(?<=\?id=)[^&]+)"
    result = re.search(pattern, url)
    image_set_id = result.group('image_set_id')
    image_id = result.group('image_id')
    id_dict = {'image_set_id': image_set_id, 'image_id': image_id}

    return id_dict


async def add_images_to_collection(collection_dict: dict) -> None:
    session = requests.session()
    statuses = {x for x in range(100, 600) if x != 200}
    retries = Retry(total=5, backoff_factor=1, status_forcelist=statuses)
    session.mount('http://', requests.adapters.HTTPAdapter(max_retries=retries))
    tasks = [add_image_to_collection(session, item['content'])
             for collection in collection_dict['collections'] if should_add_collection_to_images(collection)
             for item in collection['collectionPage']['items'] if should_add_item_to_images(item)
             ]
    logging.info(f"Adding {len(tasks)} images to the new collection.")
    await asyncio.gather(*tasks)


async def add_image_to_collection(session, content_dict: dict) -> None:
    logging.info(f'Adding image {content_dict["url"]} to the collection.')
    thumbnail_base64 = await _get_thumbnail_base64(session, content_dict['thumbnails'][0]['thumbnailUrl'])
    header = {
        "content-type": "application/json",
        "cookie": os.getenv('COOKIE'),
        "sid": "0"
    }
    body = {
        "Items": [
            {
                "Title": content_dict['title'],
                "ClickThroughUrl": content_dict['url'],
                "ContentId": content_dict['contentId'],
                "ItemTagPath": content_dict['itemTagPath'],
                "ThumbnailInfo": [{
                    "Thumbnail": f"data:image/jpeg;base64,{thumbnail_base64}",
                    "Width": 1024,
                    "Height": 1024
                }],
                "CustomData": content_dict['customData']
            }
        ],
        "TargetCollection": {
            "CollectionId": "3a165902d3a64b6c8f05f52ea2b830ee"
        }
    }
    response = session.post(
        url='https://www.bing.com/mysaves/collections/items/add?sid=0',
        headers=header,
        data=json.dumps(body)
    )
    try:
        response_json = response.json()
    except requests.JSONDecodeError:
        raise Exception(f"The request to add the item to the collection was unsuccessful:"
                        f"{response.status_code}")
    if response.status_code != 200 or not response_json['isSuccess']:
        raise Exception(f"Adding item to collection failed with following response:"
                        f"{response.json()}")


async def _get_thumbnail_base64(session, thumbnail_url: str) -> str:
    thumbnail_url = re.match(r'[^?]+\?[^&]+', thumbnail_url).group(0)
    thumbnail_response = session.get(url=thumbnail_url)
    thumbnail_base64 = str(base64.b64encode(thumbnail_response.content).decode("utf-8"))

    return thumbnail_base64


async def main() -> None:
    """
    Entry point for the program. Calls all high level functionality.
    :return: None
    """
    start = time.time()

    logging.info(f"Fetching metadata of collections...")
    image_data = gather_image_data()
    await set_creation_dates(image_data)
    logging.info(f"Starting download of {len(image_data)} images.")
    await download_and_zip_images(image_data)

    end = time.time()
    elapsed = end - start
    logging.info(f"Finished downloading {len(image_data)} images in {round(elapsed, 2)} seconds.")


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(
        filename='13_bing_images.log',
        filemode='a',
        format='%(asctime)s %(levelname)s %(message)s',
        level=logging.INFO)
    asyncio.run(main())
