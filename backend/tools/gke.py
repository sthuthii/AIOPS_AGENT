"""
GKE helpers: list clusters across every zone/region and flag unhealthy ones.
"""
from . import tool
from google.cloud import container_v1
from google.api_core.exceptions import GoogleAPIError

_HEALTHY_STATUSES = {"RUNNING"}


@tool(
    name="list_gke_clusters",
    description="List GKE (Kubernetes) clusters in the project with their status. Can optionally filter to only unhealthy clusters.",
    parameters={
        "type": "object",
        "properties": {
            "only_unhealthy": {
                "type": "boolean",
                "description": "If true, return only clusters not in RUNNING state.",
            }
        },
        "required": [],
    },
)
def list_clusters(credentials, project_id: str, only_unhealthy: bool = False) -> list[dict]:
    try:
        client = container_v1.ClusterManagerClient(credentials=credentials)
        # "-" for zone/location means "all locations" for this project.
        parent = f"projects/{project_id}/locations/-"
        response = client.list_clusters(parent=parent)
        clusters = [
            {
                "name": c.name,
                "location": c.location,
                "status": c.status.name,
                "node_count": c.current_node_count,
            }
            for c in response.clusters
        ]
        if only_unhealthy:
            clusters = [c for c in clusters if c["status"] not in _HEALTHY_STATUSES]
        return clusters
    except GoogleAPIError as e:
        return [{"error": str(e)}]
