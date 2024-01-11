from utilities.config import Config


class ImageValidator:
    """
    Used to evaluate if different data should be considered for download.
    """

    @staticmethod
    def should_add_collection_to_images(_collection: dict) -> bool:
        """
        Checks if a collection should be considered for download
        by checking the included collections and necessary keys.
        :param _collection: Collection to determine for download.
        :return: Whether the collection should be added or not.
        """
        if 'collectionPage' in _collection and 'items' in _collection['collectionPage']:
            collections_to_include = Config().value['collection']['collections_to_include']
            if len(collections_to_include) == 0:
                return True
            else:
                return (('knownCollectionType' in _collection and 'Saved Images' in collections_to_include)
                        or _collection['title'] in collections_to_include)
        else:
            return False

    @staticmethod
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
