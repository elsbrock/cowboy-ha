"""Tests for the Cowboy API client."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import pytest
from requests import HTTPError, Response

from custom_components.cowboy._client import CowboyAPIClient


def _response(status_code=200, payload=None, headers=None):
    """Build a real requests response for client tests."""
    response = Response()
    response.status_code = status_code
    response.url = "https://app-api.cowboy.bike/test"
    response._content = json.dumps(payload or {}).encode()
    if headers:
        response.headers.update(headers)
    return response


def _login_response(
    token="initial-token", client="initial-client", expiry=9_999_999_999
):
    """Build a successful login response."""
    return _response(
        payload={"data": {"bike": {"id": 123}}},
        headers={
            "Access-Token": token,
            "Uid": "test@example.com",
            "Client": client,
            "Expiry": str(expiry),
        },
    )


def test_response_auth_headers_are_rotated():
    """Successful responses should update credentials for the next request."""
    rotated_headers = {
        "Access-Token": "rotated-token",
        "Uid": "rotated@example.com",
        "Client": "rotated-client",
        "Expiry": "9999999999",
    }

    with (
        patch(
            "custom_components.cowboy._client.requests.post",
            return_value=_login_response(),
        ),
        patch(
            "custom_components.cowboy._client.requests.get",
            side_effect=[
                _response(payload={"id": 123}, headers=rotated_headers),
                _response(payload={"id": 123}),
            ],
        ) as mock_get,
    ):
        client = CowboyAPIClient()
        client.login("test@example.com", "password")

        client.get_bike()
        client.get_bike()

    first_headers = mock_get.call_args_list[0].kwargs["headers"]
    second_headers = mock_get.call_args_list[1].kwargs["headers"]
    assert first_headers["Access-Token"] == "initial-token"
    assert second_headers["Access-Token"] == "rotated-token"
    assert second_headers["Uid"] == "rotated@example.com"
    assert second_headers["Client"] == "rotated-client"
    assert client.token_expires == 9_999_999_999


def test_expired_token_is_renewed_before_request():
    """An expired session should be renewed before sending the request."""
    with (
        patch(
            "custom_components.cowboy._client.requests.post",
            side_effect=[
                _login_response(expiry=100),
                _login_response("renewed-token", "renewed-client", 300),
            ],
        ) as mock_post,
        patch(
            "custom_components.cowboy._client.requests.get",
            return_value=_response(payload={"id": 123}),
        ) as mock_get,
        patch("custom_components.cowboy._client.time.time", return_value=100),
    ):
        client = CowboyAPIClient()
        client.login("test@example.com", "password")

        result = client.get_bike()

    assert result == {"id": 123}
    assert mock_post.call_count == 2
    assert mock_get.call_count == 1
    assert mock_get.call_args.kwargs["headers"]["Access-Token"] == "renewed-token"
    assert mock_get.call_args.kwargs["headers"]["Client"] == "renewed-client"


def test_unauthorized_request_reauthenticates_and_retries_once():
    """A 401 should trigger one login and one retry with new credentials."""
    with (
        patch(
            "custom_components.cowboy._client.requests.post",
            side_effect=[
                _login_response(),
                _login_response("renewed-token", "renewed-client"),
            ],
        ) as mock_post,
        patch(
            "custom_components.cowboy._client.requests.get",
            side_effect=[
                _response(status_code=401),
                _response(payload={"id": 123}),
            ],
        ) as mock_get,
    ):
        client = CowboyAPIClient()
        client.login("test@example.com", "password")

        result = client.get_bike()

    assert result == {"id": 123}
    assert mock_post.call_count == 2
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[0].kwargs["headers"]["Access-Token"] == (
        "initial-token"
    )
    assert mock_get.call_args_list[1].kwargs["headers"]["Access-Token"] == (
        "renewed-token"
    )


def test_repeated_unauthorized_is_raised():
    """A repeated 401 should be raised instead of starting a retry loop."""
    repeated_unauthorized = _response(status_code=401)

    with (
        patch(
            "custom_components.cowboy._client.requests.post",
            side_effect=[_login_response(), _login_response("renewed-token")],
        ) as mock_post,
        patch(
            "custom_components.cowboy._client.requests.get",
            side_effect=[_response(status_code=401), repeated_unauthorized],
        ) as mock_get,
    ):
        client = CowboyAPIClient()
        client.login("test@example.com", "password")

        with pytest.raises(HTTPError) as error:
            client.get_bike()

    assert error.value.response is repeated_unauthorized
    assert mock_post.call_count == 2
    assert mock_get.call_count == 2


def test_non_authentication_error_is_not_retried():
    """A non-401 response should be raised without reauthentication."""
    server_error = _response(status_code=500)

    with (
        patch(
            "custom_components.cowboy._client.requests.post",
            return_value=_login_response(),
        ) as mock_post,
        patch(
            "custom_components.cowboy._client.requests.get",
            return_value=server_error,
        ) as mock_get,
    ):
        client = CowboyAPIClient()
        client.login("test@example.com", "password")

        with pytest.raises(HTTPError) as error:
            client.get_bike()

    assert error.value.response is server_error
    assert mock_post.call_count == 1
    assert mock_get.call_count == 1


def test_requests_are_serialized():
    """Concurrent requests should not race while rotating credentials."""
    first_request_started = Event()
    release_first_request = Event()
    second_request_started = Event()
    request_headers = []

    def get_response(url, headers, timeout):
        """Block the first request while recording credentials in use."""
        request_headers.append(headers)
        if len(request_headers) == 1:
            first_request_started.set()
            assert release_first_request.wait(timeout=2)
            return _response(
                payload={"id": 123},
                headers={"Access-Token": "rotated-token"},
            )
        second_request_started.set()
        return _response(payload={"id": 123})

    with (
        patch(
            "custom_components.cowboy._client.requests.post",
            return_value=_login_response(),
        ),
        patch(
            "custom_components.cowboy._client.requests.get",
            side_effect=get_response,
        ),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        client = CowboyAPIClient()
        client.login("test@example.com", "password")
        first_result = executor.submit(client.get_bike)
        assert first_request_started.wait(timeout=2)
        second_result = executor.submit(client.get_bike)

        try:
            assert not second_request_started.wait(timeout=0.1)
        finally:
            release_first_request.set()

        assert first_result.result(timeout=2) == {"id": 123}
        assert second_result.result(timeout=2) == {"id": 123}

    assert request_headers[0]["Access-Token"] == "initial-token"
    assert request_headers[1]["Access-Token"] == "rotated-token"
