import asyncio
import json
import logging
import os
import re
import sys
import time
import zipfile
from datetime import date
from urllib.parse import urljoin

import aiofiles
import aiohttp
import asyncio_pool
import piexif as piexif
import unicodedata
from aiolimiter import AsyncLimiter


async def get_image_tuples(img_url_list: list) -> list:
    """
    Asynchronous wrapper to gather all the results from the tasks once they are completed.
    :param img_url_list: List of URLs to find images by.
    :return: A list containing the src and alt attributes for each image.
    """
    pool = asyncio_pool.AioPool(size=32)
    results = await pool.map(get_image_from_url, img_url_list)
    return list(results)


async def get_image_from_url(url: str) -> tuple:
    """
    Retrieves the image src and alt using the given url and returns it as a tuple.
    :param url: URL used to build a new fetchURL.
    :return: Tuple containing the src and alt attribute of the image.
    """
    try:
        logging.info(f"Getting image for URL: {url}")
        limiter = AsyncLimiter(5000, 1)
        async with limiter:
            async with aiohttp.ClientSession() as session:
                image_fetch_url = await build_image_fetch_url(url)
                async with session.get(image_fetch_url) as response:
                    if response.status == 200:
                        response_body = await response.json()
                        index = response_body['selectedIndex']
                        image_data_array = response_body['value']
                        image_data = image_data_array[index]
                        src = image_data['contentUrl']
                        alt = image_data['imageAltText']
                        return src, alt
                    else:
                        logging.warning(f"Failed to fetch image for URL: {url} "
                                        f"for Reason: {response.status}: {response.reason}")
    except Exception as e:
        logging.error(e)


async def build_image_fetch_url(url: str) -> str:
    """
    Builds the url that is used to fetch the image src and alt attributes.
    :param url: URL from text file. Used to extract the set and image id.
    :return: The built url for requesting the image information.
    """
    set_and_image_id = await extract_set_and_image_id(url)
    base_url = 'https://www.bing.com'
    path = f"images/create/detail/async/{set_and_image_id['setId']}"
    fetch_url = f"{urljoin(base_url, path)}?imageId={set_and_image_id['imageId']}"
    return fetch_url


async def extract_set_and_image_id(url: str) -> dict:
    """
    Extracts the set id and image id out of the url using regex and returns them as a dictionary.
    :param url: The url from the original text file.
    :return: A dictionary containing the setId and imageId.
    """
    pattern = r'([a-f0-9]{32}\?id=[^&]+)'
    match = re.search(pattern, url)
    if match:
        set_and_image_id = match.group(1)
        set_and_image_id = set_and_image_id.replace('id=', '')
        set_and_image_id_list = set_and_image_id.split('?')
        set_and_image_id_dict = {
            'setId': set_and_image_id_list[0],
            'imageId': set_and_image_id_list[1]
        }
        return set_and_image_id_dict
    else:
        raise ValueError(f"The set and image id couldn't be extracted for the url: {url}")


async def download_and_zip_images(image_tuples: list) -> None:
    """
    Downloads all images supplied in the image_tuples list and zips them.
    :param image_tuples: List of tuples containing the link and alt of the images.
    :return: None
    """
    zip_file = zipfile.ZipFile(f"bing_images_{date.today()}.zip", "w")
    limiter = AsyncLimiter(5000, 1)
    async with limiter:
        async with aiohttp.ClientSession() as session:
            tasks = [
                download_and_save_image(session, src, alt, index)
                for index, (src, alt)
                in enumerate(image_tuples)
            ]
            file_names = await asyncio.gather(*tasks)
            for file_name in file_names:
                if file_name is not None:
                    file_name: str
                    zip_file.write(file_name)
                    os.remove(file_name)
    zip_file.close()


async def download_and_save_image(
        session: aiohttp.ClientSession,
        src: str,
        alt: str,
        index: int) -> str:
    """
    Downloads an image using the src and the existing session.
    :param session: The ClientSession to use for the request.
    :param src: The url the image is located at.
    :param alt: The alternative text of the image, in this case the prompt.
    :param index: An index that gets added to the filename. Only used to prevent duplicate names.
    :return: The filename of the downloaded file.
    """
    try:
        async with session.get(src) as response:
            if response.status == 200:
                filename_alt = await slugify(alt)
                filename = f"{filename_alt[:50]}_{str(index)}.jpg"
                async with aiofiles.open(filename, "wb") as f:
                    await f.write(await response.read())
                await add_exif_metadata(src, alt, filename)
                logging.info(f"Downloading image from: {src}")
                return filename
            else:
                logging.warning(f"Failed to download {src} for Reason: {response.status}: {response.reason}")
    except Exception as e:
        logging.error(e)


async def add_exif_metadata(src: str, alt: str, filename: str) -> None:
    """
    Adds the src and alt parameter to the image as EXIF metadata.
    :param src: The link the image was fetched from.
    :param alt: The description of the image, in this case its prompt.
    :param filename: The name of the file containing the image.
    :return: None
    """
    with open(filename, 'rb') as img:
        exif_dict = piexif.load(img.read())
        user_comment = {
            'prompt': alt,
            'image_link:': src
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

    with open("images_clipboard.txt", "r", encoding='utf8') as f:
        content = f.read().splitlines()
    image_url_list = [line for line in content if line.startswith("https://www.bing.com/images/create")]

    logging.info(f"Preparing {len(image_url_list)} URLs for download...")
    image_tuples = await get_image_tuples(image_url_list)
    await download_and_zip_images(image_tuples)

    end = time.time()
    elapsed = end - start
    logging.info(f"Finished downloading {len(image_url_list)} images in {round(elapsed, 2)} seconds.")


if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
