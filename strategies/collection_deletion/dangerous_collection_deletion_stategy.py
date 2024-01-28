import logging
from typing import List

from models.image import Image
from strategies.collection_deletion.collection_deletion_strategy import CollectionDeletionStrategy
from utilities.collection_utility import CollectionUtility


class DangerousCollectionDeletionStrategy(CollectionDeletionStrategy):
    """
    Deletes the collection(s) whether all images were downloaded successfully or not.
    """

    def delete_collection(self, images: List[Image]) -> None:
        """
        Deletes the collection(s) whether all images were downloaded successfully or not.
        :return: None.
        """
        collection_ids = list(set(image.collection_id for image in images))
        if collection_ids:
            CollectionUtility.delete_collection(collection_ids=collection_ids)
        else:
            logging.warning("No collections were valid for deletion.")
