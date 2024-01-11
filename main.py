import asyncio
import logging
import os
import sys
import time
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from tomllib import load

from dotenv import load_dotenv

from models.image_download import ImageDownload
from utilities.config import Config


async def main() -> None:
    """
    Entry point for the program. Calls all high level functionality.
    :return: None
    """
    start = time.time()
    image_download = ImageDownload()
    await image_download.run()
    end = time.time()
    elapsed = end - start
    logging.info(f"Successfully downloaded {image_download.successful_image_count}"
                 f" of {image_download.total_image_count} images in"
                 f" {round(elapsed, 2)} seconds.\n")


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
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file = os.path.join(log_dir, config['debug']['debug_filename'])
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * (10 ** 6),
            backupCount=1)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)


if __name__ == "__main__":
    load_dotenv()
    with open('config.toml', 'rb') as cfg_file:
        config = Config(load(cfg_file)).value
    init_logging()
    asyncio.run(main())
