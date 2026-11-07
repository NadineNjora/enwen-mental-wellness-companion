// Exercise the copy-ready helpers with a synthetic form; no network or storage.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const checks = [];
for (const config of [
  { file: "student_prompts.js", prefix: "mood", field: "mood-note", label: 'label[for="mood-note"]', limit: 1000, buttons: 8 },
  { file: "reflection_prompts.js", prefix: "journal", field: "journal-content", label: 'label[for="journal-title"]', limit: 10000, buttons: 5 },
]) {
  const nodes = [];
  const element = () => {
    const item = { children: [], listeners: {}, textContent: "", disabled: false, value: "", maxLength: config.limit,
      append(...values) { this.children.push(...values); },
      before(value) { this.beforeNode = value; },
      setAttribute() {}, addEventListener(name, fn) { this.listeners[name] = fn; },
      dispatchEvent() {}, focus() {}, setSelectionRange() {},
    }; nodes.push(item); return item;
  };
  const fields = element(), form = element(), input = element(), label = element();
  const selectors = { [`#${config.prefix}-fields`]: fields, [`#${config.prefix}-form`]: form,
    [`#${config.field}`]: input, [config.label]: label };
  const context = vm.createContext({ Event: class {}, document: {
    querySelector: selector => selectors[selector] || nodes.find(node => "#" + node.id === selector) || null,
    createElement: () => element(),
  } });
  const source = fs.readFileSync(path.join(__dirname, "../frontend", config.file), "utf8");
  vm.runInContext(source, context);
  const buttons = nodes.filter(node => node.type === "button");
  assert.equal(buttons.length, config.buttons);
  assert.ok(label.beforeNode);
  checks.push(`${config.prefix}: panel placed before the existing input label`);
  fields.disabled = true; buttons[0].listeners.click(); assert.equal(input.value, "");
  fields.disabled = false; input.disabled = true; buttons[0].listeners.click(); assert.equal(input.value, "");
  input.disabled = false;
  checks.push(`${config.prefix}: disabled forms cannot insert prompts`);
  input.value = "Keep my original writing"; buttons[0].listeners.click();
  assert.ok(input.value.startsWith("Keep my original writing\n\n"));
  const once = input.value; buttons[0].listeners.click(); assert.equal(input.value, once);
  checks.push(`${config.prefix}: preserves the draft and prevents repeated prompt duplication`);
  input.value = "x".repeat(config.limit); buttons[1].listeners.click(); assert.equal(input.value, "x".repeat(config.limit));
  checks.push(`${config.prefix}: character limit never truncates existing writing`);
  input.value = ""; buttons[1].listeners.click();
  const status = nodes.find(node => node.className === "enwen-prompt-message"); assert.ok(status.textContent);
  form.listeners.reset(); assert.equal(status.textContent, "");
  checks.push(`${config.prefix}: form reset clears helper status`);
  const beforeCount = nodes.length; vm.runInContext(source, context); assert.equal(nodes.length, beforeCount);
  checks.push(`${config.prefix}: duplicate script inclusion does not duplicate the panel`);
}
console.log(JSON.stringify({ passed: checks.length, checks, requests: "none; synthetic forms only" }, null, 2));
