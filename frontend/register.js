"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("register-form");
const fields = byId("register-fields");
const button = byId("register-button");
const message = byId("registration-status");
const retry = byId("reload-notices");
const loginLink = byId("registration-login-link");
const wellnessCheck = byId("register-consent");
const contactCheck = byId("contact-consent");
const backButton = byId("register-back");
const editButton = byId("edit-account");
const checkLoginLink = byId("registration-check-login");

let notices = null;
let saving = false;
let loading = false;
let completed = false;
let currentStep = 1;

function showStep(step, { focus = true } = {}) {
  currentStep = step;
  byId("account-step").hidden = step !== 1;
  byId("contact-step").hidden = step !== 2;
  backButton.hidden = step === 1;
  button.textContent = step === 1 ? "Continue to trusted person →" : "Create my account";
  byId("register-heading").textContent = step === 1 ? "Create your account" : "Your trusted person";
  byId("register-eyebrow").textContent = step === 1
    ? "Let’s make room for you · Step 1 of 2" : "One person in your corner · Step 2 of 2";
  byId("register-step-description").textContent = step === 1
    ? "A few details to make this space yours."
    : "Someone you trust. One person in your corner.";
  byId("register-account-summary").textContent = byId("register-name").value.trim();
  for (const [number, id] of [[1, "account-step-indicator"], [2, "contact-step-indicator"]]) {
    const indicator = byId(id);
    if (number === step) indicator.setAttribute("aria-current", "step");
    else indicator.removeAttribute("aria-current");
    indicator.classList.toggle("step-complete", number < step);
  }
  if (focus) {
    byId("register-heading").focus({ preventScroll: true });
    byId("register-heading").scrollIntoView({ behavior: "auto", block: "nearest" });
  }
}

function invalidField(step, id, text) {
  if (currentStep !== step) showStep(step, { focus: false });
  showMessage(text, true);
  byId(id).focus();
  return false;
}

function validateStep(step) {
  const ids = step === 1
    ? ["register-name", "register-email", "register-password", "register-confirm-password", "register-consent"]
    : ["contact-name", "contact-relationship", "contact-email", "contact-consent"];
  for (const id of ids) {
    const input = byId(id);
    if (!input.checkValidity()) {
      if (currentStep !== step) showStep(step, { focus: false });
      showMessage("Please complete the highlighted field before continuing.", true);
      input.reportValidity();
      return false;
    }
  }
  const nameId = step === 1 ? "register-name" : "contact-name";
  if (!byId(nameId).value.trim() || byId(nameId).value.includes("\0")) {
    return invalidField(step, nameId, "Enter a name using non-blank text without null characters.");
  }
  if (step === 1 && byId("register-password").value !== byId("register-confirm-password").value) {
    return invalidField(1, "register-confirm-password", "Your passwords do not match. Please check them.");
  }
  if (step === 2) {
    if (byId("contact-relationship").value.includes("\0")) {
      return invalidField(2, "contact-relationship", "The relationship must not include null characters.");
    }
    if (byId("register-email").value.trim().toLowerCase() === byId("contact-email").value.trim().toLowerCase()) {
      return invalidField(2, "contact-email", "Your trusted contact needs a different email from yours.");
    }
  }
  return true;
}

function showMessage(text, error = false) {
  message.textContent = text;
  message.classList.toggle("error", error);
}

