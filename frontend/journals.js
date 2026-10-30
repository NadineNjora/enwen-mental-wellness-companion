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

let journalGeneration = 0;
let journalConsent = false;
let journalSaving = false;
const journalJobs = new Map();

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
  const message =
    "Current wellness consent is needed. Please review the current notice before continuing.";
  consentStatus.textContent = message;
  journalStatus(moodMessage, message, true);
  journalStatus(historyMessage, message, true);
  journalStatus(journalMessage, message, true);
  journalStatus(journalHistoryMessage, message, true);
}

async function journalRequest(path, job, payload) {
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
      method: payload === undefined ? "GET" : "POST",
      headers,
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: job.controller.signal,
      cache: "no-store",
    });

    if (!job.current()) return null;

    const data = await response.json().catch(() => null);

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
      journalRefresh.disabled = false;
    }
  }
}

async function readJournalEntry(id) {
  if (!accessToken || !journalConsent) return;

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

  const job = beginJournalJob("save");
  journalSaving = true;
  journalFields.disabled = true;
  journalSave.textContent = "Saving...";
  journalStatus(journalMessage, "Saving your entry...");

  try {
    const entry = await journalRequest("/journals", job, payload);

    if (!job.current()) return;

    if (!validJournalSummary(entry) || typeof entry.content !== "string") {
      throw new Error("Could not confirm the save.");
    }

    journalForm.reset();
    journalStatus(
      journalMessage,
      "Entry saved. A little space for your thoughts."
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
      journalSaving = false;
      journalFields.disabled = false;
      journalSave.textContent = journalSaveLabel;
    }
  }
});

journalRefresh.addEventListener("click", () => {
  if (!journalRefresh.disabled) void loadJournalHistory();
});

document.querySelector("#close-journal").addEventListener("click", () => {
  closeJournalReader();

  if (!document.querySelector("#page-journal").hidden) {
    journalRefresh.focus();
  }
});