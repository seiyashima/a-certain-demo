const body = document.body;

const modeMockButton = document.getElementById("mode-mock");
const modeStatusButton = document.getElementById("mode-status");
const profileSelect = document.getElementById("demo-profile");
const avatarInitials = document.getElementById("avatar-initials");
const mockGreeting = document.getElementById("mock-greeting");
const mockTitle = document.getElementById("mock-title");
const mockProfileTag = document.getElementById("mock-profile-tag");
const mockProfileLabel = document.getElementById("mock-profile-label");
const mockProfileDescription = document.getElementById("mock-profile-description");
const mockCoverage = document.getElementById("mock-coverage");
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
const mockView = document.getElementById("mock-view");
const threadShell = document.querySelector(".thread-shell");
const statusView = document.getElementById("status-view");

const searchForm = document.getElementById("search-form");
const subjectInput = document.getElementById("subject");
const targetSystemInput = document.getElementById("target-system");
const queryInput = document.getElementById("query");
const searchButton = document.getElementById("search-button");
const runSearchDemoButton = document.getElementById("run-search-demo");
const runChecksButton = document.getElementById("run-checks");

const connectorStrip = document.getElementById("connector-strip");
const resultStatus = document.getElementById("result-status");
const resultSummary = document.getElementById("result-summary");
const results = document.getElementById("results");

const checkHealthz = document.getElementById("check-healthz");
const checkRuntime = document.getElementById("check-runtime");
const checkConnectors = document.getElementById("check-connectors");
const checkSearch = document.getElementById("check-search");
const lastChecked = document.getElementById("last-checked");

const metaService = document.getElementById("meta-service");
const metaRevision = document.getElementById("meta-revision");
const metaProject = document.getElementById("meta-project");
const metaEnvironment = document.getElementById("meta-environment");
const metaConnectorCount = document.getElementById("meta-connector-count");
const metaUptime = document.getElementById("meta-uptime");

const state = {
  demoConfig: null,
  demoSourceSamples: [],
  selectedProfileId: null,
  selectedMockSystems: new Set(),
  mode: "mock",
  statusLoaded: false,
};

const CONNECTOR_LABELS = {
  servicenow: "ServicenowConnector",
  workday: "WorkdayConnector",
  "compliance-system": "CompliancesysConnector",
  sharepoint: "SharepointConnector",
  confluence: "ConfluenceConnector",
};

function setStatus(node, status, label) {
  if (!node) return;
  node.dataset.status = status;
  node.textContent = label;
}

function clearNode(node) {
  if (node) {
    node.innerHTML = "";
  }
}

function formatUptime(ms) {
  if (typeof ms !== "number") return "-";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function getAllMockSystems() {
  return state.demoSourceSamples.map((item) => item.system);
}

function normalizeMockSystemName(system) {
  return String(system || "").trim().toLowerCase();
}

function getSelectedMockSystems() {
  const all = getAllMockSystems();
  if (all.length === 0 || state.selectedMockSystems.size === 0) {
    return all;
  }
  return all.filter((item) => state.selectedMockSystems.has(item));
}

function updateConnectorSummary() {
  if (!mockConnectorSummary) return;
  const selected = getSelectedMockSystems();
  const all = getAllMockSystems();

  if (selected.length === all.length) {
    mockConnectorSummary.textContent = `${all.length} systems selected`;
    return;
  }

  const labels = selected.map((system) => CONNECTOR_LABELS[system] || system);
  mockConnectorSummary.textContent = labels.join(", ");
}

function syncConnectorCheckboxState() {
  if (!mockConnectorOptions) return;

  const selected = new Set(getSelectedMockSystems());
  const allSystems = getAllMockSystems();
  if (mockSelectAllConnectors) {
    mockSelectAllConnectors.checked = selected.size === allSystems.length;
  }

  Array.from(mockConnectorOptions.querySelectorAll("input[type='checkbox'][data-system]")).forEach((checkbox) => {
    const system = checkbox.dataset.system;
    checkbox.checked = selected.has(system);
  });

  updateConnectorSummary();
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

    const file = document.createElement("small");
    file.textContent = item.source_sample_file;

    row.append(input, name, file);
    mockConnectorOptions.appendChild(row);
  });

  syncConnectorCheckboxState();
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || body.detail?.error || body.detail || "request failed");
  }
  return body;
}

