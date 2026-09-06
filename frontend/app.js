const API_BASE = "/api";

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

// Fields whose visibility depends on the selected request type.
const conditionalFields = Array.from(document.querySelectorAll(".field[data-for]"));

const REQUESTED_VALUE_LABELS = {
  loan_rate_negotiation: "Requested rate (%)",
  fee_waiver: "Fee amount",
  credit_limit_increase: "Requested increase (%)",
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
    customer_message: "I was charged a 500 rupee overdraft fee, can you waive it? First time this happens.",
    requested_value: 500,
    fee_type: "overdraft",
  },
  4: {
    customer_id: "CUST1002",
    request_type: "credit_limit_increase",
    customer_message: "Can I get a temporary credit limit increase of 40% for a large purchase?",
    requested_value: 40,
    account_id: "ACC2002",
  },
};

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
}

async function submitRequest(payload) {
  showState("loading");
  submitBtn.disabled = true;
  submitBtn.textContent = "Routing…";
  try {
    const res = await fetch(`${API_BASE}/decide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
  });
});

setRequestType("loan_rate_negotiation");
loadCustomers();
