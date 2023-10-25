import logging
import re
import sys
import unicodedata

import aiofiles
import asyncio
from datetime import date
import time
import os
import platform
import zipfile

import aiohttp
import structlog

from arsenic import get_session
from arsenic.browsers import Firefox
from arsenic.constants import SelectorType
from arsenic.services import Geckodriver


async def get_image_tuples(img_url_list: list):
    results = await asyncio.gather(*map(get_image_from_url, img_url_list))
    return list(results)


async def get_image_from_url(url):
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


async def download_and_zip_images(image_tuples: list):
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


async def download_and_save_image(session, src, alt, index):
    try:
        async with session.get(src) as response:
            if response.status == 200:
                alt = await slugify(alt)
                filename = f"{alt[:50]}_{str(index)}.jpg"
                async with aiofiles.open(filename, "wb") as f:
                    await f.write(await response.read())
                logging.info(f"Downloading image from: {src}")
                return filename
            else:
                print(f"Failed to download {src}")
    except Exception as e:
        print(e)


async def slugify(text):
    """
    Convert spaces or repeated dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    Source: https://github.com/django/django/blob/main/django/utils/text.py
    """
    text = str(text)
    text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-_")


def set_arsenic_log_level(level=logging.WARNING):
    logger = logging.getLogger('arsenic')

    def logger_factory():
        return logger

    structlog.configure(logger_factory=logger_factory)
    logger.setLevel(level)


async def main():
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
