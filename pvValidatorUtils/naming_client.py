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
        except requests.exceptions.ConnectionError as e:
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
