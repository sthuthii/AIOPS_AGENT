import { useEffect, useMemo, useState } from 'react';

const api = async (path, options = {}) => {
  const res = await fetch(path, { credentials: 'include', ...options });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
};

const Bubble = ({ kind, text }) => {
  const className = `bubble ${kind}`;
  return <div className={className}>{text}</div>;
};

function App() {
  const [status, setStatus] = useState({ signed_in: false });
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState('');
  const [chatLog, setChatLog] = useState([]);
  const [message, setMessage] = useState('');
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [processingSteps, setProcessingSteps] = useState([]);
  const [error, setError] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [toolResults, setToolResults] = useState([]);
  const [incidentSummary, setIncidentSummary] = useState(null);

  const signedIn = status.signed_in;

  const loadProjects = async (preselect) => {
    setLoadingProjects(true);
    try {
      const data = await api('/api/projects');
      const nextProjects = data.projects || [];
      setProjects(nextProjects);
      if (preselect) {
        setProjectId(preselect);
      } else if (nextProjects.length > 0 && nextProjects[0].project_id) {
        setProjectId(nextProjects[0].project_id);
      }
    } catch (err) {
      setError(`Couldn't load your GCP projects: ${err.message}`);
    } finally {
      setLoadingProjects(false);
    }
  };

  const selectProject = async (nextProjectId) => {
    if (!nextProjectId) return;
    await api('/api/select-project', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: nextProjectId }),
    });
  };

  const sendMessage = async (evt) => {
    evt.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;
    setMessage('');

    setChatLog((log) => [
      ...log,
      { kind: 'user', text: trimmed },
      { kind: 'agent pending', text: 'Thinking…' },
    ]);
    setToolResults([]);
    setIncidentSummary(null);
    setProcessingSteps([
      'Sending prompt to the agent',
      'Waiting for the agent to decide which tools to call',
    ]);

    try {
      const data = await api('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed }),
      });
      setProcessingSteps([
        'Received agent response',
        'Formatting the final reply',
      ]);
      setChatLog((log) =>
        log.map((item) =>
          item.kind === 'agent pending' && item.text === 'Thinking…'
            ? { kind: 'agent', text: data.reply }
            : item
        )
      );
      setPendingAction(data.pending_action || null);
      setToolResults(data.tool_results || []);
      setIncidentSummary(data.incident_summary || null);
    } catch (err) {
      setChatLog((log) =>
        log.map((item) =>
          item.kind === 'agent pending' && item.text === 'Thinking…'
            ? { kind: 'agent error', text: `Error: ${err.message}` }
            : item
        )
      );
      setError(`Agent request failed: ${err.message}`);
    } finally {
      setProcessingSteps([]);
    }
  };

  useEffect(() => {
    api('/api/status')
      .then((data) => {
        if (data.signed_in) {
          setStatus(data);
          loadProjects(data.project_id);
        }
      })
      .catch(() => setStatus({ signed_in: false }));
  }, []);

  const currentProjectOptions = useMemo(
    () => projects.map((p) => ({ value: p.project_id, label: `${p.name} (${p.project_id})` })),
    [projects]
  );

  const confirmPendingAction = async (confirm) => {
    if (!pendingAction) return;

    setChatLog((log) => [
      ...log,
      { kind: 'user', text: confirm ? 'Yes' : 'Cancel' },
      { kind: 'agent pending', text: 'Thinking…' },
    ]);
    setProcessingSteps([
      'Confirming the requested action',
      'Waiting for the agent to execute the operation',
    ]);

    try {
      const data = await api('/api/confirm-action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pending_action: pendingAction, confirm }),
      });
      setChatLog((log) =>
        log.map((item) =>
          item.kind === 'agent pending' && item.text === 'Thinking…'
            ? { kind: 'agent', text: data.reply }
            : item
        )
      );
    } catch (err) {
      setChatLog((log) =>
        log.map((item) =>
          item.kind === 'agent pending' && item.text === 'Thinking…'
            ? { kind: 'agent error', text: `Error: ${err.message}` }
            : item
        )
      );
      setError(`Action execution failed: ${err.message}`);
    } finally {
      setProcessingSteps([]);
      setPendingAction(null);
    }
  };

  return (
    <div id="app">
      <header className="topbar">
        <div className="brand">
          <span className="dot" />
          <h1>AIOps Agent</h1>
        </div>
        <div id="auth-area">
          {signedIn ? (
            <div className="user-chip">
              <span>{status.email || 'Signed in'}</span>
              <button className="btn ghost small" onClick={() => (window.location.href = '/auth/logout')}>Sign out</button>
            </div>
          ) : (
            <button className="btn primary" onClick={() => (window.location.href = '/auth/login')}>Sign in with Google</button>
          )}
        </div>
      </header>

      {!signedIn ? (
        <main className="hero">
          <h2>Manage your GCP infrastructure in plain English</h2>
          <p>Sign in with Google to connect your own project. Nothing is stored beyond your session.</p>
          <button className="btn primary" onClick={() => (window.location.href = '/auth/login')}>Sign in with Google</button>
          <div className="examples">
            <p className="examples-label">Try things like:</p>
            <ul>
              <li>"List all Compute Engine VM instances"</li>
              <li>"Show CPU utilization for production VMs"</li>
              <li>"List unhealthy Kubernetes clusters"</li>
              <li>"Restart the VM named app-server-01"</li>
              <li>"Show Cloud SQL instances with high CPU usage"</li>
              <li>"Summarize any infrastructure alerts from the last 24 hours"</li>
            </ul>
          </div>
        </main>
      ) : (
        <main className="workspace">
          <section className="project-bar">
            <label htmlFor="project-select">Active project:</label>
            <select
              id="project-select"
              value={projectId}
              onChange={(e) => {
                setProjectId(e.target.value);
                selectProject(e.target.value);
              }}
            >
              {currentProjectOptions.length === 0 ? (
                <option>{loadingProjects ? 'Loading projects…' : 'No accessible projects found'}</option>
              ) : (
                currentProjectOptions.map((project) => (
                  <option key={project.value} value={project.value}>
                    {project.label}
                  </option>
                ))
              )}
            </select>
            <button className="btn ghost" onClick={() => loadProjects(projectId)} title="Refresh project list">
              ↻
            </button>
          </section>

          <div className="layout-grid">
            <section className="chat-panel">
              <div className="chat-header">
                <div>
                  <p className="chat-tag">Live agent chat</p>
                  <h2>Ask your infrastructure copilot</h2>
                </div>
                <div className="chat-status">
                  {processingSteps.length === 0 ? 'Ready for your next command' : 'Processing...'}
                </div>
              </div>

              {processingSteps.length > 0 && (
                <section className="processing-window">
                  <div className="processing-header">Agent processing</div>
                  <ul>
                    {processingSteps.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </section>
              )}

              <section id="chat-log" className="chat-log">
                {chatLog.map((entry, index) => (
                  <Bubble key={index} kind={entry.kind} text={entry.text} />
                ))}
              </section>

              {error && <div className="error-bar">{error}</div>}

              {pendingAction && (
                <div className="confirm-bar">
                  <span>Confirm restart for <strong>{pendingAction.args.instance_name}</strong>?</span>
                  <div className="confirm-actions">
                    <button type="button" className="btn ghost" onClick={() => confirmPendingAction(false)}>
                      Cancel
                    </button>
                    <button type="button" className="btn primary" onClick={() => confirmPendingAction(true)}>
                      Yes, restart
                    </button>
                  </div>
                </div>
              )}

              <form className="chat-form" onSubmit={sendMessage}>
                <input
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  type="text"
                  placeholder="Ask the agent to check or manage your infrastructure…"
                  autoComplete="off"
                />
                <button type="submit" className="btn primary">
                  Send
                </button>
              </form>
            </section>

            <aside className="sidebar">
              <section className="sidebar-card">
                <h3>Quick tips</h3>
                <ul>
                  <li>List VM instances in the project</li>
                  <li>Show unhealthy GKE clusters</li>
                  <li>Get CPU utilization for VMs</li>
                  <li>Restart a VM after confirmation</li>
                </ul>
              </section>

              {incidentSummary && (
                <section className="incident-summary-card">
                  <div className="incident-summary-header">
                    <h3>Incident Summary</h3>
                    <span>{incidentSummary.project_id}</span>
                  </div>
                  <div className="incident-summary-body">
                    <div>
                      <h4>Resources</h4>
                      <ul>
                        {incidentSummary.resources?.length ? incidentSummary.resources.map((resource, index) => (
                          <li key={`${resource.name}-${index}`}>
                            <strong>{resource.name}</strong> — {resource.type} · {resource.status}
                          </li>
                        )) : <li>No resource data returned.</li>}
                      </ul>
                    </div>
                    <div>
                      <h4>Alerts</h4>
                      <ul>
                        {incidentSummary.alerts?.length ? incidentSummary.alerts.map((alert, index) => (
                          <li key={`${alert.message}-${index}`}>
                            <strong>[{alert.severity}]</strong> {alert.message}
                          </li>
                        )) : <li>No recent alerts detected.</li>}
                      </ul>
                    </div>
                    <div>
                      <h4>Recommended next steps</h4>
                      <ul>
                        {incidentSummary.recommendations?.length ? incidentSummary.recommendations.map((recommendation, index) => (
                          <li key={`${recommendation}-${index}`}>{recommendation}</li>
                        )) : <li>Continue monitoring the environment.</li>}
                      </ul>
                    </div>
                  </div>
                </section>
              )}

              {(() => {
                const cpuItems = toolResults
                  .filter((r) => r.tool === 'get_cpu_utilization' && Array.isArray(r.result))
                  .flatMap((r) => r.result || [])
                  .filter((item) => item && typeof item.utilization_percent === 'number');

                if (cpuItems.length === 0) {
                  return null;
                }

                return (
                  <section className="chart-panel">
                    <h3>CPU Utilization</h3>
                    <div className="chart-grid">
                      {cpuItems.map((item) => (
                        <div key={item.resource || Math.random()} className="bar-row">
                          <div className="bar-label">{item.resource || 'unknown resource'}</div>
                          <div className="bar-wrap">
                            <div className="bar" style={{ width: `${Math.min(item.utilization_percent, 100)}%` }} />
                          </div>
                          <div className="bar-value">{item.utilization_percent}%</div>
                        </div>
                      ))}
                    </div>
                  </section>
                );
              })()}
            </aside>
          </div>
        </main>
      )}
    </div>
  );
}

export default App;
