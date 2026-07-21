const profileSelect = document.getElementById("demo-profile");
const avatarButton = document.getElementById("avatar-button");
const avatarInitials = document.getElementById("avatar-initials");
const profilePanel = document.getElementById("profile-panel");

const mockGreeting = document.getElementById("mock-greeting");
const mockTitle = document.getElementById("mock-title");
const mockShortcuts = document.getElementById("mock-shortcuts");
const mockMessages = document.getElementById("mock-messages");
const mockStatus = document.getElementById("mock-status");
const mockQueryInput = document.getElementById("mock-query");
const mockSendButton = document.getElementById("mock-send");

const mockConnectorToggle = document.getElementById("mock-connector-toggle");
const mockConnectorMenu = document.getElementById("mock-connector-menu");
const mockConnectorOptions = document.getElementById("mock-connector-options");
const mockSelectAllConnectors = document.getElementById("mock-select-all-connectors");
const mockConnectorSummary = document.getElementById("mock-connector-summary");

const threadShell = document.querySelector(".thread-shell");

const state = {
  demoConfig: null,
  demoSourceSamples: [],
  selectedProfileId: null,
  selectedMockSystems: new Set(),
};

const CONNECTOR_LABELS = {
  servicenow: "ServiceNow",
  workday: "Workday",
  "compliance-system": "Compliance",
  sharepoint: "SharePoint",
  confluence: "Confluence",
};

const CONNECTOR_ICONS = {
  servicenow: "S",
  workday: "W",
  "compliance-system": "C",
  sharepoint: "P",
  confluence: "N",
};

function clearNode(node) {
  if (node) node.innerHTML = "";
}

function setStatus(node, status, label) {
  if (!node) return;
  node.dataset.status = status;
  node.textContent = label;
}

function requestJson(url, options = {}) {
  return fetch(url, options).then(async (response) => {
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.error || body.detail?.error || body.detail || "request failed");
    }
    return body;
  });
}

function getAllMockSystems() {
  return state.demoSourceSamples.map((item) => item.system);
}

function getSelectedMockSystems() {
  const all = getAllMockSystems();
  if (all.length === 0 || state.selectedMockSystems.size === 0) return all;
  return all.filter((system) => state.selectedMockSystems.has(system));
}

function updateConnectorSummary() {
  if (!mockConnectorSummary) return;

  const selected = getSelectedMockSystems();
  const all = getAllMockSystems();
  if (selected.length === all.length) {
    mockConnectorSummary.textContent = "すべてのコネクタを使用";
    return;
  }

  mockConnectorSummary.textContent = selected.map((system) => CONNECTOR_LABELS[system] || system).join(" / ");
}

function renderShortcuts() {
  if (!mockShortcuts) return;
  clearNode(mockShortcuts);

  const selected = getSelectedMockSystems();
  selected.forEach((system) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "shortcut-pill";
    chip.innerHTML = `<span class="shortcut-icon">${CONNECTOR_ICONS[system] || "•"}</span>${CONNECTOR_LABELS[system] || system}`;
    chip.addEventListener("click", () => {
      state.selectedMockSystems = new Set([system]);
      syncConnectorCheckboxState();
    });
    mockShortcuts.appendChild(chip);
  });
}

function syncConnectorCheckboxState() {
  if (!mockConnectorOptions) return;

  const selected = new Set(getSelectedMockSystems());
  const all = getAllMockSystems();

  if (mockSelectAllConnectors) {
    mockSelectAllConnectors.checked = selected.size === all.length;
  }

  Array.from(mockConnectorOptions.querySelectorAll("input[type='checkbox'][data-system]"))
    .forEach((checkbox) => {
      checkbox.checked = selected.has(checkbox.dataset.system);
    });

  updateConnectorSummary();
  renderShortcuts();
}

