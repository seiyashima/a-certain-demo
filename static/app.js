const form = document.getElementById("chat-form");
const messageInput = document.getElementById("message");
const messages = document.getElementById("messages");
const template = document.getElementById("message-template");
const sendButton = document.getElementById("send-button");

function appendMessage(role, text) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  node.querySelector(".role").textContent = role === "user" ? "You" : "Demo";
  node.querySelector(".text").textContent = text;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

async function postMessage(message) {
  const requestId = crypto.randomUUID();
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Request-Id": requestId,
    },
    body: JSON.stringify({ message }),
  });

  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "request failed");
  }

  return body.reply;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message) {
    return;
  }

  appendMessage("user", message);
  messageInput.value = "";
  sendButton.disabled = true;

  try {
    const reply = await postMessage(message);
    appendMessage("assistant", reply);
  } catch (error) {
    appendMessage("assistant", `Error: ${error.message}`);
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
});

appendMessage("assistant", "Ready. Send a message to test /api/chat.");
