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
let authGeneration = 0;
let renewalTimer = null;
let renewalRequest = null;

function showStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}

function endSession(message = "You are logged out of this page.") {
  authGeneration++;
  clearTimeout(renewalTimer);
  resetMoodPanel();
  resetTrustedContactPanel();
  window.enwenLiveContacts?.reset();
  window.enwenSuggestions?.reset();
  window.enwenResources?.reset();
  window.enwenPause?.reset();
  window.enwenChat?.reset();

  accessToken = null;
  clearTimeout(expiryTimer);
  expiryTimer = null;

  loginForm.reset();
  welcomeTitle.textContent = "";
  accountEmail.textContent = "";
  consentStatus.textContent = "";
  document.querySelector("#student-badge").textContent = "Your wellness space";

  accountPanel.hidden = true;
  loginPanel.hidden = false;
  renderPage({ focus: false, reset: true });
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

    installAccessToken(login);

    const user = await apiRequest("/auth/me");
    if (!accessToken) return;

    welcomeTitle.textContent =
      `Welcome, ${user.display_name || "student"}!`;
    document.querySelector("#student-badge").textContent = user.display_name || "Your wellness space";

    accountEmail.textContent = user.email;

    consentStatus.textContent = user.wellness_consent_current
      ? "Your current wellness consent is recorded."
      : "Current wellness consent is needed before using wellness features.";

    loginPanel.hidden = true;
    accountPanel.hidden = false;

    setupMoodPanel(user);
    setupJournalPanel(user);
    setupTrustedContactPanel();
    window.enwenResources?.setup(user);
    window.enwenPause?.setup(user);
    void window.enwenChat?.setup(user);

    showStatus("Login successful. Your account is connected.");
    renderPage();
  } catch (error) {
    endSession("");
    showStatus(error.message, true);
  } finally {
    passwordInput.value = "";
    loginButton.disabled = false;
    loginButton.textContent = "Log in";
  }
});

// Revoke the saved cookie session before clearing the signed-in screen.
document.querySelector("#logout-button").addEventListener("click", async () => {
  const button = document.querySelector("#logout-button");
  if (button.disabled) return;
  button.disabled = true;
  try {
    await apiRequest("/auth/logout", {method: "POST"});
    endSession("You are logged out.");
  } catch (error) {
    showStatus("Logout could not be confirmed. Check your connection and try again.", true);
  } finally { button.disabled = false; }
});

function installAccessToken(login) {
  if (!login?.access_token || !(login.expires_in > 0)) throw new Error("Invalid session response.");
  accessToken = login.access_token;
  clearTimeout(expiryTimer); clearTimeout(renewalTimer);
  expiryTimer = setTimeout(async () => {
    if (!await renewSavedSession() && accessToken) endSession("Your session expired. Please log in again.");
  }, login.expires_in * 1000);
  renewalTimer = setTimeout(() => void renewSavedSession(), Math.max(1000, login.expires_in * 1000 - 60000));
}

async function renewSavedSession() {
  if (renewalRequest) return renewalRequest;
  const generation = authGeneration;
  renewalRequest = (async () => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("/auth/session", {method:"POST", credentials:"same-origin", cache:"no-store", signal:controller.signal});
      if (generation !== authGeneration) return false;
      if (response.status === 401) { if (accessToken) endSession("Your saved session expired. Please log in again."); return false; }
      if (!response.ok) throw new Error("Saved login is temporarily unavailable.");
      const login = await response.json();
      if (generation !== authGeneration) return false;
      installAccessToken(login);
      return true;
    } catch (error) {
      if (generation === authGeneration) {
        showStatus("Could not restore your saved login. Check your connection or log in again.", true);
        if (accessToken) renewalTimer = setTimeout(() => void renewSavedSession(), 10000);
      }
      return false;
    } finally { clearTimeout(timeout); renewalRequest = null; }
  })();
  return renewalRequest;
}

async function restoreSavedLogin() {
  loginButton.disabled = true;
  const generation = authGeneration;
  try {
    if (!await renewSavedSession() || generation !== authGeneration) return;
    const user = await apiRequest("/auth/me");
    if (!accessToken || generation !== authGeneration) return;
    welcomeTitle.textContent = `Welcome, ${user.display_name || "student"}!`;
    document.querySelector("#student-badge").textContent = user.display_name || "Your wellness space";
    accountEmail.textContent = user.email;
    consentStatus.textContent = user.wellness_consent_current ? "Your current wellness consent is recorded." : "Current wellness consent is needed before using wellness features.";
    loginPanel.hidden = true; accountPanel.hidden = false;
    setupMoodPanel(user); setupJournalPanel(user); setupTrustedContactPanel();
    window.enwenResources?.setup(user); window.enwenPause?.setup(user);
    void window.enwenChat?.setup(user);
    showStatus("Welcome back. Your saved login is connected.");
    renderPage({focus:false});
  } catch (error) {
    if (generation === authGeneration) endSession("Could not load your account. Please try logging in again.");
  } finally { loginButton.disabled = false; }
}

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
    scale_max: 10,
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
      pauseWellnessFeatures();
      return;
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

