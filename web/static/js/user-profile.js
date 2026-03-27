window.addEventListener("DOMContentLoaded", () => {
    const avatar = document.getElementById("user-avatar");
    const dropdown = document.getElementById("user-dropdown");
  
    if (!avatar || !dropdown) return;
  
    // Toggle dropdown menu
    avatar.addEventListener("click", (e) => {
      e.stopPropagation();
      dropdown.classList.toggle("visible");
    });
  
    // Close dropdown if clicking outside
    document.addEventListener("click", () => {
      dropdown.classList.remove("visible");
    });
  
    // Optional: If you have user data on frontend (for future)
    if (window.currentUser?.pseudo) {
      avatar.textContent = window.currentUser.pseudo[0].toUpperCase();
    }
  });
  