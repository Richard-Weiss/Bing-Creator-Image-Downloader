import json
import logging
import os

from strategies.collection_deletion.collection_deletion_strategy import CollectionDeletionStrategy
from utilities.network_utility import NetworkUtility


class CollectionUtility:
    """
    Contains different functions related to collections.
    """

    @staticmethod
    def delete_collection(collection_id: str = None, collection_ids: list = None) -> None:
        """
        Deletes the collection with the given collection_id or collection_ids.
        :param collection_id: The id of the collection to delete.
        :param collection_ids: A list of ids of the collections to delete.
        """
        if collection_id is not None and collection_ids is not None:
            raise ValueError("Only one of collection_id or collection_ids should be provided.")

        if collection_id is not None:
            collection_ids = [collection_id]
        elif collection_ids is not None:
            collection_ids = collection_ids
        else:
            raise ValueError("Either collection_id or collection_ids must be provided.")

        request_url = f"https://www.bing.com/mysaves/collections/delete?sid=0"
        header = {
            "Content-Type": "application/json",
            "cookie": os.getenv('COOKIE'),
            "sid": "0"
        }
        body = {
            "targetCollections": [{"collectionId": _id} for _id in collection_ids]
        }
        response = NetworkUtility.create_session().post(
            url=request_url,
            headers=header,
            data=json.dumps(body)
        )
        collection_plural = 's' if len(collection_ids) > 1 else ''
        if response.status_code == 200:
            response_body = response.json()
            is_success = response_body.get('isSuccess', False)
            if is_success:
                logging.info(f"Successfully deleted collection{collection_plural} with id{collection_plural}: "
                             f"{', '.join(collection_ids)}")
            else:
                message = response_body.get('message', 'No message provided.')
                logging.error(f"Failed to delete collection{collection_plural} "
                              f"for Reason: {message}")
        else:
            logging.error(f"Failed to delete collection{collection_plural} "
                          f"for Reason: {response.reason}: ")

    @staticmethod
    def get_collection_deletion_strategy(mode: str) -> CollectionDeletionStrategy or None:
        """
        Returns the collection deletion strategy based on the supplied mode.
        :param mode: The mode to use for deleting collections.
        :return: The collection deletion strategy or None if none was found.
        """
        match mode:
            case 'safest':
                from strategies.collection_deletion.safest_collection_deletion_strategy import \
                    SafestCollectionDeletionStrategy
                return SafestCollectionDeletionStrategy()
            case 'safeish':
                from strategies.collection_deletion.safeish_collection_deletion_stategy import \
                    SafeishCollectionDeletionStrategy
                return SafeishCollectionDeletionStrategy()
            case 'dangerous':
                from strategies.collection_deletion.dangerous_collection_deletion_stategy import \
                    DangerousCollectionDeletionStrategy
                return DangerousCollectionDeletionStrategy()
