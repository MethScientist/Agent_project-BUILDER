// assets/js/history.js

const mockHistory = [
    {
      id: 1,
      date: "2025-08-05",
      prompt: "Build me a full-stack blog system with login, dashboard, and post editor",
    },
    {
      id: 2,
      date: "2025-08-06",
      prompt: "Generate Unity 3D game prototype for a platformer with enemies and health bar",
    },
    {
      id: 3,
      date: "2025-08-07",
      prompt: "Create a plugin system with dynamic loading and activation",
    },
  ];
  
  function loadHistory() {
    const container = document.getElementById("history-list");
    container.innerHTML = "";
  
    mockHistory.forEach((entry) => {
      const item = document.createElement("div");
      item.className = "history-item";
  
      item.innerHTML = `
        <h4>${entry.prompt}</h4>
        <small>🗓️ ${entry.date}</small>
        <button onclick="rerunPrompt(${entry.id})">↻ Re-run</button>
        <button onclick="viewDetails(${entry.id})">🔍 View</button>
        <button onclick="deletePrompt(${entry.id})">🗑️ Delete</button>
      `;
  
      container.appendChild(item);
    });
  }
  
  function rerunPrompt(id) {
    const prompt = mockHistory.find((p) => p.id === id);
    alert(`Re-running prompt:\n\n"${prompt.prompt}"`);
    // TODO: send prompt back to dashboard or agent
  }
  
  function viewDetails(id) {
    const prompt = mockHistory.find((p) => p.id === id);
    alert(`Show full result for:\n\n"${prompt.prompt}"`);
    // TODO: navigate to detail view (project viewer)
  }
  
  function deletePrompt(id) {
    if (confirm("Delete this prompt from history?")) {
      const index = mockHistory.findIndex((p) => p.id === id);
      if (index !== -1) {
        mockHistory.splice(index, 1);
        loadHistory();
      }
    }
  }
  
  document.getElementById("profile-icon").addEventListener("click", () => {
    const dropdown = document.getElementById("profile-dropdown");
    dropdown.classList.toggle("hidden");
  });
  
  loadHistory();
  