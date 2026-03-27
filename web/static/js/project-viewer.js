// Simulated project data
const project = {
    prompt: "Generate a Python script that fetches the weather and saves it to a CSV file.",
    structure: `
  weather_project/
  ├── fetch_weather.py
  ├── utils/
  │   └── formatter.py
  └── data/
      └── weather.csv
    `,
    files: [
      {
        filename: "fetch_weather.py",
        content: `import requests\nimport csv\n# ... fetches weather and writes to CSV`
      },
      {
        filename: "utils/formatter.py",
        content: `def format_temperature(temp):\n    return f"{temp}°C"`
      },
      {
        filename: "data/weather.csv",
        content: "date,temp\n2025-08-07,29\n..."
      }
    ]
  };
  
  function loadProject() {
    document.getElementById("project-prompt").innerText = project.prompt;
    document.getElementById("project-structure").innerText = project.structure;
  
    const fileList = document.getElementById("file-list");
    project.files.forEach(file => {
      const div = document.createElement("div");
      div.className = "file-card";
  
      div.innerHTML = `
        <h4>${file.filename}</h4>
        <pre>${file.content}</pre>
      `;
  
      fileList.appendChild(div);
    });
  }
  
  function downloadProject() {
    alert("🔧 Download not implemented yet — backend needed to zip project.");
  }
  
  function openInEditor() {
    alert("🧠 Open in online editor or local VSCode — coming soon!");
  }
  
  document.getElementById("profile-icon").addEventListener("click", () => {
    const dropdown = document.getElementById("profile-dropdown");
    dropdown.classList.toggle("hidden");
  });
  
  loadProject();
  