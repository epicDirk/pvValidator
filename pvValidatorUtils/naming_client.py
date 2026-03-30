"""Client for the ESS Naming Service REST API.

Encapsulates all HTTP communication with the Naming Service.
URLs configurable, proper timeout and error handling, result caching.

API endpoints used:
  GET /rest/parts/mnemonic/{mnemonic}  — validate System, Subsystem, Discipline, Device
  GET /rest/deviceNames/{name}         — check if ESS name is registered
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote as url_quote

import requests

from .exceptions import NamingServiceConnectionError, NamingServiceResponseError

logger = logging.getLogger("pvvalidator")


class NamingServiceClient:
    """Client for ESS Naming Service REST API.

    Attributes:
        base_url: Naming Service base URL
        timeout: HTTP request timeout in seconds
        environment: 'prod' or 'test'
    """

    DEFAULT_URLS = {
        "prod": "https://naming.esss.lu.se/",
        "test": "https://naming-test-01.cslab.esss.lu.se/",
    }

    def __init__(
        self,
        environment: str = "prod",
        base_url: Optional[str] = None,
        timeout: float = 5.0,
    ):
        self.environment = environment
        self.base_url = base_url or self.DEFAULT_URLS.get(
            environment, self.DEFAULT_URLS["prod"]
        )
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"accept": "application/json"})

        # Retry logic: 3 attempts with exponential backoff for transient failures
        from requests.adapters import HTTPAdapter

        try:
            from urllib3.util.retry import Retry

            retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[502, 503, 504])
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        except ImportError:
            pass  # urllib3 retry not available — proceed without

        # In-memory caches
        self._parts_cache: Dict[str, List[Dict]] = {}
        self._names_cache: Dict[str, Dict] = {}
        self._sys_cache: Dict[str, bool] = {}
        self._dev_cache: Dict[str, bool] = {}

    @property
    def parts_url(self) -> str:
        return self.base_url + "rest/parts/mnemonic/"

    @property
    def names_url(self) -> str:
        return self.base_url + "rest/deviceNames/"

    # -----------------------------------------------------------------
    # Connection check
    # -----------------------------------------------------------------

    def check_connectivity(self) -> bool:
        """Check if the Naming Service is reachable.

        Raises:
            NamingServiceConnectionError: If the service is unreachable.
        """
        try:
            self.session.head(self.base_url, timeout=1)
            return True
        except (requests.exceptions.ConnectionError, ConnectionError, OSError) as e:
            raise NamingServiceConnectionError(
                f"Failed to connect to Naming Service at {self.base_url}: {e}"
            ) from e

    # -----------------------------------------------------------------
    # Low-level API calls
    # -----------------------------------------------------------------

    def _get_parts(self, mnemonic: str) -> List[Dict]:
        """GET /rest/parts/mnemonic/{mnemonic}"""
        if mnemonic in self._parts_cache:
            return self._parts_cache[mnemonic]
        try:
            resp = self.session.get(
                self.parts_url + url_quote(mnemonic, safe="-:"),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            self._parts_cache[mnemonic] = data
            return data
        except requests.exceptions.RequestException as e:
            raise NamingServiceResponseError(
                f"Failed to query parts for '{mnemonic}': {e}"
            ) from e

    def _get_device_name(self, name: str) -> Dict:
        """GET /rest/deviceNames/{name}"""
        if name in self._names_cache:
            return self._names_cache[name]
        try:
            resp = self.session.get(
                self.names_url + url_quote(name, safe="-:"),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            self._names_cache[name] = data
            return data
        except requests.exceptions.RequestException as e:
            raise NamingServiceResponseError(
                f"Failed to query device name '{name}': {e}"
            ) from e

    # -----------------------------------------------------------------
    # High-level validation methods
    # -----------------------------------------------------------------

    def validate_system(self, system: str) -> bool:
        """Check if a system mnemonic is registered and approved.

        Args:
            system: System mnemonic (e.g., 'DTL', 'ISrc')

        Returns:
            True if system is approved in the Naming Service.
        """
        cache_key = f"sys:{system}"
        if cache_key in self._sys_cache:
            return self._sys_cache[cache_key]

        try:
            parts = self._get_parts(system)
            result = any(
                item.get("status") == "Approved"
                and item.get("type") == "System Structure"
                and item.get("level") in ("1", "2")
                for item in parts
            )
        except NamingServiceResponseError:
            result = False

        self._sys_cache[cache_key] = result
        return result

    def validate_subsystem(self, system: str, subsystem: str) -> bool:
        """Check if a subsystem is registered under its parent system.

        Args:
            system: Parent system mnemonic
            subsystem: Subsystem mnemonic

        Returns:
            True if subsystem is approved under the given system.
        """
        full = f"{system}-{subsystem}"
        cache_key = f"sub:{full}"
        if cache_key in self._sys_cache:
            return self._sys_cache[cache_key]

        try:
            parts = self._get_parts(subsystem)
            result = any(
                item.get("status") == "Approved"
                and item.get("type") == "System Structure"
                and item.get("level") == "3"
                and full in item.get("mnemonicPath", "")
                for item in parts
            )
        except NamingServiceResponseError:
            result = False

        self._sys_cache[cache_key] = result
        return result

    def validate_discipline(self, discipline: str) -> bool:
        """Check if a discipline mnemonic is registered.

        Args:
            discipline: Discipline mnemonic (e.g., 'EMR', 'WtrC')

        Returns:
            True if discipline is approved.
        """
        cache_key = f"dis:{discipline}"
        if cache_key in self._dev_cache:
            return self._dev_cache[cache_key]

        try:
            parts = self._get_parts(discipline)
            result = any(
                item.get("status") == "Approved"
                and item.get("type") == "Device Structure"
                and item.get("level") == "1"
                for item in parts
            )
        except NamingServiceResponseError:
            result = False

        self._dev_cache[cache_key] = result
        return result

    def validate_device(self, discipline: str, device: str) -> bool:
        """Check if a device type is registered under its discipline.

        Args:
            discipline: Parent discipline mnemonic
            device: Device type mnemonic

        Returns:
            True if device is approved under the given discipline.
        """
        full = f"{discipline}-{device}"
        cache_key = f"dev:{full}"
        if cache_key in self._dev_cache:
            return self._dev_cache[cache_key]

        try:
            parts = self._get_parts(device)
            result = any(
                item.get("status") == "Approved"
                and item.get("type") == "Device Structure"
                and item.get("level") == "3"
                and full in item.get("mnemonicPath", "")
                for item in parts
            )
        except NamingServiceResponseError:
            result = False

        self._dev_cache[cache_key] = result
        return result

    def validate_name(self, ess_name: str) -> Dict[str, Any]:
        """Check if an ESS name is registered and its status.

        Args:
            ess_name: Full ESS name (e.g., 'DTL-010:EMR-TT-001')

        Returns:
            Dict with 'registered' (bool), 'status' (str), 'message' (str)
        """
        try:
            data = self._get_device_name(ess_name)
            status = data.get("status", "")

            if status == "ACTIVE":
                return {
                    "registered": True,
                    "status": status,
                    "message": f'The Name "{ess_name}" is registered in the Naming Service',
                }
            elif status == "OBSOLETE":
                return {
                    "registered": False,
                    "status": status,
                    "message": f'The Name "{ess_name}" was modified in the Naming Service',
                }
            elif status == "DELETED":
                return {
                    "registered": False,
                    "status": status,
                    "message": f'The Name "{ess_name}" was canceled in the Naming Service',
                }
            else:
                return {
                    "registered": False,
                    "status": status,
                    "message": f'The Name "{ess_name}" has unknown status "{status}"',
                }
        except NamingServiceResponseError:
            return {
                "registered": False,
                "status": "",
                "message": f'The Name "{ess_name}" is not registered in the Naming Service',
            }

    # -----------------------------------------------------------------
    # Confusable mnemonic detection (ELEM-3, ELEM-4)
    # -----------------------------------------------------------------

    def find_confusables(
        self, mnemonic: str, category: Optional[str] = None
    ) -> List[str]:
        """Find registered mnemonics that are visually confusable with *mnemonic*.

        Uses the same skeleton normalization as property uniqueness checks:
        I↔l↔1, O↔0, VV↔W (case-insensitive).

        Searches the Naming Service for mnemonics sharing the first 1-2
        characters (prefix search) and also checks the local cache.

        Args:
            mnemonic: The mnemonic to check (e.g., "ISrc")
            category: Optional filter — "system" or "discipline"

        Returns:
            List of confusable registered mnemonics (excluding *mnemonic* itself).
        """
        from .rules import normalize_for_confusion

        target_skeleton = normalize_for_confusion(mnemonic)

        # Gather candidates from API prefix search + cache
        candidates: set = set()
        for prefix_len in (1, 2):
            if len(mnemonic) >= prefix_len:
                results = self.search_parts(mnemonic[:prefix_len])
                for r in results:
                    if r.get("status") != "Approved" or not r.get("mnemonic"):
                        continue
                    if category == "system" and r.get("type") != "System Structure":
                        continue
                    if category == "discipline" and r.get("type") != "Device Structure":
                        continue
                    candidates.add(r["mnemonic"])

        for cand in self._collect_candidates(category):
            candidates.add(cand)

        # Find those whose skeleton matches but whose name differs
        confusables = []
        for cand in candidates:
            if cand.lower() == mnemonic.lower():
                continue  # same mnemonic (case-insensitive)
            if normalize_for_confusion(cand) == target_skeleton:
                confusables.append(cand)

        return confusables

    # -----------------------------------------------------------------
    # Search / "Did you mean?" support
    # -----------------------------------------------------------------

    def search_parts(self, query: str) -> List[Dict]:
        """Search for mnemonics matching a query (prefix/substring).

        Uses GET /rest/parts/mnemonic/search/{query}.
        Returns list of matching parts with mnemonic, name, status.
        """
        try:
            resp = self.session.get(
                self.base_url + "rest/parts/mnemonic/search/"
                + url_quote(query, safe="-:"),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException:
            return []

    def suggest_correction(self, mnemonic: str, category: Optional[str] = None) -> Optional[str]:
        """Suggest a correction for an unrecognized mnemonic.

        Uses a combination of API prefix search and local edit-distance
        matching against cached and search-fetched mnemonics.

        Args:
            mnemonic: The unrecognized mnemonic (e.g., "DLT")
            category: Optional filter — "system", "discipline", or None

        Returns:
            A suggestion string like 'Did you mean "DTL"?' or None.
        """
        # Strategy 1: API exact-prefix search
        results = self.search_parts(mnemonic)
        approved = [
            r for r in results
            if r.get("status") == "Approved"
            and r.get("mnemonic", "").lower() != mnemonic.lower()
        ] if results else []
        if approved:
            best = approved[0]
            name = best.get("name", "")
            if name:
                return f'Did you mean "{best["mnemonic"]}" ({name})?'
            return f'Did you mean "{best["mnemonic"]}"?'

        # Strategy 2: Short-prefix search to find nearby mnemonics,
        # then edit-distance ranking. This catches character-swap typos
        # like "DLT" → "DTL" that a prefix search misses.
        nearby = set()
        for prefix_len in (1, 2):
            if len(mnemonic) >= prefix_len:
                prefix_results = self.search_parts(mnemonic[:prefix_len])
                for r in prefix_results:
                    if r.get("status") != "Approved" or not r.get("mnemonic"):
                        continue
                    if category == "system" and r.get("type") != "System Structure":
                        continue
                    if category == "discipline" and r.get("type") != "Device Structure":
                        continue
                    nearby.add(r["mnemonic"])

        # Also include cached mnemonics
        for cand in self._collect_candidates(category):
            nearby.add(cand)

        if nearby:
            best_match = self._closest_match(mnemonic, list(nearby))
            if best_match:
                return f'Did you mean "{best_match}"?'

        return None

    def _collect_candidates(self, category: Optional[str]) -> List[str]:
        """Collect known mnemonics from cache for edit-distance matching."""
        candidates = set()
        for key, items in self._parts_cache.items():
            if not isinstance(items, list):
                continue
            for item in items:
                mnem = item.get("mnemonic", "")
                if not mnem:
                    continue
                if item.get("status") != "Approved":
                    continue
                if category == "system" and item.get("type") != "System Structure":
                    continue
                if category == "discipline" and item.get("type") != "Device Structure":
                    continue
                candidates.add(mnem)
        return list(candidates)

    @staticmethod
    def _closest_match(query: str, candidates: List[str], max_distance: int = 2) -> Optional[str]:
        """Find the closest match by Levenshtein edit distance.

        Only returns a match if the distance is <= max_distance.
        """
        best = None
        best_dist = max_distance + 1
        q_lower = query.lower()
        for candidate in candidates:
            dist = NamingServiceClient._edit_distance(q_lower, candidate.lower())
            if dist < best_dist:
                best_dist = dist
                best = candidate
        return best if best_dist <= max_distance else None

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """Compute Damerau-Levenshtein distance (includes transpositions).

        Unlike plain Levenshtein, this counts adjacent character swaps
        (e.g., "DLT" → "DTL") as a single operation.
        """
        len1, len2 = len(s1), len(s2)
        # Use a full matrix for Damerau-Levenshtein
        d = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        for i in range(len1 + 1):
            d[i][0] = i
        for j in range(len2 + 1):
            d[0][j] = j
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                d[i][j] = min(
                    d[i - 1][j] + 1,       # deletion
                    d[i][j - 1] + 1,        # insertion
                    d[i - 1][j - 1] + cost,  # substitution
                )
                # Transposition
                if (
                    i > 1
                    and j > 1
                    and s1[i - 1] == s2[j - 2]
                    and s1[i - 2] == s2[j - 1]
                ):
                    d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
        return d[len1][len2]
