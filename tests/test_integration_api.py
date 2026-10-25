import os
import requests

BASE_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:5200")
SCAN_ID = "hubspot_scan_001"


def test_health_endpoint():
    response = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_scan_status_is_completed():
    response = requests.get(
        f"{BASE_URL}/api/scan/{SCAN_ID}/status", timeout=10
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "completed"
    assert body["data"]["recordsExtracted"] == 5


def test_deals_results_have_unique_ids_and_names():
    response = requests.get(
        f"{BASE_URL}/api/results/{SCAN_ID}/result",
        params={"tableName": "hubspot_deals", "limit": 10},
        timeout=10,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True

    records = body["data"]["records"]
    assert len(records) == 5

    ids = [record["hubspot_deal_id"] for record in records]
    assert len(ids) == len(set(ids))
    assert all(record.get("deal_name") for record in records)
