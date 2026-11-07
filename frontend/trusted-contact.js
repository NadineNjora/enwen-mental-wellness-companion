"use strict";

// Contact details and tokens remain in memory and are cleared at logout.
const contactUI = Object.fromEntries([
  "home-status", "state", "refresh", "message", "details", "name", "email",
  "relationship", "invitation-summary", "invite-form", "invite-fields",
  "test-notice", "replacement-note", "test-ack", "send", "send-message",
].map(key => [key, document.getElementById("contact-" + key)]));
let contactGeneration = 0;
let contactLoading = false;
let contactSending = false;
let contactRecord = null;
let contactNotice = null;
let contactCooldownTimer = null;
const contactControllers = new Set();

function contactMessage(key, message, error = false) {
  contactUI[key].textContent = message;
  contactUI[key].classList.toggle("error", error);
}

function resetTrustedContactPanel() {
  window.enwenContactSetup?.reset();
  contactGeneration += 1;
  for (const controller of contactControllers) controller.abort();
  contactControllers.clear();
  clearTimeout(contactCooldownTimer);
  contactCooldownTimer = null;
  contactRecord = null;
  contactNotice = null;
  contactLoading = false;
  contactSending = false;
  contactUI["invite-form"].reset();
  contactUI["invite-form"].hidden = true;
  contactUI.details.hidden = true;
  contactUI["invite-fields"].disabled = true;
  contactUI.send.disabled = true;
  contactUI.refresh.disabled = true;
  contactUI.state.textContent = "Not loaded";
  contactUI.state.removeAttribute("data-state");
  for (const key of ["home-status", "message", "name", "email", "relationship",
    "invitation-summary", "test-notice", "send-message"]) contactMessage(key, "");
}

function setupTrustedContactPanel() {
  resetTrustedContactPanel();
  void loadTrustedContact();
}

async function contactRequest(path, generation, body) {
  const controller = new AbortController();
  contactControllers.add(controller);
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        Accept: "application/json", Authorization: `Bearer ${accessToken}`,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store", credentials: "omit", signal: controller.signal,
    });
    const data = await response.json().catch(() => null);
    if (generation !== contactGeneration) throw new Error("Old session ignored.");
    if (response.status === 401) endSession("Your session expired. Please log in again.");
    if (!response.ok) {
      const error = new Error(typeof data?.detail === "string" ? data.detail : "The request could not be completed.");
      error.status = response.status;
      throw error;
    }
    return data;
  } finally {
    clearTimeout(timeout);
    contactControllers.delete(controller);
  }
}

function updateContactControls() {
  contactUI.refresh.disabled = !accessToken || contactLoading || contactSending;
  contactUI["invite-fields"].disabled = !accessToken || contactLoading || contactSending
    || !contactRecord?.can_invite || !contactNotice;
  contactUI.send.disabled = contactUI["invite-fields"].disabled || !contactUI["test-ack"].checked;
}

function renderTrustedContact() {
  const states = { pending: contactRecord.latest_invitation?.status === "expired"
      ? "Invitation expired" : contactRecord.latest_invitation ? "Awaiting response" : "Invitation not sent",
    confirmed: "Accepted",
    declined: "Declined", revoked: "Revoked" };
  const state = contactRecord.confirmation_status;
  if (!(state in states) || contactRecord.delivery_mode !== "local_test"
      || contactRecord.live_notifications_enabled !== false) {
    throw new Error("Unexpected contact status. Local testing is unavailable.");
  }
  contactUI.state.textContent = states[state];
  contactUI.state.dataset.state = state;
  contactUI["home-status"].textContent = `${contactRecord.full_name} — ${states[state]}`;
  contactUI.name.textContent = contactRecord.full_name;
  contactUI.email.textContent = contactRecord.email;
  contactUI.relationship.textContent = contactRecord.relationship_label || "Not specified";
  contactUI.details.hidden = false;
  const latest = contactRecord.latest_invitation;
  const date = latest ? new Date(latest.expires_at) : null;
  const expiry = date && !Number.isNaN(date.getTime()) ? date.toLocaleString() : "date unavailable";
  contactUI["invitation-summary"].textContent = !latest
    ? "No invitation has been prepared yet."
    : latest.status === "awaiting_response"
      ? `Your invitation is waiting in the local inbox. The link expires ${expiry}.`
      : latest.status === "expired" ? "The last invitation expired. You can request a replacement."
      : `Last invitation: ${latest.status}. No live alerts are enabled.`;
  contactUI["invite-form"].hidden = state !== "pending";
  if (state !== "pending") contactMessage("send-message", "");
  contactUI["replacement-note"].hidden = !latest;
  contactUI.send.textContent = latest ? "Prepare replacement invitation" : "Prepare invitation";
  contactMessage("message", contactRecord.invitation_block_reason || "Contact status is up to date.");
  if (contactRecord.retry_after_seconds > 0 && state === "pending") {
    const seconds = Math.min(61, Math.ceil(contactRecord.retry_after_seconds));
    contactMessage("message", `Please wait about ${seconds} seconds before requesting another invitation.`);
    // Recheck with the server, rather than trusting the browser to unlock sending.
    const generation = contactGeneration;
    contactCooldownTimer = setTimeout(() => {
      if (generation === contactGeneration) void loadTrustedContact();
    }, (seconds + 1) * 1000);
  }
}

