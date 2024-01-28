import os
from typing import List


class Config:
    """
    Singleton class that holds the configuration for the program.
    """
    _instance = None
    _config: dict = None
    _cookie_dict: dict = None

    def __new__(cls, config: dict = None):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._config = config
            cls._cookie_dict = cls.get_cookie_dict()
        return cls._instance

    @property
    def value(self) -> dict:
        return self._config

    @property
    def collections_to_include(self) -> List[str]:
        return self._config['collection']['collections_to_include']

    @property
    def delete_collection_after_download(self) -> dict:
        return self._config['collection']['delete_collection_after_download']

    @property
    def delete_collection_after_download_toggle(self) -> bool:
        return self.delete_collection_after_download['toggle']

    @property
    def delete_collection_after_download_mode(self) -> str:
        return self.delete_collection_after_download['mode']

    @property
    def detailed_statistics(self) -> bool:
        return self._config['debug']['detailed_statistics']

    @property
    def image_source_method(self) -> str:
        return self._config['image_source']['method']

    @property
    def use_local_time_zone(self) -> bool:
        return self._config['filename']['use_local_time_zone']

    @property
    def filename_pattern(self) -> str:
        return self._config['filename']['filename_pattern']

    def detail_max_attempts(self) -> int:
        """
        Returns the maximum number of attempts to get detailed information for an image.
        :return: The value specified in the config file.
        """
        return self._config['detail_api']['max_attempts']

    @staticmethod
    def get_cookie_dict() -> dict:
        """
        Parses the cookie from the .env file into a dictionary.
        :return: A dictionary containing the cookie values.
        """
        cookie = os.getenv('COOKIE')
        cookie_values = cookie.split(';')
        cookie_dict = {}
        for cookie_value in cookie_values:
            cookie_value = cookie_value.strip()
            if '=' in cookie_value:
                key, value = cookie_value.split('=', 1)
                cookie_dict[key] = Config.__parse_cookie(value)
        return cookie_dict

    @staticmethod
    def __parse_cookie(cookie_value: str) -> dict | str:
        """
        Recursively parse a cookie value into a dictionary.
        :param cookie_value: The cookie value to parse.
        :return: The parsed cookie value dictionary or string.
        """
        if '&' in cookie_value or '=' in cookie_value:
            sub_dict = {}
            for sub_value in cookie_value.split('&'):
                if '=' in sub_value:
                    sub_key, sub_value = sub_value.split('=', 1)
                    sub_dict[sub_key] = Config.__parse_cookie(sub_value)
            return sub_dict
        else:
            return cookie_value
