const API_BASE = "/api";

async function requestJson(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const apiKey = sessionStorage.getItem("bankmind-api-key");
  if (apiKey) headers.set("Authorization", `Bearer ${apiKey}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let body;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const detail = body && typeof body === "object" ? body.detail : null;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  if (body === null) throw new Error("The server returned an invalid response.");
  return body;
}

const apiKeyForm = document.getElementById("api-key-form");
const apiKeyInput = document.getElementById("api-key");
const apiKeyStatus = document.getElementById("api-key-status");
const clearApiKeyButton = document.getElementById("clear-api-key");

apiKeyForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const key = apiKeyInput.value.trim();
  if (!key) {
    apiKeyStatus.textContent = "Enter a key or use Clear.";
    return;
  }
  sessionStorage.setItem("bankmind-api-key", key);
  apiKeyInput.value = "";
  apiKeyStatus.textContent = "API key active for this browser tab.";
  loadCustomers();
  updateEscalationBadge();
});

clearApiKeyButton.addEventListener("click", () => {
  sessionStorage.removeItem("bankmind-api-key");
  apiKeyInput.value = "";
  apiKeyStatus.textContent = "API key cleared.";
});

function textElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text ?? "";
  return element;
}

// Elements - Intake
const form = document.getElementById("request-form");
const customerSelect = document.getElementById("customer");
const requestTypeGroup = document.getElementById("request-type-group");
const requestTypeInput = document.getElementById("request_type");
const submitBtn = document.getElementById("submit-btn");

const emptyEl = document.getElementById("statement-empty");
const loadingEl = document.getElementById("statement-loading");
const errorEl = document.getElementById("statement-error");
const errorMsgEl = document.getElementById("statement-error-message");
const resultEl = document.getElementById("statement-result");

// Elements - Tabs & Cockpit
const navTabs = document.querySelectorAll(".nav-tab");
const tabViews = document.querySelectorAll(".tab-view");
const escalationBadge = document.getElementById("escalation-badge");
const escalationsList = document.getElementById("escalations-list");
const escalationsEmpty = document.getElementById("escalations-empty");
const refreshEscalationsBtn = document.getElementById("refresh-escalations-btn");

// Modal
const reviewDialog = document.getElementById("review-dialog");
const reviewForm = document.getElementById("review-form");
const reviewSubmitBtn = document.getElementById("submit-review-btn");
const modalCloseBtn = document.getElementById("modal-close-btn");
const modalCaseTitle = document.getElementById("modal-case-title");
const modalCaseDetails = document.getElementById("modal-case-details");
const reviewDecisionGroup = document.getElementById("review-decision-group");
const reviewDecisionInput = document.getElementById("review_decision");
const overrideField = document.getElementById("override-field");
const overrideValueInput = document.getElementById("override_value");
const reviewError = document.getElementById("review-error");
let currentReviewCase = null;

// Elements - Audit
const verifyAuditBtn = document.getElementById("verify-audit-btn");
const auditStatusBanner = document.getElementById("audit-status-banner");
const auditStatusText = document.getElementById("audit-status-text");
const auditTableBody = document.getElementById("audit-table-body");

const conditionalFields = Array.from(document.querySelectorAll(".field[data-for]"));

const REQUESTED_VALUE_LABELS = {
  loan_rate_negotiation: "Requested rate (%)",
  fee_waiver: "Fee amount",
  credit_limit_increase: "Requested increase (%)",
  retention_offer: "Requested retention credit",
};

const SAMPLES = {
  1: {
    customer_id: "CUST1001",
    request_type: "loan_rate_negotiation",
    customer_message: "I found a personal loan at 9.8% at another bank, can you match it?",
    requested_value: 9.8,
    loan_id: "LOAN3001",
  },
  2: {
    customer_id: "CUST1004",
    request_type: "loan_rate_negotiation",
    customer_message: "My credit card rate is too high, I want it dropped to 9%.",
    requested_value: 9.0,
  },
  3: {
    customer_id: "CUST1005",
    request_type: "fee_waiver",
    customer_message: "I was charged a 500 overdraft fee on account ACC2005, can you waive it? First time this happens.",
    requested_value: 500,
    fee_type: "overdraft",
  },
  4: {
    customer_id: "CUST1002",
    request_type: "credit_limit_increase",
    customer_message: "Can I get a temporary credit limit increase of 40% on card 4532-1111-2222-3333 for a large purchase?",
    requested_value: 40,
    account_id: "ACC2002",
    is_temporary: true,
  },
  5: {
    customer_id: "CUST1005",
    request_type: "retention_offer",
    customer_message: "A competitor bank offered me a signup bonus — thinking about moving my accounts unless you can offer something.",
    requested_value: 1500,
    closing_all_accounts: false,
  },
};

// --- Tab Navigation ---
navTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    navTabs.forEach((t) => {
      t.classList.remove("is-active");
      t.setAttribute("aria-selected", "false");
      t.tabIndex = -1;
    });
    tab.classList.add("is-active");
    tab.setAttribute("aria-selected", "true");
    tab.tabIndex = 0;

    const targetView = tab.dataset.view;
    tabViews.forEach((v) => {
      v.hidden = v.id !== `view-${targetView}`;
    });

    if (targetView === "underwriter") loadEscalations();
    if (targetView === "audit") loadAuditLedger();
  });

  tab.addEventListener("keydown", (event) => {
    const tabs = Array.from(navTabs);
    const index = tabs.indexOf(tab);
    let nextIndex;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex !== undefined) {
      event.preventDefault();
      tabs[nextIndex].click();
      tabs[nextIndex].focus();
    }
  });
});

function setRequestType(value) {
  requestTypeInput.value = value;
  for (const btn of requestTypeGroup.querySelectorAll(".segmented__option")) {
    btn.classList.toggle("is-active", btn.dataset.value === value);
    btn.setAttribute("aria-pressed", String(btn.dataset.value === value));
  }
  document.getElementById("requested_value_label").textContent =
    REQUESTED_VALUE_LABELS[value] || "Requested value";

  for (const field of conditionalFields) {
    const applicable = field.dataset.for.split(",").includes(value);
    field.hidden = !applicable;
    for (const control of field.querySelectorAll("input, select, textarea")) {
      control.disabled = !applicable;
    }
  }
}

requestTypeGroup.addEventListener("click", (e) => {
  const btn = e.target.closest(".segmented__option");
  if (!btn) return;
  setRequestType(btn.dataset.value);
});

async function loadCustomers() {
  try {
    const customers = await requestJson("/customers");
    for (const c of customers) {
      const opt = document.createElement("option");
      opt.value = c.customer_id;
      opt.textContent = `${c.full_name} — ${c.customer_id} (${capitalize(c.tier)})`;
      customerSelect.appendChild(opt);
    }
  } catch (err) {
    const opt = document.createElement("option");
    opt.textContent = `Couldn't load customers: ${err.message}`;
    opt.disabled = true;
    customerSelect.appendChild(opt);
  }
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

function showState(state) {
  emptyEl.hidden = state !== "empty";
  loadingEl.hidden = state !== "loading";
  errorEl.hidden = state !== "error";
  resultEl.hidden = state !== "result";
}

const AGENT_LABELS = {
  CustomerProfileAgent: "Customer profile",
  PolicyComplianceAgent: "Policy check",
  NegotiationAgent: "Negotiation",
  ExecutionAgent: "Execution",
  EscalationAgent: "Escalation",
  SupervisorAgent: "Supervisor",
};

function renderDecision(decision) {
  const stampEl = document.getElementById("outcome-stamp");
  stampEl.textContent = capitalize(decision.outcome);
  const outcomes = new Set(["approved", "denied", "escalated", "pending"]);
  stampEl.className = `stamp${outcomes.has(decision.outcome) ? ` stamp--${decision.outcome}` : ""}`;

  document.getElementById("result-customer-name").textContent =
    customerSelect.options[customerSelect.selectedIndex]?.text.split(" — ")[0] || "";
  document.getElementById("result-customer-id").textContent = decision.customer_id;

  const caseIdEl = document.getElementById("result-case-id");
  if (decision.case_id) {
    caseIdEl.textContent = `Escalation Case: ${decision.case_id}`;
    caseIdEl.hidden = false;
  } else {
    caseIdEl.hidden = true;
  }

  const hashSec = document.getElementById("hash-section");
  const hashEl = document.getElementById("result-record-hash");
  if (decision.record_hash) {
    hashEl.textContent = decision.record_hash;
    hashSec.hidden = false;
  } else {
    hashSec.hidden = true;
  }

  document.getElementById("result-reasoning").textContent = decision.reasoning;

  const termsSection = document.getElementById("terms-section");
  const termsList = document.getElementById("terms-list");
  termsList.replaceChildren();
  const termEntries = Object.entries(decision.terms || {});
  termsSection.hidden = termEntries.length === 0;
  for (const [key, value] of termEntries) {
    const dt = document.createElement("dt");
    dt.textContent = key.replace(/_/g, " ");
    const dd = document.createElement("dd");
    dd.textContent = typeof value === "object" ? JSON.stringify(value) : String(value);
    termsList.appendChild(dt);
    termsList.appendChild(dd);
  }

  const citationsSection = document.getElementById("citations-section");
  const citationsList = document.getElementById("citations-list");
  citationsList.replaceChildren();
  const citations = decision.policy_citations || [];
  citationsSection.hidden = citations.length === 0;
  for (const c of citations) {
    const li = document.createElement("li");
    li.textContent = c;
    citationsList.appendChild(li);
  }

  const traceList = document.getElementById("trace-list");
  traceList.replaceChildren();
  for (const step of decision.trace || []) {
    const li = document.createElement("li");
    const label = AGENT_LABELS[step.agent] || step.agent;
    li.append(
      textElement("strong", "", label),
      document.createTextNode(` — ${step.action ?? ""}`),
      textElement("span", "trace-detail", step.detail)
    );
    traceList.appendChild(li);
  }

  showState("result");
  updateEscalationBadge();
}

async function submitRequest(payload) {
  showState("loading");
  submitBtn.disabled = true;
  submitBtn.textContent = "Routing…";
  try {
    const decision = await requestJson("/decide", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": `IDEMP-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      },
      body: JSON.stringify(payload),
    });
    renderDecision(decision);
  } catch (err) {
    errorMsgEl.textContent = err.message || "Something went wrong reaching the supervisor.";
    showState("error");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Route to supervisor";
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const formData = new FormData(form);
  const payload = {
    customer_id: formData.get("customer_id"),
    request_type: formData.get("request_type"),
    customer_message: formData.get("customer_message"),
  };
  const requestedValue = formData.get("requested_value");
  if (requestedValue) payload.requested_value = parseFloat(requestedValue);
  const loanId = formData.get("loan_id");
  if (loanId) payload.loan_id = loanId;
  const accountId = formData.get("account_id");
  if (accountId) payload.account_id = accountId;
  const feeType = formData.get("fee_type");
  if (feeType) payload.fee_type = feeType;
  payload.closing_all_accounts = formData.get("closing_all_accounts") === "on";
  payload.is_temporary = formData.get("is_temporary") === "on";

  submitRequest(payload);
});

