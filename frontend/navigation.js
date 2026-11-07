"use strict";

// Each route displays one screen.
// Access tokens stay in memory; the server restores login via an HttpOnly cookie.
const enwenPages = [
  ...document.querySelectorAll("[data-page]"),
];

const enwenNav = document.querySelector("#app-nav");

const enwenRouteTitles = new Map([
  ["home", "Home"],
  ["check-in", "Mood check-in"],
  ["mood-history", "Mood history"],
  ["journal", "Journal"],
  ["chat", "Let's talk"],
  ["trusted-contact", "Trusted contact"],
  ["resources", "Wellness resources"],
  ["pause", "A mindful minute"],
]);

const enwenLoginTitle = document.title;
let enwenPendingRoute = null;

function clearJournalScreen() {
  resetJournalPanel();
}

function renderPage({ focus = true, reset = false } = {}) {
  if (reset) {
    enwenPendingRoute = null;
    history.replaceState(null, "", "#/login");
  }

  const requested = location.hash.startsWith("#/")
    ? location.hash.slice(2)
    : "";

  const validRoute = enwenRouteTitles.has(requested);
  const signedIn = Boolean(accessToken) && !accountPanel.hidden;

  document.body.classList.toggle("signed-in", signedIn);
  enwenNav.hidden = !signedIn;
  loginPanel.hidden = signedIn;
  accountPanel.hidden = !signedIn;

  for (const page of enwenPages) {
    page.hidden = true;
  }

  for (const link of enwenNav.querySelectorAll("a")) {
    link.removeAttribute("aria-current");
  }

  // Never reveal account screens when logged out.
  if (!signedIn) {
    window.enwenResources?.reset();
    window.enwenPause?.reset();
    if (validRoute && !reset) {
      enwenPendingRoute = requested;
    }

    clearJournalScreen();
    document.title = enwenLoginTitle;
    history.replaceState(null, "", "#/login");

    if (focus) {
      emailInput.focus();
    }

    return;
  }

  const route = validRoute
    ? requested
    : enwenPendingRoute || "home";

  enwenPendingRoute = null;

  const page = enwenPages.find(
    (item) => item.dataset.page === route
  );

  page.hidden = false;
  if (route !== "pause") window.enwenPause?.leave();
  if (route === "resources") void window.enwenResources?.load();
  if (route === "trusted-contact") void loadTrustedContact();
  document.title = "ENWEN | " + enwenRouteTitles.get(route);
  history.replaceState(null, "", "#/" + route);

  for (const link of enwenNav.querySelectorAll("a")) {
    if (link.dataset.route === route) {
      link.setAttribute("aria-current", "page");
    }
  }

  if (focus) {
    const heading = page.querySelector("h2, h3, h4");

    heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });

    window.scrollTo({
      top: 0,
      behavior: "auto",
    });
  }
}

// Support navigation links and browser Back/Forward.
window.addEventListener("hashchange", () => {
  renderPage();
});

// Check the session when a browser page is restored.
window.addEventListener("pageshow", () => {
  renderPage({ focus: false });
});

renderPage({ focus: false });
