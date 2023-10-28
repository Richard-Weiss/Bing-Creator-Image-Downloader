import asyncio
import json
import logging
import os
import platform
import re
import sys
import time
import unicodedata
import zipfile
from datetime import date

import aiofiles
import aiohttp
import piexif as piexif
import structlog
from arsenic import get_session
from arsenic.browsers import Firefox
from arsenic.constants import SelectorType
from arsenic.services import Geckodriver


async def get_image_tuples(img_url_list: list) -> list:
    """
    Asynchronous wrapper to gather all the results from the tasks once they are completed.
    :param img_url_list: List of URLs to find images by.
    :return: A list containing the src and alt attributes for each image.
    """
    results = await asyncio.gather(*map(get_image_from_url, img_url_list))
    return list(results)


async def get_image_from_url(url: str) -> tuple:
    """
    Retrieves the image src and alt from the given url and returns it as a tuple.
    :param url: URL to use to find the image.
    :return: Tuple containing the src and alt attribute of the image.
    """
    service = Geckodriver(
        binary='C:\\Users\\icepe\\Developer_Tools\\Gecko Driver\\geckodriver.exe',
        log_file=os.devnull
    )
    options = Firefox(**{
        "moz:firefoxOptions": {
            "args": ["-headless"]
        }
    })
    async with get_session(service, options) as session:
        await session.get(url)
        logging.info(f"Getting image for URL: {url}")
        img = await session.wait_for_element(20, "//div[@class='imgContainer']/img", SelectorType.xpath)
        return await img.get_attribute("src"), await img.get_attribute("alt")


async def download_and_zip_images(image_tuples: list) -> None:
    """
    Downloads all images supplied in the image_tuples list and zips them.
    :param image_tuples: List of tuples containing the link and alt of the images.
    :return: None
    """
    zip_file = zipfile.ZipFile(f"bing_images_{date.today()}.zip", "w")
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
                print(f"Failed to download {src}")
    except Exception as e:
        print(e)


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


def set_arsenic_log_level(level: int=logging.WARNING) -> None:
    """
    Sets the log level of the arsenic module to "WARNING" to prevent it spamming the CLI.
    :param level: The logging level to set for the arsenic logger.
    :return: None
    """
    logger = logging.getLogger('arsenic')

    def logger_factory():
        return logger

    structlog.configure(logger_factory=logger_factory)
    logger.setLevel(level)


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
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    set_arsenic_log_level()
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
