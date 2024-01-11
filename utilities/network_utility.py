import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import aiohttp_retry
from aiohttp_retry import ExponentialRetry, RetryClient


class NetworkUtility:
    """
    Different request related functions.
    """

    @staticmethod
    def create_session() -> requests.Session:
        """
        Create a new request.Session with retry.
        :return: A new request.Session with retry.
        """
        session = requests.session()
        statuses = {x for x in range(100, 600) if x != 200}
        retries = Retry(total=5, backoff_factor=1, status_forcelist=statuses)
        session.mount('http://', HTTPAdapter(max_retries=retries))

        return session

    @staticmethod
    def create_retry_client(session: aiohttp.ClientSession) -> aiohttp_retry.RetryClient:
        """
        Creates a retry client used for making requests to the different APIs.
        :param session: Session to use in the retry client.
        :return: The created retry client.
        """
        statuses = {x for x in range(100, 600) if x != 200}
        retry_options = ExponentialRetry(statuses=statuses)
        retry_client = RetryClient(client_session=session, retry_options=retry_options)

        return retry_client

    @staticmethod
    async def should_retry_add_collection(response: aiohttp.ClientResponse) -> bool:
        """
        Callback functions for the collections API for retrying.
        :param response: The response to evaluate.
        :return: Whether the request should be retried or not.
        """
        invalid_response = response.content_type != 'application/json'
        if not invalid_response:
            response_json = await response.json()
            invalid_response = not response_json['isSuccess']
        if invalid_response:
            pass
        return invalid_response
