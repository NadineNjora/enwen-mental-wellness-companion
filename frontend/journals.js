"use strict";

const journalForm = document.querySelector("#journal-form");
const journalFields = document.querySelector("#journal-fields");
const journalTitle = document.querySelector("#journal-title");
const journalContent = document.querySelector("#journal-content");
const journalSave = document.querySelector("#journal-save-button");
const journalMessage = document.querySelector("#journal-message");
const journalList = document.querySelector("#journal-list");
const journalHistoryMessage = document.querySelector("#journal-history-message");
const journalRefresh = document.querySelector("#refresh-journals");
const journalReader = document.querySelector("#journal-reader");
const journalReaderTitle = document.querySelector("#journal-reader-title");
const journalReaderDate = document.querySelector("#journal-reader-date");
const journalReaderContent = document.querySelector("#journal-reader-content");
const journalSaveLabel = journalSave.textContent;
const journalLegend = journalFields.querySelector("legend");
const journalLegendLabel = journalLegend.textContent;
const journalClose = document.querySelector("#close-journal");

// Add controls without replacing your page headings or journal wording.
const journalActions = document.createElement("div");
journalActions.className = "journal-actions";
const journalEdit = document.createElement("button");
journalEdit.id = "journal-edit-button";
journalEdit.type = "button";
journalEdit.textContent = "Edit entry";
const journalDelete = document.createElement("button");
journalDelete.id = "journal-delete-button";
journalDelete.type = "button";
journalDelete.textContent = "Delete entry";
journalActions.append(journalEdit, journalDelete);
journalClose.before(journalActions);
const journalCancelEdit = document.createElement("button");
journalCancelEdit.id = "journal-cancel-edit";
journalCancelEdit.type = "button";
journalCancelEdit.textContent = "Cancel editing";
journalCancelEdit.hidden = true;
journalSave.after(journalCancelEdit);

let journalGeneration = 0;
let journalConsent = false;
let journalSaving = false;
const journalJobs = new Map();
let journalActiveEntry = null;
let journalEditingId = null;
let journalOriginalDraft = null;

function setJournalEditing(entry = null) {
  journalEditingId = entry?.journal_id || null;
  journalOriginalDraft = entry ? { title: entry.title, content: entry.content } : null;
  journalLegend.textContent = entry ? "Edit your entry" : journalLegendLabel;
  journalSave.textContent = entry ? "Save changes" : journalSaveLabel;
  journalCancelEdit.hidden = !entry;
  journalFields.setAttribute("data-editing", String(Boolean(entry)));
}

function journalDraftChanged() {
  return journalOriginalDraft
    ? journalTitle.value !== journalOriginalDraft.title || journalContent.value !== journalOriginalDraft.content
    : Boolean(journalTitle.value || journalContent.value);
}

function setJournalBusy(busy) {
  journalSaving = busy;
  journalFields.disabled = busy || !journalConsent;
  journalRefresh.disabled = busy || !journalConsent || journalJobs.has("list");
  journalEdit.disabled = busy || !journalActiveEntry || !journalConsent;
  journalDelete.disabled = busy || !journalActiveEntry || !journalConsent;
  journalClose.disabled = busy;
  for (const button of journalList.querySelectorAll("button")) button.disabled = busy;
}

function cancelJournalListForMutation() {
  cancelJournalJob("list");
  journalList.setAttribute("aria-busy", "false");
  journalStatus(journalHistoryMessage);
}

