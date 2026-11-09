"use strict";
(() => {
  const el = id => document.getElementById(id);
  const form = el("chat-form"), fields = el("chat-fields"), input = el("chat-input");
  const thread = el("chat-messages"), message = el("chat-status"), agree = el("chat-consent");
  const historyList = el("chat-history-list"), historyMessage = el("chat-history-message");
  const previous = el("chat-history-prev"), next = el("chat-history-next"), refresh = el("chat-history-refresh");
  const newButton = el("chat-clear"), supportButton = el("chat-support"), title = el("chat-active-title");
  const managePanel = el("chat-manage"), renameButton = el("chat-rename"), deleteButton = el("chat-delete");
  const renameForm = el("chat-rename-form"), nameInput = el("chat-name"), saveName = el("chat-name-save"), cancelName = el("chat-name-cancel");
  let generation = 0, view = 0, noticeVersion = null, wellness = false, userId = null;
  let conversationId = null, conversationPaused = false, manualPaused = false, visibleCount = 0;
  let requestTimeout = 35000, pendingAttempt = null, historyOffset = 0, historyHasNext = false;
  let sending = false, reading = false, listing = false, helping = false, managing = false;
  const jobs = new Map(), renderedTurns = new Set();
  const validId = value => typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
  const status = (text = "", error = false) => { message.textContent = text; message.classList.toggle("error", error); };
  const selectionKey = id => "enwen.chat.conversation." + id;
  function storedSelection(id) {
    try { const saved = window.sessionStorage.getItem(selectionKey(id)); return validId(saved) ? saved : null; } catch { return null; }
  }
  function saveSelection() {
    if (!userId) return;
    try {
      if (conversationId) window.sessionStorage.setItem(selectionKey(userId), conversationId);
      else window.sessionStorage.removeItem(selectionKey(userId));
    } catch { /* Storage may be disabled; database history still works. */ }
  }
  function controls() {
    fields.disabled = !wellness || !noticeVersion || sending || reading || managing || conversationPaused || manualPaused || Boolean(window.enwenSafety?.active());
    newButton.disabled = !wellness || sending || reading || managing;
    refresh.disabled = !wellness || listing || managing;
    previous.disabled = !wellness || listing || managing || historyOffset === 0;
    next.disabled = !wellness || listing || managing || !historyHasNext;
    managePanel.hidden = !conversationId;
    renameButton.disabled = deleteButton.disabled = saveName.disabled = cancelName.disabled = nameInput.disabled = !wellness || !conversationId || sending || reading || managing || helping;
    supportButton.disabled = helping;
    for (const button of historyList.querySelectorAll("button")) button.disabled = !wellness || sending || reading || managing;
  }
  function begin(lane, timeout = 15000, boundToView = true) {
    jobs.get(lane)?.controller.abort();
    const controller = new AbortController(), session = generation, screen = view, token = accessToken;
    const job = {controller, token, session, screen, lane,
      current: () => session === generation && (!boundToView || screen === view) && token === accessToken && jobs.get(lane) === job};
    job.timer = setTimeout(() => controller.abort(), timeout);
    jobs.set(lane, job);
    return job;
  }
  function finish(job) { clearTimeout(job.timer); if (jobs.get(job.lane) === job) jobs.delete(job.lane); }
  function cancel(lane) { const job = jobs.get(lane); if (job) { job.controller.abort(); finish(job); } }
  function cancelView() { view++; cancel("send"); cancel("conversation"); cancel("support"); sending = reading = helping = false; }
  function reset() {
    generation++; view++;
    for (const job of jobs.values()) { job.controller.abort(); clearTimeout(job.timer); }
    jobs.clear();
    conversationId = null; saveSelection(); userId = null;
    conversationPaused = manualPaused = wellness = sending = reading = listing = helping = managing = false;
    visibleCount = historyOffset = 0; historyHasNext = false; noticeVersion = null; pendingAttempt = null;
    renderedTurns.clear(); form.reset(); agree.checked = false; thread.replaceChildren(); historyList.replaceChildren();
    el("chat-notice").textContent = ""; el("chat-consent-label").textContent = "Read the AI processing notice before sending.";
    title.textContent = "A new conversation"; historyMessage.textContent = ""; status("");
    renameForm.hidden = true; nameInput.value = "";
    window.enwenSafety?.reset(); controls();
  }
  async function request(path, job, options = {}) {
    const response = await fetch(path, {method: options.method || "GET", cache: "no-store", signal: job.controller.signal,
      headers: {Accept: "application/json", Authorization: "Bearer " + job.token, ...(options.body === undefined ? {} : {"Content-Type": "application/json"})},
      body: options.body === undefined ? undefined : JSON.stringify(options.body)});
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!job.current()) return null;
    if (response.status === 401) { endSession("Your session expired. Please log in again."); return null; }
    if (!response.ok) {
      const error = new Error(typeof data?.detail === "string" ? data.detail : "The conversation request could not be completed.");
      error.status = response.status; throw error;
    }
    if (options.expectedStatus && response.status !== options.expectedStatus) throw new Error("The requested change could not be confirmed. Refresh history before trying again.");
    return data;
  }
  function blockForConsent() {
    reset(); status("Current wellness consent is required before viewing or saving conversations.", true);
  }
  async function setup(user) {
    const restore = validId(String(user.user_id || "")) ? storedSelection(String(user.user_id)) : null;
    reset();
    userId = String(user.user_id || ""); wellness = user.wellness_consent_current === true;
    if (!wellness) { status("Current wellness consent is required before using private chat history.", true); controls(); return; }
    const job = begin("notice", 15000, false);
    try {
      const notice = await request("/chat/notice", job);
      if (!notice || !job.current()) return;
      noticeVersion = notice.notice_version;
      requestTimeout = notice.local === true ? 150000 : 35000;
      el("chat-notice").textContent = notice.notice_text;
      el("chat-consent-label").textContent = notice.consent_label;
      status(notice.configured ? (notice.local ? "Nia is ready when you are." : "Ready when you are. Read the processing notice.")
        : "AI replies are not connected yet. Human-support options remain available.");
      controls();
      await loadHistory();
      if (restore && job.current()) await openConversation(restore, {confirmDraft: false, restoring: true});
    } catch (error) {
      if (job.current()) {
        if (error.status === 403) blockForConsent();
        else status(error.message, true);
      }
    } finally { finish(job); controls(); }
  }
  function safeHttps(value) {
    try { const url = new URL(value); return url.protocol === "https:" && !url.username && !url.password ? url.href : null; } catch { return null; }
  }
  function sources(rows) {
    if (!Array.isArray(rows) || !rows.length) return;
    const row = document.createElement("li"), heading = document.createElement("strong");
    row.className = "chat-sources"; heading.textContent = "Resource summaries supplied to the AI"; row.append(heading);
    rows.slice(0, 10).forEach((source, i) => {
      if (!source || typeof source.title !== "string" || typeof source.publisher !== "string") return;
      const url = safeHttps(source.url); if (!url) return;
      const link = document.createElement("a"); link.textContent = "[" + (i + 1) + "] " + source.title + " · " + source.publisher;
      link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; row.append(link);
    });
    if (row.children.length > 1) thread.append(row);
  }
  function bubble(role, content, state, safety) {
    const row = document.createElement("li"), name = document.createElement("strong"), body = document.createElement("p");
    name.textContent = role === "user" ? "You" : safety?.level === "urgent" ? "ENWEN · Human support" : "Nia 🌼";
    body.textContent = safety?.level === 'urgent' ? 'Let’s bring in human support. Your options are below.' : content; row.className = "chat-bubble " + role; row.append(name, body);
    if (role === "user" && (state === "pending" || state === "failed")) {
      const note = document.createElement("small");
      note.className = "chat-turn-state";
      note.textContent = state === "pending" ? "A reply was still pending when this history was loaded. Refresh before retrying."
        : "This attempt did not receive a saved AI reply. Nothing was automatically retried.";
      row.append(note);
    }
    thread.append(row); visibleCount++;
  }
  async function loadHistory(offset = historyOffset) {
    if (!wellness || !accessToken) return;
    const job = begin("history", 15000, false);
    listing = true; historyMessage.textContent = "Loading your private conversations..."; controls();
    try {
      const rows = await request("/chat/conversations?limit=20&offset=" + offset, job);
      if (!rows || !job.current()) return;
      if (!Array.isArray(rows)) throw new Error("Conversation history could not be read.");
      const fragment = document.createDocumentFragment();
      for (const item of rows) {
        const id = item.conversation_id || item.id;
        if (!validId(id) || typeof item.title !== "string") throw new Error("Conversation history contained an invalid entry.");
        const li = document.createElement("li"), button = document.createElement("button"), name = document.createElement("strong"), date = document.createElement("small");
        button.type = "button"; name.textContent = item.title;
        const parsed = new Date(item.updated_at);
        date.textContent = (item.safety_paused ? "Paused for human support · " : "")
          + (Number.isNaN(parsed.getTime()) ? "Date unavailable" : parsed.toLocaleString(undefined, {dateStyle:"medium", timeStyle:"short", timeZone:"Africa/Nairobi"}));
        button.append(name, date); button.setAttribute("data-chat-conversation", id); button.setAttribute("aria-current", id === conversationId ? "true" : "false");
        button.addEventListener("click", () => void openConversation(id));
        li.append(button); fragment.append(li);
      }
      historyList.replaceChildren(fragment); historyOffset = offset; historyHasNext = rows.length === 20;
      historyMessage.textContent = rows.length ? "Showing conversations " + (offset + 1) + "–" + (offset + rows.length) + ". Your saved conversations stay private to your account."
        : offset ? "No older conversations on this page. Choose Newer to go back." : "No saved conversations yet. Your first acknowledged message begins one.";
    } catch (error) {
      if (job.current()) {
        if (error.status === 403) blockForConsent();
        else { historyList.replaceChildren(); historyMessage.textContent = error.message; }
      }
    } finally { if (job.session === generation && jobs.get("history") === job) listing = false; finish(job); controls(); }
  }
  async function openConversation(id, {confirmDraft = true, restoring = false} = {}) {
    if (!wellness || !validId(id) || sending || reading || managing) return;
    if (confirmDraft && input.value.trim() && !window.confirm("Switch conversations and discard the unsaved draft? Saved messages will stay in history.")) return;
    cancelView(); const job = begin("conversation", 30000); reading = true; controls();
    status("Loading this private conversation...");
    try {
      let offset = 0, summary = null, previousBoundary = null; const messages = [], seen = new Set();
      while (true) {
        const data = await request("/chat/conversations/" + encodeURIComponent(id) + "?limit=100&offset=" + offset, job);
        if (!data || !job.current()) return;
        if (!Array.isArray(data.messages) || (data.conversation_id || data.id) !== id) throw new Error("This conversation could not be read.");
        if (!summary) summary = data;
        for (const item of data.messages) {
          if (!["user","assistant"].includes(item.role) || typeof item.content !== "string") throw new Error("A saved message could not be read.");
          const key = item.message_id || (item.turn_id ? item.turn_id + "-" + item.role : null);
          if (key && seen.has(key)) continue;
          if (key) seen.add(key);
          messages.push(item);
        }
        if (!data.has_more) break;
        if (!Number.isInteger(data.turn_count) || data.turn_count < 1) throw new Error("Conversation pages did not advance.");
        const boundary = JSON.stringify([data.messages[0]?.turn_id, data.messages.at(-1)?.turn_id, data.messages.length]);
        if (boundary === previousBoundary) throw new Error("Conversation pages repeated. Please try Refresh history.");
        previousBoundary = boundary;
        offset += data.turn_count;
      }
      if (!job.current()) return;
      conversationId = id; saveSelection(); input.value = ""; pendingAttempt = null;
      renameForm.hidden = true; nameInput.value = "";
      thread.replaceChildren(); renderedTurns.clear(); visibleCount = 0;
      let intervention = null;
      for (const item of messages) {
        bubble(item.role, item.content, item.status, item.safety);
        if (item.role === "assistant") sources(item.sources);
        if (item.turn_id) renderedTurns.add(item.turn_id);
        if (item.safety?.level === "urgent") intervention = item.safety;
      }
      conversationPaused = summary.safety_paused === true || Boolean(intervention);
      title.textContent = summary.title || "Your saved conversation";
      if (intervention) window.enwenSafety?.show(intervention);
      else if (conversationPaused) {
        window.enwenSafety?.show({level:"urgent", event_id:id, message:"This saved conversation is paused for human support.",
          resources:[], alert:{status:"uncertain",message:"The saved contact-alert outcome could not be loaded. Do not wait for a notification before contacting someone directly."}});
      } else if (!manualPaused) window.enwenSafety?.reset();
      status(conversationPaused ? "This conversation is paused for human support. Start a new conversation when you choose to return to ordinary AI."
        : manualPaused ? "Human-support mode is open. Choose New conversation to return to ordinary AI."
        : "Saved conversation loaded. Read the current processing notice before continuing.");
      for (const button of historyList.querySelectorAll("button")) button.setAttribute("aria-current", button.getAttribute("data-chat-conversation") === id ? "true" : "false");
    } catch (error) {
      if (job.current()) {
        if (error.status === 403) blockForConsent();
        else if (error.status === 404 && restoring) {
          conversationId = null; saveSelection(); title.textContent = "A new conversation";
          status("That saved conversation is unavailable. You can start a new one.");
        } else status(error.message, true);
      }
    } finally { if (job.session === generation && jobs.get("conversation") === job) reading = false; finish(job); controls(); }
  }
  function requestId(text) {
    if (pendingAttempt && pendingAttempt.text === text && pendingAttempt.conversationId === conversationId) return pendingAttempt.requestId;
    if (typeof window.crypto?.randomUUID !== "function") throw new Error("A secure message identifier could not be created. Use ENWEN at localhost in a current browser.");
    pendingAttempt = {text, conversationId, requestId:window.crypto.randomUUID()};
    return pendingAttempt.requestId;
  }
  renameButton.addEventListener("click", () => {
    if (renameButton.disabled) return;
    nameInput.value = title.textContent;
    renameForm.hidden = false;
    nameInput.focus();
  });
  cancelName.addEventListener("click", () => {
    if (cancelName.disabled) return;
    renameForm.hidden = true; nameInput.value = ""; renameButton.focus();
  });
  renameForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (saveName.disabled) return;
    const name = nameInput.value.replace(/\s+/g, " ").trim();
    if (!name || name.length > 80) { status("Choose a conversation name between 1 and 80 characters.", true); return; }
    const id = conversationId, job = begin("manage", 15000, false);
    cancel("history"); listing = false; managing = true; controls(); status("Saving this conversation's name...");
    try {
      const data = await request("/chat/conversations/" + encodeURIComponent(id), job, {method:"PATCH", body:{title:name}});
      if (!job.current()) return;
      if (data?.conversation_id !== id || typeof data.title !== "string") throw new Error("The updated name could not be confirmed. Refresh history before trying again.");
      title.textContent = data.title; renameForm.hidden = true; nameInput.value = "";
      status("Conversation renamed. Your saved messages and unsaved draft are unchanged.");
      await loadHistory();
    } catch (error) {
      if (job.current()) status(["AbortError", "TypeError"].includes(error.name)
        ? "The name change could not be confirmed. Refresh history before trying again; nothing was automatically retried." : error.message, true);
    } finally {
      if (job.session === generation && jobs.get("manage") === job) managing = false;
      finish(job); controls();
    }
  });
  deleteButton.addEventListener("click", async () => {
    if (deleteButton.disabled) return;
    if (!window.confirm("Delete this saved conversation and all of its messages from ENWEN's active database? This cannot be undone here. Your unsaved draft will be kept. Separate notification records and minimal request identifiers remain; backups are not erased.")) return;
    const id = conversationId, job = begin("manage", 15000, false);
    cancel("history"); listing = false; managing = true; controls(); status("Removing this saved conversation...");
    try {
      await request("/chat/conversations/" + encodeURIComponent(id), job, {method:"DELETE", expectedStatus:204});
      if (!job.current()) return;
      // A missing record is also harmless on a manual retry after an uncertain
      // deletion. Never resend messages or claim notifications were withdrawn.
      releaseDeletedConversation();
      await loadHistory(0);
    } catch (error) {
      if (job.current()) {
        if (error.status === 404) { releaseDeletedConversation(); await loadHistory(0); }
        else status(["AbortError", "TypeError"].includes(error.name)
          ? "Deletion could not be confirmed. Your draft and this screen are kept. Refresh history before trying again; no automatic retry was made." : error.message, true);
      }
    } finally {
      if (job.session === generation && jobs.get("manage") === job) managing = false;
      finish(job); controls();
    }
  });
  function releaseDeletedConversation() {
    // Removing history does not establish that somebody is safe. Keep any
    // already-visible support mode open until New conversation is chosen.
    manualPaused = manualPaused || conversationPaused || Boolean(window.enwenSafety?.active());
    conversationId = null; saveSelection(); pendingAttempt = null; conversationPaused = false;
    thread.replaceChildren(); renderedTurns.clear(); visibleCount = 0;
    title.textContent = "A new conversation"; renameForm.hidden = true; nameInput.value = "";
    status(manualPaused ? "Saved messages removed. Human-support options stay open. Choose New conversation to return to ordinary AI."
      : "Saved conversation removed. Your unsaved draft is kept; sending it would start a new conversation.");
  }
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!wellness || !accessToken || !noticeVersion || sending || reading || managing || conversationPaused || manualPaused || window.enwenSafety?.active()) return;
    const text = input.value.trim(); if (!text) return;
    if (text.length > 2000) { status("Please keep this message within 2,000 characters.", true); return; }
    let id;
    try { id = requestId(text); } catch(error) { status(error.message, true); return; }
    const acknowledged = agree.checked === true, job = begin("send", requestTimeout);
    let urgentSupport = null;
    sending = true; controls(); status("Nia is finding a little room for your thoughts…");
    try {
      // Show support before waiting for persistence or email transport.
      // The chat endpoint repeats the same server-side screen authoritatively.
      try {
        const screening = await request("/chat/screen", job, {method:"POST", body:{message:text}});
        if (!job.current()) return;
        if (screening?.urgent && screening.support?.level === "urgent") {
          urgentSupport = screening.support;
          conversationPaused = true;
          window.enwenSafety?.show(screening.support);
          status("Let’s bring in human support. Checking your contact request…");
        }
      } catch (screenError) {
        if (!job.current()) return;
        // /chat also screens before any model call; never substitute an AI reply here.
        if (screenError.status === 401) return;
      }
      const data = await request("/chat", job, {method:"POST", body:{messages:[{role:"user",content:text}], request_id:id,
        conversation_id:conversationId, external_ai_consent:acknowledged, notice_version:noticeVersion}});
      if (!data || !job.current()) return;
      if (typeof data.reply !== "string") throw new Error("The reply could not be read. Review history before retrying.");
      if (validId(data.conversation_id)) { conversationId = data.conversation_id; saveSelection(); }
      if (!data.turn_id || !renderedTurns.has(data.turn_id)) {
        bubble("user", text);
        bubble("assistant", data.reply, undefined, data.safety);
        sources(data.sources);
        if (data.turn_id) renderedTurns.add(data.turn_id);
      }
      input.value = ""; pendingAttempt = null;
      if (title.textContent === "A new conversation") title.textContent = text.replace(/\s+/g, " ").slice(0,80);
      if (data.safety?.level === "urgent") {
        conversationPaused = true; window.enwenSafety?.show(data.safety);
        status(data.history_saved === true ? "The conversation is paused. Your support response is saved in your private history."
          : "The conversation is paused. Help is shown, but this event was not saved to chat history.");
      } else status(data.history_saved === true ? "Reply saved to your private chat history."
        : "Reply received. Saving this response to history was not confirmed; refresh history before retrying.");
      void loadHistory(0);
    } catch (error) {
      if (job.current()) {
        if (urgentSupport) window.enwenSafety?.show({...urgentSupport,alert:{status:'uncertain',message:'The contact request could not be confirmed. Please reach a person directly.'}});
        if (error.status === 403 && acknowledged) blockForConsent();
        else {
          if (error.status === 409) agree.checked = false;
          status(error.name === "AbortError" || error instanceof TypeError
            ? "We could not confirm the reply. Your draft is kept. Refresh chat history before retrying; no automatic retry was made."
            : error.message, true);
        }
      }
    } finally { if (job.session === generation && jobs.get("send") === job) sending = false; finish(job); controls(); }
  });
  newButton.addEventListener("click", () => {
    if (!wellness || sending || reading || managing) return;
    if (input.value.trim() && !window.confirm("Start a new conversation and discard this unsaved draft? Saved history is kept.")) return;
    cancelView(); conversationId = null; saveSelection(); pendingAttempt = null;
    conversationPaused = manualPaused = false; visibleCount = 0; renderedTurns.clear();
    input.value = ""; thread.replaceChildren(); title.textContent = "A new conversation";
    renameForm.hidden = true; nameInput.value = "";
    window.enwenSafety?.reset(); status("A fresh conversation. Earlier saved messages are still in history."); controls();
  });
  supportButton.addEventListener("click", async () => {
    if (helping) return;
    cancelView(); manualPaused = true; helping = true; controls();
    const job = begin("support", 10000);
    try {
      const response = await fetch("/safety/support", {cache:"no-store",signal:job.controller.signal,headers:{Accept:"application/json"}});
      const data = await response.json().catch(()=>null);
      if (!job.current()) return;
      if (!response.ok || data?.level !== "urgent") throw new Error("Support contacts could not be loaded.");
      window.enwenSafety?.show(data); status("Human-support options are open. No alert was requested by this button.");
    } catch(error) {
      if (job.current()) {
        window.enwenSafety?.show({level:"urgent",message:"The AI conversation is paused. Please seek human support nearby if you need help now.",
          resources:[],alert:{status:"not_requested",message:"No notification was requested. Support contact details could not be loaded."}});
        status("Support contacts could not be loaded. No alert was requested.",true);
      }
    } finally { if(job.session===generation && jobs.get("support")===job) helping=false; finish(job); controls(); }
  });
  previous.addEventListener("click", () => { if (!previous.disabled) void loadHistory(Math.max(0, historyOffset-20)); });
  next.addEventListener("click", () => { if (!next.disabled) void loadHistory(historyOffset+20); });
  refresh.addEventListener("click", () => { if (!refresh.disabled) void loadHistory(); });
  window.enwenChat = {setup, reset, loadHistory, openConversation};
  controls();
})();
