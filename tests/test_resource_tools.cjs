// Synthetic DOM/API and a controllable clock. No real bookmarks or timers remain.
const assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const tick = () => new Promise(resolve => setImmediate(resolve));
const html = fs.readFileSync(path.join(__dirname, "../frontend/index.html"), "utf8");
const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, "../backend/resources_catalog.json"), "utf8")).map(row => ({ ...row, saved: false }));
const reply = (status, data) => ({status, ok: status >= 200 && status < 300, json: async () => { assert.notEqual(status, 204); return data; }});
function page(file) {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(new Set(ids).size, ids.length);
  const nodes = {}, intervals = new Map(), events = {}, calls = []; let now = 0, serial = 0;
  class Element {
    constructor(tag = "div") { this.tag = tag; this.children = []; this.textContent = ""; this.value = ""; this.checked = false; this.disabled = false; this.handlers = {}; this.attrs = {}; this.dataset = {}; this.classes = new Set(); this.classList = { toggle: (key, value) => value ? this.classes.add(key) : this.classes.delete(key) }; }
    append(...items) { for (const item of items) this.children.push(...(item.tag === "fragment" ? item.children : [item])); }
    replaceChildren(...items) { this.children = []; this.append(...items); }
    addEventListener(type, fn) { this.handlers[type] = fn; }
    setAttribute(key, value) { this.attrs[key] = value; }
    querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tag === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
    reset() { for (const id of ["resources-search", "resources-category"]) nodes[id].value = ""; nodes["resources-saved-only"].checked = false; }
    reportValidity() { return true; }
    focus() {}
    fire(type) { return this.handlers[type]?.({ preventDefault() {} }); }
  }
  ids.forEach(id => nodes[id] = new Element());
  let responder = () => reply(200, catalog.map(row => ({ ...row })));
  const ctx = vm.createContext({
    document: { getElementById: id => nodes[id], createElement: tag => new Element(tag), createDocumentFragment: () => new Element("fragment"), addEventListener: (name, fn) => events[name] = fn, hidden: false },
    window: { addEventListener: (name, fn) => events[name] = fn },
    accessToken: "synthetic-token", URL, URLSearchParams, AbortController,
    performance: { now: () => now },
    setInterval(fn) { intervals.set(++serial, fn); return serial; }, clearInterval: id => intervals.delete(id),
    setTimeout, clearTimeout,
    fetch: async (url, options) => { calls.push({url, options}); return responder(url, options); },
    endSession() { ctx.window.enwenResources.reset(); ctx.accessToken = null; },
    pauseWellnessFeatures() { ctx.window.enwenResources.reset(); },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../frontend/" + file), "utf8"), ctx);
  return { nodes, ctx, events, calls, intervals,
    respond: fn => responder = fn,
    async load() { await ctx.window.enwenResources.load(); },
    advance(ms) { now += ms; for (const fn of [...intervals.values()]) fn(); },
    buttons: () => nodes["resources-list"].querySelectorAll("button"),
  };
}
(async () => {
  const checks = [];
  let p = page("resources.js"); const library = p.ctx.window.enwenResources;
  library.setup({ wellness_consent_current: true }); assert.equal(p.calls.length, 0); await p.load();
  assert.equal(p.nodes["resources-list"].children.length, catalog.length);
  const link = p.nodes["resources-list"].querySelectorAll("a")[0];
  assert.equal(p.nodes["resources-list"].querySelectorAll("a").length,catalog.length);
  assert.equal(link.target, "_blank"); assert.equal(link.rel, "noopener noreferrer");
  checks.push("library loads on demand and renders source links safely");
  p.nodes["resources-category"].value = "rest"; p.nodes["resources-search"].value = "sleep"; await p.load();
  assert.match(p.calls.at(-1).url, /q=sleep/); assert.match(p.calls.at(-1).url, /category=rest/);
  checks.push("filters reach the API as encoded query parameters");
  p.respond((url, options) => options.method === "PUT" ? reply(204) : reply(200, catalog));
  p.buttons()[0].fire("click"); await tick();
  assert.equal(p.calls.at(-1).options.method, "PUT"); assert.equal(p.buttons()[0].attrs["aria-pressed"], "true");
  checks.push("save waits for API confirmation and updates the saved state");
  p.respond((url, options) => options.method === "GET" ? reply(200, [{ ...catalog[0], saved: true }]) : reply(204));
  p.nodes["resources-saved-only"].checked = true; await p.load(); p.buttons()[0].fire("click"); await tick();
  assert.equal(p.calls.at(-1).options.method, "DELETE"); assert.equal(p.nodes["resources-list"].children.length, 0);
  checks.push("unsave removes the card from the Saved by me view");
  p.nodes["resources-saved-only"].checked = false; p.respond(() => reply(200, catalog)); await p.load();
  p.respond(() => reply(503, {})); p.buttons()[0].fire("click"); await tick();
  assert.equal(p.buttons()[0].attrs["aria-pressed"], "false"); assert.match(p.nodes["resources-message"].textContent, /could not confirm/);
  checks.push("failed save is not shown as success and does not retry automatically");
  let finish; p.respond(() => new Promise(resolve => { finish = () => resolve(reply(200, catalog)); }));
  const pending = p.load(); library.reset(); finish(); await pending;
  assert.equal(p.nodes["resources-list"].children.length, 0); assert.equal(p.nodes["resources-fields"].disabled, true);
  checks.push("late results cannot repopulate a logged-out screen");
  for (const status of [401, 403]) {
    p = page("resources.js"); p.ctx.window.enwenResources.setup({ wellness_consent_current: true });
    p.respond(() => reply(status, {})); await p.load();
    assert.equal(p.nodes["resources-list"].children.length, 0); assert.equal(p.nodes["resources-fields"].disabled, true);
    checks.push(`${status} clears library state and disables controls`);
  }
  p = page("resources.js"); p.ctx.window.enwenResources.setup({ wellness_consent_current: true });
  p.respond(() => reply(200, [{ ...catalog[0], url: "javascript:alert(1)" }])); await p.load();
  assert.equal(p.nodes["resources-list"].children.length, 0);
  checks.push("untrusted URL schemes are rejected before rendering");
  p.respond(() => reply(200, [])); await p.load(); assert.match(p.nodes["resources-message"].textContent, /Nothing matches/);
  checks.push("empty results provide a usable next step");
  p.respond(() => reply(200, catalog)); await p.load(); let done;
  p.respond(() => new Promise(resolve => { done = () => resolve(reply(204)); }));
  p.buttons()[0].fire("click"); await tick(); p.buttons()[0].fire("click");
  assert.equal(p.calls.filter(call => call.options.method === "PUT").length, 1); done(); await tick();
  checks.push("double clicking Save cannot issue duplicate mutations");

  p = page("pause.js"); const activity = p.ctx.window.enwenPause;
  activity.setup({ wellness_consent_current: true }); assert.equal(p.nodes["pause-clock"].textContent, "1:04");
  p.nodes["pause-start"].fire("click");
  assert.equal(p.nodes["breath-phase"].textContent,"Breathe in");
  p.advance(4000); assert.equal(p.nodes["breath-phase"].textContent,"Hold gently");
  p.advance(4000); assert.equal(p.nodes["breath-phase"].textContent,"Breathe out");
  p.advance(4000); assert.equal(p.nodes["breath-phase"].textContent,"Rest before the next breath");
  p.advance(4000); assert.equal(p.nodes["breath-round"].textContent,"Round 2 of 4");
  p.nodes["breath-still"].checked=true; p.nodes["breath-still"].fire("change");
  assert.match(p.nodes["breath-petals"].attrs.transform,/scale\(1\)/);
  checks.push("flower follows all four four-second phases and supports still-flower mode");
  p.nodes["pause-reset"].fire("click");
  p.nodes["pause-start"].fire("click"); p.nodes["pause-start"].fire("click"); assert.equal(p.intervals.size, 1);
  p.advance(10000); assert.equal(p.nodes["pause-clock"].textContent, "0:54");
  checks.push("one timer counts elapsed time and duplicate Start is blocked");
  p.nodes["pause-stop"].fire("click"); p.advance(30000); assert.equal(p.nodes["pause-clock"].textContent, "0:54");
  p.nodes["pause-start"].fire("click"); p.advance(5000); assert.equal(p.nodes["pause-clock"].textContent, "0:49");
  checks.push("Pause and Continue preserve remaining time");
  activity.leave(); p.advance(10000); assert.equal(p.nodes["pause-clock"].textContent, "0:49");
  checks.push("leaving the activity stops its clock");
  p.nodes["pause-start"].fire("click"); p.ctx.document.hidden = true; p.events.visibilitychange(); assert.equal(p.intervals.size, 0);
  checks.push("hiding the browser pauses the activity");
  p.nodes["pause-reset"].fire("click"); assert.equal(p.nodes["pause-clock"].textContent, "1:04");
  p.nodes["pause-start"].fire("click"); p.advance(65000); assert.equal(p.nodes["pause-clock"].textContent, "0:00");
  assert.equal(p.intervals.size, 0); assert.equal(p.nodes["pause-start"].disabled, true); assert.match(p.nodes["pause-status"].textContent, /complete/);
  checks.push("completion stops at zero and asks for reset before another run");
  p.nodes["pause-reset"].fire("click"); p.nodes["pause-start"].fire("click"); const oldTick = [...p.intervals.values()][0];
  activity.reset(); oldTick(); assert.equal(p.nodes["pause-clock"].textContent, "1:04"); assert.equal(p.intervals.size, 0);
  p.nodes["pause-start"].fire("click"); assert.equal(p.intervals.size, 0);
  checks.push("logout clears the timer and a queued callback cannot restart it");
  activity.setup({wellness_consent_current: false}); p.nodes["pause-start"].fire("click"); assert.equal(p.intervals.size, 0);
  checks.push("activity respects the existing wellness-consent gate");
  console.log(JSON.stringify({passed: checks.length, checks, scope: "synthetic requests and clock; no public records changed"}, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
