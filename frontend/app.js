const API_BASE = "/api";

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
const modalCloseBtn = document.getElementById("modal-close-btn");
const modalCaseTitle = document.getElementById("modal-case-title");
const modalCaseDetails = document.getElementById("modal-case-details");
const reviewDecisionGroup = document.getElementById("review-decision-group");
const reviewDecisionInput = document.getElementById("review_decision");
const overrideField = document.getElementById("override-field");
const overrideValueInput = document.getElementById("override_value");
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
    navTabs.forEach((t) => t.classList.remove("is-active"));
    tab.classList.add("is-active");

    const targetView = tab.dataset.view;
    tabViews.forEach((v) => {
      v.hidden = v.id !== `view-${targetView}`;
    });

    if (targetView === "underwriter") loadEscalations();
    if (targetView === "audit") loadAuditLedger();
  });
});

function setRequestType(value) {
  requestTypeInput.value = value;
  for (const btn of requestTypeGroup.querySelectorAll(".segmented__option")) {
    btn.classList.toggle("is-active", btn.dataset.value === value);
  }
  document.getElementById("requested_value_label").textContent =
    REQUESTED_VALUE_LABELS[value] || "Requested value";

  for (const field of conditionalFields) {
    const applicable = field.dataset.for.split(",").includes(value);
    field.style.display = applicable ? "" : "none";
  }
}

requestTypeGroup.addEventListener("click", (e) => {
  const btn = e.target.closest(".segmented__option");
  if (!btn) return;
  setRequestType(btn.dataset.value);
});

async function loadCustomers() {
  try {
    const res = await fetch(`${API_BASE}/customers`);
    const customers = await res.json();
    for (const c of customers) {
      const opt = document.createElement("option");
      opt.value = c.customer_id;
      opt.textContent = `${c.full_name} — ${c.customer_id} (${capitalize(c.tier)})`;
      customerSelect.appendChild(opt);
    }
  } catch (err) {
    const opt = document.createElement("option");
    opt.textContent = "Couldn't load customers — is the API running?";
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
  stampEl.className = "stamp stamp--" + decision.outcome;

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
  termsList.innerHTML = "";
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
  citationsList.innerHTML = "";
  const citations = decision.policy_citations || [];
  citationsSection.hidden = citations.length === 0;
  for (const c of citations) {
    const li = document.createElement("li");
    li.textContent = c;
    citationsList.appendChild(li);
  }

  const traceList = document.getElementById("trace-list");
  traceList.innerHTML = "";
  for (const step of decision.trace || []) {
    const li = document.createElement("li");
    const label = AGENT_LABELS[step.agent] || step.agent;
    li.innerHTML = `<strong>${label}</strong> — ${step.action}<span class="trace-detail"></span>`;
    li.querySelector(".trace-detail").textContent = step.detail;
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
    const res = await fetch(`${API_BASE}/decide`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": `IDEMP-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    const decision = await res.json();
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
    document.getElementById("closing_all_accounts").checked = !!sample.closing_all_accounts;
  });
});

// --- Underwriter Cockpit (HITL) Logic ---
async function updateEscalationBadge() {
  try {
    const res = await fetch(`${API_BASE}/escalations?status=pending`);
    const data = await res.json();
    escalationBadge.textContent = data.length || 0;
  } catch (_) {}
}

async function loadEscalations() {
  try {
    const res = await fetch(`${API_BASE}/escalations?status=pending`);
    const escalations = await res.json();
    escalationBadge.textContent = escalations.length || 0;

    escalationsList.innerHTML = "";
    if (escalations.length === 0) {
      escalationsEmpty.hidden = false;
      return;
    }
    escalationsEmpty.hidden = true;

    for (const esc of escalations) {
      const card = document.createElement("div");
      card.className = "escalation-card";
      card.innerHTML = `
        <div class="escalation-card__head">
          <h3 class="escalation-card__title mono">${esc.case_id}</h3>
          <span class="hitl-case-tag">${esc.request_type.replace(/_/g, " ")}</span>
        </div>
        <div class="escalation-card__body">
          <div><strong>Customer:</strong> ${esc.customer_id}</div>
          <div><strong>Requested Value:</strong> ${esc.requested_value !== null ? esc.requested_value : "N/A"}</div>
          <ul class="escalation-card__reasons">
            ${(esc.reasons || []).map((r) => `<li>${r}</li>`).join("")}
          </ul>
        </div>
        <button type="button" class="review-btn">Review Case</button>
      `;
      card.querySelector(".review-btn").addEventListener("click", () => openReviewModal(esc));
      escalationsList.appendChild(card);
    }
  } catch (err) {
    escalationsList.innerHTML = `<p class="muted">Failed to load escalations: ${err.message}</p>`;
  }
}