function journalStatus(element, message = "", isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function cancelJournalJob(name) {
  journalJobs.get(name)?.controller.abort();
  journalJobs.delete(name);
}

function beginJournalJob(name) {
  cancelJournalJob(name);
  const generation = journalGeneration;
  const token = accessToken;
  const job = {
    controller: new AbortController(),
    token,
    current: () => generation === journalGeneration
      && token === accessToken && Boolean(token) && journalConsent
      && journalJobs.get(name) === job,
  };
  journalJobs.set(name, job);
  return job;
}

function closeJournalReader() {
  cancelJournalJob("read");
  journalActiveEntry = null;
  journalEdit.disabled = true;
  journalDelete.disabled = true;
  journalReader.hidden = true;
  journalReader.setAttribute("aria-busy", "false");
  journalReaderTitle.textContent = "";
  journalReaderDate.textContent = "";
  journalReaderDate.removeAttribute("datetime");
  journalReaderContent.textContent = "";
}

function resetJournalPanel() {
  journalGeneration += 1;
  for (const name of [...journalJobs.keys()]) cancelJournalJob(name);
  journalConsent = false;
  journalSaving = false;
  journalClose.disabled = false;
  setJournalEditing();
  journalForm.reset();
  journalFields.disabled = true;
  journalSave.textContent = journalSaveLabel;
  journalRefresh.disabled = true;
  journalList.replaceChildren();
  journalList.setAttribute("aria-busy", "false");
  journalStatus(journalMessage);
  journalStatus(journalHistoryMessage);
  closeJournalReader();
}

function setupJournalPanel(user) {
  resetJournalPanel();
  journalConsent = user.wellness_consent_current === true;
  journalFields.disabled = !journalConsent;
  journalRefresh.disabled = !journalConsent;
  if (journalConsent) {
    void loadJournalHistory();
  } else {
    journalStatus(
      journalMessage,
      "Current wellness consent is needed to use your journal.",
      true
    );
  }
}

// A consent rejection must pause both wellness features.
function pauseWellnessFeatures() {
  resetMoodPanel();
  resetJournalPanel();
  window.enwenResources?.reset();
  window.enwenPause?.reset();
  const message =
    "Current wellness consent is needed. Please review the current notice before continuing.";
  consentStatus.textContent = message;
  journalStatus(moodMessage, message, true);
  journalStatus(historyMessage, message, true);
  journalStatus(journalMessage, message, true);
  journalStatus(journalHistoryMessage, message, true);
}

async function journalRequest(path, job, payload, method = payload === undefined ? "GET" : "POST") {
  const timeout = setTimeout(() => job.controller.abort(), 15000);
  try {
    const headers = {
      Accept: "application/json",
      Authorization: `Bearer ${job.token}`,
    };

    if (payload !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(path, {
      method,
      headers,
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: job.controller.signal,
      cache: "no-store",
    });

    if (!job.current()) return null;

    const data = response.status === 204 ? null : await response.json().catch(() => null);

    if (!job.current()) return null;

    if (response.status === 401) {
      endSession("Your session expired. Please log in again.");
      return null;
    }

    if (response.status === 403) {
      pauseWellnessFeatures();
      return null;
    }

    if (!response.ok) {
      const error = new Error(
        typeof data?.detail === "string"
          ? data.detail
          : "The request failed. Please check your details and try again."
      );
      error.status = response.status;
      throw error;
    }

    return data;
  } finally {
    clearTimeout(timeout);
  }
}

function journalDate(element, value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    element.removeAttribute("datetime");
    element.textContent = "Date unavailable";
    return;
  }

  element.dateTime = date.toISOString();
  element.textContent = date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function validJournalSummary(entry) {
  return entry && typeof entry.journal_id === "string"
    && typeof entry.title === "string"
    && typeof entry.created_at === "string";
}

function journalLoadError(error) {
  if (error.name === "AbortError") {
    return "This took too long. Please try again.";
  }

  if (error instanceof TypeError) {
    return "Cannot reach ENWEN. Check your connection and try again.";
  }

  return error.message;
}

async function loadJournalHistory() {
  if (!accessToken || !journalConsent) return;

  const job = beginJournalJob("list");
  journalRefresh.disabled = true;
  journalList.replaceChildren();
  journalList.setAttribute("aria-busy", "true");
  journalStatus(journalHistoryMessage, "Loading your entries...");

  try {
    const entries = await journalRequest(
      "/journals?limit=20&offset=0",
      job
    );

    if (!job.current()) return;

    if (!Array.isArray(entries) || !entries.every(validJournalSummary)) {
      throw new Error("Unexpected response. Please try Refresh journals.");
    }

    const fragment = document.createDocumentFragment();

    for (const entry of entries) {
      const item = document.createElement("li");
      const title = document.createElement("strong");
      const date = document.createElement("time");
      const button = document.createElement("button");

      // User-written text is displayed as text, never HTML.
      title.textContent = entry.title;
      journalDate(date, entry.created_at);

      button.type = "button";
      button.disabled = journalSaving;
      button.textContent = "Read entry";
      button.setAttribute("aria-label", "Read entry: " + entry.title);
      button.addEventListener("click", () => {
        void readJournalEntry(entry.journal_id);
      });

      item.append(title, date, button);
      fragment.append(item);
    }

    journalList.replaceChildren(fragment);

    journalStatus(
      journalHistoryMessage,
      entries.length
        ? "Showing your latest " + entries.length
          + " entries (up to 20), newest first."
        : "No entries yet. Your first saved entry will appear here."
    );
  } catch (error) {
    if (job.current()) {
      journalStatus(journalHistoryMessage, journalLoadError(error), true);
    }
  } finally {
    if (job.current()) {
      journalJobs.delete("list");
      journalList.setAttribute("aria-busy", "false");
      journalRefresh.disabled = journalSaving;
    }
  }
}

async function readJournalEntry(id) {
  if (!accessToken || !journalConsent || journalSaving) return;

  closeJournalReader();
  const job = beginJournalJob("read");

  journalReader.hidden = false;
  journalReader.setAttribute("aria-busy", "true");
  journalReaderTitle.textContent = "Opening your entry...";

  try {
    const entry = await journalRequest(
      "/journals/" + encodeURIComponent(id),
      job
    );

    if (!job.current()) return;

    if (!validJournalSummary(entry) || typeof entry.content !== "string") {
      throw new Error("Unexpected response. Please open the entry again.");
    }

    journalActiveEntry = entry;
    journalEdit.disabled = false;
    journalDelete.disabled = false;
    journalReaderTitle.textContent = entry.title;
    journalDate(journalReaderDate, entry.created_at);
    journalReaderContent.textContent = entry.content;
  } catch (error) {
    if (!job.current()) return;

    journalReaderTitle.textContent = "Could not open this entry";
    journalReaderContent.textContent = journalLoadError(error);
  } finally {
    if (job.current()) {
      journalJobs.delete("read");
      journalReader.setAttribute("aria-busy", "false");

      if (!document.querySelector("#page-journal").hidden) {
        journalReaderTitle.focus();
      }
    }
  }
}

journalForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!accessToken || !journalConsent || journalSaving) return;
  if (!journalForm.reportValidity()) return;

  const payload = {
    title: journalTitle.value.trim(),
    content: journalContent.value,
  };

  if (!payload.title || !payload.content.trim()
      || payload.title.length > 150 || payload.content.length > 10000
      || payload.title.includes("\0") || payload.content.includes("\0")) {
    journalStatus(
      journalMessage,
      "Add a title (up to 150 characters) and an entry (up to 10,000). Neither can be blank or contain null characters.",
      true
    );
    return;
  }

  const editingId = journalEditingId;
  cancelJournalListForMutation();
  if (journalJobs.has("read")) closeJournalReader();
  const job = beginJournalJob("save");
  setJournalBusy(true);
  journalSave.textContent = "Saving...";
  journalStatus(journalMessage, "Saving your entry...");

  try {
    const entry = await journalRequest(
      editingId ? "/journals/" + encodeURIComponent(editingId) : "/journals",
      job, payload, editingId ? "PUT" : "POST"
    );

    if (!job.current()) return;

    if (!validJournalSummary(entry) || typeof entry.content !== "string"
        || (editingId && entry.journal_id !== editingId)) {
      throw new Error("Could not confirm the save.");
    }

    if (editingId && journalActiveEntry?.journal_id === editingId) closeJournalReader();
    journalForm.reset();
    setJournalEditing();
    journalStatus(
      journalMessage,
      editingId ? "Changes saved. Your entry has been updated." : "Entry saved. A little space for your thoughts."
    );

    // Refresh failure must not change a successful save into a failure.
    void loadJournalHistory();
  } catch (error) {
    if (!job.current()) return;

    journalStatus(
      journalMessage,
      !error.status || error.status >= 500
        ? "We could not confirm the save. Your draft is still here. Use Refresh journals and check for this entry before trying to save again."
        : error.message,
      true
    );
  } finally {
    if (job.current()) {
      journalJobs.delete("save");
      setJournalBusy(false);
      journalSave.textContent = journalEditingId ? "Save changes" : journalSaveLabel;
    }
  }
});

