import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubspot-deals-etl"
    / "hubspot-deals-etl"
)
sys.path.insert(0, str(PROJECT_DIR))

from services.api_service import APIService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(body=None):
    r = Mock()
    r.status_code = 200
    r.headers = {}
    r.json.return_value = body or {"results": [{"id": "123"}]}
    return r


def _err(status, raise_on_status=True):
    r = Mock()
    r.status_code = status
    r.headers = {}
    r.text = f"HTTP {status}"
    if raise_on_status:
        r.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"{status} Error"
        )
    return r


# ---------------------------------------------------------------------------
# 429 rate-limit handling (existing)
# ---------------------------------------------------------------------------

def test_get_data_retries_after_429():
    service = APIService()

    rate_limited = _err(429, raise_on_status=False)
    rate_limited.headers = {"Retry-After": "0"}

    with patch.object(
        service.session, "get", side_effect=[rate_limited, _ok()]
    ) as mock_get, patch("services.api_service.time.sleep"):
        result = service.get_data(access_token="fake-test-token")

    assert result["results"][0]["id"] == "123"
    assert mock_get.call_count == 2
    for call in mock_get.call_args_list:
        assert call.kwargs.get("timeout") is not None


def test_get_data_does_not_retry_after_second_429():
    service = APIService()

    first_429 = _err(429, raise_on_status=False)
    first_429.headers = {"Retry-After": "0"}
    second_429 = _err(429)
    second_429.headers = {"Retry-After": "0"}

    with patch.object(
        service.session, "get", side_effect=[first_429, second_429]
    ) as mock_get, patch("services.api_service.time.sleep"):
        with pytest.raises(requests.exceptions.HTTPError):
            service.get_data(access_token="fake-test-token")

    assert mock_get.call_count == 2


def test_get_data_parses_http_date_retry_after():
    service = APIService()

    rate_limited = _err(429, raise_on_status=False)
    rate_limited.headers = {
        "Retry-After": format_datetime(
            datetime.now(timezone.utc) + timedelta(seconds=30),
            usegmt=True,
        )
    }

    with patch.object(
        service.session, "get", side_effect=[rate_limited, _ok()]
    ) as mock_get, patch("services.api_service.time.sleep") as mock_sleep:
        result = service.get_data(access_token="fake-test-token")

    assert result["results"][0]["id"] == "123"
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()
    assert 0 <= mock_sleep.call_args.args[0] <= 30


# ---------------------------------------------------------------------------
# 5xx retry handling (new policy)
# ---------------------------------------------------------------------------

def test_get_data_retries_after_503_then_succeeds():
    """A single 503 is retried and the subsequent 200 is returned."""
    service = APIService()

    with patch.object(
        service.session, "get", side_effect=[_err(503, raise_on_status=False), _ok()]
    ) as mock_get, patch("services.api_service.time.sleep"):
        result = service.get_data(access_token="fake-test-token")

    assert result["results"][0]["id"] == "123"
    assert mock_get.call_count == 2


def test_get_data_raises_after_repeated_503():
    """Exhausting all retries on 503 raises HTTPError."""
    service = APIService()  # max_retries=2 → 2 attempts

    first_503 = _err(503, raise_on_status=False)
    second_503 = _err(503)  # raise_for_status raises on the final attempt

    with patch.object(
        service.session, "get", side_effect=[first_503, second_503]
    ) as mock_get, patch("services.api_service.time.sleep"):
        with pytest.raises(requests.exceptions.HTTPError):
            service.get_data(access_token="fake-test-token")

    assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# Network-error retry handling (new policy)
# ---------------------------------------------------------------------------

def test_get_data_retries_after_timeout_then_succeeds():
    """A single Timeout is retried and the subsequent 200 is returned."""
    service = APIService()

    with patch.object(
        service.session,
        "get",
        side_effect=[requests.exceptions.Timeout("timed out"), _ok()],
    ) as mock_get, patch("services.api_service.time.sleep"):
        result = service.get_data(access_token="fake-test-token")

    assert result["results"][0]["id"] == "123"
    assert mock_get.call_count == 2


def test_get_data_raises_after_repeated_connection_errors():
    """Exhausting all retries on ConnectionError re-raises the network error."""
    service = APIService()  # max_retries=2 → 2 attempts

    with patch.object(
        service.session,
        "get",
        side_effect=requests.exceptions.ConnectionError("unreachable"),
    ) as mock_get, patch("services.api_service.time.sleep"):
        with pytest.raises(requests.exceptions.ConnectionError):
            service.get_data(access_token="fake-test-token")

    assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# Permanent errors — must never retry
