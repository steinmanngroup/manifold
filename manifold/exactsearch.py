from dataclasses import dataclass
import requests
from typing import Dict, List, Optional
from simplejson.errors import JSONDecodeError

from .manifold import InvalidSmilesError, make_batches, Manifold


@dataclass
class ManifoldInchiKeyMatches:
    is_exact: bool
    parent: bool
    connectivity: bool


@dataclass
class ManifoldSupplierPurchaseInfo:
    """ Purchase information for a supplier """
    lead_time_weeks: float
    price_information: str
    is_building_block: bool
    is_screening: bool


@dataclass
class ManifoldCatalogEntry:
    supplier: str
    id: str
    smiles: str
    link: str
    purchase_info: Optional[ManifoldSupplierPurchaseInfo]
    match: Optional[ManifoldInchiKeyMatches]


def parse_supplier_purchase_information(item: Dict) -> Optional[ManifoldSupplierPurchaseInfo]:
    """

    :param item:
    :return:
    """
    try:
        lead_time = float(item["scrLeadTimeWeeks"])
        price_information = item["scrPriceRange"]
        is_building_block = bool(item["isBuildingBlock"])
        is_screening = bool(item["isScreening"])
    except KeyError:
        return None
    else:
        return ManifoldSupplierPurchaseInfo(lead_time, price_information, is_building_block, is_screening)


def _parse_inchi_matches(value: Dict) -> ManifoldInchiKeyMatches:
    return ManifoldInchiKeyMatches(
            bool(value["exact"]),
            bool(value["parent"]),
            bool(value["connectivity"])
    )


def _parse_catalog_entries(values: Dict) -> List[ManifoldCatalogEntry]:
    entries = []
    item: Dict
    for item in values:
        catalog_name: str = item.get("catalogName", "N/A")
        catalog_id: str = item.get("catalogId", "N/A")
        link: str = item.get("link", "N/A")
        smiles: str = item.get("smiles", "")

        matches: Optional[ManifoldInchiKeyMatches] = None
        if item.get("inchikeyMatches", None) is not None:
            matches = _parse_inchi_matches(item["inchikeyMatches"])

        purchase_information: Optional[ManifoldSupplierPurchaseInfo] = None
        if item.get("purchaseInfo", None) is not None:
            purchase_information = parse_supplier_purchase_information(item["purchaseInfo"])

        entries.append(
                ManifoldCatalogEntry(catalog_name,
                                     catalog_id,
                                     smiles,
                                     link,
                                     purchase_information,
                                     matches)
                       )
    return entries


class ExactSearch(Manifold):
    """ Searches the PostEra Manifold for a number of suppliers for a specific compound """

    URL = "exact/"

    def __init__(self, smiles: str, api_key: str):
        Manifold.__init__(self, api_key)
        self._smiles = smiles

        response = requests.post(
                url=self.api_endpoint(self.URL),
                headers={"X-API-KEY": self._api_key},
                json={"smiles": self._smiles,
                      "queryThirdPartyServices": False}
        )
        self._results: List[ManifoldCatalogEntry]
        status_code = response.status_code
        try:
            results = response.json()
        except JSONDecodeError:
            self._results = []
        else:
            if status_code == 422:
                raise InvalidSmilesError(results["error"])
            elif status_code == 500:
                self._results = []
            else:
                self._results = _parse_catalog_entries(results.get("results", []))

    def result(self) -> List[ManifoldCatalogEntry]:
        return self._results

    def result_exact_matches(self) -> List[ManifoldCatalogEntry]:
        results = []
        for entry in self._results:
            if entry.match is not None and entry.match.is_exact:
                results.append(entry)
        return results


class ExactSearchBatch(Manifold):
    """ Searches a"""
    URL = "exact/batch/"
    MAX_BATCH_SIZE = 1000

    def __init__(self, smiles: List[str], api_key: str):
        Manifold.__init__(self, api_key)
        self._smiles = smiles[:]
        self._results: List = []

        batches = make_batches(smiles, self.MAX_BATCH_SIZE)
        for batch in batches:
            response = requests.post(
                    url=self.api_endpoint(self.URL),
                    headers={"X-API-KEY": self._api_key},
                    json={"smilesList": batch}
            )
            return_values = response.json()
            for item in return_values["results"]:
                if "error" in item:
                    self._results.append([])
                else:
                    self._results.append(_parse_catalog_entries(item["catalogEntries"]))

    def result(self) -> List:
        return self._results