document.querySelectorAll(".samples__item").forEach((btn) => {
  btn.addEventListener("click", () => {
    const sample = SAMPLES[btn.dataset.sample];
    if (!sample) return;

    customerSelect.value = sample.customer_id;
    setRequestType(sample.request_type);
    document.getElementById("customer_message").value = sample.customer_message;
    document.getElementById("requested_value").value = sample.requested_value ?? "";
    document.getElementById("loan_id").value = sample.loan_id ?? "";
    document.getElementById("account_id").value = sample.account_id ?? "";
    document.getElementById("fee_type").value = sample.fee_type ?? "";
    document.getElementById("is_temporary").checked = !!sample.is_temporary;
    document.getElementById("closing_all_accounts").checked = !!sample.closing_all_accounts;
  });
});

// --- Underwriter Cockpit (HITL) Logic ---
async function updateEscalationBadge() {
  try {
    const data = await requestJson("/escalations?status=pending");
    escalationBadge.textContent = data.length || 0;
  } catch (err) {
    console.error("Could not refresh the pending escalation count.", err);
  }
}

async function loadEscalations() {
  if (refreshEscalationsBtn.disabled) return;
  refreshEscalationsBtn.disabled = true;
  const refreshLabel = refreshEscalationsBtn.textContent;
  refreshEscalationsBtn.textContent = "Refreshing…";
  try {
    const escalations = await requestJson("/escalations?status=pending");
    if (!Array.isArray(escalations)) throw new Error("Unexpected escalation response.");
    escalationBadge.textContent = escalations.length || 0;

    escalationsList.replaceChildren();
    if (escalations.length === 0) {
      escalationsEmpty.hidden = false;
      return;
    }
    escalationsEmpty.hidden = true;

    for (const esc of escalations) {
      const card = document.createElement("div");
      card.className = "escalation-card";
      const head = document.createElement("div");
      head.className = "escalation-card__head";
      head.append(
        textElement("h3", "escalation-card__title mono", esc.case_id),
        textElement("span", "hitl-case-tag", (esc.request_type || "").replace(/_/g, " "))
      );

      const body = document.createElement("div");
      body.className = "escalation-card__body";
      const customer = document.createElement("div");
      customer.append(textElement("strong", "", "Customer: "), document.createTextNode(esc.customer_id ?? "—"));
      const requestedValue = document.createElement("div");
      requestedValue.append(
        textElement("strong", "", "Requested value: "),
        document.createTextNode(esc.requested_value ?? "N/A")
      );
      const reasons = document.createElement("ul");
      reasons.className = "escalation-card__reasons";
      for (const reason of esc.reasons || []) reasons.appendChild(textElement("li", "", reason));
      body.append(customer, requestedValue, reasons);

      const reviewButton = textElement("button", "review-btn", "Review case");
      reviewButton.type = "button";
      reviewButton.addEventListener("click", () => openReviewModal(esc));
      card.append(head, body, reviewButton);
      escalationsList.appendChild(card);
    }
  } catch (err) {
    escalationsEmpty.hidden = true;
    escalationsList.replaceChildren(textElement("p", "muted", `Failed to load escalations: ${err.message}`));
  } finally {
    refreshEscalationsBtn.disabled = false;
    refreshEscalationsBtn.textContent = refreshLabel;
  }
}

