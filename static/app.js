const form = document.getElementById("chat-form");
const messageInput = document.getElementById("message");
const messages = document.getElementById("messages");
const template = document.getElementById("message-template");
const sendButton = document.getElementById("send-button");
const runChecksButton = document.getElementById("run-checks");

const checkHealthz = document.getElementById("check-healthz");
const checkRuntime = document.getElementById("check-runtime");
const checkChat = document.getElementById("check-chat");
const lastChecked = document.getElementById("last-checked");

const metaService = document.getElementById("meta-service");
const metaRevision = document.getElementById("meta-revision");
const metaProject = document.getElementById("meta-project");
const metaEnvironment = document.getElementById("meta-environment");
const metaUptime = document.getElementById("meta-uptime");

function appendMessage(role, text) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  node.querySelector(".role").textContent = role === "user" ? "You" : "Demo";
  node.querySelector(".text").textContent = text;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

function setCheckStatus(node, status, label) {
  if (!node) {
    return;
  }
  node.dataset.status = status;
  node.textContent = label;
}

function formatUptime(ms) {
  if (typeof ms !== "number") {
    return "-";
  }
  if (ms < 1000) {
    return `${ms} ms`;
  }
  return `${(ms / 1000).toFixed(1)} s`;
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

async function runRuntimeChecks() {
  if (runChecksButton) {
    runChecksButton.disabled = true;
  }

  setCheckStatus(checkHealthz, "pending", "checking");
  setCheckStatus(checkRuntime, "pending", "checking");
  setCheckStatus(checkChat, "pending", "checking");

  try {
    const healthzRes = await fetch("/healthz");
    const healthzBody = await healthzRes.json();
    const healthzOk = healthzRes.ok && healthzBody.status === "ok";
    setCheckStatus(checkHealthz, healthzOk ? "ok" : "error", healthzOk ? "ok" : "failed");

    const runtimeRes = await fetch("/api/runtime");
    const runtimeBody = await runtimeRes.json();
    const runtimeOk = runtimeRes.ok && runtimeBody.status === "ok";
    setCheckStatus(checkRuntime, runtimeOk ? "ok" : "error", runtimeOk ? "ok" : "failed");

    if (runtimeOk) {
      metaService.textContent = runtimeBody.service || "-";
      metaRevision.textContent = runtimeBody.revision || "-";
      metaProject.textContent = runtimeBody.project || "-";
      metaEnvironment.textContent = runtimeBody.environment || "-";
      metaUptime.textContent = formatUptime(runtimeBody.uptime_ms);
    }

    try {
      await postMessage("ping");
      setCheckStatus(checkChat, "ok", "ok");
    } catch (error) {
      setCheckStatus(checkChat, "error", "failed");
    }

    if (lastChecked) {
      lastChecked.textContent = `Last checked: ${new Date().toLocaleString()}`;
    }
  } catch (error) {
    setCheckStatus(checkHealthz, "error", "failed");
    setCheckStatus(checkRuntime, "error", "failed");
    setCheckStatus(checkChat, "error", "failed");

    if (lastChecked) {
      lastChecked.textContent = `Check failed: ${error.message}`;
    }
  } finally {
    if (runChecksButton) {
      runChecksButton.disabled = false;
    }
  }
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

if (runChecksButton) {
  runChecksButton.addEventListener("click", runRuntimeChecks);
  runRuntimeChecks();
}
