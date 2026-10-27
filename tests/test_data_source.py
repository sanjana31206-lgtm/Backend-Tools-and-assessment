import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from dlt.extract.exceptions import ResourceExtractionError

PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubspot-deals-etl"
    / "hubspot-deals-etl"
)
sys.path.insert(0, str(PROJECT_DIR))

from services.data_source import create_data_source


def make_deal(deal_id, name):
    return {
        "id": str(deal_id),
        "properties": {
            "dealname": name,
            "amount": "100",
        },
    }


def test_data_source_extracts_multiple_pages():
    first_page = {
        "results": [make_deal(1, "Deal One"), make_deal(2, "Deal Two")],
        "paging": {"next": {"after": "cursor-page-2"}},
    }
    second_page = {
        "results": [make_deal(3, "Deal Three")],
    }

    with patch("services.data_source.APIService") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.get_data.side_effect = [first_page, second_page]

        source_factory = create_data_source(
            job_config={"organizationId": "test-org"},
            auth_config={"accessToken": "fake-test-token"},
            filters={"scan_id": "test-scan"},
        )

        resource = source_factory[0]
        records = list(resource)

    assert [record["id"] for record in records] == ["1", "2", "3"]
    assert mock_api.get_data.call_count == 2
    assert mock_api.get_data.call_args_list[1].kwargs["after"] == "cursor-page-2"


def test_data_source_resumes_mid_page_without_duplicate_records():
    page = {
        "results": [
            make_deal(1, "Deal One"),
            make_deal(2, "Deal Two"),
            make_deal(3, "Deal Three"),
        ],
        "paging": {"next": {"after": "cursor-page-2"}},
    }

    pause_state = {"calls": 0}
    checkpoints = []

    def pause_callback(job_id):
        pause_state["calls"] += 1
        return pause_state["calls"] >= 3

    def checkpoint_callback(job_id, checkpoint):
        checkpoints.append(checkpoint)

    with patch("services.data_source.APIService") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.get_data.side_effect = [
            page,
            page,
            {"results": []},
        ]
        first_source = create_data_source(
            job_config={"organizationId": "test-org"},
            auth_config={"accessToken": "fake-test-token"},
            filters={"scan_id": "test-scan"},
            checkpoint_callback=checkpoint_callback,
            check_pause_callback=pause_callback,
        )

        first_records = list(first_source[0])

        mid_page = next(
            checkpoint
            for checkpoint in checkpoints
            if checkpoint["phase"] == "main_data_paused_mid_page"
        )

        checkpoint_data = mid_page["checkpoint_data"]
        resume_from = {
            "cursor": mid_page["cursor"],
            "page_number": mid_page["page_number"],
            "records_processed": mid_page["records_processed"],
            "records_completed_in_page": checkpoint_data[
                "records_completed_in_page"
            ],
        }

        second_source = create_data_source(
            job_config={"organizationId": "test-org"},
            auth_config={"accessToken": "fake-test-token"},
            filters={"scan_id": "test-scan"},
            resume_from=resume_from,
        )

        resumed_records = list(second_source[0])

    all_ids = [record["id"] for record in first_records + resumed_records]

    assert all_ids == ["1", "2", "3"]
    assert len(all_ids) == len(set(all_ids))


def test_data_source_preserves_contact_and_company_associations():
    page = {
        "results": [
            {
                "id": "42",
                "properties": {
                    "dealname": "Deal with associations",
                    "amount": "100",
                },
                "associations": {
                    "contacts": {
                        "results": [{"id": "101"}, {"id": "102"}]
                    },
                    "companies": {
                        "results": [{"id": "201"}]
                    },
                },
            }
        ]
    }

    with patch("services.data_source.APIService") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.get_data.return_value = page

        source_factory = create_data_source(
            job_config={"organizationId": "test-org"},
            auth_config={"accessToken": "fake-test-token"},
            filters={"scan_id": "test-scan"},
        )

        records = list(source_factory[0])

    assert records[0]["associated_contact_ids"] == ["101", "102"]
    assert records[0]["associated_company_ids"] == ["201"]
    assert (
        mock_api.get_data.call_args.kwargs["associations"]
        == "contacts,companies"
    )


def test_data_source_handles_429_during_pagination():
    """A 429 raised by get_data during pagination propagates (wrapped by DLT) correctly."""
    first_page = {
        "results": [make_deal(1, "Deal One")],
        "paging": {"next": {"after": "cursor-page-2"}},
    }

    with patch("services.data_source.APIService") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.get_data.side_effect = [
            first_page,
            requests.exceptions.HTTPError("429 Too Many Requests"),
        ]

        source_factory = create_data_source(
            job_config={"organizationId": "test-org"},
            auth_config={"accessToken": "fake-test-token"},
            filters={"scan_id": "test-scan"},
        )

        with pytest.raises((requests.exceptions.HTTPError, ResourceExtractionError)):
            list(source_factory[0])

    assert mock_api.get_data.call_count == 2


def test_data_source_deals_without_associations():
    """Deals with no associations produce empty id lists without errors."""
    page = {
        "results": [
            {
                "id": "99",
                "properties": {"dealname": "No Assoc Deal", "amount": "50"},
            }
        ]
    }

    with patch("services.data_source.APIService") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.get_data.return_value = page

        source_factory = create_data_source(
            job_config={"organizationId": "test-org"},
            auth_config={"accessToken": "fake-test-token"},
            filters={"scan_id": "test-scan"},
        )

        records = list(source_factory[0])

    assert records[0]["associated_contact_ids"] == []
    assert records[0]["associated_company_ids"] == []


def test_data_source_raises_on_page_safety_limit():
    """When the 1000-page safety limit is hit with more pages remaining,
    the generator must raise RuntimeError rather than silently completing."""
    counter = {"n": 0}

    def _always_more_page(*args, **kwargs):
        counter["n"] += 1
        return {
            "results": [{"id": str(counter["n"]), "properties": {}}],
            "paging": {"next": {"after": f"cursor-{counter['n']}"}},
        }

    with patch("services.data_source.APIService") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.get_data.side_effect = _always_more_page

        source_factory = create_data_source(
            job_config={"organizationId": "test-org"},
            auth_config={"accessToken": "fake-test-token"},
            filters={"scan_id": "test-scan"},
        )

        with pytest.raises((RuntimeError, Exception)) as exc_info:
            list(source_factory[0])

    # The raised exception must be our safety-limit RuntimeError (possibly
    # wrapped by DLT's ResourceExtractionError).
    full_msg = str(exc_info.value).lower()
    assert "safety limit" in full_msg or "incomplete" in full_msg, (
        f"Expected safety-limit error, got: {exc_info.value}"
    )
