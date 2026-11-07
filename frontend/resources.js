"use strict";

(() => {
  const byId = id => document.getElementById(id);
  const form = byId("resources-filter-form"), fields = byId("resources-fields");
  const search = byId("resources-search"), category = byId("resources-category");
  const savedOnly = byId("resources-saved-only"), refresh = byId("resources-refresh");
  const list = byId("resources-list"), message = byId("resources-message");
  const categories = { stress: "🌿 Stress & grounding", studies: "📚 Studies & deadlines", rest: "🌙 Rest & sleep", connection: "🫶 Connection", "human-support": "🤝 Human support" };
  const publishers = new Set(["www.who.int", "www.nhs.uk", "studentlife.uonbi.ac.ke", "sumc.strathmore.edu", "www.daystar.ac.ke", "www.kindredcollectivetherapy.com", "www.facebook.com", "counselling.usiu.ac.ke", "counseling.mku.ac.ke", "www.nhsinform.scot"]);
  let generation = 0, requestNumber = 0, consent = false, loading = false, saving = false;
  let rows = [], controller = null;

  function status(text = "", error = false) {
    message.textContent = text;
    message.classList.toggle("error", error);
  }
  function controls() {
    fields.disabled = !consent || loading || saving;
    for (const button of list.querySelectorAll("button")) button.disabled = !consent || saving || loading;
  }
  function reset() {
    generation++;
    requestNumber++;
    controller?.abort();
    controller = null;
    consent = loading = saving = false;
    rows = [];
    form.reset();
    list.replaceChildren();
    list.setAttribute("aria-busy", "false");
    status();
    controls();
  }
  function setup(user) {
    reset();
    consent = user.wellness_consent_current === true;
    if (!consent) status("Current wellness consent is needed to use the library.", true);
    controls();
  }
  function validResource(row) {
    try {
      const url = new URL(row.url);
      return url.protocol === "https:" && publishers.has(url.hostname) && !url.username && !url.password
        && typeof row.resource_id === "string" && typeof row.title === "string"
        && typeof row.summary === "string" && typeof row.publisher === "string"
        && typeof row.audience_note === "string" && typeof row.saved === "boolean"
        && Object.hasOwn(categories, row.category);
    } catch { return false; }
  }
  function current(job) {
    return generation === job.generation && requestNumber === job.number
      && Boolean(job.token) && accessToken === job.token && consent;
  }
  async function request(path, method, job) {
    const timeout = setTimeout(() => job.controller.abort(), 15000);
    try {
      const response = await fetch(path, { method, cache: "no-store", signal: job.controller.signal,
        headers: { Accept: "application/json", Authorization: `Bearer ${job.token}` } });
      if (!current(job)) return null;
      const data = response.status === 204 ? null : await response.json().catch(() => null);
      if (!current(job)) return null;
      if (response.status === 401) { endSession("Your session expired. Please log in again."); return null; }
      if (response.status === 403) { pauseWellnessFeatures(); return null; }
      if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "The library could not complete this request.");
      return data;
    } finally { clearTimeout(timeout); }
  }
  function begin() {
    controller?.abort();
    controller = new AbortController();
    return { generation, number: ++requestNumber, token: accessToken, controller };
  }
  function render() {
    const fragment = document.createDocumentFragment();
    for (const row of rows.filter(item => !savedOnly.checked || item.saved)) {
      const card = document.createElement("article");
      card.className = "resource-card";
      card.dataset.category = row.category;
      const topic = document.createElement("p"); topic.className = "resource-topic"; topic.textContent = categories[row.category];
      const title = document.createElement("h3"); title.textContent = row.title;
      const publisher = document.createElement("p"); publisher.className = "resource-publisher"; publisher.textContent = row.publisher;
      const summary = document.createElement("p"); summary.textContent = row.summary;
      const note = document.createElement("p"); note.className = "resource-audience"; note.textContent = row.audience_note;
      const actions = document.createElement("div"); actions.className = "resource-actions";
      const link = document.createElement("a"); link.href = row.url; link.target = "_blank"; link.rel = "noopener noreferrer";
      link.referrerPolicy = "no-referrer"; link.textContent = "Read at the source ↗";
      link.setAttribute("aria-label", `Read ${row.title} at ${row.publisher} (opens a new tab)`);
      const bookmark = document.createElement("button"); bookmark.type = "button";
      bookmark.dataset.resourceId = row.resource_id;
      bookmark.textContent = row.saved ? "Saved ✓" : "Save for later ♡";
      bookmark.setAttribute("aria-pressed", String(row.saved));
      bookmark.setAttribute("aria-label", `${row.saved ? "Unsave" : "Save"} ${row.title}`);
      bookmark.addEventListener("click", () => void toggle(row));
      actions.append(link, bookmark);
      card.append(topic, title, publisher, summary, note, actions);
      fragment.append(card);
    }
    list.replaceChildren(fragment);
    controls();
  }
  async function load() {
    if (!accessToken || !consent || saving) return;
    const job = begin();
    loading = true;
    rows = [];
    list.replaceChildren();
    list.setAttribute("aria-busy", "true");
    controls(); status("Finding something for you...");
    const query = new URLSearchParams();
    if (search.value.trim()) query.set("q", search.value.trim());
    if (category.value) query.set("category", category.value);
    if (savedOnly.checked) query.set("saved_only", "true");
    try {
      const data = await request("/resources?" + query, "GET", job);
      if (!current(job)) return;
      if (!Array.isArray(data) || !data.every(validResource)) throw new Error("Unexpected resource response. Please try Refresh.");
      rows = data;
      render();
      status(data.length ? `${data.length} resource${data.length === 1 ? "" : "s"} to explore.`
        : savedOnly.checked ? "No saved resources match these filters. Try All topics or save a reading first."
        : "Nothing matches yet. Try another topic or a shorter search.");
    } catch (error) {
      if (current(job)) status(error.name === "AbortError" ? "The library took too long. Try Refresh."
        : error instanceof TypeError ? "Cannot reach ENWEN. Check your connection and try Refresh." : error.message, true);
    } finally {
      if (current(job)) { loading = false; controller = null; list.setAttribute("aria-busy", "false"); controls(); }
    }
  }
  async function toggle(row) {
    if (!accessToken || !consent || loading || saving) return;
    const job = begin();
    saving = true; controls();
    status(row.saved ? "Removing this saved link..." : "Saving this link...");
    try {
      await request(`/resources/${encodeURIComponent(row.resource_id)}/bookmark`, row.saved ? "DELETE" : "PUT", job);
      if (!current(job)) return;
      row.saved = !row.saved;
      render();
      status(row.saved ? "Saved to your account. Find it using Saved by me."
        : "Removed from your saved links. You can save it again whenever you like.");
    } catch (error) {
      if (current(job)) status("We could not confirm the change. Refresh the library before trying again.", true);
    } finally {
      if (current(job)) {
        saving = false; controller = null; controls();
        const next = [...list.querySelectorAll("button")].find(button => button.dataset.resourceId === row.resource_id);
        (next || savedOnly).focus();
      }
    }
  }
  form.addEventListener("submit", event => { event.preventDefault(); if (form.reportValidity()) void load(); });
  refresh.addEventListener("click", () => { if (!refresh.disabled) void load(); });
  category.addEventListener("change", () => void load());
  savedOnly.addEventListener("change", () => void load());
  window.enwenResources = Object.freeze({ setup, reset, load });
})();