function renderConnectorOptions() {
  if (!mockConnectorOptions) return;

  clearNode(mockConnectorOptions);
  state.demoSourceSamples.forEach((item) => {
    const row = document.createElement("label");
    row.className = "connector-menu-item";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.dataset.system = item.system;
    input.checked = state.selectedMockSystems.has(item.system);
    input.addEventListener("change", () => {
      if (input.checked) {
        state.selectedMockSystems.add(item.system);
      } else {
        state.selectedMockSystems.delete(item.system);
      }

      if (state.selectedMockSystems.size === 0) {
        state.selectedMockSystems = new Set(getAllMockSystems());
      }
      syncConnectorCheckboxState();
    });

    const name = document.createElement("span");
    name.textContent = CONNECTOR_LABELS[item.system] || item.system;

    row.append(input, name);
    mockConnectorOptions.appendChild(row);
  });

  syncConnectorCheckboxState();
}

function getProfileInitials(label) {
  const plain = String(label || "").split("(")[0].trim();
  const parts = plain.split(/\s+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "U";
}

function renderProfileSelection(profiles) {
  if (!profileSelect) return;
  clearNode(profileSelect);

  profiles.forEach((profile) => {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = profile.label;
    profileSelect.appendChild(option);
  });

  const selected = profiles.find((profile) => profile.id === state.selectedProfileId) || profiles[0];
  if (!selected) return;

  state.selectedProfileId = selected.id;
  profileSelect.value = selected.id;
  applyProfile(selected.id, false);
}

function getSelectedProfile() {
  return state.demoConfig?.profiles.find((profile) => profile.id === state.selectedProfileId) || null;
}

function applyProfile(profileId, resetConversation = true) {
  const profiles = state.demoConfig?.profiles || [];
  const profile = profiles.find((item) => item.id === profileId) || profiles[0];
  if (!profile) return;

  state.selectedProfileId = profile.id;
  if (profileSelect) profileSelect.value = profile.id;

  const displayName = (profile.display_name || profile.label || "").split("(")[0].trim();
  if (avatarInitials) avatarInitials.textContent = getProfileInitials(displayName || profile.label);
  if (mockGreeting) mockGreeting.textContent = `こんにちは、 ${displayName} さん`;
  if (mockTitle) mockTitle.textContent = "作業を始めましょう";
  if (mockQueryInput) {
    mockQueryInput.placeholder = profile.suggested_queries?.[0] || "質問を入力してください";
  }

  const defaultSystem = profile.default_target_system || "all";
  state.selectedMockSystems = defaultSystem === "all" ? new Set(getAllMockSystems()) : new Set([defaultSystem]);
  syncConnectorCheckboxState();

  if (resetConversation) resetMockConversation();
}

function resetMockConversation() {
  if (!mockMessages) return;

  clearNode(mockMessages);
  const welcome = document.createElement("article");
  welcome.className = "message-bubble assistant";
  welcome.innerHTML = "<p class=\"message-role\">Gemini Enterprise</p><p class=\"message-text\">質問を入力すると、選択中のユーザ権限とコネクタ設定で回答します。</p>";
  mockMessages.appendChild(welcome);
}

function appendMessage(role, text, metadata = []) {
  if (!mockMessages) return;

  const bubble = document.createElement("article");
  bubble.className = `message-bubble ${role}`;

  const roleLabel = document.createElement("p");
  roleLabel.className = "message-role";
  roleLabel.textContent = role === "user" ? "You" : "Gemini Enterprise";

  const message = document.createElement("p");
  message.className = "message-text";
  message.textContent = text;

  bubble.append(roleLabel, message);

  if (metadata.length > 0) {
    const row = document.createElement("div");
    row.className = "citation-row";
    metadata.forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "citation-chip";
      chip.textContent = item;
      row.appendChild(chip);
    });
    bubble.appendChild(row);
  }

  mockMessages.appendChild(bubble);
  mockMessages.scrollTop = mockMessages.scrollHeight;
}

function renderMockResponse(payload) {
  if (threadShell) threadShell.classList.add("is-visible");

  appendMessage("user", payload.query);
  const citationLabels = (payload.citations || []).map((item) => `${item.id} · ${item.title}`);
  const blockedLabels = (payload.blocked_documents || []).map((item) => `${item.id} (blocked)`);
  appendMessage("assistant", payload.reply || "No answer", [...citationLabels, ...blockedLabels]);

  setStatus(mockStatus, citationLabels.length > 0 ? "ok" : "pending", citationLabels.length > 0 ? "answered" : "no hit");
}

