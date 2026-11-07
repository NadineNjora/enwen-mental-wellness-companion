"use strict";
(() => {
  let installPrompt = null;
  const button = document.getElementById("install-enwen"), status = document.getElementById("install-status");
  const help = document.getElementById("install-help");
  if (!button || !status || !help) return;
  const standalone = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  function installed() {
    installPrompt = null; button.hidden = true;
    status.textContent = "ENWEN is open as an installed app."; help.hidden = true;
  }
  if (standalone()) installed();
  window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault(); installPrompt = event; button.hidden = false;
    status.textContent = "Keep your wellness space a little closer.";
  });
  window.addEventListener("appinstalled", installed);
  button.addEventListener("click", async () => {
    if (!installPrompt) { help.hidden = !help.hidden; return; }
    const prompt = installPrompt; installPrompt = null; button.disabled = true;
    try {
      await prompt.prompt(); const choice = await prompt.userChoice;
      status.textContent = choice.outcome === "accepted" ? "Install request accepted. Your browser will finish the installation." : "You can keep using ENWEN in this browser.";
    } catch { help.hidden = false; status.textContent = "Use your browser's installation menu to continue."; }
    finally { button.disabled = false; }
  });
  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", {scope:"/", updateViaCache:"none"}).catch(() => {
        status.textContent = "ENWEN works in this browser. Offline support is not ready; refresh when connected.";
      });
    }, {once:true});
  } else {
    status.textContent = "Use HTTPS or localhost for app installation support.";
  }
})();
