"""
Alert summary: surfaces WARNING+ log entries from Cloud Logging over a
recent window. This is a simplified stand-in for a full Monitoring
alerting-policy integration, documented as a limitation in the README.
"""
from . import tool
import datetime

from google.cloud import logging as gcp_logging
from google.api_core.exceptions import GoogleAPIError


@tool(
    name="summarize_alerts",
    description="Fetch recent WARNING-or-higher log entries across the project as a proxy for infrastructure alerts.",
    parameters={
        "type": "object",
        "properties": {"hours": {"type": "integer", "description": "Look-back window in hours, default 24."}},
        "required": [],
    },
)
def summarize_alerts(credentials, project_id: str, hours: int = 24, page_size: int = 20) -> list[dict]:
    try:
        client = gcp_logging.Client(project=project_id, credentials=credentials)
        start = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).isoformat("T") + "Z"
        filter_str = f'severity>=WARNING AND timestamp>="{start}"'

        entries = client.list_entries(filter_=filter_str, page_size=page_size)
        out = []
        for entry in entries:
            out.append(
                {
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                    "severity": entry.severity,
                    "resource_type": entry.resource.type if entry.resource else None,
                    "message": _extract_message(entry),
                }
            )
            if len(out) >= page_size:
                break
        return out
    except GoogleAPIError as e:
        return [{"error": str(e)}]


def _extract_message(entry) -> str:
    payload = entry.payload
    if isinstance(payload, str):
        return payload[:300]
    if isinstance(payload, dict):
        return str(payload.get("message", payload))[:300]
    return str(payload)[:300]
