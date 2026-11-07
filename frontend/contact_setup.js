"use strict";

(() => {
  const el = id => document.getElementById(id);
  const panel = el("contact-setup-panel"), form = el("contact-setup-form"), fields = el("contact-setup-fields");
  const name = el("setup-contact-name"), relation = el("setup-contact-relationship"), email = el("setup-contact-email");
  const noticeText = el("contact-setup-notice"), ack = el("contact-setup-ack");
  const message = el("contact-setup-message"), retry = el("contact-setup-retry");
  let generation = 0, notice = null, loading = false, saving = false, controller = null;
  function status(text = "", error = false) { message.textContent = text; message.classList.toggle("error", error); }
  function reset() {
    generation++; controller?.abort(); controller = null;
    notice = null; loading = saving = false; panel.hidden = true;
    fields.disabled = true; form.reset(); retry.hidden = true; noticeText.textContent = ""; status();
  }
  function current(job) { return generation === job.generation && accessToken === job.token && Boolean(job.token); }
  async function request(path, job, payload) {
    const timeout = setTimeout(() => job.controller.abort(), 12000);
    try {
      const response = await fetch(path, {method: payload ? "POST" : "GET", cache: "no-store", credentials: "omit", signal: job.controller.signal,
        headers: {Accept: "application/json", Authorization: "Bearer " + job.token, ...(payload ? {"Content-Type": "application/json"} : {})},
        body: payload ? JSON.stringify(payload) : undefined});
      const data = await response.json().catch(() => null);
      if (!current(job)) return null;
      if (response.status === 401) { endSession("Your session expired. Please log in again."); return null; }
      if (!response.ok) { const error = new Error(typeof data?.detail === "string" ? data.detail : "The request could not be completed."); error.status = response.status; throw error; }
      return data;
    } finally { clearTimeout(timeout); }
  }
  function begin() { controller?.abort(); controller = new AbortController(); return {controller, token: accessToken, generation}; }
  async function show() {
    if (!accessToken || loading || saving) return;
    panel.hidden = false;
    if (notice) { fields.disabled = false; return; }
    const job = begin(); loading = true; fields.disabled = true; retry.hidden = true;
    noticeText.textContent = "Loading your privacy notice...";
    try {
      const value = await request("/auth/contact-consent", job);
      if (!current(job)) return;
      if (!value?.version || !value?.text || value.delivery_mode !== "simulation_only") throw new Error("The current contact notice is unavailable.");
      notice = value; noticeText.textContent = value.text; ack.checked = false; fields.disabled = false; status();
    } catch (error) {
      if (current(job)) { status("We could not load the current notice. Please try again.", true); retry.hidden = false; }
    } finally { if (current(job)) loading = false; }
  }
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!accessToken || saving || loading || !notice || !form.reportValidity()) return;
    if (!name.value.trim() || name.value.includes("\0") || relation.value.includes("\0")) { status("Please use a name and relationship without blank or invalid characters.", true); return; }
    const job = begin(); saving = true; fields.disabled = true; status("Saving your trusted person...");
    try {
      const saved = await request("/trusted-contact", job, {trusted_contact: {full_name: name.value.trim(), relationship_label: relation.value.trim() || null, email: email.value.trim()}, contact_consent_accepted: ack.checked, contact_consent_version: notice.version});
      if (!current(job)) return;
      if (saved?.confirmation_status !== "pending" || !saved.contact_id) throw new Error("Could not confirm the save.");
      reset(); await loadTrustedContact();
    } catch (error) {
      if (!current(job)) return;
      status(error.status && error.status < 500 ? error.message : "We could not confirm the save. Use Refresh status before trying again; your details are still here.", true);
      if (error.status === 409) { notice = null; ack.checked = false; retry.hidden = false; }
      if (error.status === 403) { notice = null; ack.checked = false; retry.hidden = true; pauseWellnessFeatures(); }
    } finally { if (current(job)) { saving = false; fields.disabled = !notice; } }
  });
  retry.addEventListener("click", () => void show());
  window.enwenContactSetup = Object.freeze({reset, show});
})();
