import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.tools import compute as compute_module


class DummyInstance:
    def __init__(self, status):
        self.status = status


class DummyClient:
    def __init__(self, credentials=None, status="PROVISIONING"):
        self._status = status
        self.started = False

    def get(self, project, zone, instance):
        return DummyInstance(self._status)

    def reset(self, project, zone, instance):
        if self._status != "RUNNING":
            raise AssertionError("reset should not be called for non-running instances")

    def start(self, project, zone, instance):
        self.started = True


def test_restart_instance_fails_when_vm_is_not_ready():
    original_client = compute_module.compute_v1.InstancesClient
    def create_dummy(credentials=None):
        return DummyClient(status="PROVISIONING")

    compute_module.compute_v1.InstancesClient = create_dummy
    try:
        result = compute_module.restart_instance(
            credentials=None,
            project_id="demo-project",
            instance_name="collabboard-backend-service",
            zone="us-central1-a",
        )
    finally:
        compute_module.compute_v1.InstancesClient = original_client

    assert result["status"] == "failed"
    assert "not ready" in result["error"].lower()
    assert result["zone"] == "us-central1-a"


def test_restart_instance_starts_terminated_vm():
    original_client = compute_module.compute_v1.InstancesClient
    started_client = None

    def create_dummy(credentials=None):
        nonlocal started_client
        started_client = DummyClient(status="TERMINATED")
        return started_client

    compute_module.compute_v1.InstancesClient = create_dummy
    try:
        result = compute_module.restart_instance(
            credentials=None,
            project_id="demo-project",
            instance_name="collabboard-backend-service",
            zone="us-central1-a",
        )
    finally:
        compute_module.compute_v1.InstancesClient = original_client

    assert result["status"] == "submitted"
    assert result["action"] == "start"
    assert started_client is not None and started_client.started is True
    assert result["zone"] == "us-central1-a"
