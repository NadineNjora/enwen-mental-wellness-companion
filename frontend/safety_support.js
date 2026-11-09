"use strict";

(() => {
  // The backend makes the screening decision. This module only presents the
  // intervention and reported delivery outcome; it never sends an alert.
  let panel = null, isActive = false, lastEvent = null;
  const statusLabels = {
    provider_accepted: "A check-in email is on its way to your trusted person",
    blocked_demo: "Fictional demonstration; no real person notified",
    local_test_captured: "Local demonstration email captured",
    blocked_no_contact: "No trusted contact is saved",
    blocked_unconfirmed: "Trusted contact has not agreed",
    blocked_consent: "Notification permission is not recorded",
    blocked_live_not_configured: "Real contact alerts are not connected",
    blocked_cooldown: "No duplicate notification sent",
    not_requested: "No contact notification requested",
    queued: "Submitted to the message provider",
    sent: "Submitted to the message provider",
    delivered: "Delivery confirmed",
    failed: "The alert could not be sent",
    uncertain: "Delivery is not confirmed",
    pending: "Checking your contact request",
    not_configured: "Messaging is not connected",
    no_contact: "No trusted contact is saved",
    not_eligible: "The trusted contact is not ready for alerts",
    blocked: "No alert sent",
    suppressed: "No additional alert sent",
    duplicate: "No duplicate alert sent",
    not_sent: "No alert sent",
    disabled: "Live alerts are disabled",
    not_requested: "No contact alert requested",
    blocked_consent: "No contact alert sent",
    blocked_no_contact: "No trusted contact is saved",
    blocked_unconfirmed: "The trusted contact has not confirmed",
    blocked_live_not_configured: "Live contact alerts are not connected",
    blocked_cooldown: "No duplicate contact alert sent",
    local_test_captured: "Test notification captured in the local inbox",
  };

  function text(value, fallback, limit = 2000) {
    return typeof value === "string" && value.trim()
      ? value.trim().slice(0, limit)
      : fallback;
  }

  function make(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = value;
    return node;
  }

  function safePhone(value) {
    if (typeof value !== "string" || value.length > 50 || !/^[+\d ()-]+$/.test(value)) return null;
    const compact = value.replace(/[ ()-]/g, "");
    return /^(?:\+\d{7,15}|\d{3,15})$/.test(compact) ? compact : null;
  }

  function safeUrl(value) {
    if (typeof value !== "string" || value.length > 1500) return null;
    try {
      const url = new URL(value);
      return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
    } catch { return null; }
  }

  function safePhoneUrl(value, phone) {
    if (!phone) return null;
    if (value === undefined || value === null) return "tel:" + phone;
    if (typeof value !== "string" || value.length > 150) return null;
    // Retain the connector's attribution query exactly, while disallowing
    // arbitrary dial modifiers, recipients, query parameters, or URI schemes.
    const match = /^tel:(\+?\d{3,15})(?:\?oai_link_source=model_response_hotline)?$/.exec(value);
    return match && match[1] === phone ? value : null;
  }

  function mount() {
    if (panel) return panel;
    const page = document.getElementById("page-chat"), form = document.getElementById("chat-form");
    if (!page || !form) return null;
    panel = make("section", "safety-support");
    panel.id = "chat-safety-support";
    panel.setAttribute("aria-labelledby", "chat-safety-heading");
    panel.hidden = true;
    form.before(panel);
    return panel;
  }

  function show(data) {
    if (!data || data.level !== "urgent") return false;
    const target = mount();
    if (!target) return false;
    isActive = true;
    const fields = document.getElementById("chat-fields");
    if (fields) fields.disabled = true;
    const composer = document.getElementById("chat-form");
    if (composer) composer.hidden = true;

    const event = typeof data.event_id === "string" ? data.event_id : null;
    const focusNewEvent = target.hidden || !event || event !== lastEvent;
    const eyebrow = make("p", "safety-support-eyebrow", "A real person, a little closer");
    const heading = make("h3", "safety-support-heading", "Let's bring in human support.");
    heading.id = "chat-safety-heading";
    heading.setAttribute("tabindex", "-1");
    const description = make("p", "safety-support-message", text(data.message,
      "The AI conversation is paused. Please connect with someone who can support you now.").replace('If this describes your safety right now, ',''));
    const pauseNote = make("p", "safety-support-pause", "Ordinary AI replies are paused for this conversation.");
    const resources = make("ul", "safety-support-resources");
    let resourceCount = 0;
    for (const resource of (Array.isArray(data.resources) ? data.resources.slice(0, 6) : [])) {
      if (!resource || typeof resource !== "object") continue;
      const phone = safePhone(resource.phone), callUrl = safePhoneUrl(resource.phone_url, phone), url = safeUrl(resource.url);
      if (!callUrl && !url) continue;
      const name = text(resource.name, "Support service", 120);
      const item = make("li", "safety-support-resource");
      item.append(make("strong", "", name));
      if (callUrl) {
        const call = make("a", "safety-support-call", "Call " + text(resource.phone, phone, 50));
        call.href = callUrl;
        call.setAttribute("aria-label", "Call " + name + ": " + phone);
        item.append(call);
      }
      if (url) {
        const source = make("a", "safety-support-source", "Visit the service website");
        source.href = url;
        source.target = "_blank";
        source.rel = "noopener noreferrer";
        item.append(source);
      }
      if (typeof resource.detail === "string" && resource.detail.trim()) {
        item.append(make("p", "safety-support-detail", resource.detail.trim().slice(0, 500)));
      }
      if (typeof resource.source_checked_on === "string" && /^\d{4}-\d{2}-\d{2}$/.test(resource.source_checked_on)) {
        item.append(make("small", "safety-support-checked", "Contact details checked " + resource.source_checked_on));
      }
      resources.append(item);
      resourceCount++;
    }
    if (!resourceCount) resources.append(make("li", "", "Support contacts could not be loaded. Use your local emergency service or seek help from someone nearby."));

    const alertBox = make("section", "safety-support-delivery");
    alertBox.setAttribute("aria-label", "Trusted-contact alert status");
    alertBox.append(make("h4", "", "Your trusted-contact alert"));
    const delivery = make("p", "safety-support-delivery-status");
    delivery.setAttribute("role", "status");
    const alert = data.alert && typeof data.alert === "object" ? data.alert : {};
    const label = statusLabels[alert.status] || "Delivery is not confirmed";
    delivery.textContent = alert.status === "provider_accepted"
      ? "A check-in email has been submitted for your trusted person. Please reach out directly too; they may not have seen it yet."
      : label + ". " + text(alert.message,"Please reach out to a person directly too.",1200);
    const shortStatus={
      blocked_consent:'No email was sent because required permission is missing. You can reach out to your person directly.',
      blocked_unconfirmed:'No email was sent because the invitation has not been accepted. Please reach out to someone directly.',
      blocked_demo:'This fictional test did not contact a person.',
      blocked_cooldown:'A recent request is already recorded. No additional email was sent.',
      disabled:'Email sending is unavailable. Please reach out to someone directly.',
      uncertain:'We could not confirm the email send. Please reach out to someone directly.',
      pending:'Checking your contact permission. You can reach human support now.',
      not_requested:'No contact email was requested from this view.'
    };
    if(shortStatus[alert.status])delivery.textContent=shortStatus[alert.status];
    alertBox.append(delivery);

    const links = make("nav", "safety-support-actions");
    links.setAttribute("aria-label", "Human support and grounding options");
    for (const [name, href] of [["View your trusted contact", "#/trusted-contact"],
      ["Find human support", "#/resources"], ["Take a mindful pause", "#/pause"]]) {
      const link = make("a", "", name);
      link.href = href;
      links.append(link);
    }
    target.replaceChildren(eyebrow, heading, description, pauseNote, resources, alertBox, links);
    target.hidden = false;
    lastEvent = event;
    if (focusNewEvent) heading.focus({preventScroll: false});
    return true;
  }

  function reset() {
    isActive = false;
    const composer = document.getElementById("chat-form");
    if (composer) composer.hidden = false;
    lastEvent = null;
    if (panel) { panel.hidden = true; panel.replaceChildren(); }
    // Never re-enable a composer here: the chat controller owns consent,
    // request state, and the backend's conversation lock.
  }

  window.enwenSafety = {show, reset, active: () => isActive};
})();
