from dataclasses import dataclass
import requests
from typing import Dict, List, Optional
from simplejson.errors import JSONDecodeError

from .manifold import InvalidSmilesError, TooManyRequestsError, make_batches, Manifold


@dataclass
class ManifoldSyntheticAccessibility:
    score: float
    num_steps: Optional[int]
    warning: Optional[str]
    url: Optional[str]


def parse_synthetic_accessibility(sa_entry: Dict) -> ManifoldSyntheticAccessibility:
    """ Parses the manifold synthetic accessibility data

    This data can come from either:
      1. the Fast model (https://api.postera.ai/api/v1/docs/#operation/api_v1_synthetic-accessibility_fast-score_create)
    or from:
      2. the Retrosynthesis model (https://api.postera.ai/api/v1/docs/#operation/api_v1_synthetic-accessibility_retrosynthesis_create)

    :param sa_entry:
    :return:
    """
    score: float
    num_steps: Optional[int] = sa_entry.get("minNumSteps", None)
    warning: Optional[str] = sa_entry.get("SAAlertLevel", None)
    url: Optional[str]
    if "fastSAScore" in sa_entry:
        score = sa_entry.get("fastSAScore", 1.0)
        url = sa_entry.get("SAAlertImgURL", None)
    elif "score" in sa_entry:
        score = sa_entry.get("score", 1.0)
        url = sa_entry.get("manifoldLink", None)
    else:
        raise ValueError("Could not parse synthetic accessibility.")
    return ManifoldSyntheticAccessibility(score=score,
                                          num_steps=num_steps,
                                          warning=warning,
                                          url=url)


def parse_synthetic_accessibilities(sa_entries: List[Dict]) -> List[Optional[ManifoldSyntheticAccessibility]]:
    results: List[Optional[ManifoldSyntheticAccessibility]] = []
    for sa_data in sa_entries:
        try:
            value = sa_data["SAData"]
        except KeyError:
            results.append(None)
        else:
            results.append(parse_synthetic_accessibility(value))

    return results


class SyntheticAccessibility(Manifold):
    def __init__(self, smiles: str, api_key: str):
        Manifold.__init__(self, api_key)
        self._smiles: str = smiles
        self._results: Optional[ManifoldSyntheticAccessibility]
        response = self._setup_request()
        self._parse_response(response)

    def _setup_request(self):
        raise NotImplementedError

    def _parse_response(self, response):
        status_code = response.status_code
        try:
            results = response.json()
        except JSONDecodeError:
            self._results = None
        else:
            if status_code == 500:
                self._results = None
            elif status_code == 422:
                raise InvalidSmilesError(results["error"])
            else:
                if "detail" in results:
                    raise TooManyRequestsError(results["detail"])
                self._results = parse_synthetic_accessibility(results)

    def result(self) -> Optional[ManifoldSyntheticAccessibility]:
        return self._results

    def as_floats(self) -> float:
        if self._results is None:
            return 1.0
        return self._results.score


class SyntheticAccessibilityFast(SyntheticAccessibility):
    URL = "synthetic-accessibility/fast-score/"

    def __init__(self, smiles: str, api_key: str, alerts: bool = False):
        self._alerts: bool = alerts
        SyntheticAccessibility.__init__(self, smiles, api_key)

    def _setup_request(self):
        return requests.post(
                url=self.api_endpoint(self.URL),
                headers={"X-API-KEY": self._api_key},
                json={"smiles": self._smiles,
                      "getAlertSvg": self._alerts}
        )


class SyntheticAccessibilityRetroSynthesis(SyntheticAccessibility):
    URL = "synthetic-accessibility/retrosynthesis/"

    def __init__(self, smiles: str, api_key: str):
        SyntheticAccessibility.__init__(self, smiles, api_key)

    def _setup_request(self):
        return requests.post(
                url=self.api_endpoint(self.URL),
                headers={"X-API-KEY": self._api_key},
                json={"smiles": self._smiles}
        )


class SyntheticAccessibilityBatch(Manifold):
    """ Computes synthetic accessibility in batches with the Manifold API

        Each algorithm that is derived from this must specify two variables
          1) MAX_BATCH_SIZE: int that determines the size per batch
          2) URL: str the API endpoint
    """
    MAX_BATCH_SIZE: int

    def __init__(self, smiles: List[str], api_key: str):
        Manifold.__init__(self, api_key)
        self._smiles = smiles[:]
        self._results: List[Optional[ManifoldSyntheticAccessibility]] = []
        responses = self._setup_requests()
        self._parse_response(responses)

    def _setup_requests(self):
        batches = make_batches(self._smiles, self.MAX_BATCH_SIZE)
        responses = []
        for batch in batches:
            response = self._setup_request(batch)
            responses.append(response.json())
        return responses

    def _setup_request(self, batch: List[str]):
        raise NotImplementedError

    def _parse_response(self, responses):
        for response in responses:
            try:
                results = response["results"]
            except KeyError:
                if "detail" in response:
                    raise TooManyRequestsError(response["detail"])
                else:
                    raise KeyError
            else:
                self._results.extend(parse_synthetic_accessibilities(results))

    def result(self) -> List[Optional[ManifoldSyntheticAccessibility]]:
        return self._results

    def as_floats(self) -> List[float]:
        return [m.score if m is not None else 1.0 for m in self._results]


class SyntheticAccessibilityFastBatch(SyntheticAccessibilityBatch):
    URL = "synthetic-accessibility/fast-score/batch/"
    MAX_BATCH_SIZE = 100

    def __init__(self, smiles: List[str], api_key: str, alerts: bool = False):
        self._alerts = alerts
        SyntheticAccessibilityBatch.__init__(self, smiles, api_key)

    def _setup_request(self, batch: List[str]):
        return requests.post(
                url=self.api_endpoint(self.URL),
                headers={"X-API-KEY": self._api_key},
                json={"smilesList": batch,
                      "getAlertSvg": self._alerts}
        )


class SyntheticAccessibilityRetroSynthesisBatch(SyntheticAccessibilityBatch):
    URL = "synthetic-accessibility/retrosynthesis/batch/"
    MAX_BATCH_SIZE = 10

    def __init__(self, smiles: List[str], api_key: str):
        SyntheticAccessibilityBatch.__init__(self, smiles, api_key)

    def _setup_request(self, batch: List[str]):
        return requests.post(
                url=self.api_endpoint(self.URL),
                headers={"X-API-KEY": self._api_key},
                json={"smilesList": batch}
        )
