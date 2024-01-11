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
