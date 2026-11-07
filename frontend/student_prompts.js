"use strict";

(() => {
  const fields = document.querySelector("#mood-fields");
  const note = document.querySelector("#mood-note");
  const form = document.querySelector("#mood-form");
  const label = document.querySelector('label[for="mood-note"]');
  if (!fields || !note || !form || !label || document.querySelector("#student-prompt-panel")) return;
  const panel = document.createElement("section");
  panel.id = "student-prompt-panel";
  panel.className = "enwen-prompts";
  panel.setAttribute("aria-labelledby", "student-prompt-title");
  const title = document.createElement("h4");
  title.id = "student-prompt-title";
  title.textContent = "What's been part of your day?";
  const help = document.createElement("p");
  help.textContent = "Choose a starting point, or write your own.";
  const options = document.createElement("div");
  options.className = "enwen-prompt-options";
  const message = document.createElement("p");
  message.className = "enwen-prompt-message";
  message.setAttribute("role", "status");
  const prompts = [
    ["📚 Classes & deadlines", "Classes or deadlines are affecting my day because..."],
    ["💸 Money", "Something on my mind about fees or everyday costs is..."],
    ["🌦️ Weather", "Today's weather has made my day feel..."],
    ["🚌 Getting to class", "Getting to class today was..."],
    ["🫶 People around me", "Something about my friends, family or relationships today is..."],
    ["🌙 Rest & energy", "My energy today feels..."],
    ["🌟 A small win", "One small thing I want to acknowledge today is..."],
    ["🎉 A special occasion", "Today feels different because..."],
  ];
  for (const [name, prompt] of prompts) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = name;
    button.addEventListener("click", () => {
      if (fields.disabled || note.disabled) return;
      if (note.value.includes(prompt)) {
        message.textContent = "That starting point is already in your note. You can edit it below.";
        note.focus();
        return;
      }
      const next = note.value + (note.value ? "\n\n" : "") + prompt + "\n";
      if (next.length > note.maxLength) {
        message.textContent = "Your note is nearly full. Shorten it before adding a starting point.";
        return;
      }
      note.value = next;
      note.dispatchEvent(new Event("input", { bubbles: true }));
      message.textContent = "Starting point added. Add your own words, then save your check-in.";
      note.focus();
      note.setSelectionRange(next.length, next.length);
    });
    options.append(button);
  }
  panel.append(title, help, options, message);
  label.before(panel);
  form.addEventListener("reset", () => { message.textContent = ""; });
})();
