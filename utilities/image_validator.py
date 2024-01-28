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
        if _collection.get('collectionPage', {}).get('items'):
            collections_to_include = Config().collections_to_include
            if len(collections_to_include) == 0:
                return True
            else:
                saved_images_in_config = (_collection.get('knownCollectionType')
                                          and 'Saved Images' in collections_to_include)
                collection_in_config = _collection.get('title') in collections_to_include
                return saved_images_in_config or collection_in_config
        else:
            return False

    @staticmethod
    def should_add_item_to_images(_item: dict) -> bool:
        """
        Checks for the necessary keys in the item and returns whether they are present.
        :param _item: Item to consider for download.
        :return: Whether the item dictionary is valid for download.
        """
        custom_data = _item.get('content', {}).get('customData', {})
        if custom_data:
            valid_custom_data = 'MediaUrl' in custom_data and 'ToolTip' in custom_data
            return valid_custom_data
        else:
            return False