journalRefresh.addEventListener("click", () => {
  if (!journalRefresh.disabled) void loadJournalHistory();
});

journalClose.addEventListener("click", () => {
  if (journalSaving) return;
  closeJournalReader();

  if (!document.querySelector("#page-journal").hidden) {
    journalRefresh.focus();
  }
});
// Editing uses the existing writing area; selecting Edit never saves anything.
journalEdit.addEventListener("click", () => {
  if (!accessToken || !journalConsent || journalSaving || !journalActiveEntry) return;
  if (journalEditingId === journalActiveEntry.journal_id) {
    journalTitle.focus();
    return;
  }
  if (journalDraftChanged() && !window.confirm("Replace the unsaved writing in the form with this entry?")) return;
  setJournalEditing(journalActiveEntry);
  journalTitle.value = journalActiveEntry.title;
  journalContent.value = journalActiveEntry.content;
  journalStatus(journalMessage, "Editing an existing entry. Choose Save changes when ready.");
  journalTitle.focus();
});

journalCancelEdit.addEventListener("click", () => {
  if (journalSaving || !journalEditingId) return;
  if (journalDraftChanged() && !window.confirm("Discard your unsaved changes to this entry?")) return;
  journalForm.reset();
  setJournalEditing();
  journalStatus(journalMessage, "Editing cancelled. The saved entry is unchanged.");
  journalTitle.focus();
});