async function loadTrustedContact() {
  if (!accessToken || contactLoading || contactSending) return;
  const generation = contactGeneration;
  clearTimeout(contactCooldownTimer);
  contactLoading = true;
  contactRecord = null;
  contactNotice = null;
  contactUI["test-ack"].checked = false;
  updateContactControls();
  contactMessage("message", "Checking your contact status...");
  try {
    const record = await contactRequest("/trusted-contact", generation);
    if (generation !== contactGeneration) return;
    contactRecord = record;
    window.enwenContactSetup?.reset();
    renderTrustedContact();
    if (record.confirmation_status === "pending") {
      const notice = await contactRequest("/trusted-contact/invitation-notice", generation);
      if (generation !== contactGeneration) return;
      if (notice?.delivery_mode !== "local_test" || typeof notice.text !== "string"
          || !notice.text.trim() || typeof notice.notice_version !== "string" || !notice.notice_version.trim()) {
        throw new Error("The invitation notice is unavailable.");
      }
      contactNotice = notice;
      contactUI["test-notice"].textContent = notice.text;
    }
  } catch (error) {
    if (generation !== contactGeneration) return;
    contactRecord = null;
    contactNotice = null;
    contactUI.details.hidden = true;
    contactUI["invite-form"].hidden = true;
    contactUI["invitation-summary"].textContent = "";
    contactUI.state.textContent = error.status === 404 ? "No contact on this account" : "Status unavailable";
    contactUI.state.removeAttribute("data-state");
    contactUI["home-status"].textContent = contactUI.state.textContent;
    contactMessage("message", error.status === 404
      ? "Add your trusted person below to get started."
      : error.status ? error.message : "Could not refresh contact status. Check your connection and try Refresh status.", error.status !== 404);
    if (error.status === 404) void window.enwenContactSetup?.show();
  } finally {
    if (generation === contactGeneration) {
      contactLoading = false;
      updateContactControls();
    }
  }
}

contactUI["test-ack"].addEventListener("change", updateContactControls);
contactUI.refresh.addEventListener("click", () => void loadTrustedContact());
contactUI["invite-form"].addEventListener("submit", async event => {
  event.preventDefault();
  if (contactUI.send.disabled || !contactRecord?.can_invite || !contactNotice
      || !contactUI["invite-form"].reportValidity()) return;
  const generation = contactGeneration;
  const noticeVersion = contactNotice.notice_version;
  contactSending = true;
  updateContactControls();
  contactMessage("send-message", "Preparing your invitation...");
  try {
    const result = await contactRequest("/trusted-contact/invitations", generation, {
      notice_version: noticeVersion, test_only_acknowledged: true,
    });
    if (generation !== contactGeneration) return;
    if (result?.delivery_mode !== "local_test" || !result.invitation_id) {
      throw new Error("Capture could not be confirmed.");
    }
    contactMessage("send-message", "Invitation prepared in the local inbox. Open it, follow the invitation link, then return and refresh the status. Live email delivery is off.");
  } catch (error) {
    if (generation !== contactGeneration) return;
    contactMessage("send-message", error.status && error.status < 500
      ? error.message
      : "Could not confirm the invitation. Check Mailpit and refresh the contact status before retrying. No automatic resend occurred.", true);
  } finally {
    if (generation === contactGeneration) {
      contactSending = false;
      contactUI["test-ack"].checked = false;
      await loadTrustedContact();
    }
  }
});

// Coming back from the invitation tab refreshes status, never sends an email.
window.addEventListener("focus", () => {
  if (accessToken && location.hash === "#/trusted-contact") void loadTrustedContact();
});