# ---------------------------------------------------------------------------

def test_get_data_does_not_retry_after_401():
    service = APIService()

    with patch.object(
        service.session, "get", return_value=_err(401)
    ) as mock_get, patch("services.api_service.time.sleep"):
        with pytest.raises(requests.exceptions.HTTPError):
            service.get_data(access_token="fake-test-token")

    assert mock_get.call_count == 1


def test_get_data_does_not_retry_after_403():
    service = APIService()

    with patch.object(
        service.session, "get", return_value=_err(403)
    ) as mock_get, patch("services.api_service.time.sleep"):
        with pytest.raises(requests.exceptions.HTTPError):
            service.get_data(access_token="fake-test-token")

    assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# Misc / existing
# ---------------------------------------------------------------------------

def test_get_data_returns_empty_results():
    service = APIService()

    ok = Mock()
    ok.status_code = 200
    ok.headers = {}
    ok.json.return_value = {"results": []}

    with patch.object(service.session, "get", return_value=ok) as mock_get:
        result = service.get_data(access_token="fake-test-token")

    assert result["results"] == []
    assert mock_get.call_count == 1


def test_max_retries_is_configurable():
    """max_retries=3 means 3 total attempts before giving up."""
    service = APIService(max_retries=3)

    r429 = _err(429, raise_on_status=False)
    r429.headers = {"Retry-After": "0"}
    final_429 = _err(429)
    final_429.headers = {"Retry-After": "0"}

    with patch.object(
        service.session, "get", side_effect=[r429, r429, final_429]
    ) as mock_get, patch("services.api_service.time.sleep"):
        with pytest.raises(requests.exceptions.HTTPError):
            service.get_data(access_token="fake-test-token")

    assert mock_get.call_count == 3


def test_backoff_delay_is_bounded():
    """Exponential backoff must not exceed the 60-second cap."""
    service = APIService(max_retries=3)

    r503 = _err(503, raise_on_status=False)
    final_503 = _err(503)

    with patch.object(
        service.session, "get", side_effect=[r503, r503, final_503]
    ) as mock_get, patch("services.api_service.time.sleep") as mock_sleep:
        with pytest.raises(requests.exceptions.HTTPError):
            service.get_data(access_token="fake-test-token")

    for call in mock_sleep.call_args_list:
        assert call.args[0] <= 60


# ---------------------------------------------------------------------------
# validate_token
# ---------------------------------------------------------------------------

def test_validate_token_uses_timeout():
    service = APIService()
    ok = Mock()
    ok.status_code = 200

    with patch.object(service.session, "get", return_value=ok) as mock_get:
        assert service.validate_token("fake-test-token") is True

    assert mock_get.call_args.kwargs.get("timeout") is not None


def test_validate_token_returns_false_on_401():
    service = APIService()
    unauth = Mock()
    unauth.status_code = 401

    with patch.object(service.session, "get", return_value=unauth):
        assert service.validate_token("bad-token") is False


def test_validate_token_returns_false_on_network_error():
    service = APIService()

    with patch.object(
        service.session,
        "get",
        side_effect=requests.exceptions.ConnectionError("unreachable"),
    ):
        assert service.validate_token("fake-test-token") is False


# ---------------------------------------------------------------------------
# zero / negative max_retries — must not AttributeError on None response
# ---------------------------------------------------------------------------

def test_get_data_zero_max_retries_still_makes_one_attempt():
    """max_retries=0 must still attempt the request once and return the result."""
    service = APIService(max_retries=0)

    with patch.object(service.session, "get", return_value=_ok()) as mock_get:
        result = service.get_data(access_token="fake-test-token")

    assert result["results"][0]["id"] == "123"
    assert mock_get.call_count == 1


def test_get_data_negative_max_retries_still_makes_one_attempt():
    """max_retries=-1 must still attempt the request once and not AttributeError."""
    service = APIService(max_retries=-1)

    with patch.object(service.session, "get", return_value=_ok()) as mock_get:
        result = service.get_data(access_token="fake-test-token")

    assert result["results"][0]["id"] == "123"
    assert mock_get.call_count == 1