function setMode(mode) {
  state.mode = mode;
  body.dataset.mode = mode;
  modeMockButton.classList.toggle("is-active", mode === "mock");
  modeStatusButton.classList.toggle("is-active", mode === "status");
  mockView.hidden = mode !== "mock";
  statusView.hidden = mode !== "status";

  if (mode === "status" && !state.statusLoaded) {
    runRuntimeChecks();
    state.statusLoaded = true;
  }
}

function updateMockHeader(profile) {
  if (!profile) return;

  mockProfileTag.textContent = profile.default_target_system === "all" ? "auto" : profile.default_target_system;
  mockProfileLabel.textContent = profile.label;
  mockProfileDescription.textContent = profile.description;
  avatarInitials.textContent = profile.label
    .split(/[\s\/]+/)
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  if (mockGreeting) {
    mockGreeting.textContent = `こんにちは、 Seiya さん`;
  }

  if (mockTitle) {
    mockTitle.textContent = "何から始めますか?";
  }
}

function renderMockCoverage(profile) {
  clearNode(mockCoverage);
  profile.coverage_titles.forEach((title) => {
    const item = document.createElement("li");
    item.textContent = title;
    mockCoverage.appendChild(item);
  });
}

function renderMockShortcuts(profile) {
  clearNode(mockShortcuts);

  profile.suggested_queries.forEach((query) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "shortcut-pill";
    button.textContent = query;
    button.addEventListener("click", () => {
      mockQueryInput.value = query;
      mockQueryInput.focus();
    });
    mockShortcuts.appendChild(button);
  });
}

function renderProfileSelection(profiles) {
  clearNode(profileSelect);
  profiles.forEach((profile) => {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = profile.label;
    profileSelect.appendChild(option);
  });

  const preferred = profiles.find((profile) => profile.id === state.selectedProfileId) || profiles[0];
  if (preferred) {
    state.selectedProfileId = preferred.id;
    profileSelect.value = preferred.id;
    applyProfile(preferred.id, false);
  }
}

function getSelectedProfile() {
  return state.demoConfig?.profiles.find((profile) => profile.id === state.selectedProfileId) || null;
}

function resetMockConversation() {
  clearNode(mockMessages);

  const welcome = document.createElement("article");
  welcome.className = "message-bubble assistant";
  welcome.innerHTML = `
    <p class="message-role">Gemini Enterprise</p>
    <p class="message-text">質問を入力すると、選択中のプロフィールに対応したテストデータで回答します。</p>
  `;
  mockMessages.appendChild(welcome);
}

function appendMessage(role, text, metadata = []) {
  const bubble = document.createElement("article");
  bubble.className = `message-bubble ${role}`;

  const roleLabel = document.createElement("p");
  roleLabel.className = "message-role";
  roleLabel.textContent = role === "user" ? "You" : "Gemini Enterprise";

  const content = document.createElement("p");
  content.className = "message-text";
  content.textContent = text;

  bubble.append(roleLabel, content);

  if (metadata.length > 0) {
    const chipRow = document.createElement("div");
    chipRow.className = "citation-row";
    metadata.forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "citation-chip";
      chip.textContent = item;
      chipRow.appendChild(chip);
    });
    bubble.appendChild(chipRow);
  }

  mockMessages.appendChild(bubble);
  mockMessages.scrollTop = mockMessages.scrollHeight;
}

function renderMockResponse(payload) {
  if (threadShell) {
    threadShell.classList.add("is-visible");
  }

  appendMessage("user", payload.query);

  const citationLabels = payload.citations.map((citation) => `${citation.id} · ${citation.title}`);
  const blockedLabels = payload.blocked_documents.map((document) => `${document.id} (blocked)`);
  const assistantText = payload.reply;

  appendMessage("assistant", assistantText, [...citationLabels, ...blockedLabels]);

  setStatus(mockStatus, citationLabels.length > 0 ? "ok" : "pending", citationLabels.length > 0 ? "answered" : "no hit");
}

async function loadDemoConfig() {
  const payload = await requestJson("/api/demo/config");
  state.demoConfig = payload;
  state.selectedProfileId = state.selectedProfileId || payload.profiles[0]?.id || null;
  renderProfileSelection(payload.profiles);
}

