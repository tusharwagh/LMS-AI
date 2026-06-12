const TOKEN_KEY = "lms_staff_token";
const USER_KEY = "lms_staff_user";

const state = {
  user: null,
  issue: {
    patronId: null,
    patronName: "",
    patronMeta: null,
    searchResults: [],
    selectedHit: null,
    selectedCopy: null,
    step: 1,
    loanId: null,
    holdingId: null,
    holdingBarcode: null,
  },
  return: {
    context: null,
    pickupFulfillmentId: null,
  },
  agent: {
    sessionId: null,
    pendingApproval: null,
    messages: [],
  },
};

function uuid() {
  return crypto.randomUUID();
}

function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

function clearAuth() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

function parseError(body) {
  if (!body) return "Request failed";
  if (typeof body === "string") return body;
  if (body.message) return body.message;
  if (body.detail?.message) return body.detail.message;
  if (typeof body.detail === "string") return body.detail;
  if (body.details?.violations?.length) {
    return body.details.violations.map((v) => v.message).join("; ");
  }
  if (body.detail?.details?.violations?.length) {
    return body.detail.details.violations.map((v) => v.message).join("; ");
  }
  if (Array.isArray(body.detail)) {
    return body.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  }
  return JSON.stringify(body);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  const res = await fetch(path, { ...options, headers });
  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    if (res.status === 401) {
      clearAuth();
      showLogin();
    }
    throw new Error(parseError(data));
  }
  return data;
}

async function login(username, password) {
  const form = new FormData();
  form.append("username", username);
  form.append("password", password);
  const tokenRes = await fetch("/api/v1/auth/token", { method: "POST", body: form });
  const tokenBody = await tokenRes.json();
  if (!tokenRes.ok) throw new Error(parseError(tokenBody));
  setToken(tokenBody.access_token);
  const me = await api("/api/v1/auth/me");
  sessionStorage.setItem(USER_KEY, JSON.stringify(me));
  state.user = me;
  return me;
}

function showLogin() {
  document.getElementById("login-view").classList.remove("hidden");
  document.getElementById("app-shell").classList.add("hidden");
}

function showApp() {
  document.getElementById("login-view").classList.add("hidden");
  document.getElementById("app-shell").classList.remove("hidden");
  const user = state.user || JSON.parse(sessionStorage.getItem(USER_KEY) || "null");
  state.user = user;
  document.getElementById("nav-user").textContent = user
    ? `${user.display_name || user.username} (${user.role})`
    : "";
  document.querySelectorAll(".admin-only").forEach((el) => {
    el.classList.toggle("hidden", user?.role !== "ADMIN");
  });
}

function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  document.getElementById(`view-${name}`)?.classList.remove("hidden");
  document.querySelectorAll(".nav-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === name);
  });
  if (name === "overdue") loadOverdue();
  if (name === "admin") loadAdmin();
  if (name === "agent") ensureAgentSession();
}

function renderAgentChat() {
  const box = document.getElementById("agent-chat");
  if (!box) return;
  box.innerHTML = state.agent.messages
    .map((m) => `<div class="agent-msg ${m.role}">${escapeHtml(m.content)}</div>`)
    .join("");
  box.scrollTop = box.scrollHeight;
}

function showAgentApproval(pending) {
  const panel = document.getElementById("agent-approval");
  const summary = document.getElementById("agent-approval-summary");
  if (!panel || !summary) return;
  if (!pending) {
    panel.classList.add("hidden");
    summary.textContent = "";
    state.agent.pendingApproval = null;
    return;
  }
  state.agent.pendingApproval = pending;
  summary.textContent = pending.summary;
  panel.classList.remove("hidden");
}

async function ensureAgentSession() {
  if (state.agent.sessionId) return;
  try {
    const res = await api("/api/v1/agent/issue/sessions", { method: "POST" });
    state.agent.sessionId = res.session_id;
    state.agent.messages = [];
    showAgentApproval(null);
    renderAgentChat();
    document.getElementById("agent-alert").innerHTML = "";
  } catch (err) {
    document.getElementById("agent-alert").innerHTML = alertHtml("error", err.message);
  }
}

async function sendAgentMessage() {
  const input = document.getElementById("agent-input");
  const text = input.value.trim();
  if (!text) return;
  await ensureAgentSession();
  state.agent.messages.push({ role: "user", content: text });
  renderAgentChat();
  input.value = "";
  try {
    const res = await api(
      `/api/v1/agent/issue/sessions/${state.agent.sessionId}/message`,
      { method: "POST", body: { message: text } },
    );
    state.agent.messages.push({ role: "assistant", content: res.assistant_message });
    renderAgentChat();
    showAgentApproval(res.pending_approval);
  } catch (err) {
    document.getElementById("agent-alert").innerHTML = alertHtml("error", err.message);
  }
}