async function requestJSON(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const headers = { Accept: "application/json" };

    if (payload !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(path, {
      method: payload === undefined ? "GET" : "POST",
      headers,
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: controller.signal,
      cache: "no-store",
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const error = new Error(
        typeof data?.detail === "string"
          ? data.detail
          : "Please check the required fields and your password length."
      );

      error.status = response.status;
      throw error;
    }

    return { status: response.status, data };
  } finally {
    clearTimeout(timeout);
  }
}

function validNotice(value) {
  return value && typeof value.version === "string"
    && value.version.trim().length > 0
    && value.version.length <= 30
    && typeof value.text === "string"
    && value.text.trim().length > 0;
}

async function loadNotices() {
  if (loading || saving || completed) return false;

  loading = true;
  notices = null;
  fields.disabled = true;
  retry.disabled = true;

  wellnessCheck.checked = false;
  contactCheck.checked = false;

  byId("registration-consent-text").textContent =
    "Loading the current notice...";
  byId("contact-consent-text").textContent =
    "Loading the current notice...";

  byId("registration-consent-version").textContent = "";
  byId("contact-consent-version").textContent = "";

  showMessage("Loading both consent notices...");

  try {
    const [wellness, contact] = await Promise.all([
      requestJSON("/auth/consent"),
      requestJSON("/auth/contact-consent"),
    ]);

    if (
      !validNotice(wellness.data)
      || !validNotice(contact.data)
      || contact.data.delivery_mode !== "simulation_only"
    ) {
      throw new Error("The notices are incomplete or not in test mode.");
    }

    notices = {
      wellness: wellness.data,
      contact: contact.data,
    };

    byId("registration-consent-text").textContent = wellness.data.text;
    byId("registration-consent-version").textContent =
      "Notice version: " + wellness.data.version;

    byId("contact-consent-text").textContent = contact.data.text;
    byId("contact-consent-version").textContent =
      "Notice version: " + contact.data.version;

    fields.disabled = false;
    retry.hidden = true;

    showMessage("");
    return true;
  } catch {
    retry.hidden = false;

    showMessage(
      "We could not load the current privacy notices. Please try again.",
      true
    );

    return false;
  } finally {
    loading = false;
    retry.disabled = false;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (saving || completed) return;

  if (!notices || loading) {
    showMessage("Both current notices must load before registration.", true);
    return;
  }

  if (!validateStep(1)) return;
  if (currentStep === 1) {
    showStep(2);
    showMessage("");
    return;
  }
  if (!validateStep(2)) return;

  const name = byId("register-name").value.trim();
  const email = byId("register-email").value.trim();
  const password = byId("register-password").value;

  const contactName = byId("contact-name").value.trim();
  const relationship = byId("contact-relationship").value.trim();
  const contactEmail = byId("contact-email").value.trim();

  const payload = {
    email,
    display_name: name,
    password,
    consent_accepted: wellnessCheck.checked,
    consent_version: notices.wellness.version,
    trusted_contact: {
      full_name: contactName,
      relationship_label: relationship || null,
      email: contactEmail,
    },
    contact_consent_accepted: contactCheck.checked,
    contact_consent_version: notices.contact.version,
  };

  saving = true;
  fields.disabled = true;
  retry.disabled = true;
  button.textContent = "Creating your account...";
  loginLink.hidden = true;
  checkLoginLink.hidden = true;

  showMessage("Saving your account and trusted person...");

  let refreshNotices = false;

  try {
    const { status, data } = await requestJSON(
      "/auth/register",
      payload
    );

    if (
      status !== 201
      || !data
      || typeof data.user_id !== "string"
      || typeof data.email !== "string"
    ) {
      throw new Error("The save could not be confirmed.");
    }

    completed = true;
    form.reset();
    form.hidden = true;
    retry.hidden = true;
    loginLink.hidden = false;
    checkLoginLink.hidden = true;
    byId("registration-success").hidden = false;
    byId("registration-save-note").hidden = true;
    byId("register-heading").textContent = "You’ve made room for yourself.";
    byId("register-eyebrow").textContent = "Both steps complete";
    byId("register-step-description").textContent = "Your ENWEN account is ready.";
    for (const id of ["account-step-indicator", "contact-step-indicator"]) {
      byId(id).removeAttribute("aria-current");
      byId(id).classList.add("step-complete");
    }

    showMessage(
      "Account created. Your trusted contact is pending confirmation; no email was sent. You can now log in."
    );

    loginLink.focus();
  } catch (error) {
    refreshNotices =
      error.status === 409 && /notice/i.test(error.message);

    if (!error.status || error.status >= 500) {
      checkLoginLink.hidden = false;

      showMessage(
        "We could not confirm whether your account was saved. Try logging in before submitting again. Nothing will be retried automatically.",
        true
      );
    } else {
      if (error.status === 409 && !refreshNotices) {
        checkLoginLink.hidden = false;
      }

      showMessage(error.message, true);
    }
  } finally {
    saving = false;
    fields.disabled = completed || !notices;
    retry.disabled = false;

    byId("register-password").value = "";
    byId("register-confirm-password").value = "";
    if (!completed) showStep(1, { focus: false });
  }

  if (refreshNotices && await loadNotices()) {
    showMessage(
      "A consent notice changed. Read both notices and tick the boxes again before resubmitting.",
      true
    );
  }
});

retry.addEventListener("click", () => void loadNotices());
backButton.addEventListener("click", () => {
  if (!saving && !completed) { showStep(1); showMessage(""); }
});
editButton.addEventListener("click", () => {
  if (!saving && !completed) { showStep(1); showMessage(""); }
});

window.addEventListener("pageshow", (event) => {
  if (event.persisted && !completed) {
    byId("register-password").value = "";
    byId("register-confirm-password").value = "";
    showStep(1, { focus: false });
    void loadNotices();
  }
});

showStep(1, { focus: false });
void loadNotices();
