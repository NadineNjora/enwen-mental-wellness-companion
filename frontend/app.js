"use strict";

// Login and account elements.
const loginForm = document.querySelector("#login-form");
const loginPanel = document.querySelector("#login-panel");
const accountPanel = document.querySelector("#account-panel");
const loginButton = document.querySelector("#login-button");
const statusMessage = document.querySelector("#status");
const emailInput = document.querySelector("#email");
const passwordInput = document.querySelector("#password");
const welcomeTitle = document.querySelector("#welcome-title");
const accountEmail = document.querySelector("#account-email");
const consentStatus = document.querySelector("#consent-status");

let accessToken = null;
let expiryTimer = null;

function showStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}

function endSession(message = "You are logged out of this page.") {
  resetMoodPanel();

  accessToken = null;
  clearTimeout(expiryTimer);
  expiryTimer = null;

  loginForm.reset();
  welcomeTitle.textContent = "";
  accountEmail.textContent = "";
  consentStatus.textContent = "";

  accountPanel.hidden = true;
  loginPanel.hidden = false;

  showStatus(message);
  emailInput.focus();
}

async function apiRequest(path, { method = "GET", body } = {}) {
  const headers = {
    Accept: "application/json",
  };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      cache: "no-store",
    });

    const data = response.status === 204
      ? null
      : await response.json().catch(() => null);

    if (!response.ok) {
      if (response.status === 401 && accessToken) {
        endSession("Your session expired. Please log in again.");
      }

      const detail = typeof data?.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Please check your details.`;

      throw new Error(detail);
    }

    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(
        "The request timed out. Check that the backend is running."
      );
    }

    if (error instanceof TypeError) {
      throw new Error(
        "Cannot reach ENWEN. Check that the backend is running."
      );
    }

    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

// Log in.
loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (loginButton.disabled) return;

  loginButton.disabled = true;
  loginButton.textContent = "Logging in...";
  showStatus("");

  try {
    const login = await apiRequest("/auth/login", {
      method: "POST",
      body: {
        email: emailInput.value.trim(),
        password: passwordInput.value,
      },
    });

    if (!login?.access_token) {
      throw new Error("Login did not return a token.");
    }

    accessToken = login.access_token;

    clearTimeout(expiryTimer);
    expiryTimer = setTimeout(
      () => endSession("Your session expired. Please log in again."),
      login.expires_in * 1000
    );

    const user = await apiRequest("/auth/me");

    welcomeTitle.textContent =
      `Welcome, ${user.display_name || "student"}!`;

    accountEmail.textContent = user.email;

    consentStatus.textContent = user.wellness_consent_current
      ? "Your current wellness consent is recorded."
      : "Current wellness consent is needed before using wellness features.";

    loginPanel.hidden = true;
    accountPanel.hidden = false;

    setupMoodPanel(user);

    showStatus("Login successful. Your account is connected.");
    welcomeTitle.focus();
  } catch (error) {
    endSession("");
    showStatus(error.message, true);
  } finally {
    passwordInput.value = "";
    loginButton.disabled = false;
    loginButton.textContent = "Log in";
  }
});

// Log out.
document.querySelector("#logout-button").addEventListener("click", () => {
  endSession();
});

// Mood check-in elements.
const moodForm = document.querySelector("#mood-form");
const moodFields = document.querySelector("#mood-fields");
const moodNote = document.querySelector("#mood-note");
const moodMessage = document.querySelector("#mood-message");

let moodGeneration = 0;
let moodConsent = false;
let moodSaving = false;

function resetMoodPanel() {
  moodGeneration += 1;
  clearMoodHistory();

  moodConsent = false;
  moodSaving = false;

  moodForm.reset();
  moodFields.disabled = true;
  moodMessage.textContent = "";
  moodMessage.classList.remove("error");
}

function setupMoodPanel(user) {
  resetMoodPanel();

  moodConsent = user.wellness_consent_current === true;
  moodFields.disabled = !moodConsent;

  if (!moodConsent) {
    moodMessage.textContent =
      "Current wellness consent is needed to save a check-in.";
  } else {
    void loadMoodHistory();
  }
}

// Save a mood check-in.
moodForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!accessToken || !moodConsent || moodSaving) return;

  const choice = moodForm.querySelector(
    'input[name="mood_score"]:checked'
  );

  if (!choice) {
    moodForm.reportValidity();
    return;
  }

  const payload = {
    mood_score: Number(choice.value),
    note: moodNote.value.trim() || null,
  };

  const generation = moodGeneration;

  moodSaving = true;
  moodFields.disabled = true;
  moodMessage.classList.remove("error");
  moodMessage.textContent = "Saving your check-in...";

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch("/moods", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
      cache: "no-store",
    });

    const data = await response.json().catch(() => null);

    // Ignore responses belonging to an earlier login session.
    if (generation !== moodGeneration) return;

    if (response.status === 401) {
      endSession("Your session expired. Please log in again.");
      return;
    }

    if (response.status === 403) {
      moodConsent = false;
      clearMoodHistory();

      consentStatus.textContent =
        "Current wellness consent is needed for wellness features.";
    }

    if (!response.ok) {
      throw new Error(
        typeof data?.detail === "string"
          ? data.detail
          : "The check-in could not be saved. Please check your details."
      );
    }

    moodForm.reset();

    moodMessage.textContent =
      "Check-in saved. There is no right or wrong way to feel.";

    // Refreshing history is separate from saving the check-in.
    void loadMoodHistory();
  } catch (error) {
    if (generation !== moodGeneration) return;

    moodMessage.classList.add("error");

    moodMessage.textContent =
      error.name === "AbortError" || error instanceof TypeError
        ? "We could not confirm the save. Use Refresh under Your recent check-ins before retrying."
        : error.message;
  } finally {
    clearTimeout(timeout);

    if (generation === moodGeneration) {
      moodSaving = false;
      moodFields.disabled = !moodConsent;
    }
  }
});

// Recent mood history.
const historyList = document.querySelector("#mood-history-list");
const historyMessage = document.querySelector("#mood-history-message");
const historyRefresh = document.querySelector("#refresh-moods");

const moodNames = ["", "Very low", "Low", "Okay", "Good", "Great"];

let historyRequest = 0;
let historyController = null;

function clearMoodHistory() {
  historyRequest += 1;
  historyController?.abort();
  historyController = null;

  historyList.replaceChildren();
  historyList.setAttribute("aria-busy", "false");

  historyMessage.textContent = "";
  historyMessage.classList.remove("error");
  historyRefresh.disabled = true;
}

async function loadMoodHistory() {
  if (!accessToken || !moodConsent) return;

  const generation = moodGeneration;
  const request = ++historyRequest;

  historyController?.abort();

  const controller = new AbortController();
  historyController = controller;

  const isCurrent = () =>
    generation === moodGeneration && request === historyRequest;

  historyRefresh.disabled = true;
  historyList.replaceChildren();
  historyList.setAttribute("aria-busy", "true");

  historyMessage.classList.remove("error");
  historyMessage.textContent = "Loading your check-ins...";

  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch("/moods?limit=20", {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      signal: controller.signal,
      cache: "no-store",
    });

    const entries = await response.json().catch(() => null);

    // Ignore results from an earlier login session or refresh.
    if (!isCurrent()) return;

    if (response.status === 401) {
      endSession("Your session expired. Please log in again.");
      return;
    }

    if (response.status === 403) {
      moodConsent = false;
      moodFields.disabled = true;
      clearMoodHistory();

      const message =
        "Current wellness consent is needed to view your check-ins.";

      consentStatus.textContent = message;
      historyMessage.textContent = message;
      historyMessage.classList.add("error");
      return;
    }

    if (!response.ok) {
      throw new Error(
        typeof entries?.detail === "string"
          ? entries.detail
          : "Your mood history could not be loaded."
      );
    }

    if (!Array.isArray(entries)) {
      throw new Error(
        "Unexpected response. Please refresh your mood history."
      );
    }

    if (!moodConsent) return;

    const fragment = document.createDocumentFragment();

    for (const entry of entries) {
      const item = document.createElement("li");
      const heading = document.createElement("strong");
      const timestamp = document.createElement("time");
      const note = document.createElement("p");

      heading.textContent =
        (moodNames[entry.mood_score] || "Mood")
        + " · " + entry.mood_score + "/5";

      const date = new Date(entry.created_at);

      timestamp.dateTime = entry.created_at;
      timestamp.textContent = Number.isNaN(date.getTime())
        ? "Date unavailable"
        : date.toLocaleString(undefined, {
            dateStyle: "medium",
            timeStyle: "short",
          });

      // Show notes as plain text, never executable HTML.
      note.textContent = entry.note || "No note added.";

      item.append(heading, timestamp, note);
      fragment.append(item);
    }

    historyList.replaceChildren(fragment);

    historyMessage.textContent = entries.length
      ? "Showing " + entries.length + " recent check-in"
        + (entries.length === 1 ? "." : "s.")
      : "No check-ins yet. Your first saved mood will appear here.";
  } catch (error) {
    if (!isCurrent()) return;

    historyList.replaceChildren();
    historyMessage.classList.add("error");

    historyMessage.textContent =
      error.name === "AbortError"
        ? "History took too long to load. Please try Refresh."
        : error instanceof TypeError
          ? "Cannot load history. Check your connection and try Refresh."
          : error.message;
  } finally {
    clearTimeout(timeout);

    if (isCurrent()) {
      historyController = null;
      historyList.setAttribute("aria-busy", "false");
      historyRefresh.disabled = !moodConsent;
    }
  }
}

historyRefresh.addEventListener("click", () => {
  if (!historyRefresh.disabled) {
    void loadMoodHistory();
  }
});