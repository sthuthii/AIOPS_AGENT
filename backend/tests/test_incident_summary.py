import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import agent as agent_module


def test_build_incident_summary_formats_key_sections():
    summary = agent_module.build_incident_summary(
        project_id="demo-project",
        resources=[
            {"name": "api-prod-01", "type": "vm", "status": "RUNNING"},
            {"name": "orders-db", "type": "cloudsql", "status": "RUNNABLE"},
        ],
        alerts=[
            {"severity": "WARNING", "message": "High CPU on api-prod-01"},
            {"severity": "ERROR", "message": "Database connection failures"},
        ],
        recommendations=["Restart the affected VM", "Check database connectivity"],
    )

    text = summary["reply"]
    assert "Incident Summary" in text
    assert "demo-project" in text
    assert "api-prod-01" in text
    assert "High CPU on api-prod-01" in text
    assert "Restart the affected VM" in text


def test_summarize_tool_results_formats_compute_instances():
    text = agent_module._summarize_tool_results([
        {
            "tool": "list_compute_instances",
            "result": [
                {"name": "api-prod-01", "status": "RUNNING", "zone": "us-central1-a"}
            ],
        }
    ])

    assert "Compute Engine instances:" in text
    assert "api-prod-01" in text
