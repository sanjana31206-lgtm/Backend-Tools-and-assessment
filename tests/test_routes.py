import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from flask import Flask

PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubspot-deals-etl"
    / "hubspot-deals-etl"
)
sys.path.insert(0, str(PROJECT_DIR))

from api.routes import create_api


@pytest.fixture
def client():
    fake_service = Mock()
    fake_service.get_scan_status.return_value = None

    with patch(
        "api.routes.ExtractionService",
        return_value=fake_service,
    ):
        app = Flask(__name__)
        api = create_api()
        api.init_app(app)
        app.config["TESTING"] = True

        yield app.test_client(), fake_service


def test_start_scan_without_json_returns_400(client):
    test_client, _ = client

    response = test_client.post("/api/scan/start")

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_start_scan_with_invalid_json_data_returns_400(client):
    test_client, fake_service = client

    response = test_client.post(
        "/api/scan/start",
        json={"config": {}},
    )

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    fake_service.get_scan_status.assert_not_called()


def test_unknown_scan_status_returns_404(client):
    test_client, fake_service = client
    fake_service.get_scan_status.return_value = None

    response = test_client.get(
        "/api/scan/nonexistent_scan_123/status"
    )

    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_resume_scan_returns_result_and_schedules_execution(client):
    test_client, fake_service = client
    fake_service.resume_scan.return_value = {
        "success": True,
        "scanId": "scan-123",
        "status": "resuming",
    }
    fake_service.execute_scan = AsyncMock()

    with patch("api.routes.executor.submit") as submit:
        response = test_client.post("/api/scan/scan-123/resume")

    assert response.status_code == 200
    assert response.get_json()["status"] == "resuming"
    fake_service.resume_scan.assert_called_once_with("scan-123")
    fake_service.execute_scan.assert_called_once_with("scan-123")
    submit.assert_called_once()
    assert submit.call_args.args[0] is asyncio.run
    submit.call_args.args[1].close()


def test_resume_scan_does_not_schedule_when_resume_fails(client):
    test_client, fake_service = client
    fake_service.resume_scan.return_value = {
        "success": False,
        "message": "Scan cannot be resumed",
    }

    with patch("api.routes.executor.submit") as submit:
        response = test_client.post("/api/scan/scan-123/resume")

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    submit.assert_not_called()
