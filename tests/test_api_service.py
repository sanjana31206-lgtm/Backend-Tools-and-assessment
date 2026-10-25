
from unittest.mock import Mock, patch

import sys
from pathlib import Path

PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubspot-deals-etl"
    / "hubspot-deals-etl"
)
sys.path.insert(0, str(PROJECT_DIR))

from services.api_service import APIService


def test_get_data_retries_after_429():
    service = APIService()

    rate_limited = Mock()
    rate_limited.status_code = 429
    rate_limited.headers = {"Retry-After": "0"}
    rate_limited.text = "Rate limited"

    success = Mock()
    success.status_code = 200
    success.headers = {}
    success.json.return_value = {
        "results": [{"id": "123"}]
    }

    with patch.object(
        service.session,
        "get",
        side_effect=[rate_limited, success],
    ) as mock_get, patch(
        "services.api_service.time.sleep"
    ):
        result = service.get_data(access_token="fake-test-token")

    assert result["results"][0]["id"] == "123"
    assert mock_get.call_count == 2

    # Both requests must have a timeout.
    for call in mock_get.call_args_list:
        assert call.kwargs.get("timeout") is not None

    
def test_get_data_does_not_retry_after_503():
    import requests
    import pytest

    service = APIService()

    server_error = Mock()
    server_error.status_code = 503
    server_error.headers = {}
    server_error.text = "Service unavailable"
    server_error.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "503 Service Unavailable"
    )

    with patch.object(
        service.session,
        "get",
        return_value=server_error,
    ) as mock_get:
        with pytest.raises(requests.exceptions.HTTPError):
            service.get_data(access_token="fake-test-token")

    assert mock_get.call_count == 1


def test_get_data_does_not_retry_after_timeout():
    import requests
    import pytest

    service = APIService()

    with patch.object(
        service.session,
        "get",
        side_effect=requests.exceptions.Timeout("Request timed out"),
    ) as mock_get:
        with pytest.raises(requests.exceptions.Timeout):
            service.get_data(access_token="fake-test-token")

    assert mock_get.call_count == 1
    


def test_get_data_returns_empty_results():
    service = APIService()

    success = Mock()
    success.status_code = 200
    success.headers = {}
    success.json.return_value = {"results": []}

    with patch.object(
        service.session,
        "get",
        return_value=success,
    ) as mock_get:
        result = service.get_data(access_token="fake-test-token")

    assert result["results"] == []
    assert mock_get.call_count == 1


def test_get_data_does_not_retry_after_401():
    import requests
    import pytest

    service = APIService()

    unauthorized = Mock()
    unauthorized.status_code = 401
    unauthorized.headers = {}
    unauthorized.text = "Unauthorized"
    unauthorized.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "401 Unauthorized"
    )

    with patch.object(
        service.session,
        "get",
        return_value=unauthorized,
    ) as mock_get, patch("services.api_service.time.sleep"):
        with pytest.raises(requests.exceptions.HTTPError):
            service.get_data(access_token="fake-test-token")

    assert mock_get.call_count == 1

def test_get_data_does_not_retry_after_second_429():
    import pytest
    import requests

    service = APIService()

    first_429 = Mock()
    first_429.status_code = 429
    first_429.headers = {"Retry-After": "0"}
    first_429.text = "Rate limited"

    second_429 = Mock()
    second_429.status_code = 429
    second_429.headers = {"Retry-After": "0"}
    second_429.text = "Rate limited again"
    second_429.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "429 Too Many Requests"
    )

    with patch.object(
        service.session,
        "get",
        side_effect=[first_429, second_429],
    ) as mock_get, patch("services.api_service.time.sleep"):
        with pytest.raises(requests.exceptions.HTTPError):
            service.get_data(access_token="fake-test-token")

    assert mock_get.call_count == 2


def test_get_data_parses_http_date_retry_after():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    service = APIService()

    rate_limited = Mock()
    rate_limited.status_code = 429
    rate_limited.headers = {
        "Retry-After": format_datetime(
            datetime.now(timezone.utc) + timedelta(seconds=30),
            usegmt=True,
        )
    }
    rate_limited.text = "Rate limited"

    success = Mock()
    success.status_code = 200
    success.headers = {}
    success.json.return_value = {"results": [{"id": "123"}]}

    with patch.object(
        service.session,
        "get",
        side_effect=[rate_limited, success],
    ) as mock_get, patch(
        "services.api_service.time.sleep"
    ) as mock_sleep:
        result = service.get_data(access_token="fake-test-token")

    assert result["results"][0]["id"] == "123"
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()
    delay = mock_sleep.call_args.args[0]
    assert 0 <= delay <= 30
