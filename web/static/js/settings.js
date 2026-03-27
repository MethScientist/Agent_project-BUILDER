// assets/js/settings.js

document.getElementById("profile-icon").addEventListener("click", () => {
    const dropdown = document.getElementById("profile-dropdown");
    dropdown.classList.toggle("hidden");
  });
  
  document.querySelector(".settings-form").addEventListener("submit", (e) => {
    e.preventDefault();
  
    const liveTracking = document.getElementById("liveTrackingToggle").checked;
    const autoGen = document.getElementById("autoGenToggle").checked;
    const defaultAgent = document.getElementById("defaultAgent").value;
    const theme = document.getElementById("themeSelect").value;
  
    // TODO: Save these settings in localStorage or backend
    console.log("Saved settings:", {
      liveTracking,
      autoGen,
      defaultAgent,
      theme,
    });
  
    alert("Settings saved successfully!");
  });
  