async function runMockChat() {
  const profile = getSelectedProfile();
  if (!profile || !mockQueryInput || !mockSendButton) return;

  const query = mockQueryInput.value.trim();
  if (!query) {
    setStatus(mockStatus, "error", "missing input");
    return;
  }

  mockSendButton.disabled = true;
  setStatus(mockStatus, "pending", "thinking");
  if (threadShell) threadShell.classList.add("is-visible");

  try {
    const selectedSystems = getSelectedMockSystems();
    const targetSystem = selectedSystems.length === 1 ? selectedSystems[0] : "all";

    const payload = await requestJson("/api/demo/mock/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Request-Id": crypto.randomUUID(),
      },
      body: JSON.stringify({
        profile_id: profile.id,
        query,
        target_system: targetSystem,
        target_systems: selectedSystems,
      }),
    });

    renderMockResponse(payload);
  } catch (error) {
    setStatus(mockStatus, "error", "failed");
    appendMessage("assistant", error.message);
  } finally {
    mockSendButton.disabled = false;
  }
}

async function loadDemoConfig() {
  const payload = await requestJson("/api/demo/config");
  state.demoConfig = payload;
  state.selectedProfileId = payload.profiles?.[0]?.id || null;
  renderProfileSelection(payload.profiles || []);
}

async function loadDemoSourceSamples() {
  const payload = await requestJson("/api/demo/source-samples");
  state.demoSourceSamples = payload.systems || [];
  state.selectedMockSystems = new Set(getAllMockSystems());
  renderConnectorOptions();
}

function bindUiEvents() {
  if (profileSelect) {
    profileSelect.addEventListener("change", () => applyProfile(profileSelect.value));
  }

  if (mockSendButton) {
    mockSendButton.addEventListener("click", runMockChat);
  }

  if (mockQueryInput) {
    mockQueryInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        runMockChat();
      }
    });
  }

  if (mockConnectorToggle && mockConnectorMenu) {
    mockConnectorToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      const expanded = mockConnectorToggle.getAttribute("aria-expanded") === "true";
      mockConnectorToggle.setAttribute("aria-expanded", expanded ? "false" : "true");
      mockConnectorMenu.hidden = expanded;
    });
  }

  if (mockSelectAllConnectors) {
    mockSelectAllConnectors.addEventListener("change", () => {
      if (mockSelectAllConnectors.checked) {
        state.selectedMockSystems = new Set(getAllMockSystems());
      } else {
        const first = getAllMockSystems()[0];
        state.selectedMockSystems = first ? new Set([first]) : new Set();
      }
      syncConnectorCheckboxState();
    });
  }

  if (avatarButton && profilePanel) {
    avatarButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const expanded = avatarButton.getAttribute("aria-expanded") === "true";
      avatarButton.setAttribute("aria-expanded", expanded ? "false" : "true");
      profilePanel.hidden = expanded;
    });
  }

  document.addEventListener("click", (event) => {
    const target = event.target;

    if (mockConnectorMenu && mockConnectorToggle) {
      const insideMenu = mockConnectorMenu.contains(target);
      const insideToggle = mockConnectorToggle.contains(target);
      if (!insideMenu && !insideToggle) {
        mockConnectorMenu.hidden = true;
        mockConnectorToggle.setAttribute("aria-expanded", "false");
      }
    }

    if (profilePanel && avatarButton) {
      const insidePanel = profilePanel.contains(target);
      const insideAvatar = avatarButton.contains(target);
      if (!insidePanel && !insideAvatar) {
        profilePanel.hidden = true;
        avatarButton.setAttribute("aria-expanded", "false");
      }
    }
  });
}

async function initialize() {
  await loadDemoConfig();
  await loadDemoSourceSamples();
  resetMockConversation();
  bindUiEvents();
}

initialize();