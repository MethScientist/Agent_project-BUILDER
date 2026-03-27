document.addEventListener("DOMContentLoaded", () => {
  const tabButtons = document.querySelectorAll(".lesson-tabs button");
  const tabPanes = document.querySelectorAll(".tab-pane");

  function showTab(tabName) {
    // Hide all tabs
    tabPanes.forEach(pane => {
      pane.classList.remove("active");
      pane.style.display = "none"; // Hide all
    });

    // Remove active class from all buttons
    tabButtons.forEach(btn => btn.classList.remove("active"));

    // Show the selected tab
    const selectedPane = document.getElementById(tabName);
    if (selectedPane) {
      selectedPane.classList.add("active");
      selectedPane.style.display = "block"; // Show only this one
    }

    // Mark the button as active
    tabButtons.forEach(btn => {
      if (btn.dataset.tab === tabName) {
        btn.classList.add("active");
      }
    });
  }

  // On tab click
  tabButtons.forEach(button => {
    button.addEventListener("click", () => {
      showTab(button.dataset.tab);
    });
  });

  // Show first tab by default
  const firstTab = tabButtons[0]?.dataset.tab;
  if (firstTab) {
    showTab(firstTab);
  }
});
