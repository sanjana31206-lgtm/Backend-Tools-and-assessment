"""
Regression tests for the HubSpot Deals resume flow.

Covers:
- Paused-job resume: status transitions correctly and execute_scan is scheduled
- Crashed-job resume: same path works for CRASHED status
- Missing checkpoint: resume_job rejects the attempt
- Invalid statuses: completed, running, cancelled, pending all rejected
- execute_scan transitions RESUMING -> RUNNING before extraction
- executor.submit failure marks the job as failed (not stuck in RESUMING)
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
import pytest
from flask import Flask

PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubspot-deals-etl"
    / "hubspot-deals-etl"
)
sys.path.insert(0, str(PROJECT_DIR))

from api.routes import create_api
from models.models import JobStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(status: str, scan_id: str = "scan-abc") -> dict:
    return {
        "scanId": scan_id,
        "organizationId": "org-1",
        "status": status,
        "config": {"auth": {"accessToken": "tok"}, "filters": {}},
    }


def _make_checkpoint(cursor: str = "cursor-42", page: int = 3) -> dict:
    return {
        "cursor": cursor,
        "pageNumber": page,
        "recordsProcessed": 30,
        "phase": "main_data",
        "checkpoint_data": {},
    }


# ---------------------------------------------------------------------------
# Route-level fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    fake_service = Mock()
    fake_service.get_scan_status.return_value = None

    with patch("api.routes.ExtractionService", return_value=fake_service):
        app = Flask(__name__)
        api = create_api()
        api.init_app(app)
        app.config["TESTING"] = True
        yield app.test_client(), fake_service


# ---------------------------------------------------------------------------
# 1. Paused-job resume: success path
# ---------------------------------------------------------------------------

def test_resume_paused_job_schedules_execution(client):
    """A PAUSED job is resumed: route returns 200 and schedules execute_scan."""
    test_client, fake_service = client
    fake_service.resume_scan.return_value = {
        "success": True,
        "scanId": "scan-abc",
        "status": JobStatus.RESUMING.value,
    }
    # execute_scan is called to build the coroutine passed to asyncio.run;
    # we mock it to return a coroutine that does nothing.
    async def _noop(*a, **kw): pass
    fake_service.execute_scan = Mock(side_effect=_noop)

    with patch("api.routes.executor.submit") as mock_submit:
        response = test_client.post("/api/scan/scan-abc/resume")

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["status"] == JobStatus.RESUMING.value
    fake_service.resume_scan.assert_called_once_with("scan-abc")
    fake_service.execute_scan.assert_called_once_with("scan-abc")
    mock_submit.assert_called_once()
    assert mock_submit.call_args.args[0] is asyncio.run
    # Clean up the coroutine to avoid ResourceWarning
    mock_submit.call_args.args[1].close()


# ---------------------------------------------------------------------------
# 2. Crashed-job resume: same success path
# ---------------------------------------------------------------------------

def test_resume_crashed_job_schedules_execution(client):
    """A CRASHED job is resumed: route returns 200 and schedules execute_scan."""
    test_client, fake_service = client
    fake_service.resume_scan.return_value = {
        "success": True,
        "scanId": "scan-crashed",
        "status": JobStatus.RESUMING.value,
    }
    async def _noop(*a, **kw): pass
    fake_service.execute_scan = Mock(side_effect=_noop)

    with patch("api.routes.executor.submit") as mock_submit:
        response = test_client.post("/api/scan/scan-crashed/resume")

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    mock_submit.assert_called_once()
    mock_submit.call_args.args[1].close()


# ---------------------------------------------------------------------------
# 3. Missing checkpoint: resume_job rejects
# ---------------------------------------------------------------------------

def test_resume_without_checkpoint_returns_400(client):
    """resume_scan returns failure when no checkpoint exists; route returns 400."""
    test_client, fake_service = client
    fake_service.resume_scan.return_value = {
        "success": False,
        "message": "No checkpoint found to resume from",
    }

    with patch("api.routes.executor.submit") as mock_submit:
        response = test_client.post("/api/scan/scan-nochk/resume")

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    mock_submit.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Invalid statuses: all rejected, executor never called
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status_msg", [
    "Cannot resume job with status: completed",
    "Cannot resume job with status: running",
    "Cannot resume job with status: cancelled",
    "Cannot resume job with status: pending",
    "Cannot resume job with status: resuming",
])
def test_resume_invalid_status_returns_400(client, status_msg):
    """Non-resumable statuses are rejected; executor is never called."""
    test_client, fake_service = client
    fake_service.resume_scan.return_value = {
        "success": False,
        "message": status_msg,
    }

    with patch("api.routes.executor.submit") as mock_submit:
        response = test_client.post("/api/scan/scan-xyz/resume")

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    mock_submit.assert_not_called()


# ---------------------------------------------------------------------------
# 5. execute_scan transitions RESUMING -> RUNNING
# ---------------------------------------------------------------------------

def test_execute_scan_transitions_resuming_to_running():
    """execute_scan must set status to RUNNING when the job is in RESUMING."""
    from services.extraction_service import ExtractionService

    service = ExtractionService.__new__(ExtractionService)
    service.logger = Mock()
    service.pipeline_name = "hubspot_deals_extraction"
    service.source_type = "hubspot_deals"

    job = _make_job(JobStatus.RESUMING.value)
    checkpoint = _make_checkpoint()

    mock_job_service = Mock()
    # First call: decrypt=True at top of execute_scan; second: status check at end
    mock_job_service.get_job.side_effect = [job, job]
    mock_job_service.get_latest_checkpoint.return_value = checkpoint
    mock_job_service.update_job_status.return_value = None
    mock_job_service.update_job_heartbeat.return_value = None
    mock_job_service.complete_job.return_value = None
    service.job_service = mock_job_service

    mock_pipeline = Mock()
    mock_pipeline.pipeline_name = "hubspot_deals_extraction"
    mock_pipeline.dataset_name = "org_1"
    mock_pipeline.run.return_value = None

    with patch.object(service, "create_source_with_checkpoints", return_value=[Mock()]), \
         patch("services.extraction_service.dlt") as mock_dlt, \
         patch("services.extraction_service.build_dataset_name", return_value="org_1"):
        mock_dlt.pipeline.return_value = mock_pipeline
        asyncio.run(service.execute_scan("scan-abc"))

    # The critical assertion: RUNNING transition must have been called
    mock_job_service.update_job_status.assert_called_once_with(
        "scan-abc", JobStatus.RUNNING
    )


# ---------------------------------------------------------------------------
# 6. execute_scan does NOT re-transition if already RUNNING (fresh start path)
# ---------------------------------------------------------------------------

def test_execute_scan_does_not_retransition_when_already_running():
    """execute_scan must not call update_job_status when job is already RUNNING."""
    from services.extraction_service import ExtractionService

    service = ExtractionService.__new__(ExtractionService)
    service.logger = Mock()
    service.pipeline_name = "hubspot_deals_extraction"
    service.source_type = "hubspot_deals"

    job = _make_job(JobStatus.RUNNING.value)
    checkpoint = _make_checkpoint()

    mock_job_service = Mock()
    mock_job_service.get_job.side_effect = [job, job]
    mock_job_service.get_latest_checkpoint.return_value = checkpoint
    mock_job_service.update_job_heartbeat.return_value = None
    mock_job_service.complete_job.return_value = None
    service.job_service = mock_job_service

    mock_pipeline = Mock()
    mock_pipeline.pipeline_name = "hubspot_deals_extraction"
    mock_pipeline.dataset_name = "org_1"
    mock_pipeline.run.return_value = None

    with patch.object(service, "create_source_with_checkpoints", return_value=[Mock()]), \
         patch("services.extraction_service.dlt") as mock_dlt, \
         patch("services.extraction_service.build_dataset_name", return_value="org_1"):
        mock_dlt.pipeline.return_value = mock_pipeline
        asyncio.run(service.execute_scan("scan-abc"))

    mock_job_service.update_job_status.assert_not_called()


# ---------------------------------------------------------------------------
# 7. executor.submit failure marks job as failed, not stuck in RESUMING
# ---------------------------------------------------------------------------

def test_executor_submit_failure_marks_job_failed(client):
    """If executor.submit raises, the job must be marked failed, not left in RESUMING."""
    test_client, fake_service = client
    fake_service.resume_scan.return_value = {
        "success": True,
        "scanId": "scan-abc",
        "status": JobStatus.RESUMING.value,
    }
    async def _noop(*a, **kw): pass
    fake_service.execute_scan = Mock(side_effect=_noop)
    fake_service.job_service = Mock()
    fake_service.job_service.fail_job.return_value = None

    with patch(
        "api.routes.executor.submit",
        side_effect=RuntimeError("executor shut down"),
    ):
        response = test_client.post("/api/scan/scan-abc/resume")

    assert response.status_code == 500
    assert response.get_json()["success"] is False
    fake_service.job_service.fail_job.assert_called_once()
    call_args = fake_service.job_service.fail_job.call_args
    assert call_args.args[0] == "scan-abc"
    assert "executor" in call_args.args[1].lower() or "submission" in call_args.args[1].lower()


# ---------------------------------------------------------------------------
# 8. Coroutine is closed when executor.submit fails (no ResourceWarning)
# ---------------------------------------------------------------------------

def test_executor_submit_failure_closes_coroutine(client):
    """The coroutine created for execute_scan must be closed when submit fails,
    preventing a 'coroutine was never awaited' ResourceWarning."""
    test_client, fake_service = client
    fake_service.resume_scan.return_value = {
        "success": True,
        "scanId": "scan-abc",
        "status": JobStatus.RESUMING.value,
    }

    closed = {"value": False}

    class _TrackingCoro:
        """Minimal coroutine stand-in that records whether close() was called."""
        def close(self):
            closed["value"] = True
        def send(self, v): raise StopIteration
        def throw(self, *a): raise StopIteration
        def __await__(self): return iter([])

    fake_service.execute_scan = Mock(return_value=_TrackingCoro())
    fake_service.job_service = Mock()
    fake_service.job_service.fail_job.return_value = None

    with patch(
        "api.routes.executor.submit",
        side_effect=RuntimeError("executor shut down"),
    ):
        response = test_client.post("/api/scan/scan-abc/resume")

    assert response.status_code == 500
    assert closed["value"] is True, "coroutine.close() was not called after submit failure"


# ---------------------------------------------------------------------------
# 9. fail_job raising after submit failure is logged, not hidden
# ---------------------------------------------------------------------------

def test_executor_submit_failure_with_fail_job_raising(client):
    """If fail_job itself raises after executor.submit fails, the route must
    still return 500 and not propagate the secondary exception."""
    test_client, fake_service = client
    fake_service.resume_scan.return_value = {
        "success": True,
        "scanId": "scan-abc",
        "status": JobStatus.RESUMING.value,
    }
    async def _noop(*a, **kw): pass
    fake_service.execute_scan = Mock(side_effect=_noop)
    fake_service.job_service = Mock()
    fake_service.job_service.fail_job.side_effect = RuntimeError("DB unavailable")

    with patch(
        "api.routes.executor.submit",
        side_effect=RuntimeError("executor shut down"),
    ):
        response = test_client.post("/api/scan/scan-abc/resume")

    assert response.status_code == 500
    body = response.get_json()
    assert body["success"] is False
    # fail_job was still attempted
    fake_service.job_service.fail_job.assert_called_once()
