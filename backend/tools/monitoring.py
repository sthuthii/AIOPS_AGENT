"""
Cloud Monitoring helpers: pull CPU utilization time series for Compute
Engine VMs or Cloud SQL instances over a recent window.
"""
from . import tool
import time

from google.cloud import monitoring_v3
from google.api_core.exceptions import GoogleAPIError

_METRIC_BY_RESOURCE = {
    "gce_instance": "compute.googleapis.com/instance/cpu/utilization",
    "cloudsql_database": "cloudsql.googleapis.com/database/cpu/utilization",
}

_LABEL_BY_RESOURCE = {
    "gce_instance": "instance_name",
    "cloudsql_database": "database_id",
}


@tool(
    name="get_cpu_utilization",
    description="Get recent average CPU utilization percentage per resource, for either Compute Engine VMs or Cloud SQL instances.",
    parameters={
        "type": "object",
        "properties": {
            "resource_type": {
                "type": "string",
                "enum": ["gce_instance", "cloudsql_database"],
                "description": "Which kind of resource to pull CPU metrics for.",
            },
            "minutes": {
                "type": "integer",
                "description": "How many minutes of recent history to average over (default 10).",
            },
        },
        "required": ["resource_type"],
    },
)
def get_cpu_utilization(credentials, project_id: str, resource_type: str = "gce_instance", minutes: int = 10) -> list[dict]:
    """
    Returns a list of {resource, utilization_percent} for the given
    resource_type ("gce_instance" or "cloudsql_database"), averaged
    over the last `minutes` minutes.
    """
    metric_type = _METRIC_BY_RESOURCE.get(resource_type)
    if not metric_type:
        return [{"error": f"Unsupported resource_type: {resource_type}"}]

    try:
        client = monitoring_v3.MetricServiceClient(credentials=credentials)
        project_name = f"projects/{project_id}"

        now = time.time()
        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": int(now)},
                "start_time": {"seconds": int(now - minutes * 60)},
            }
        )

        results = client.list_time_series(
            request={
                "name": project_name,
                "filter": f'metric.type="{metric_type}" AND resource.type="{resource_type}"',
                "interval": interval,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )

        label_key = _LABEL_BY_RESOURCE[resource_type]
        out = []
        for ts in results:
            values = [p.value.double_value for p in ts.points]
            if not values:
                continue
            avg_pct = round(sum(values) / len(values) * 100, 1)
            resource_name = ts.resource.labels.get(label_key, "unknown")
            out.append({"resource": resource_name, "utilization_percent": avg_pct})
        return out
    except GoogleAPIError as e:
        return [{"error": str(e)}]
