"""
Lists the GCP projects the signed-in user can access, so the frontend
can offer a project picker after OAuth login.
"""
from . import tool
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


@tool(
    name="list_projects",
    description="List GCP projects the signed-in user can access.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def list_projects(credentials) -> list[dict]:
    try:
        service = build("cloudresourcemanager", "v1", credentials=credentials, cache_discovery=False)
        resp = service.projects().list().execute()
        return [
            {"project_id": p["projectId"], "name": p.get("name", p["projectId"]) }
            for p in resp.get("projects", [])
            if p.get("lifecycleState") == "ACTIVE"
        ]
    except HttpError as e:
        return [{"error": str(e)}]