journalDelete.addEventListener("click", async () => {
  if (!accessToken || !journalConsent || journalSaving || !journalActiveEntry) return;
  const id = journalActiveEntry.journal_id;
  const discardsDraft = journalEditingId === id;
  if (!window.confirm("Permanently delete this journal entry? This cannot be undone."
      + (discardsDraft ? " The edit currently in the form will also be cleared." : ""))) return;
  cancelJournalListForMutation();
  if (journalJobs.has("read")) closeJournalReader();
  const job = beginJournalJob("delete");
  setJournalBusy(true);
  journalStatus(journalMessage, "Deleting this entry...");
  try {
    await journalRequest("/journals/" + encodeURIComponent(id), job, undefined, "DELETE");
    if (!job.current()) return;
    closeJournalReader();
    if (discardsDraft) { journalForm.reset(); setJournalEditing(); }
    journalStatus(journalMessage, "Entry deleted.");
    void loadJournalHistory();
  } catch (error) {
    if (!job.current()) return;
    journalStatus(journalMessage, !error.status || error.status >= 500
      ? "We could not confirm the deletion. Use Refresh journals to check before trying again."
      : error.message, true);
  } finally {
    if (job.current()) {
      journalJobs.delete("delete");
      setJournalBusy(false);
    }
  }
});

// Warn before a page reload would discard writing kept only in memory.
window.addEventListener("beforeunload", event => {
  if (accessToken && (journalDraftChanged() || journalSaving)) {
    event.preventDefault();
    event.returnValue = "";
  }
});
