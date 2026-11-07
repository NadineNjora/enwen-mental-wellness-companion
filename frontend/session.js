"use strict";

// Runs after the account screens and navigation are ready. The saved secret is
// an HttpOnly cookie; never put it in localStorage or expose it to JavaScript.
void restoreSavedLogin();

window.addEventListener("pageshow", event => {
  if (event.persisted) { endSession(""); void restoreSavedLogin(); }
});
