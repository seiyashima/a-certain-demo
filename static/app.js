const form = document.getElementById("search-form");
const subjectInput = document.getElementById("subject");
const targetSystemInput = document.getElementById("target-system");
const queryInput = document.getElementById("query");
const form = document.getElementById("search-form");
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

function setStatus(node, status, label) {
  if (!node) {
    return;
  }
  node.dataset.status = status;
  node.textContent = label;
}

function clearNode(node) {
  if (node) {
    node.innerHTML = "";
  }
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

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(body.error || body.detail?.error || "request failed");
  }

  return body;
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runSearch();
});

if (runSearchDemoButton) {
  runSearchDemoButton.addEventListener("click", runSearch);
}

if (runChecksButton) {
  runChecksButton.addEventListener("click", runRuntimeChecks);
}

fetchConnectors();
runRuntimeChecks();
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runSearch();
});

if (runSearchDemoButton) {
  runSearchDemoButton.addEventListener("click", runSearch);
}

if (runChecksButton) {
  runChecksButton.addEventListener("click", runRuntimeChecks);
}

fetchConnectors();
runRuntimeChecks();
