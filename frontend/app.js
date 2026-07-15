const signedOutView = document.getElementById("signed-out-view");
const signedInView = document.getElementById("signed-in-view");
const authArea = document.getElementById("auth-area");
const loginBtn = document.getElementById("login-btn");
const projectSelect = document.getElementById("project-select");
const refreshProjectsBtn = document.getElementById("refresh-projects");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

loginBtn.addEventListener("click", () => {
  window.location.href = "/auth/login";
});

async function api(path, options = {}) {
  const res = await fetch(path, { credentials: "include", ...options });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

function renderSignedIn(email) {
  signedOutView.style.display = "none";
  signedInView.style.display = "flex";
  authArea.innerHTML = `
    <div class="user-chip">
      <span>${email || "Signed in"}</span>
      <button id="logout-btn" class="btn ghost small">Sign out</button>
    </div>`;
  document.getElementById("logout-btn").addEventListener("click", async () => {
    await fetch("/auth/logout", { method: "POST", credentials: "include" });
    window.location.reload();
  });
}

function renderSignedOut() {
  signedOutView.style.display = "block";
  signedInView.style.display = "none";
  authArea.innerHTML = "";
}

async function loadProjects(preselect) {
  projectSelect.innerHTML = "<option>Loading projects…</option>";
  try {
    const data = await api("/api/projects");
    const projects = data.projects || [];
    if (projects.length === 0 || projects[0].error) {
      projectSelect.innerHTML = `<option value="">No accessible projects found</option>`;
      return;
    }
    projectSelect.innerHTML = projects
      .map((p) => `<option value="${p.project_id}">${p.name} (${p.project_id})</option>`)
      .join("");
    if (preselect) projectSelect.value = preselect;
    await selectProject(projectSelect.value);
  } catch (e) {
    projectSelect.innerHTML = `<option value="">Failed to load projects</option>`;
    addBubble("agent error", `Couldn't load your GCP projects: ${e.message}`);
  }
}

async function selectProject(projectId) {
  if (!projectId) return;
  await api("/api/select-project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId }),
  });
}

projectSelect.addEventListener("change", () => selectProject(projectSelect.value));
refreshProjectsBtn.addEventListener("click", () => loadProjects(projectSelect.value));

function addBubble(kind, text) {
  const el = document.createElement("div");
  el.className = `bubble ${kind}`;
  el.textContent = text;
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
  return el;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  chatInput.value = "";
  addBubble("user", message);
  const pending = addBubble("agent pending", "Thinking…");

  try {
    const data = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    pending.textContent = data.reply;
    pending.classList.remove("pending");
  } catch (err) {
    pending.textContent = `Error: ${err.message}`;
    pending.classList.add("error");
    pending.classList.remove("pending");
  }
});

(async function init() {
  try {
    const status = await api("/api/status");
    if (status.signed_in) {
      renderSignedIn(status.email);
      await loadProjects(status.project_id);
    } else {
      renderSignedOut();
    }
  } catch (e) {
    renderSignedOut();
  }
})();
