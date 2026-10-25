import sys
from pathlib import Path

import pytest
from marshmallow import ValidationError

PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubspot-deals-etl"
    / "hubspot-deals-etl"
)
sys.path.insert(0, str(PROJECT_DIR))

from api.schemas import validate_scan_request


def valid_scan_request():
    return {
        "config": {
            "scanId": "test_scan_001",
            "organizationId": "test_org",
            "type": ["user"],
            "auth": {
                "accessToken": "fake-test-token"
            }
        }
    }


def test_valid_scan_request():
    result = validate_scan_request(valid_scan_request())
    assert result["scanId"] == "test_scan_001"
    assert result["type"] == ["user"]


def test_scan_request_rejects_invalid_scan_id():
    request_data = valid_scan_request()
    request_data["config"]["scanId"] = "invalid scan id!"

    with pytest.raises(ValidationError):
        validate_scan_request(request_data)


def test_scan_request_rejects_missing_access_token():
    request_data = valid_scan_request()
    request_data["config"]["auth"] = {}

    with pytest.raises(ValidationError):
        validate_scan_request(request_data)


def test_scan_request_rejects_reversed_date_range():
    request_data = valid_scan_request()
    request_data["config"]["filters"] = {
        "dateRange": {
            "startDate": "2026-10-20",
            "endDate": "2026-10-10"
        }
    }

    with pytest.raises(ValidationError):
        validate_scan_request(request_data)
