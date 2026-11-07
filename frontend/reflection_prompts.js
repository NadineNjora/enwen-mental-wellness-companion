"use strict";


(() => {
  const fields = document.querySelector("#journal-fields");
  const content = document.querySelector("#journal-content");
  const form = document.querySelector("#journal-form");
  const label = document.querySelector('label[for="journal-title"]');
  if (!fields || !content || !form || !label || document.querySelector("#reflection-prompt-panel")) return;
  const panel = document.createElement("section");
  panel.id = "reflection-prompt-panel";
  panel.className = "enwen-prompts";
  panel.setAttribute("aria-labelledby", "reflection-prompt-title");
  const title = document.createElement("h4");
  title.id = "reflection-prompt-title";
  title.textContent = "Need a little starting point?";
  const help = document.createElement("p");
  help.textContent = "Pick a question, write freely, or leave the prompts alone. This is your space.";
  const options = document.createElement("div");
  options.className = "enwen-prompt-options";
  const message = document.createElement("p");
  message.className = "enwen-prompt-message";
  message.setAttribute("role", "status");
  const prompts = [
    ["📝 Let it out", "What feels heavy today, and what would I like to say about it?"],
    ["🌼 Small wins", "What went a little better than expected today?"],
    ["💛 A kinder voice", "What would I say to a friend who was having a day like mine?"],
    ["🍃 Make some room", "What can wait until tomorrow?"],
    ["🤝 A little support", "Who could I reach out to, and what would I want them to know?"],
  ];
  for (const [name, prompt] of prompts) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = name;
    button.addEventListener("click", () => {
      if (fields.disabled || content.disabled) return;
      if (content.value.includes(prompt)) {
        message.textContent = "That question is already in your writing. You can change or remove it.";
        content.focus();
        return;
      }
      const next = content.value + (content.value ? "\n\n" : "") + prompt + "\n\n";
      if (next.length > content.maxLength) {
        message.textContent = "Your entry is nearly full. Shorten it before adding another question.";
        return;
      }
      content.value = next;
      content.dispatchEvent(new Event("input", { bubbles: true }));
      message.textContent = "Question added. Your earlier writing is still here. Nothing has been saved yet.";
      content.focus();
      content.setSelectionRange(next.length, next.length);
    });
    options.append(button);
  }
  panel.append(title, help, options, message);
  label.before(panel);
  form.addEventListener("reset", () => { message.textContent = ""; });
})();
