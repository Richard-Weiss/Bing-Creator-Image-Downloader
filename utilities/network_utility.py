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
    def create_retry_client(session: aiohttp.ClientSession, attempts=4, max_timeout=16) -> aiohttp_retry.RetryClient:
        """
        Creates a retry client used for making requests to the different APIs.
        :param session: Session to use in the retry client.
        :param attempts: How many times a request should be retried.
        :param max_timeout: Maximum timeout in seconds.
        :return: The created retry client.
        """
        statuses = {x for x in range(100, 600) if x != 200}
        retry_options = ExponentialRetry(attempts=attempts, start_timeout=1, max_timeout=max_timeout, statuses=statuses)
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

    @staticmethod
    async def should_retry_get_detail_image(response: aiohttp.ClientResponse) -> bool:
        """
        Callback functions for the detail API for retrying.
        :param response: The response to evaluate.
        :return: Whether the request should be retried or not.
        """
        should_retry = True
        if response.status == 200:
            data = await response.json()
            valid_response = data is not None and 'value' in data and data['value'] is not None
            should_retry = not valid_response

        return should_retry