refreshEscalationsBtn.addEventListener("click", loadEscalations);

function openReviewModal(esc) {
  currentReviewCase = esc;
  modalCaseTitle.textContent = `Review ${esc.case_id}`;
  modalCaseDetails.replaceChildren();
  for (const [label, value] of [
    ["Customer", esc.customer_id],
    ["Request", (esc.request_type || "").replace(/_/g, " ")],
    ["Flagged reasons", (esc.reasons || []).join("; ") || "None listed"],
  ]) {
    const detail = document.createElement("p");
    detail.append(textElement("strong", "", `${label}: `), document.createTextNode(value ?? "—"));
    modalCaseDetails.appendChild(detail);
  }
  reviewForm.reset();
  reviewDecisionInput.value = "approve";
  overrideField.hidden = true;
  overrideValueInput.required = false;
  reviewError.hidden = true;
  for (const button of reviewDecisionGroup.querySelectorAll(".segmented__option")) {
    const selected = button.dataset.decision === "approve";
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-pressed", String(selected));
  }
  reviewDialog.showModal();
}

modalCloseBtn.addEventListener("click", () => reviewDialog.close());

reviewDecisionGroup.addEventListener("click", (e) => {
  const btn = e.target.closest(".segmented__option");
  if (!btn) return;
  for (const b of reviewDecisionGroup.querySelectorAll(".segmented__option")) {
    b.classList.toggle("is-active", b === btn);
    b.setAttribute("aria-pressed", String(b === btn));
  }
  reviewDecisionInput.value = btn.dataset.decision;
  overrideField.hidden = btn.dataset.decision !== "override";
  overrideValueInput.required = btn.dataset.decision === "override";
  reviewError.hidden = true;
});

reviewForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (reviewSubmitBtn.disabled) return;
  if (!currentReviewCase) {
    reviewError.textContent = "Select an escalation case before submitting a review.";
    reviewError.hidden = false;
    return;
  }

  const decision = reviewDecisionInput.value;
  const notes = document.getElementById("reviewer_notes").value;
  let overriddenTerms = null;

  if (decision === "override") {
    const val = parseFloat(overrideValueInput.value);
    if (!Number.isFinite(val)) {
      reviewError.textContent = "Enter a valid value for the overridden terms.";
      reviewError.hidden = false;
      overrideValueInput.focus();
      return;
    }
    if (currentReviewCase.request_type === "loan_rate_negotiation") overriddenTerms = { new_rate: val };
    if (currentReviewCase.request_type === "fee_waiver") overriddenTerms = { waived_amount: val };
    if (currentReviewCase.request_type === "credit_limit_increase") overriddenTerms = { new_limit: val };
    if (currentReviewCase.request_type === "retention_offer") overriddenTerms = { credit_amount: val };
  }

  const payload = {
    decision,
    reviewer_notes: notes,
    overridden_terms: overriddenTerms,
  };

  reviewSubmitBtn.disabled = true;
  reviewSubmitBtn.textContent = "Submitting review…";
  try {
    await requestJson(`/escalations/${encodeURIComponent(currentReviewCase.case_id)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    reviewDialog.close();
    loadEscalations();
    updateEscalationBadge();
  } catch (err) {
    reviewError.textContent = `Could not complete review: ${err.message}`;
    reviewError.hidden = false;
  } finally {
    reviewSubmitBtn.disabled = false;
    reviewSubmitBtn.textContent = "Commit Review & Execute";
  }
});

// --- Cryptographic Audit Logic ---
async function loadAuditLedger() {
  try {
    const records = await requestJson("/audit/ledger");
    if (!Array.isArray(records)) throw new Error("Unexpected audit ledger response.");
    auditTableBody.replaceChildren();
    if (records.length === 0) {
      const emptyRow = document.createElement("tr");
      const emptyCell = textElement("td", "muted", "No transactions recorded yet.");
      emptyCell.colSpan = 6;
      emptyRow.appendChild(emptyCell);
      auditTableBody.appendChild(emptyRow);
      return;
    }
    for (const r of records) {
      const tr = document.createElement("tr");
      const timestamp = String(r.executed_on || "—").slice(0, 19).replace("T", " ");
      const outcome = String(r.outcome || "unknown");
      const outcomeClasses = new Set(["approved", "denied", "escalated", "pending"]);
      tr.append(
        textElement("td", "mono", `#${r.id ?? "—"}`),
        textElement("td", "muted", timestamp),
        textElement("td", "mono", r.customer_id),
        textElement("td", "", r.action_type),
      );
      const outcomeCell = document.createElement("td");
      const outcomeStamp = textElement(
        "span",
        `stamp${outcomeClasses.has(outcome) ? ` stamp--${outcome}` : ""}`,
        outcome
      );
      outcomeCell.appendChild(outcomeStamp);
      tr.append(
        outcomeCell,
        textElement("td", "mono audit-hash", r.record_hash ? `${r.record_hash.slice(0, 20)}…` : "—")
      );
      auditTableBody.appendChild(tr);
    }
  } catch (err) {
    const errorRow = document.createElement("tr");
    const errorCell = textElement("td", "muted", `Could not load audit ledger: ${err.message}`);
    errorCell.colSpan = 6;
    errorRow.appendChild(errorCell);
    auditTableBody.replaceChildren(errorRow);
  }
}

verifyAuditBtn.addEventListener("click", async () => {
  verifyAuditBtn.disabled = true;
  verifyAuditBtn.textContent = "Verifying chain…";
  try {
    const data = await requestJson("/audit/verify");
    auditStatusBanner.hidden = false;
    auditStatusBanner.className = `status-banner ${data.valid ? "is-valid" : "is-invalid"}`;
    const status = textElement("strong", "", data.valid ? "Hash chain verified" : "Hash chain check failed");
    auditStatusText.replaceChildren(
      status,
      document.createTextNode(` — ${data.message} (${data.total_records} records checked).`)
    );
  } catch (err) {
    auditStatusBanner.hidden = false;
    auditStatusBanner.className = "status-banner is-invalid";
    auditStatusText.textContent = `Verification error: ${err.message}`;
  } finally {
    verifyAuditBtn.disabled = false;
    verifyAuditBtn.textContent = "Verify hash chain";
  }
});

// Initialize
setRequestType("loan_rate_negotiation");
loadCustomers();
updateEscalationBadge();