async function loadDemoSourceSamples() {
  const payload = await requestJson("/api/demo/source-samples");
  state.demoSourceSamples = payload.systems || [];

  const allSystems = getAllMockSystems();
  state.selectedMockSystems = new Set(allSystems);
  renderConnectorOptions();
}

function applyProfile(profileId, resetConversation = true) {
  if (!state.demoConfig) return;

  const profile = state.demoConfig.profiles.find((item) => item.id === profileId) || state.demoConfig.profiles[0];
  if (!profile) return;

  state.selectedProfileId = profile.id;
  profileSelect.value = profile.id;
  updateMockHeader(profile);
  renderMockCoverage(profile);
  renderMockShortcuts(profile);

  const defaultSystem = profile.default_target_system || "all";
  if (defaultSystem === "all") {
    state.selectedMockSystems = new Set(getAllMockSystems());
  } else {
    state.selectedMockSystems = new Set([defaultSystem]);
  }
  syncConnectorCheckboxState();

  mockQueryInput.placeholder = profile.suggested_queries[0] || "質問を入力してください";

  if (resetConversation) {
    resetMockConversation();
  }
}

async function runMockChat() {
  const profile = getSelectedProfile();
  if (!profile) return;

  const query = mockQueryInput.value.trim();
  if (!query) {
    setStatus(mockStatus, "error", "missing input");
    return;
  }

  mockSendButton.disabled = true;
  setStatus(mockStatus, "pending", "thinking");

  if (threadShell) {
    threadShell.classList.add("is-visible");
  }

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

function renderConnectors(connectors) {
  clearNode(connectorStrip);

  connectors.forEach((connector) => {
    const chip = document.createElement("span");
    chip.className = "connector-chip";
    chip.textContent = connector.label;
    chip.title = connector.description;
    connectorStrip.appendChild(chip);
  });
}

function renderResults(payload) {
  clearNode(results);

  const summary = `${payload.subject} / ${payload.target_system} / ${payload.query}`;
  resultSummary.textContent = `${summary} · allowed: ${payload.allowed_targets.join(", ")} · ${payload.elapsed_ms} ms`;
  setStatus(resultStatus, "ok", "ok");

  payload.results.forEach((connector) => {
    const card = document.createElement("article");
    card.className = "connector-result";
    card.dataset.status = connector.hit_count > 0 ? "ok" : "pending";

    const header = document.createElement("div");
    header.className = "result-header";

    const title = document.createElement("strong");
    title.textContent = connector.label;

    const badge = document.createElement("span");
    badge.className = "status-pill";
    badge.dataset.status = connector.hit_count > 0 ? "ok" : "pending";
    badge.textContent = `${connector.hit_count} hits`;

    header.append(title, badge);

    const description = document.createElement("p");
    description.className = "ops-note";
    description.textContent = `${connector.description} · ${connector.route_reason}`;

    card.append(header, description);

    if (connector.documents.length === 0) {
      const emptyState = document.createElement("p");
      emptyState.className = "empty-state";
      emptyState.textContent = "No matches for this query.";
      card.appendChild(emptyState);
    } else {
      const list = document.createElement("ul");
      list.className = "document-list";

      connector.documents.forEach((document) => {
        const item = document.createElement("li");
        const tags = document.tags.length > 0 ? ` · ${document.tags.join(", ")}` : "";
        item.innerHTML = `
          <strong>${document.title}</strong>
          <span>${document.snippet}${tags}</span>
        `;
        list.appendChild(item);
      });

      card.appendChild(list);
    }

    results.appendChild(card);
  });
}

async function runSearch() {
  const subject = subjectInput.value.trim();
  const targetSystem = targetSystemInput.value;
  const query = queryInput.value.trim();

  if (!subject || !query) {
    setStatus(resultStatus, "error", "missing input");
    resultSummary.textContent = "Subject and query are required.";
    clearNode(results);
    return;
  }

  if (searchButton) {
    searchButton.disabled = true;
  }
  setStatus(resultStatus, "pending", "searching");

  try {
    const payload = await requestJson("/api/search", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Request-Id": crypto.randomUUID(),
      },
      body: JSON.stringify({ subject, query, target_system: targetSystem }),
    });

    renderResults(payload);
  } catch (error) {
    setStatus(resultStatus, "error", "failed");
    resultSummary.textContent = error.message;
    clearNode(results);
  } finally {
    if (searchButton) {
      searchButton.disabled = false;
    }
  }
}

