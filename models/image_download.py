import asyncio
from io import BytesIO
import logging
import os
import zipfile
from typing import List

import aiofiles.tempfile
import aiohttp
from PIL import Image as PIL_Image
import string
from dateutil import parser as dateutil_parser

from utilities.statistics import Statistics
from utilities.config import Config
from models.image import Image
from utilities.image_utility import ImageUtility
from utilities.network_utility import NetworkUtility
from datetime import date


class ImageDownload:
    """
    This class is used to download all images from the supplied collections.
    It gathers all the necessary data from the collections and downloads the images from them.
    """

    def __init__(self):
        self.__config = Config().value
        self.__images: List[Image] = []
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
        strategy_method = self.__config['image_source']['method']
        image_source_strategy = ImageUtility.get_image_source_strategy(strategy_method)
        self.__images = await image_source_strategy.get_images()
        self.total_image_count = len(self.__images)
        await self.__download_and_zip_images()

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
                if self.__config['debug']['detailed_statistics']:
                    statistics_str = Statistics(self.__images).create_statistics()
                    logging.info("Statistics zipped.")
                    zip_file.writestr('detailed_statistics.md', statistics_str)

    async def __download_and_save_image(
            self,
            image: Image,
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
                    async with NetworkUtility.create_retry_client(session).get(url) as response:
                        logging.info(f"Downloading image #{image.index} from: {url}")
                        image.attempts = image.attempts + 1
                        if response.status == 200 and response.content_type == 'image/jpeg':
                            filename_image_prompt = await ImageUtility.slugify(image.prompt)
                            if self.__config['filename']['use_local_time_zone']:
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
                            template = string.Template(self.__config['filename']['filename_pattern'])
                            file_name_formatted = template.safe_substitute(file_name_substitute_dict)
                            image_bytes = await response.read()
                            with PIL_Image.open(BytesIO(image_bytes)) as pil_image:
                                image_width = pil_image.width
                            if image_width < 1024:
                                file_name_formatted += '_T'
                                image.is_thumbnail = True
                            filename = f"{temp_dir}{os.sep}{file_name_formatted}.jpg"

                            async with aiofiles.open(filename, "wb") as f:
                                await f.write(image_bytes)

                            image.used_image_url = str(response.url)
                            image.file_name = filename
                            await ImageUtility.add_exif_metadata(image)
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
            if Config().value['debug']['debug']:
                logging.exception(e)
            else:
                logging.error(e)
