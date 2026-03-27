const chatBox = document.getElementById("chat-box");
const input = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

sendBtn.addEventListener("click", sendMessage);

function appendMessage(role, text) {
  const msg = document.createElement("div");
  msg.className = `message ${role}`;
  msg.innerText = text;
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  appendMessage("user", text);
  input.value = "";

  // Simulate AI response (replace with fetch to backend)
  appendMessage("ai", "Thinking...");
  setTimeout(() => {
    const last = document.querySelector(".message.ai:last-child");
    last.innerText = `💬 AI says: "${text}"\n(This is a placeholder response.)`;
  }, 1000);
}

// Profile dropdown
document.getElementById("profile-icon").addEventListener("click", () => {
  const dropdown = document.getElementById("profile-dropdown");
  dropdown.classList.toggle("hidden");
});