async function resumeAgent(approved) {
  if (!state.agent.sessionId) return;
  try {
    const res = await api(
      `/api/v1/agent/issue/sessions/${state.agent.sessionId}/resume`,
      { method: "POST", body: { approved } },
    );
    state.agent.messages.push({ role: "assistant", content: res.assistant_message });
    renderAgentChat();
    showAgentApproval(null);
  } catch (err) {
    document.getElementById("agent-alert").innerHTML = alertHtml("error", err.message);
  }
}

function resetAgentSession() {
  state.agent = { sessionId: null, pendingApproval: null, messages: [] };
  showAgentApproval(null);
  renderAgentChat();
  document.getElementById("agent-alert").innerHTML = "";
  ensureAgentSession();
}

function alertHtml(type, message) {
  return `<div class="alert ${type}">${escapeHtml(message)}</div>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const FULFILLMENT_MODE_LABELS = {
  DESK: "Desk handover",
  DELIVERY: "Delivery to class / home",
  PICKUP_POINT: "Pick-up point",
};

const FULFILLMENT_STATUS_LABELS = {
  PENDING: "Pending",
  IN_TRANSIT: "In transit",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

function formatFulfillmentMode(mode) {
  return FULFILLMENT_MODE_LABELS[mode] || mode.replace(/_/g, " ").toLowerCase();
}

function formatFulfillmentStatus(status) {
  return FULFILLMENT_STATUS_LABELS[status] || status.replace(/_/g, " ").toLowerCase();
}

function formatPatronStatus(status) {
  const labels = { ACTIVE: "Active", SUSPENDED: "Suspended", EXITED: "Exited" };
  return labels[status] || status;
}

function patronIdentifiers(patron) {
  const parts = [];
  if (patron?.external_ref) parts.push(`Admission ${patron.external_ref}`);
  if (patron?.card_barcode) parts.push(`Card ${patron.card_barcode}`);
  return parts.join(" · ");
}

function renderPatronSummary(patron, extraHtml = "") {
  const ids = patronIdentifiers(patron);
  const typeLine = [
    patron.patron_type_name ? patron.patron_type_name : null,
    patron.class_section_label ? patron.class_section_label : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return `
    <p><strong>${escapeHtml(patron.display_name)}</strong></p>
    ${ids ? `<p class="meta">${escapeHtml(ids)}</p>` : ""}
    ${typeLine ? `<p class="meta">${escapeHtml(typeLine)}</p>` : ""}
    <p class="meta">Status: ${escapeHtml(formatPatronStatus(patron.status))}${patron.blocked ? " · Blocked from borrowing" : ""}</p>
    ${extraHtml}
  `;
}

function violationsHtml(report) {
  if (!report?.violations?.length) return "";
  const items = report.violations
    .map((v) => `<li>${escapeHtml(v.message)}</li>`)
    .join("");
  return `<div class="alert warn"><p>Validation issues:</p><ul class="violation-list">${items}</ul></div>`;
}

function setIssueStep(step) {
  state.issue.step = step;
  document.querySelectorAll("#issue-steps .step").forEach((el) => {
    const n = Number(el.dataset.step);
    el.classList.toggle("active", n === step);
    el.classList.toggle("done", n < step);
  });
  for (let i = 1; i <= 4; i++) {
    document.getElementById(`issue-step-${i}`)?.classList.toggle("hidden", i !== step);
  }
  document.getElementById("issue-done").classList.add("hidden");
}

function resetIssue() {
  state.issue = {
    patronId: null,
    patronName: "",
    patronMeta: null,
    searchResults: [],
    selectedHit: null,
    selectedCopy: null,
    step: 1,
    loanId: null,
    holdingId: null,
    holdingBarcode: null,
  };
  document.getElementById("issue-card").value = "";
  document.getElementById("issue-admission").value = "";
  document.getElementById("issue-name").value = "";
  document.getElementById("issue-search").value = "";
  document.getElementById("issue-patron-candidates").innerHTML = "";
  document.getElementById("issue-patron-info").classList.add("hidden");
  document.getElementById("issue-search-results").innerHTML = "";
  document.getElementById("issue-copies").innerHTML = "";
  document.getElementById("issue-alert").innerHTML = "";
  document.getElementById("issue-validate-result").innerHTML = "";
  document.getElementById("issue-mode").value = "DESK";
  document.getElementById("issue-dest-notes").value = "";
  document.getElementById("issue-dest-contact").value = "";
  document.getElementById("issue-cancel-btn").classList.remove("hidden");
  toggleIssueDestination();
  setIssueStep(1);
}

async function issueBack(targetStep) {
  if (state.issue.loanId) {
    document.getElementById("issue-alert").innerHTML = alertHtml(
      "warn",
      "Issue already committed — use Cancel issuance to roll back."
    );
    return;
  }
  try {
    await api("/api/v1/workflows/issue/back", {
      method: "POST",
      body: { target_step: targetStep },
    });
    if (targetStep <= 1) {
      state.issue.selectedHit = null;
      state.issue.selectedCopy = null;
    } else if (targetStep <= 2) {
      state.issue.selectedHit = null;
      state.issue.selectedCopy = null;
    } else if (targetStep <= 3) {
      state.issue.selectedCopy = null;
      document.getElementById("issue-validate-result").innerHTML = "";
    }
    setIssueStep(targetStep);
    document.getElementById("issue-alert").innerHTML = "";
  } catch (err) {
    document.getElementById("issue-alert").innerHTML = alertHtml("error", err.message);
  }
}

function buildIssueStartBody(extra = {}) {
  const body = { ...extra };
  const card = document.getElementById("issue-card").value.trim();
  const admission = document.getElementById("issue-admission").value.trim();
  const name = document.getElementById("issue-name").value.trim();
  if (state.issue.patronId) body.patron_id = state.issue.patronId;
  else if (card) body.card_barcode = card;
  else if (admission) body.external_ref = admission;
  else if (name) body.display_name = name;
  return body;
}

async function startIssueWithPatron(body, patronMeta = null) {
  const res = await api("/api/v1/workflows/issue/start", { method: "POST", body });
  state.issue.patronId = res.patron_id;
  state.issue.patronName = res.patron_display_name;
  if (!patronMeta) {
    try {
      patronMeta = await api(`/api/v1/reference/patrons/${res.patron_id}`);
    } catch {
      patronMeta = {
        display_name: res.patron_display_name,
        external_ref: document.getElementById("issue-admission").value.trim() || null,
        card_barcode: document.getElementById("issue-card").value.trim() || null,
        status: "ACTIVE",
        blocked: false,
      };
    }
  }
  state.issue.patronMeta = patronMeta;
  state.issue.searchResults = res.search_results || [];
  const info = document.getElementById("issue-patron-info");
  info.classList.remove("hidden");
  info.innerHTML = renderPatronSummary(state.issue.patronMeta, violationsHtml(res.patron_validation));
  document.getElementById("issue-patron-candidates").innerHTML = "";
  if (!res.patron_validation.is_valid) {
    document.getElementById("issue-alert").innerHTML = alertHtml(
      "warn",
      "Patron cannot borrow until validation issues are resolved."
    );
  }
  setIssueStep(2);
  if (state.issue.searchResults.length) renderIssueSearchResults(state.issue.searchResults);
}

async function findIssuePatron() {
  const body = buildIssueStartBody({
    search_query: document.getElementById("issue-search").value.trim() || undefined,
  });
  if (!body.patron_id && !body.card_barcode && !body.external_ref && !body.display_name) {
    document.getElementById("issue-alert").innerHTML = alertHtml(
      "error",
      "Enter card, admission number, or patron name."
    );
    return;
  }
  document.getElementById("issue-alert").innerHTML = "";
  try {
    await startIssueWithPatron(body);
  } catch (err) {
    document.getElementById("issue-alert").innerHTML = alertHtml("error", err.message);
  }
}

async function searchIssuePatronsByName() {
  const name = document.getElementById("issue-name").value.trim();
  if (!name) {
    document.getElementById("issue-alert").innerHTML = alertHtml("error", "Enter a patron name.");
    return;
  }
  document.getElementById("issue-alert").innerHTML = "";
  try {
    const res = await api("/api/v1/workflows/issue/search-patrons", {
      method: "POST",
      body: { display_name: name },
    });
    const el = document.getElementById("issue-patron-candidates");
    if (!res.patrons.length) {
      el.innerHTML = `<p class="meta">No patrons found.</p>`;
      return;
    }
    el.innerHTML = res.patrons
      .map(
        (p, idx) => `
      <div class="copy-card patron-pick" data-patron-idx="${idx}">
        <strong>${escapeHtml(p.display_name)}</strong>
        <div class="meta">${p.external_ref ? `Admission ${escapeHtml(p.external_ref)} · ` : ""}${p.card_barcode ? `Card ${escapeHtml(p.card_barcode)}` : ""}</div>
      </div>`
      )
      .join("");
    el.querySelectorAll(".patron-pick").forEach((node) => {
      node.addEventListener("click", async () => {
        const p = res.patrons[Number(node.dataset.patronIdx)];
        state.issue.patronId = p.id;
        document.getElementById("issue-card").value = p.card_barcode || "";
        document.getElementById("issue-admission").value = p.external_ref || "";
        try {
          await startIssueWithPatron(
            {
              patron_id: p.id,
              search_query: document.getElementById("issue-search").value.trim() || undefined,
            },
            {
              display_name: p.display_name,
              external_ref: p.external_ref,
              card_barcode: p.card_barcode,
              status: p.status,
              blocked: false,
            }
          );
        } catch (err) {
          document.getElementById("issue-alert").innerHTML = alertHtml("error", err.message);
        }
      });
    });
  } catch (err) {
    document.getElementById("issue-alert").innerHTML = alertHtml("error", err.message);
  }
}

function renderIssueSearchResults(hits) {
  const el = document.getElementById("issue-search-results");
  if (!hits.length) {
    el.innerHTML = `<p class="meta">No lendable copies found.</p>`;
    return;
  }
  el.innerHTML = hits
    .map(
      (hit) => `
    <div class="search-hit" data-catalog-id="${hit.catalog_id}">
      <strong>${escapeHtml(hit.title)}</strong>
      <div class="meta">${hit.lendable_copies.length} available cop${hit.lendable_copies.length === 1 ? "y" : "ies"}</div>
    </div>`
    )
    .join("");
  el.querySelectorAll(".search-hit").forEach((node) => {
    node.addEventListener("click", () => {
      const hit = hits.find((h) => h.catalog_id === node.dataset.catalogId);
      selectIssueHit(hit);
    });
  });
}

async function searchIssueCatalog() {
  if (!state.issue.patronId) return;
  const q = document.getElementById("issue-search").value.trim();
  if (!q) {
    document.getElementById("issue-alert").innerHTML = alertHtml("error", "Enter a search term.");
    return;
  }
  try {
    const body = buildIssueStartBody({
      patron_id: state.issue.patronId,
      search_query: q,
    });
    const res = await api("/api/v1/workflows/issue/start", { method: "POST", body });
    state.issue.searchResults = res.search_results || [];
    renderIssueSearchResults(state.issue.searchResults);
    document.getElementById("issue-alert").innerHTML = "";
  } catch (err) {
    document.getElementById("issue-alert").innerHTML = alertHtml("error", err.message);
  }
}

function selectIssueHit(hit) {
  state.issue.selectedHit = hit;
  state.issue.selectedCopy = null;
  document.getElementById("issue-selected-title").textContent = hit.title;
  const copiesEl = document.getElementById("issue-copies");
  copiesEl.innerHTML = hit.lendable_copies
    .map(
      (c) => `
    <div class="copy-card" data-holding-id="${c.holding_id}">
      <strong>${escapeHtml(c.barcode)}</strong>
      <div class="meta">${escapeHtml(hit.title)}</div>
      <div class="meta">Accession ${escapeHtml(c.accession_number)}${c.shelf_location ? ` · Shelf ${escapeHtml(c.shelf_location)}` : ""}</div>
    </div>`
    )
    .join("");
  copiesEl.querySelectorAll(".copy-card").forEach((node) => {
    node.addEventListener("click", () => {
      copiesEl.querySelectorAll(".copy-card").forEach((n) => n.classList.remove("selected"));
      node.classList.add("selected");
      state.issue.selectedCopy = hit.lendable_copies.find((c) => c.holding_id === node.dataset.holdingId);
      prepareIssueCommit();
    });
  });
  setIssueStep(3);
}

async function prepareIssueCommit() {
  if (!state.issue.selectedCopy || !state.issue.patronId) return;
  setIssueStep(4);
  document.getElementById("issue-commit-summary").innerHTML = `
    Issue <strong>${escapeHtml(state.issue.selectedHit.title)}</strong>
    (copy <strong>${escapeHtml(state.issue.selectedCopy.barcode)}</strong>) to
    <strong>${escapeHtml(state.issue.patronName)}</strong>
  `;
  try {
    const report = await api("/api/v1/workflows/issue/validate", {
      method: "POST",
      body: {
        patron_id: state.issue.patronId,
        holding_id: state.issue.selectedCopy.holding_id,
      },
    });
    document.getElementById("issue-validate-result").innerHTML = report.is_valid
      ? alertHtml("success", "Ready to issue.")
      : violationsHtml(report);
    document.getElementById("issue-commit-btn").disabled = !report.is_valid;
  } catch (err) {
    document.getElementById("issue-validate-result").innerHTML = alertHtml("error", err.message);
    document.getElementById("issue-commit-btn").disabled = true;
  }
}

function toggleIssueDestination() {
  const mode = document.getElementById("issue-mode").value;
  document.getElementById("issue-destination-fields").classList.toggle("hidden", mode === "DESK");
}

async function commitIssue() {
  if (!state.issue.patronId || !state.issue.selectedCopy) return;
  const mode = document.getElementById("issue-mode").value;
  const body = {
    patron_id: state.issue.patronId,
    holding_id: state.issue.selectedCopy.holding_id,
    fulfillment_mode: mode,
  };
  if (mode !== "DESK") {
    body.destination = {
      notes: document.getElementById("issue-dest-notes").value.trim() || null,
      contact: document.getElementById("issue-dest-contact").value.trim() || null,
    };
  }
  try {
    const res = await api("/api/v1/workflows/issue/commit", {
      method: "POST",
      headers: { "Idempotency-Key": uuid() },
      body,
    });
    state.issue.loanId = res.loan_id;
    state.issue.holdingId = res.holding_id;
    state.issue.holdingBarcode = state.issue.selectedCopy?.barcode ?? null;
    for (let i = 1; i <= 4; i++) document.getElementById(`issue-step-${i}`)?.classList.add("hidden");
    document.getElementById("issue-done").classList.remove("hidden");
    const title = state.issue.selectedHit?.title ?? "Book";
    const barcode = state.issue.selectedCopy?.barcode ?? "";
    let msg = `<strong>${escapeHtml(title)}</strong> issued to <strong>${escapeHtml(state.issue.patronName)}</strong>. Due ${escapeHtml(res.due_date)}.`;
    if (barcode) msg += ` Copy barcode: ${escapeHtml(barcode)}.`;
    if (res.fulfillment) {
      msg += ` ${escapeHtml(formatFulfillmentMode(res.fulfillment.mode))} — ${escapeHtml(formatFulfillmentStatus(res.fulfillment.status))}.`;
    }
    document.getElementById("issue-done-msg").innerHTML = msg;
  } catch (err) {
    document.getElementById("issue-alert").innerHTML = alertHtml("error", err.message);
  }
}

async function cancelIssue() {
  if (!state.issue.loanId) return;
  if (!confirm("Cancel this issuance and return the holding to available?")) return;
  try {
    await api("/api/v1/workflows/issue/cancel", {
      method: "POST",
      headers: { "Idempotency-Key": uuid() },
      body: { loan_id: state.issue.loanId },
    });
    document.getElementById("issue-done-msg").innerHTML =
      `<strong>${escapeHtml(state.issue.selectedHit?.title ?? "Book")}</strong> issuance cancelled. The copy is available again.`;
    document.getElementById("issue-cancel-btn").classList.add("hidden");
    state.issue.loanId = null;
  } catch (err) {
    document.getElementById("issue-alert").innerHTML = alertHtml("error", err.message);
  }
}

function resetReturn() {
  state.return = { context: null, pickupFulfillmentId: null };
  document.getElementById("return-barcode").value = "";
  document.getElementById("return-step-1").classList.remove("hidden");
  document.getElementById("return-step-2").classList.add("hidden");
  document.getElementById("return-done").classList.add("hidden");
  document.getElementById("return-alert").innerHTML = "";
  document.getElementById("return-action").value = "desk";
  document.getElementById("return-pickup-fields").classList.add("hidden");
}

async function lookupReturn() {
  const barcode = document.getElementById("return-barcode").value.trim();
  if (!barcode) {
    document.getElementById("return-alert").innerHTML = alertHtml("error", "Enter holding barcode.");
    return;
  }
  try {
    const ctx = await api("/api/v1/workflows/return/start", {
      method: "POST",
      body: { barcode },
    });
    state.return.context = ctx;
    document.getElementById("return-step-1").classList.add("hidden");
    document.getElementById("return-step-2").classList.remove("hidden");
    document.getElementById("return-context").innerHTML = `
      <div class="list-row">
        <strong>${escapeHtml(ctx.catalog_title)}</strong>
        <div class="meta">Copy barcode ${escapeHtml(ctx.holding_barcode)}</div>
        <div class="meta">Borrower: <strong>${escapeHtml(ctx.patron_display_name)}</strong> · Due ${escapeHtml(ctx.due_date)}${ctx.is_overdue ? " · <span style='color:var(--danger)'>OVERDUE</span>" : ""}</div>
        ${ctx.open_loans_for_patron > 1 ? `<div class="meta">${ctx.open_loans_for_patron - 1} other open loan${ctx.open_loans_for_patron - 1 === 1 ? "" : "s"} for this patron</div>` : ""}
      </div>
    `;
    document.getElementById("return-alert").innerHTML = "";
  } catch (err) {
    document.getElementById("return-alert").innerHTML = alertHtml("error", err.message);
  }
}

async function commitReturn() {
  const ctx = state.return.context;
  if (!ctx) return;
  const action = document.getElementById("return-action").value;
  try {
    if (action === "desk") {
      await api("/api/v1/workflows/return/commit", {
        method: "POST",
        headers: { "Idempotency-Key": uuid() },
        body: { barcode: ctx.holding_barcode },
      });
      document.getElementById("return-step-2").classList.add("hidden");
      document.getElementById("return-done").classList.remove("hidden");
      document.getElementById("return-done-msg").textContent =
        `${ctx.catalog_title} returned. Copy ${ctx.holding_barcode} is available again.`;
    } else {
      await api("/api/v1/workflows/return/pickup/initiate", {
        method: "POST",
        headers: { "Idempotency-Key": uuid() },
        body: {
          loan_id: ctx.loan_id,
          destination: {
            notes: document.getElementById("return-pickup-notes").value.trim() || null,
          },
        },
      });
      document.getElementById("return-step-2").classList.add("hidden");
      document.getElementById("return-done").classList.remove("hidden");
      document.getElementById("return-done-msg").textContent =
        `Pick-up collection scheduled for ${ctx.catalog_title}. Loan stays open until the item is collected from ${ctx.patron_display_name}.`;
    }
  } catch (err) {
    document.getElementById("return-alert").innerHTML = alertHtml("error", err.message);
  }
}

async function searchCatalog() {
  const q = document.getElementById("catalog-query").value.trim();
  if (!q) return;
  const el = document.getElementById("catalog-results");
  el.innerHTML = "<p class='meta'>Searching…</p>";
  try {
    const hits = await api(`/api/v1/catalog/catalogs/search/lendable?q=${encodeURIComponent(q)}`);
    if (!hits.length) {
      el.innerHTML = "<p class='meta'>No published titles with available copies.</p>";
      return;
    }
    el.innerHTML = hits
      .map(
        (hit) => `
      <div class="list-row">
        <strong>${escapeHtml(hit.catalog.title)}</strong>
        <div class="meta">${hit.lendable_holdings.length} available cop${hit.lendable_holdings.length === 1 ? "y" : "ies"}</div>
        <ul class="meta">${hit.lendable_holdings
          .map(
            (h) =>
              `<li>Barcode ${escapeHtml(h.barcode)}${h.shelf_location ? ` · Shelf ${escapeHtml(h.shelf_location)}` : ""}</li>`
          )
          .join("")}</ul>
      </div>`
      )
      .join("");
    document.getElementById("search-alert").innerHTML = "";
  } catch (err) {
    document.getElementById("search-alert").innerHTML = alertHtml("error", err.message);
    el.innerHTML = "";
  }
}

async function loadOverdue() {
  const el = document.getElementById("overdue-results");
  el.innerHTML = "<p class='meta'>Loading…</p>";
  try {
    const loans = await api("/api/v1/loan/loans/overdue");
    if (!loans.length) {
      el.innerHTML = "<p class='meta'>No overdue loans.</p>";
      return;
    }
    el.innerHTML = `
      <table>
        <thead><tr><th>Patron</th><th>Book</th><th>Copy</th><th>Due</th></tr></thead>
        <tbody>
          ${loans
            .map(
              (l) => `<tr>
            <td><strong>${escapeHtml(l.patron_display_name)}</strong></td>
            <td>${escapeHtml(l.catalog_title)}</td>
            <td class="meta">${escapeHtml(l.holding_barcode)}</td>
            <td>${escapeHtml(l.due_date)}</td>
          </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
    document.getElementById("overdue-alert").innerHTML = "";
  } catch (err) {
    document.getElementById("overdue-alert").innerHTML = alertHtml("error", err.message);
    el.innerHTML = "";
  }
}

async function lookupPatron() {
  const card = document.getElementById("patron-card").value.trim();
  const ref = document.getElementById("patron-ref").value.trim();
  const name = document.getElementById("patron-name").value.trim();
  if (!card && !ref && !name) {
    document.getElementById("patron-alert").innerHTML = alertHtml(
      "error",
      "Enter card, admission number, or patron name."
    );
    return;
  }
  try {
    let patron;
    if (name && !card && !ref) {
      const matches = await api(`/api/v1/reference/patrons/search?q=${encodeURIComponent(name)}`);
      if (!matches.length) {
        document.getElementById("patron-result").innerHTML = `<p class="meta">No patrons found.</p>`;
        document.getElementById("patron-alert").innerHTML = "";
        return;
      }
      if (matches.length === 1) {
        patron = matches[0];
      } else {
        document.getElementById("patron-result").innerHTML = matches
          .map(
            (p, idx) => `
          <div class="copy-card patron-result-pick" data-patron-idx="${idx}">
            <strong>${escapeHtml(p.display_name)}</strong>
            <div class="meta">${escapeHtml(patronIdentifiers(p) || "No card or admission on file")}</div>
            <div class="meta">${escapeHtml(p.patron_type_name || "")}${p.class_section_label ? ` · ${escapeHtml(p.class_section_label)}` : ""}</div>
          </div>`
          )
          .join("");
        document.getElementById("patron-result").querySelectorAll(".patron-result-pick").forEach((node) => {
          node.addEventListener("click", () => showPatronDetail(matches[Number(node.dataset.patronIdx)]));
        });
        document.getElementById("patron-alert").innerHTML = alertHtml(
          "warn",
          `${matches.length} patrons match — select one below.`
        );
        return;
      }
    } else {
      const path = card
        ? `/api/v1/reference/patrons/by-card/${encodeURIComponent(card)}`
        : `/api/v1/reference/patrons/by-external-ref/${encodeURIComponent(ref)}`;
      patron = await api(path);
    }
    await showPatronDetail(patron);
    document.getElementById("patron-alert").innerHTML = "";
  } catch (err) {
    document.getElementById("patron-alert").innerHTML = alertHtml("error", err.message);
    document.getElementById("patron-result").innerHTML = "";
  }
}

async function showPatronDetail(patron) {
  const loans = await api(`/api/v1/loan/loans/open?patron_id=${patron.id}`);
  const loansHtml = loans.length
    ? `<ul class="meta">${loans
        .map(
          (l) =>
            `<li><strong>${escapeHtml(l.catalog_title)}</strong> · copy ${escapeHtml(l.holding_barcode)} · due ${escapeHtml(l.due_date)}</li>`
        )
        .join("")}</ul>`
    : `<p class="meta">No open loans.</p>`;
  document.getElementById("patron-result").innerHTML = `
    <div class="list-row">
      ${renderPatronSummary(patron)}
      <h4 style="margin: 1rem 0 0.25rem">Open loans (${loans.length})</h4>
      ${loansHtml}
    </div>`;
}

async function loadAdmin() {
  if (state.user?.role !== "ADMIN") return;
  try {
    const [rules, types, sections] = await Promise.all([
      api("/api/v1/loan/loan-rule-sets"),
      api("/api/v1/reference/patron-types"),
      api("/api/v1/reference/class-sections"),
    ]);
    document.getElementById("admin-rules-list").innerHTML = rules
      .map((r) => `<div class="list-row meta">${escapeHtml(r.name)} — max ${r.max_active_loans}, ${r.loan_period_days} days</div>`)
      .join("") || "<p class='meta'>None yet.</p>";
    document.getElementById("admin-types-list").innerHTML = types
      .map((t) => `<div class="list-row meta">${escapeHtml(t.code)} — ${escapeHtml(t.name)}</div>`)
      .join("") || "<p class='meta'>None yet.</p>";
    document.getElementById("admin-sections-list").innerHTML = sections
      .map((s) => `<div class="list-row meta">Grade ${escapeHtml(s.grade)} ${escapeHtml(s.section)} (${escapeHtml(s.academic_year)})</div>`)
      .join("") || "<p class='meta'>None yet.</p>";
  } catch (err) {
    document.getElementById("admin-alert").innerHTML = alertHtml("error", err.message);
  }
}

async function createAdminRule() {
  try {
    await api("/api/v1/loan/loan-rule-sets", {
      method: "POST",
      body: {
        name: document.getElementById("admin-rule-name").value.trim(),
        max_active_loans: Number(document.getElementById("admin-rule-max").value),
        loan_period_days: Number(document.getElementById("admin-rule-days").value),
      },
    });
    document.getElementById("admin-alert").innerHTML = alertHtml("success", "Rule set created.");
    loadAdmin();
  } catch (err) {
    document.getElementById("admin-alert").innerHTML = alertHtml("error", err.message);
  }
}

async function createAdminType() {
  try {
    await api("/api/v1/reference/patron-types", {
      method: "POST",
      body: {
        code: document.getElementById("admin-type-code").value.trim(),
        name: document.getElementById("admin-type-name").value.trim(),
      },
    });
    document.getElementById("admin-alert").innerHTML = alertHtml("success", "Patron type created.");
    loadAdmin();
  } catch (err) {
    document.getElementById("admin-alert").innerHTML = alertHtml("error", err.message);
  }
}

async function createAdminSection() {
  try {
    await api("/api/v1/reference/class-sections", {
      method: "POST",
      body: {
        grade: document.getElementById("admin-grade").value.trim(),
        section: document.getElementById("admin-section").value.trim(),
        academic_year: document.getElementById("admin-year").value.trim(),
      },
    });
    document.getElementById("admin-alert").innerHTML = alertHtml("success", "Class section created.");
    loadAdmin();
  } catch (err) {
    document.getElementById("admin-alert").innerHTML = alertHtml("error", err.message);
  }
}

function bindEvents() {
  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errEl = document.getElementById("login-error");
    errEl.classList.add("hidden");
    try {
      await login(
        document.getElementById("username").value.trim(),
        document.getElementById("password").value
      );
      showApp();
      showView("issue");
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove("hidden");
    }
  });

  document.getElementById("logout-btn").addEventListener("click", () => {
    clearAuth();
    showLogin();
  });

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => showView(btn.dataset.view));
  });

  document.getElementById("issue-patron-btn").addEventListener("click", findIssuePatron);
  document.getElementById("issue-name-search-btn").addEventListener("click", searchIssuePatronsByName);
  document.getElementById("issue-search-btn").addEventListener("click", searchIssueCatalog);
  document.getElementById("issue-back-step-1").addEventListener("click", () => issueBack(1));
  document.getElementById("issue-back-step-2").addEventListener("click", () => issueBack(2));
  document.getElementById("issue-back-step-3").addEventListener("click", () => issueBack(3));
  document.getElementById("issue-mode").addEventListener("change", toggleIssueDestination);
  document.getElementById("issue-commit-btn").addEventListener("click", commitIssue);
  document.getElementById("issue-new-btn").addEventListener("click", resetIssue);
  document.getElementById("issue-cancel-btn").addEventListener("click", cancelIssue);

  document.getElementById("return-lookup-btn").addEventListener("click", lookupReturn);
  document.getElementById("return-action").addEventListener("change", () => {
    document
      .getElementById("return-pickup-fields")
      .classList.toggle("hidden", document.getElementById("return-action").value !== "pickup");
  });
  document.getElementById("return-commit-btn").addEventListener("click", commitReturn);
  document.getElementById("return-reset-btn").addEventListener("click", resetReturn);

  document.getElementById("catalog-search-btn").addEventListener("click", searchCatalog);
  document.getElementById("overdue-refresh-btn").addEventListener("click", loadOverdue);
  document.getElementById("patron-lookup-btn").addEventListener("click", lookupPatron);

  document.getElementById("admin-rule-create").addEventListener("click", createAdminRule);
  document.getElementById("admin-type-create").addEventListener("click", createAdminType);
  document.getElementById("admin-section-create").addEventListener("click", createAdminSection);

  document.getElementById("agent-send-btn").addEventListener("click", sendAgentMessage);
  document.getElementById("agent-approve-btn").addEventListener("click", () => resumeAgent(true));
  document.getElementById("agent-deny-btn").addEventListener("click", () => resumeAgent(false));
  document.getElementById("agent-new-session-btn").addEventListener("click", resetAgentSession);

  document.getElementById("issue-card").addEventListener("keydown", (e) => {
    if (e.key === "Enter") findIssuePatron();
  });
  document.getElementById("return-barcode").addEventListener("keydown", (e) => {
    if (e.key === "Enter") lookupReturn();
  });
}

async function init() {
  bindEvents();
  resetIssue();
  resetReturn();
  const token = getToken();
  if (token) {
    try {
      state.user = await api("/api/v1/auth/me");
      sessionStorage.setItem(USER_KEY, JSON.stringify(state.user));
      showApp();
      showView("issue");
      return;
    } catch {
      clearAuth();
    }
  }
  showLogin();
}

init();