refreshEscalationsBtn.addEventListener("click", loadEscalations);

function openReviewModal(esc) {
  currentReviewCase = esc;
  modalCaseTitle.textContent = `Review ${esc.case_id}`;
  modalCaseDetails.innerHTML = `
    <strong>Customer:</strong> ${esc.customer_id}<br/>
    <strong>Request:</strong> ${esc.request_type.replace(/_/g, " ")}<br/>
    <strong>Flagged Reasons:</strong> ${(esc.reasons || []).join("; ")}
  `;
  reviewDialog.showModal();
}

modalCloseBtn.addEventListener("click", () => reviewDialog.close());

reviewDecisionGroup.addEventListener("click", (e) => {
  const btn = e.target.closest(".segmented__option");
  if (!btn) return;
  for (const b of reviewDecisionGroup.querySelectorAll(".segmented__option")) {
    b.classList.toggle("is-active", b === btn);
  }
  reviewDecisionInput.value = btn.dataset.decision;
  overrideField.hidden = btn.dataset.decision !== "override";
});

reviewForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!currentReviewCase) return;

  const decision = reviewDecisionInput.value;
  const notes = document.getElementById("reviewer_notes").value;
  let overriddenTerms = null;

  if (decision === "override") {
    const val = parseFloat(overrideValueInput.value);
    if (!isNaN(val)) {
      if (currentReviewCase.request_type === "loan_rate_negotiation") overriddenTerms = { new_rate: val };
      if (currentReviewCase.request_type === "fee_waiver") overriddenTerms = { waived_amount: val };
      if (currentReviewCase.request_type === "credit_limit_increase") overriddenTerms = { new_limit: val };
      if (currentReviewCase.request_type === "retention_offer") overriddenTerms = { credit_amount: val };
    }
  }

  const payload = {
    decision,
    reviewer_notes: notes,
    overridden_terms: overriddenTerms,
  };

  try {
    const res = await fetch(`${API_BASE}/escalations/${currentReviewCase.case_id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Review failed");
    }
    reviewDialog.close();
    loadEscalations();
    updateEscalationBadge();
  } catch (err) {
    alert(`Could not complete review: ${err.message}`);
  }
});

// --- Cryptographic Audit Logic ---
async function loadAuditLedger() {
  try {
    const res = await fetch(`${API_BASE}/audit/ledger`);
    const records = await res.json();
    auditTableBody.innerHTML = "";
    if (records.length === 0) {
      auditTableBody.innerHTML = `<tr><td colspan="6" class="muted">No transactions executed yet.</td></tr>`;
      return;
    }
    for (const r of records) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="mono">#${r.id}</td>
        <td class="muted">${r.executed_on.slice(0, 19).replace("T", " ")}</td>
        <td class="mono">${r.customer_id}</td>
        <td>${r.action_type}</td>
        <td><span class="stamp stamp--${r.outcome}" style="font-size:0.65rem;padding:2px 6px;">${r.outcome}</span></td>
        <td class="mono" style="font-size:0.75rem;">${r.record_hash ? r.record_hash.slice(0, 20) + "…" : "—"}</td>
      `;
      auditTableBody.appendChild(tr);
    }
  } catch (err) {
    auditTableBody.innerHTML = `<tr><td colspan="6" class="muted">Error: ${err.message}</td></tr>`;
  }
}

verifyAuditBtn.addEventListener("click", async () => {
  verifyAuditBtn.disabled = true;
  verifyAuditBtn.textContent = "Verifying Chain…";
  try {
    const res = await fetch(`${API_BASE}/audit/verify`);
    const data = await res.json();
    auditStatusBanner.hidden = false;
    auditStatusBanner.className = `status-banner ${data.valid ? "is-valid" : "is-invalid"}`;
    auditStatusText.innerHTML = `<strong>${data.valid ? "✓ SHA-256 Chain Verified" : "⚠ Chain Tamper Alert"}</strong> — ${data.message} (${data.total_records} blocks verified).`;
  } catch (err) {
    auditStatusBanner.hidden = false;
    auditStatusBanner.className = "status-banner is-invalid";
    auditStatusText.textContent = `Verification error: ${err.message}`;
  } finally {
    verifyAuditBtn.disabled = false;
    verifyAuditBtn.textContent = "🛡️ Verify Hash Chain Integrity";
  }
});

// Initialize
setRequestType("loan_rate_negotiation");
loadCustomers();
updateEscalationBadge();
