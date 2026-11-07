"use strict";

(() => {
  const el = id => document.getElementById(id);
  const clock = el("pause-clock"), status = el("pause-status");
  const start = el("pause-start"), stop = el("pause-stop"), resetButton = el("pause-reset");
  const phaseLabel = el("breath-phase"), count = el("breath-count"), petals = el("breath-petals");
  const affirmation = el("breath-affirmation"), roundLabel = el("breath-round");
  const still = el("breath-still");
  const phaseDuration = 4000, duration = phaseDuration * 4 * 4;
  const phases = [
    {name: "Breathe in", affirmation: "I welcome a little peace."},
    {name: "Hold gently", affirmation: "I am here, in this moment."},
    {name: "Breathe out", affirmation: "I make room for calm."},
    {name: "Rest before the next breath", affirmation: "I can move at my own pace."}
  ];
  let remaining = duration, deadline = 0, timer = null, allowed = false, lastPhase = "";
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  still.checked = reduced?.matches === true;
  function paint() {
    const seconds = Math.max(0, Math.ceil(remaining / 1000));
    clock.textContent = Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
    clock.setAttribute("aria-label", seconds + " seconds remaining");
    start.disabled = !allowed || timer !== null || remaining <= 0;
    stop.disabled = timer === null;
    start.textContent = timer !== null ? "Breathing together..." : remaining === duration ? "Begin my mindful minute" : "Continue";
    const elapsed = duration - remaining;
    const step = Math.floor(elapsed / phaseDuration) % 4;
    const progress = (elapsed % phaseDuration) / phaseDuration;
    const phase = phases[step];
    const name = !remaining ? "A moment, just for you." : remaining === duration && timer === null ? "A breath at a time" : phase.name;
    if (name !== lastPhase) { phaseLabel.textContent = name; lastPhase = name; }
    affirmation.textContent = !remaining ? "I can take my next small step." : phase.affirmation;
    count.textContent = !remaining ? "✓" : String(Math.ceil((phaseDuration - elapsed % phaseDuration) / 1000));
    roundLabel.textContent = !remaining ? "Four rounds complete 🌼" : "Round " + Math.min(4, Math.floor(elapsed / (phaseDuration * 4)) + 1) + " of 4";
    const bloom = still.checked ? 1 : step === 0 ? .62 + .38 * progress : step === 1 ? 1 : step === 2 ? 1 - .38 * progress : .62;
    petals.setAttribute("transform", "translate(140 126) scale(" + bloom + ") translate(-140 -126)");
  }
  function clearTimer() { if (timer !== null) clearInterval(timer); timer = null; }
  function tick() {
    if (timer === null) return;
    remaining = Math.max(0, deadline - performance.now());
    if (!remaining) { clearTimer(); status.textContent = "Your four rounds are complete. Take the calm with you, at your own pace."; }
    paint();
  }
  function leave() {
    if (timer === null) return;
    remaining = Math.max(0, deadline - performance.now()); clearTimer();
    status.textContent = remaining ? "Paused. Breathe naturally and continue when you are ready." : "Your four rounds are complete.";
    paint();
  }
  function reset() {
    for (const box of document.querySelectorAll?.("[data-grounding-check]") || []) box.checked = false;
    clearTimer(); allowed = false; remaining = duration; lastPhase = "";
    status.textContent = "Four gentle rounds. Start when you feel ready."; paint();
  }
  function setup(user) {
    reset(); allowed = user.wellness_consent_current === true;
    if (!allowed) status.textContent = "Please review your current wellness consent before starting.";
    paint();
  }
  start.addEventListener("click", () => {
    if (!allowed || !accessToken || timer !== null || remaining <= 0) return;
    deadline = performance.now() + remaining; timer = setInterval(tick, 100);
    status.textContent = "Follow the flower gently. You can pause or return to your natural breathing at any time."; paint();
  });
  stop.addEventListener("click", leave);
  resetButton.addEventListener("click", () => {
    clearTimer(); remaining = duration; lastPhase = "";
    status.textContent = "A fresh start. Four gentle rounds, at your pace."; paint();
  });
  still.addEventListener("change", paint);
  document.addEventListener("visibilitychange", () => { if (document.hidden) leave(); });
  window.addEventListener("pagehide", leave);
  window.enwenPause = Object.freeze({setup, reset, leave}); paint();
})();
