"""
Cloud SQL helpers via the SQL Admin API (no dedicated google-cloud-sql
admin client exists, so we use the generic discovery-based client).
"""
from . import tool
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

try:
    from .monitoring import get_cpu_utilization
except Exception:
    from monitoring import get_cpu_utilization


@tool(
    name="list_cloud_sql_instances",
    description="List Cloud SQL instances in the project with their state, database version, and tier.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def list_sql_instances(credentials, project_id: str) -> list[dict]:
    try:
        service = build("sqladmin", "v1beta4", credentials=credentials, cache_discovery=False)
        resp = service.instances().list(project=project_id).execute()
        items = resp.get("items", [])
        return [
            {
                "name": i["name"],
                "state": i.get("state"),
                "database_version": i.get("databaseVersion"),
                "tier": i.get("settings", {}).get("tier"),
            }
            for i in items
        ]
    except HttpError as e:
        return [{"error": str(e)}]


@tool(
    name="list_high_cpu_sql_instances",
    description="List Cloud SQL instances whose recent CPU utilization is at or above a threshold percentage.",
    parameters={
        "type": "object",
        "properties": {"threshold_percent": {"type": "number", "description": "CPU percent threshold, default 80."}},
        "required": [],
    },
)
def list_high_cpu_sql_instances(credentials, project_id: str, threshold_percent: float = 80.0) -> list[dict]:
    instances = list_sql_instances(credentials, project_id)
    if instances and "error" in instances[0]:
        return instances

    utilization = get_cpu_utilization(credentials, project_id, resource_type="cloudsql_database")
    util_by_name = {u["resource"]: u["utilization_percent"] for u in utilization if "resource" in u}

    flagged = []
    for inst in instances:
        pct = util_by_name.get(inst["name"])
        if pct is not None and pct >= threshold_percent:
            flagged.append({**inst, "cpu_utilization_percent": pct})
    return flagged
