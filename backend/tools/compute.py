"""
Compute Engine helpers: list instances, look up a VM's zone, restart a VM.
"""
from . import tool
from google.cloud import compute_v1
from google.api_core.exceptions import GoogleAPIError


@tool(
    name="list_compute_instances",
    description="List all Compute Engine VM instances in the project, across all zones, with their status.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def list_instances(credentials, project_id: str) -> list[dict]:
    """List every Compute Engine VM across all zones in the project."""
    try:
        client = compute_v1.InstancesClient(credentials=credentials)
        agg = client.aggregated_list(project=project_id)
        results = []
        for zone, response in agg:
            if response.instances:
                zone_name = zone.split("/")[-1]
                for inst in response.instances:
                    results.append(
                        {
                            "name": inst.name,
                            "zone": zone_name,
                            "status": inst.status,
                            "machine_type": inst.machine_type.rsplit("/", 1)[-1],
                        }
                    )
        return results
    except GoogleAPIError as e:
        return [{"error": _normalize_compute_error(e, project_id)}]


def find_instance_zone(credentials, project_id: str, instance_name: str) -> str | None:
    for inst in list_instances(credentials, project_id):
        if inst.get("name") == instance_name:
            return inst.get("zone")
    return None


def _normalize_compute_error(error: GoogleAPIError, project_id: str | None = None) -> str:
    message = str(error)
    if (
        "Compute Engine API has not been used" in message
        or "Compute Engine API has been disabled" in message
        or ("compute.googleapis.com" in message and "disabled" in message)
    ):
        target = f" for project {project_id}" if project_id else ""
        return (
            f"Compute Engine API is not enabled{target}. "
            "Enable the Compute Engine API in the Google Cloud Console and retry."
        )
    return message


def get_instance_status(credentials, project_id: str, instance_name: str, zone: str) -> str | None:
    client = compute_v1.InstancesClient(credentials=credentials)
    instance = client.get(project=project_id, zone=zone, instance=instance_name)
    return getattr(instance, "status", None)


@tool(
    name="restart_vm",
    description="Restart (reset) a named Compute Engine VM instance. This is a real, billable, mutating action -- only call it when the user explicitly asked to restart/reboot a specific VM.",
    parameters={
        "type": "object",
        "properties": {
            "instance_name": {"type": "string", "description": "Name of the VM instance to restart."},
            "zone": {"type": "string", "description": "Zone of the VM, if known. Omit to auto-detect."},
        },
        "required": ["instance_name"],
    },
    requires_confirmation=True,
)
def restart_instance(credentials, project_id: str, instance_name: str, zone: str | None = None) -> dict:
    """Soft-restart (reset) a VM. Auto-discovers the zone if not supplied."""
    try:
        if not zone:
            zone = find_instance_zone(credentials, project_id, instance_name)
            if not zone:
                return {
                    "status": "failed",
                    "instance": instance_name,
                    "error": "Instance not found in this project.",
                }

        status = get_instance_status(credentials, project_id, instance_name, zone)
        if not status:
            return {
                "status": "failed",
                "instance": instance_name,
                "zone": zone,
                "error": "Unable to determine instance status before restart.",
            }

        client = compute_v1.InstancesClient(credentials=credentials)
        if status == "RUNNING":
            client.reset(project=project_id, zone=zone, instance=instance_name)
            return {"status": "submitted", "instance": instance_name, "zone": zone, "action": "reset"}
        if status in {"TERMINATED", "STOPPED", "STOPPING"}:
            client.start(project=project_id, zone=zone, instance=instance_name)
            return {"status": "submitted", "instance": instance_name, "zone": zone, "action": "start"}

        return {
            "status": "failed",
            "instance": instance_name,
            "zone": zone,
            "error": (
                f"Instance is not ready for restart. Current status: {status}. "
                "Wait until the VM is RUNNING or TERMINATED/STOPPED and retry."
            ),
        }
    except GoogleAPIError as e:
        return {
            "status": "failed",
            "instance": instance_name,
            "zone": zone,
            "error": _normalize_compute_error(e, project_id),
        }
