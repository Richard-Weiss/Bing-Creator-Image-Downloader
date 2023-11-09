import asyncio
import json
import logging
import os
import re
import sys
import time
import zipfile
from datetime import date

import aiofiles
import aiofiles.tempfile
import aiohttp
import piexif as piexif
import requests
import unicodedata
from aiohttp_retry import ExponentialRetry
from aiohttp_retry import RetryClient
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3 import Retry


def gather_image_data() -> list:
    """
    Gathers all image links and prompts from all collections.
    :return: A list containing dictionaries containing the image url, description/prompt and collection for each image.
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
                for item in collection['collectionPage']['items']:
                    if should_add_item_to_images(item):
                        custom_data = json.loads(item['content']['customData'])
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
        collections_to_include = [_collection.strip() for _collection in os.getenv('COLLECTIONS_TO_INCLUDE').split(',')]
        if len(collections_to_include[0]) == 0:
            return True
        else:
            return (('knownCollectionType' in _collection and 'Default' in collections_to_include)
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
            if response.status == 200:
                filename_image_prompt = await slugify(image_dict['image_prompt'])
                filename = f"{temp_dir}{os.sep}{filename_image_prompt[:50]}_{str(index)}.jpg"
                async with aiofiles.open(filename, "wb") as f:
                    await f.write(await response.read())
                await add_exif_metadata(image_dict, filename)
                logging.info(f"Downloading image from: {image_dict['image_link']}")
                return filename, image_dict['collection_name']
            else:
                logging.warning(f"Failed to download {image_dict['image_link']} "
                                f"for Reason: {response.status}: {response.reason}-> "
                                f"Retrying with thumbnail {image_dict['thumbnail_link']}")
                async with retry_client.get(image_dict['thumbnail_link']) as thumbnail_response:
                    if thumbnail_response.status == 200:
                        filename_image_prompt = await slugify(image_dict['image_prompt'])
                        filename = f"{temp_dir}{os.sep}T_{filename_image_prompt[:50]}_{str(index)}.jpg"
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
    Adds the src and alt parameter to the image as EXIF metadata.
    :param image_dict: Dictionary containing prompt, image link and thumbnail link of the image.
    :param filename: The name of the file containing the image.
    :return: None
    """
    with open(filename, 'rb') as img:
        exif_dict = piexif.load(img.read())
        user_comment = {
            'prompt': image_dict['image_prompt'],
            'image_link': image_dict['image_link'],
            'thumbnail_link': image_dict['thumbnail_link'],
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


async def main() -> None:
    """
    Entry point for the program. Calls all high level functionality.
    :return: None
    """
    start = time.time()

    logging.info(f"Fetching metadata of collections...")
    image_data = gather_image_data()
    logging.info(f"Starting download of {len(image_data)} images.")
    await download_and_zip_images(image_data)

    end = time.time()
    elapsed = end - start
    logging.info(f"Finished downloading {len(image_data)} images in {round(elapsed, 2)} seconds.")


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