// Complete history for the charts; the dated list is shown 20 entries at a time.
const historyList = document.querySelector("#mood-history-list");
const historyMessage = document.querySelector("#mood-history-message");
const historyRefresh = document.querySelector("#refresh-moods");
const historyPrev = document.querySelector("#history-prev");
const historyNext = document.querySelector("#history-next");
const moodNames = ["", "Very low 😞", "Low 😔", "Down 🙁", "A little low 😕", "In between 😐", "Okay 🙂", "Pretty good 😊", "Good 😌", "Very good 😄", "Great 🤩"];
const legacyMoodNames = ["", "Very low", "Low", "Okay", "Good", "Great"];
let historyRequest = 0, historyController = null, historyEntries = [], historyOffset = 0;

function clearMoodHistory() {
  window.enwenMoodChart?.clear();
  historyRequest++; historyController?.abort(); historyController = null;
  historyEntries = []; historyOffset = 0;
  historyList.replaceChildren(); historyList.setAttribute("aria-busy", "false");
  historyMessage.textContent = ""; historyMessage.classList.remove("error");
  historyRefresh.disabled = historyPrev.disabled = historyNext.disabled = true;
}
function renderMoodHistoryList() {
  const fragment = document.createDocumentFragment();
  for (const entry of historyEntries.slice(historyOffset, historyOffset + 20)) {
    const item = document.createElement("li"), heading = document.createElement("strong");
    const timestamp = document.createElement("time"), note = document.createElement("p");
    const scale = entry.scale_max, names = scale === 5 ? legacyMoodNames : moodNames;
    heading.textContent = (names[entry.mood_score] || "Mood") + " · " + entry.mood_score + "/" + scale
      + (scale === 5 ? " · Earlier 1–5 scale" : "");
    const date = new Date(entry.created_at); timestamp.dateTime = entry.created_at;
    timestamp.textContent = Number.isNaN(date.getTime()) ? "Date unavailable" : date.toLocaleString(undefined,
      {dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Nairobi"});
    note.textContent = entry.note || "No note added.";
    item.append(heading, timestamp, note); fragment.append(item);
  }
  historyList.replaceChildren(fragment);
  historyPrev.disabled = historyOffset === 0;
  historyNext.disabled = historyOffset + 20 >= historyEntries.length;
  historyMessage.textContent = historyEntries.length
    ? "Showing " + (historyOffset + 1) + "–" + Math.min(historyOffset + 20, historyEntries.length)
      + " of " + historyEntries.length + " check-ins. The charts include your complete saved history."
    : "No check-ins yet. Your first saved mood will appear here.";
}
async function loadMoodHistory() {
  if (!accessToken || !moodConsent) return;
  const generation = moodGeneration, request = ++historyRequest, token = accessToken;
  historyController?.abort();
  const controller = new AbortController(); historyController = controller;
  const isCurrent = () => generation === moodGeneration && request === historyRequest && token === accessToken;
  historyRefresh.disabled = historyPrev.disabled = historyNext.disabled = true;
  historyEntries = []; historyOffset = 0; historyList.replaceChildren();
  historyList.setAttribute("aria-busy", "true"); historyMessage.classList.remove("error");
  historyMessage.textContent = "Loading your complete history...";
  window.enwenMoodChart?.clear("Loading all your recorded check-ins...");
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const entries = [], seen = new Set();
    let offset = 0, lastBoundary = null;
    while (true) {
      const response = await fetch("/moods?limit=100&offset=" + offset,
        {headers: {Accept: "application/json", Authorization: "Bearer " + token}, signal: controller.signal, cache: "no-store"});
      const batch = await response.json().catch(() => null);
      if (!isCurrent()) return;
      if (response.status === 401) { endSession("Your session expired. Please log in again."); return; }
      if (response.status === 403) { pauseWellnessFeatures(); return; }
      if (!response.ok) throw new Error(typeof batch?.detail === "string" ? batch.detail : "Your mood history could not be loaded.");
      if (!Array.isArray(batch)) throw new Error("Unexpected history response. Please try Refresh.");
      for (const entry of batch) {
        if (entry.mood_id && seen.has(entry.mood_id)) continue;
        if (entry.mood_id) seen.add(entry.mood_id);
        entries.push(entry);
      }
      if (batch.length < 100) break;
      const boundary = JSON.stringify([batch[0]?.mood_id, batch[99]?.mood_id, batch[99]?.created_at]);
      if (boundary === lastBoundary) throw new Error("History pages repeated unexpectedly. Please try Refresh.");
      lastBoundary = boundary; offset += batch.length;
    }
    if (!moodConsent || !isCurrent()) return;
    historyEntries = entries;
    renderMoodHistoryList(); window.enwenMoodChart?.render(entries);
  } catch (error) {
    if (!isCurrent()) return;
    historyEntries = []; historyList.replaceChildren();
    window.enwenMoodChart?.clear("Your graph will appear when history loads successfully.");
    historyMessage.classList.add("error");
    historyMessage.textContent = error.name === "AbortError" ? "History took too long. Please try Refresh."
      : error instanceof TypeError ? "Cannot load history. Check your connection and try Refresh." : error.message;
  } finally {
    clearTimeout(timeout);
    if (isCurrent()) { historyController = null; historyList.setAttribute("aria-busy", "false"); historyRefresh.disabled = !moodConsent; }
  }
}
historyRefresh.addEventListener("click", () => { if (!historyRefresh.disabled) void loadMoodHistory(); });
historyPrev.addEventListener("click", () => { if (!historyPrev.disabled) { historyOffset -= 20; renderMoodHistoryList(); } });
historyNext.addEventListener("click", () => { if (!historyNext.disabled) { historyOffset += 20; renderMoodHistoryList(); } });
