// Synthetic DOM only. No network requests, phone calls or messages are made.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../frontend/safety_support.js"), "utf8");
const checks = [];

function environment() {
  let focuses = 0;
  class Element {
    constructor(tag) { this.tagName = tag; this.children = []; this.attrs = {}; this.hidden = false; this.disabled = false; this.textContent = ""; }
    append(...nodes) { for (const node of nodes) { this.children.push(node); node.parent = this; } }
    before(node) { const i = this.parent.children.indexOf(this); this.parent.children.splice(i, 0, node); node.parent = this.parent; }
    replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
    setAttribute(name, value) { this.attrs[name] = value; }
    focus() { focuses++; }
    set innerHTML(value) { throw new Error("Unsafe HTML insertion is forbidden in this test"); }
  }
  const page = new Element("section"), form = new Element("form"), fields = new Element("fieldset");
  const byId = {"page-chat": page, "chat-form": form, "chat-fields": fields};
  page.append(form); form.append(fields);
  const context = vm.createContext({document: {getElementById: id => byId[id], createElement: tag => new Element(tag)}, window: {}, URL});
  vm.runInContext(source, context);
  return {api: context.window.enwenSafety, page, form, fields, get focuses() { return focuses; }, get panel() { return page.children.find(node => node.id === "chat-safety-support"); }};
}
function walk(node) { return [node, ...node.children.flatMap(walk)]; }
function texts(node) { return walk(node).map(item => item.textContent).join(" "); }
function anchors(node) { return walk(node).filter(item => item.tagName === "a"); }
const urgent = {
  level: "urgent", event_id: "synthetic-event-1", message: "Synthetic intervention text.",
  resources: [{name: "Synthetic support service", phone: "+254 700 000 001", url: "https://support.example.com/info"}],
  alert: {status: "queued", message: "Synthetic provider acceptance. Delivery is not confirmed."},
};

let env = environment();
assert.equal(env.api.active(), false);
assert.equal(env.api.show({level: "ordinary"}), false);
assert.equal(env.panel, undefined);
checks.push("ordinary data does not activate or mount an urgent panel");

assert.equal(env.api.show(urgent), true);
assert.equal(env.api.active(), true);
assert.equal(env.fields.disabled, true);
assert.equal(env.page.children.indexOf(env.panel) + 1, env.page.children.indexOf(env.form));
assert.equal(env.panel.hidden, false);
checks.push("server urgent intervention mounts before composer and disables it");
assert.equal(env.focuses, 1);
assert.equal(env.panel.attrs["aria-labelledby"], "chat-safety-heading");
assert.equal(walk(env.panel).find(item => item.id === "chat-safety-heading").attrs.tabindex, "-1");
checks.push("new intervention has a labelled heading and receives focus");

let links = anchors(env.panel);
assert.ok(links.some(link => link.href === "tel:+254700000001"));
assert.ok(links.some(link => link.href === "https://support.example.com/info" && link.rel === "noopener noreferrer"));
assert.ok(links.some(link => link.href === "#/trusted-contact"));
assert.ok(links.some(link => link.href === "#/resources"));
assert.ok(links.some(link => link.href === "#/pause"));
checks.push("safe phone/service links and app support routes are available");
env.api.show({...urgent, resources: [{name:"Synthetic supported contact",phone:"+254 700 000 001",phone_url:"tel:+254700000001?oai_link_source=model_response_hotline",
  url:"https://support.example.com/?oai_link_source=model_response_hotline",detail:"Synthetic opening hours only",source_checked_on:"2026-11-06"}]});
assert.ok(anchors(env.panel).some(link=>link.href==="tel:+254700000001?oai_link_source=model_response_hotline"));
assert.ok(texts(env.panel).includes("Synthetic opening hours only"));
assert.ok(texts(env.panel).includes("Contact details checked 2026-11-06"));
checks.push("verified connector phone href is preserved exactly and supplied hours/check date are rendered as text");
env.api.show({...urgent, resources:[{name:"Unsafe dial parameter",phone:"+254700000001",phone_url:"tel:+254700000001?body=unapproved"}]});
assert.ok(anchors(env.panel).every(link=>!link.href.startsWith("tel:")));
checks.push("unapproved phone URI queries are rejected");
env.api.show(urgent);
assert.ok(texts(env.panel).includes("Submitted to the message provider"));
assert.ok(!texts(env.panel).includes("Delivery confirmed"));
checks.push("queued provider submission is not misrepresented as confirmed delivery");

env.api.show({...urgent, alert: {status: "failed", message: "Synthetic failure: reach someone directly."}});
assert.equal(env.focuses, 1);
assert.ok(texts(env.panel).includes("The alert could not be sent"));
assert.ok(texts(env.panel).includes("Synthetic failure: reach someone directly."));
checks.push("same-event delivery update is visible without stealing focus again");

env.api.show({...urgent, event_id: "synthetic-event-2", message: '<img src=x onerror="bad()">',
  resources: [{name: "Untrusted", phone: "javascript:bad()", url: "javascript:bad()"},
    {name: "Credentials in URL", phone: "+254700000001;ext=5", url: "https://user:secret@example.com/"}]});
assert.equal(env.focuses, 2);
assert.ok(texts(env.panel).includes('<img src=x onerror="bad()">'));
assert.ok(anchors(env.panel).every(link => link.href.startsWith("#/")));
checks.push("message markup stays text and malicious phone/URL values create no actionable links");
assert.ok(texts(env.panel).includes("Support contacts could not be loaded"));
checks.push("missing valid contacts produces an honest fallback instead of invented numbers");

env.api.show({...urgent, alert: {status: "unexpected"}});
assert.ok(texts(env.panel).includes("Delivery is not confirmed"));
assert.ok(!texts(env.panel).includes("Delivery confirmed."));
checks.push("unknown alert outcome never claims that help was notified");

env.api.reset();
assert.equal(env.api.active(), false);
assert.equal(env.panel.hidden, true);
assert.equal(env.panel.children.length, 0);
assert.equal(env.fields.disabled, true);
checks.push("logout/reset clears intervention data without independently unlocking chat");
env.api.show(urgent);
assert.equal(env.focuses, 4); // Event 2 -> 1 -> reset -> new event 1.
checks.push("a later session can receive a fresh intervention and focus");

console.log(JSON.stringify({passed: checks.length, checks, scope: "Synthetic DOM; no contacts or communications."}, null, 2));
