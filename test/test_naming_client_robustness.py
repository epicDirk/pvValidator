"""Robustness tests for NamingServiceClient: bounded caches, session cleanup,
and malformed-response handling. These exercise the client directly (no SWIG/
EPICS), so they run in the pure-Python test job.
"""

from unittest import mock

import pytest
import responses

from pvValidatorUtils.exceptions import NamingServiceResponseError
from pvValidatorUtils.naming_client import NamingServiceClient


def test_cache_is_bounded(monkeypatch):
    """The response cache must not grow past _MAX_CACHE_ENTRIES (oldest evicted)."""
    client = NamingServiceClient()
    monkeypatch.setattr(client, "_MAX_CACHE_ENTRIES", 3)
    for i in range(5):
        client._cache_put(client._parts_cache, f"m{i}", [i])
    assert len(client._parts_cache) == 3
    # Oldest two evicted, newest kept.
    assert "m0" not in client._parts_cache
    assert "m1" not in client._parts_cache
    assert "m4" in client._parts_cache


def test_cache_put_updates_existing_without_growth(monkeypatch):
    client = NamingServiceClient()
    monkeypatch.setattr(client, "_MAX_CACHE_ENTRIES", 2)
    client._cache_put(client._names_cache, "a", 1)
    client._cache_put(client._names_cache, "a", 2)  # update, not new key
    assert client._names_cache == {"a": 2}


def test_close_calls_session_close():
    client = NamingServiceClient()
    with mock.patch.object(client.session, "close") as closed:
        client.close()
        closed.assert_called_once()


def test_context_manager_closes_session():
    client = NamingServiceClient()
    with mock.patch.object(client.session, "close") as closed:
        with client as c:
            assert c is client
        closed.assert_called_once()


@responses.activate
def test_malformed_json_parts_raises():
    client = NamingServiceClient()
    responses.add(
        responses.GET,
        client.parts_url + "DTL",
        body="<html>not json</html>",
        status=200,
    )
    with pytest.raises(NamingServiceResponseError):
        client._get_parts("DTL")


@responses.activate
def test_malformed_json_device_name_raises():
    client = NamingServiceClient()
    responses.add(
        responses.GET,
        client.names_url + "DTL-010:EMR-TT-001",
        body="oops",
        status=200,
    )
    with pytest.raises(NamingServiceResponseError):
        client._get_device_name("DTL-010:EMR-TT-001")


@responses.activate
def test_server_error_raises_and_does_not_cache():
    client = NamingServiceClient()
    responses.add(responses.GET, client.parts_url + "DTL", status=500)
    with pytest.raises(NamingServiceResponseError):
        client._get_parts("DTL")
    assert "DTL" not in client._parts_cache