async function fetchConnectors() {
  try {
    const payload = await requestJson("/api/connectors");
    renderConnectors(payload.connectors);
    if (metaConnectorCount) {
      metaConnectorCount.textContent = `${payload.connectors.length}`;
    }
  } catch (error) {
    if (connectorStrip) {
      connectorStrip.textContent = `Connector catalog unavailable: ${error.message}`;
    }
  }
}

async function runRuntimeChecks() {
  if (runChecksButton) {
    runChecksButton.disabled = true;
  }

  setStatus(checkHealthz, "pending", "checking");
  setStatus(checkRuntime, "pending", "checking");
  setStatus(checkConnectors, "pending", "checking");
  setStatus(checkSearch, "pending", "checking");

  try {
    const healthzBody = await requestJson("/healthz");
    setStatus(checkHealthz, healthzBody.status === "ok" ? "ok" : "error", healthzBody.status === "ok" ? "ok" : "failed");

    const runtimeBody = await requestJson("/api/runtime");
    setStatus(checkRuntime, runtimeBody.status === "ok" ? "ok" : "error", runtimeBody.status === "ok" ? "ok" : "failed");

    if (runtimeBody.status === "ok") {
      metaService.textContent = runtimeBody.service || "-";
      metaRevision.textContent = runtimeBody.revision || "-";
      metaProject.textContent = runtimeBody.project || "-";
      metaEnvironment.textContent = runtimeBody.environment || "-";
      if (metaConnectorCount) {
        metaConnectorCount.textContent = `${runtimeBody.connector_count ?? "-"}`;
      }
      metaUptime.textContent = formatUptime(runtimeBody.uptime_ms);
    }

    const connectorsBody = await requestJson("/api/connectors");
    setStatus(checkConnectors, connectorsBody.status === "ok" ? "ok" : "error", connectorsBody.status === "ok" ? "ok" : "failed");

    const searchBody = await requestJson("/api/search", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Request-Id": crypto.randomUUID(),
      },
      body: JSON.stringify({
        subject: "admin-user",
        query: "runbook policy incident",
        target_system: "all",
      }),
    });
    setStatus(checkSearch, searchBody.status === "ok" ? "ok" : "error", searchBody.status === "ok" ? "ok" : "failed");

    if (lastChecked) {
      lastChecked.textContent = `Last checked: ${new Date().toLocaleString()}`;
    }
  } catch (error) {
    setStatus(checkHealthz, "error", "failed");
    setStatus(checkRuntime, "error", "failed");
    setStatus(checkConnectors, "error", "failed");
    setStatus(checkSearch, "error", "failed");

    if (lastChecked) {
      lastChecked.textContent = `Check failed: ${error.message}`;
    }
  } finally {
    if (runChecksButton) {
      runChecksButton.disabled = false;
    }
  }
}

async function initialize() {
  await loadDemoConfig();
  await loadDemoSourceSamples();
  await fetchConnectors();
  resetMockConversation();
  setMode("mock");

  if (modeMockButton) {
    modeMockButton.addEventListener("click", () => setMode("mock"));
  }
  if (modeStatusButton) {
    modeStatusButton.addEventListener("click", () => setMode("status"));
  }

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
        const current = getSelectedMockSystems();
        state.selectedMockSystems = current.length > 1 ? new Set([current[0]]) : new Set(current);
      }
      syncConnectorCheckboxState();
    });
  }

  document.addEventListener("click", (event) => {
    if (!mockConnectorMenu || !mockConnectorToggle) return;
    const target = event.target;
    const insideMenu = mockConnectorMenu.contains(target);
    const insideButton = mockConnectorToggle.contains(target);
    if (!insideMenu && !insideButton) {
      mockConnectorMenu.hidden = true;
      mockConnectorToggle.setAttribute("aria-expanded", "false");
    }
  });

  if (mockConnectorMenu) {
    mockConnectorMenu.addEventListener("click", (event) => {
      event.stopPropagation();
    });
  }

  if (searchForm) {
    searchForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await runSearch();
    });
  }

  if (runSearchDemoButton) {
    runSearchDemoButton.addEventListener("click", runSearch);
  }

  if (runChecksButton) {
    runChecksButton.addEventListener("click", runRuntimeChecks);
  }
}

initialize();