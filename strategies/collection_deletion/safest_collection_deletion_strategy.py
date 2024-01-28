import logging
from itertools import groupby
from typing import List

from models.image import Image
from strategies.collection_deletion.collection_deletion_strategy import CollectionDeletionStrategy
from utilities.collection_utility import CollectionUtility


class SafestCollectionDeletionStrategy(CollectionDeletionStrategy):
    """
    Deletes the collection(s) if all images were downloaded successfully.
    """

    def delete_collection(self, images: List[Image]) -> None:
        """
        Deletes the collection(s) only if all images were downloaded successfully.
        """
        images.sort(key=lambda image: image.collection_id)
        grouped_by_collection_id_images = {collection_id: list(image_group) for collection_id, image_group
                                           in groupby(images, key=lambda image: image.collection_id)}
        collection_ids_to_delete = []
        for collection_id, image_group in grouped_by_collection_id_images.items():
            if len(images) != 1000 and all(image.status_code == 200 and image.is_success for image in image_group):
                collection_ids_to_delete.append(collection_id)
        if collection_ids_to_delete:
            CollectionUtility.delete_collection(collection_ids=collection_ids_to_delete)
        else:
            logging.warning("No collections were valid for deletion.")
