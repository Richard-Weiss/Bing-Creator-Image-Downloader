class Config:
    """
    Singleton class that holds the configuration for the program.
    """
    _instance = None
    _config = None

    def __new__(cls, config=None):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._config = config
        return cls._instance

    @property
    def value(self):
        return self._config

    def detail_max_attempts(self) -> int:
        """
        Returns the maximum number of attempts to get detailed information for an image.
        :return: The value specified in the config file.
        """
        return self._config['detail_api']['max_attempts']
