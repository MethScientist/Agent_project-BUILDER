// --- WebSocket setup ---
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const LIVE_WS_URL = `${protocol}://127.0.0.1:8000/ws/live`;
const AGENT_WS_URL = `${protocol}://127.0.0.1:8000/ws/agent`;

const liveSocket = new WebSocket(LIVE_WS_URL);
const agentSocket = new WebSocket(AGENT_WS_URL);

// --- Logging helper ---
function appendLog(text, className = 'log-line', color = null, prefix = '') {
  const logOutput = document.getElementById("live-log");
  if (!logOutput) return;
  const line = document.createElement("div");
  line.classList.add(className);
  line.textContent = prefix ? `[${prefix}] ${text}` : text;
  if (color) line.style.color = color;
  logOutput.appendChild(line);
  logOutput.scrollTop = logOutput.scrollHeight;
}

// --- WebSocket handlers ---
function setupSocket(socket, label) {
  socket.onopen = () => appendLog(`🟢 Connected to ${label} WS.`, 'info', 'lightgreen');
  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      let msg = '';
      let color = 'white';

      switch(data.type) {
        case 'log':
          color = data.level === 'error' ? 'red' :
                  data.level === 'warn' ? 'orange' : 'lightgreen';
          msg = `[LOG - ${data.level.toUpperCase()}] ${data.message}`;
          break;

        case 'thought':
        case 'thoughts':
          color = '#6cf';
          msg = `[THOUGHT] ${data.content}`;
          break;

        case 'plan':
          color = '#fc6';
          msg = `[PLAN] Plan with ${Array.isArray(data.plan) ? data.plan.length : '?'} steps generated.`;
          break;

        case 'step_created':
          color = '#9f6';
          msg = `[STEP CREATED] ${data.step?.description ?? ''} @ ${data.step?.target_path ?? ''}`;
          break;

        case 'file_created':
          color = '#69f';
          msg = `[FILE CREATED] ${data.path}`;
          break;

        case 'code_written':
          color = '#9cf';
          msg = `[CODE WRITTEN] ${data.path} (language: ${data.language ?? 'unknown'})`;
          break;

        case 'folder_created':
          color = '#69f';
          msg = `[FOLDER CREATED] ${data.path}`;
          break;

        case 'task_started':
          color = '#fc9';
          msg = `[TASK STARTED] (${data.agent}) ${data.description} (ID: ${data.step_id})`;
          break;

        default:
          msg = `[EVENT ${data.type}] ${JSON.stringify(data.detail ?? data)}`;
          break;
      }

      appendLog(msg, 'log-line', color, label);

    } catch (e) {
      appendLog(`❌ Failed to parse message: ${e}`, 'error', 'red', label);
    }
  };
  socket.onclose = () => appendLog(`🔴 ${label} WS disconnected.`, 'info', 'orange');
  socket.onerror = (err) => appendLog(`[ERROR] ${label} WS error: ${err.message || err}`, 'error', 'orange');
}

// Setup both sockets
setupSocket(liveSocket, 'LIVE');
setupSocket(agentSocket, 'AGENT');

// --- Prompt submission ---
document.getElementById("prompt-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const promptInput = document.getElementById("user-prompt");
  const projectRootInput = document.getElementById("project-root-input");
  const prompt = promptInput.value.trim();
  const projectRoot = projectRootInput.value.trim();

  if (!prompt) { appendLog("[ERROR] Prompt cannot be empty.", "error", "red"); return; }
  if (!projectRoot) { appendLog("[ERROR] Project root path cannot be empty.", "error", "red"); return; }

  appendLog(`[PROMPT] ${prompt}`, "prompt", "lightblue");
  appendLog(`[PROJECT ROOT] ${projectRoot}`, "info", "lightgreen");

  try {
    const res = await fetch("/run-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, project_root: projectRoot })
    });

    const data = await res.json();

    if (data.logs && Array.isArray(data.logs)) {
      data.logs.forEach(log => appendLog(log));
    }

    if (data.project_id) {
      appendLog(`[PROJECT] ID: ${data.project_id}`, "info", "yellowgreen");
    }

    if (data.status === "error") {
      appendLog(`[ERROR] Server error: ${data.logs.join("\n")}`, "error", "red");
    }
  } catch (err) {
    appendLog("[ERROR] Failed to contact AI agent.", "error", "red");
  }
});

// --- Controls for WS and logs ---
document.querySelector('.controls .btn.small:nth-child(1)').addEventListener('click', () => {
  [liveSocket, agentSocket].forEach(sock => {
    if (sock.readyState === WebSocket.OPEN) sock.close();
    else appendLog("[INFO] WebSocket already closed.", 'info', 'orange');
  });
});

document.querySelector('.controls .btn.small:nth-child(2)').addEventListener('click', () => {
  const logOutput = document.getElementById("live-log");
  if (logOutput) logOutput.innerHTML = '';
});
