""" PostEra Manifold API

    A bare-bones python api for the PostEra Manifold API
"""
__author__ = "Casper Steinmann"
from typing import List


class InvalidSmilesError(ValueError):
    pass


class TooManyRequestsError(ValueError):
    pass


class Manifold(object):
    """ Base PostEra Manifold API class

    """
    URL_API = "https://api.postera.ai/api/v1/"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def api_key(self) -> str:
        return self._api_key

    def api_endpoint(self, endpoint: str):
        return self.URL_API + endpoint

    def result(self):
        """ Returns the result from the PostEra API """
        raise NotImplementedError


def make_batches(values: List[str], batch_size: int) -> List[List[str]]:
    """ Constructs a number of batches of size `batch_size` from the input data"""
    batches: List[List[str]] = []
    for i in range(0, len(values), batch_size):
        batches.append(values[i:i + batch_size])
    return batches
