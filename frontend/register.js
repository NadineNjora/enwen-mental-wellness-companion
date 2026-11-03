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

let notices = null;
let saving = false;
let loading = false;
let completed = false;

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

    showMessage("Read both notices before creating your test account.");
    return true;
  } catch {
    retry.hidden = false;

    showMessage(
      "We could not load both test notices. Check that the updated backend is running, then retry.",
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

  if (!form.reportValidity()) return;

  const name = byId("register-name").value.trim();
  const email = byId("register-email").value.trim();
  const password = byId("register-password").value;
  const confirmation = byId("register-confirm-password").value;

  const contactName = byId("contact-name").value.trim();
  const relationship = byId("contact-relationship").value.trim();
  const contactEmail = byId("contact-email").value.trim();

  if (
    !name
    || !contactName
    || [name, contactName, relationship].some(
      value => value.includes("\0")
    )
  ) {
    showMessage(
      "Enter both names using non-blank text without null characters.",
      true
    );
    return;
  }

  if (password !== confirmation) {
    showMessage("Your passwords do not match. Please check them.", true);
    byId("register-confirm-password").focus();
    return;
  }

  if (email.toLowerCase() === contactEmail.toLowerCase()) {
    showMessage(
      "Your trusted contact needs a different email from yours.",
      true
    );
    byId("contact-email").focus();
    return;
  }

  if (!wellnessCheck.checked || !contactCheck.checked) {
    showMessage(
      "Read and accept both notices before continuing.",
      true
    );
    return;
  }

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

  showMessage("Saving your test account and nominated contact...");

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

    showMessage(
      "Account created. Your trusted contact is pending confirmation; no email was sent. You can now log in."
    );

    loginLink.focus();
  } catch (error) {
    refreshNotices =
      error.status === 409 && /notice/i.test(error.message);

    if (!error.status || error.status >= 500) {
      loginLink.hidden = false;

      showMessage(
        "We could not confirm whether your account was saved. Try logging in before submitting again. Nothing will be retried automatically.",
        true
      );
    } else {
      if (error.status === 409 && !refreshNotices) {
        loginLink.hidden = false;
      }

      showMessage(error.message, true);
    }
  } finally {
    saving = false;
    button.textContent = "Create my account";
    fields.disabled = completed || !notices;
    retry.disabled = false;

    byId("register-password").value = "";
    byId("register-confirm-password").value = "";
  }

  if (refreshNotices && await loadNotices()) {
    showMessage(
      "A consent notice changed. Read both notices and tick the boxes again before resubmitting.",
      true
    );
  }
});

retry.addEventListener("click", () => void loadNotices());

window.addEventListener("pageshow", (event) => {
  if (event.persisted) void loadNotices();
});

void loadNotices();