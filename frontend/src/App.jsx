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
  const [error, setError] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [toolResults, setToolResults] = useState([]);

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

    try {
      const data = await api('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed }),
      });
      setChatLog((log) =>
        log.map((item) =>
          item.kind === 'agent pending' && item.text === 'Thinking…'
            ? { kind: 'agent', text: data.reply }
            : item
        )
      );
      setPendingAction(data.pending_action || null);
      setToolResults(data.tool_results || []);
    } catch (err) {
      setChatLog((log) =>
        log.map((item) =>
          item.kind === 'agent pending' && item.text === 'Thinking…'
            ? { kind: 'agent error', text: `Error: ${err.message}` }
            : item
        )
      );
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
    } finally {
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

          <section id="chat-log" className="chat-log">
            {chatLog.map((entry, index) => (
              <Bubble key={index} kind={entry.kind} text={entry.text} />
            ))}
          </section>

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
        </main>
      )}
    </div>
  );
}

export default App;
