// Isolated browser-like DOM/API scenarios. Never contacts the database or mail server.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tick = () => new Promise(resolve => setImmediate(resolve));
const sourceDir = path.resolve(__dirname, "../frontend");
const html = fs.readFileSync(path.join(sourceDir, "index.html"), "utf8");
const source = name => fs.readFileSync(path.join(sourceDir,
  name === "mood-chart.js" && !fs.existsSync(path.join(sourceDir, name)) ? "mood_chart.js" : name), "utf8");
const reply = (status, data) => ({ status, ok: status >= 200 && status < 300,
  async json() { assert.notEqual(status, 204, "204 must not be parsed as JSON"); return data; } });
const entry = (id = "entry-1", title = "A fictional day", content = "Synthetic journal text") => ({
  journal_id: id, title, content, created_at: "2026-11-04T08:00:00+03:00", updated_at: "2026-11-04T08:00:00+03:00",
});
function page({ app = false } = {}) {
  const elements = {}, events = {}, calls = [], confirmations = [];
  let confirmAnswer = true, focused;
  class Element {
    constructor(tag = "div") {
      this.tagName = tag; this.children = []; this.handlers = {}; this.attrs = {};
      this.value = ""; this.textContent = ""; this.hidden = false; this.disabled = false;
      this.classList = { add() {}, remove() {}, toggle() {} };
    }
    append(...nodes) { for (const node of nodes) { if (node.tagName === "fragment") this.append(...node.children); else { this.children.push(node); node.parent = this; } } }
    before(node) { const parent = this.parent || root; const i = parent.children.indexOf(this); parent.children.splice(Math.max(0, i), 0, node); node.parent = parent; }
    after(node) { const parent = this.parent || root; const i = parent.children.indexOf(this); parent.children.splice(i + 1, 0, node); node.parent = parent; }
    replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
    setAttribute(key, value) { this.attrs[key] = value; }
    removeAttribute(key) { delete this.attrs[key]; }
    addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
    focus() { focused = this; }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    querySelectorAll(selector) { return this.children.flatMap(child => [...(child.tagName === selector ? [child] : []), ...child.querySelectorAll(selector)]); }
    reset() { if (this === elements["journal-form"]) { elements["journal-title"].value = ""; elements["journal-content"].value = ""; } }
    reportValidity() { return true; }
    async fire(type) { for (const handler of this.handlers[type] || []) await handler({ preventDefault() {} }); }
  }
  const root = new Element();
  for (const match of html.matchAll(/<([a-z][\w-]*)[^>]*\bid="([^"]+)"[^>]*>/g)) {
    const el = new Element(match[1]); el.id = match[2]; elements[el.id] = el; root.append(el);
  }
  const legend = new Element("legend"); legend.textContent = "Write a new entry";
  elements["journal-fields"].append(legend, elements["journal-save-button"]);
  elements["journal-reader"].append(elements["close-journal"]);
  elements["journal-save-button"].textContent = "Save my entry";
  let rows = [entry()];
  const baseline = (url, options) => {
    if (url.startsWith("/moods")) return reply(200, []);
    if (options.method === "POST") { const item = entry("new-entry", ...Object.values(JSON.parse(options.body))); rows.unshift(item); return reply(201, item); }
    if (options.method === "PUT") { const id = decodeURIComponent(url.split("/").pop()); const payload = JSON.parse(options.body); const i = rows.findIndex(row => row.journal_id === id); if (i < 0) return reply(404, { detail: "Not found" }); rows[i] = { ...rows[i], ...payload }; return reply(200, rows[i]); }
    if (options.method === "DELETE") { rows = rows.filter(row => row.journal_id !== decodeURIComponent(url.split("/").pop())); return reply(204); }
    if (url.includes("?")) return reply(200, rows.map(({ content, ...rest }) => rest));
    return reply(200, rows.find(row => row.journal_id === decodeURIComponent(url.split("/").pop())));
  };
  let responder = baseline;
  const context = vm.createContext({
    document: {
      querySelector(selector) { const value = elements[selector.slice(1)]; assert.ok(value, selector); return value; },
      createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag),
      createDocumentFragment: () => new Element("fragment"),
    },
    window: { confirm(message) { confirmations.push(message); return confirmAnswer; }, addEventListener(name, fn) { events[name] = fn; } },
    AbortController, setTimeout, clearTimeout,
    fetch: async (url, options) => { calls.push({ url, options }); return responder(url, options); },
    ...(app ? { resetTrustedContactPanel() {}, renderPage() { vm.runInContext("resetJournalPanel()", context); } } : {
      accessToken: "fake-token", consentStatus: new Element(), moodMessage: new Element(), historyMessage: new Element(), resetMoodPanel() {},
      endSession() { vm.runInContext("resetJournalPanel(); accessToken = null", context); },
    }),
  });
  const run = code => vm.runInContext(code, context);
  if (app) { run(source("mood-chart.js")); run(source("app.js")); }
  run(source("journals.js"));
  return { elements, root, context, calls, confirmations, events, run, baseline,
    respond(fn) { responder = fn; }, confirm(value) { confirmAnswer = value; },
    async login() { if (app) run('accessToken = "fake-token"; moodConsent = true;'); run("setupJournalPanel({wellness_consent_current: true})"); await tick(); },
    control(id) { return walk(root).find(node => node.id === id); },
    draft(title, content) { elements["journal-title"].value = title; elements["journal-content"].value = content; },
    async open(id = "entry-1") { await run(`readJournalEntry(${JSON.stringify(id)})`); },
    async edit() { await this.control("journal-edit-button").fire("click"); },
    async save() { await elements["journal-form"].fire("submit"); await tick(); },
    async remove() { await this.control("journal-delete-button").fire("click"); await tick(); },
  };
}
function walk(node) { return [node, ...node.children.flatMap(walk)]; }
(async () => {
  const checks = [];
  let p = page(); await p.login(); p.draft("New reflection", "A fictional reflection"); await p.save();
  assert.equal(p.calls.filter(c => c.options.method === "POST").length, 1); assert.equal(p.elements["journal-title"].value, "");
  checks.push("existing create/list flow still works");

  await p.open(); await p.edit(); p.draft("Changed title", "Changed content"); await p.save();
  const update = p.calls.find(c => c.options.method === "PUT"); assert.equal(update.url, "/journals/entry-1");
  assert.deepEqual(JSON.parse(update.options.body), { title: "Changed title", content: "Changed content" });
  await p.open(); assert.equal(p.elements["journal-reader-title"].textContent, "Changed title");
  checks.push("Edit loads saved content; Save changes uses PUT on the same record");

  p.draft("Unsaved new title", "Unsaved new text"); p.confirm(false); await p.edit();
  assert.equal(p.elements["journal-title"].value, "Unsaved new title");
  checks.push("declining replacement preserves an unsaved draft");

  p.confirm(true); await p.edit(); p.draft("Another title", "Another text"); p.confirm(false);
  await p.control("journal-cancel-edit").fire("click"); assert.equal(p.elements["journal-title"].value, "Another title");
  p.confirm(true); await p.control("journal-cancel-edit").fire("click"); await p.open();
  assert.equal(p.elements["journal-reader-title"].textContent, "Changed title");
  checks.push("Cancel editing asks before discarding and never changes the saved record");

  p.confirm(false); await p.remove(); assert.equal(p.calls.filter(c => c.options.method === "DELETE").length, 0);
  p.confirm(true); await p.remove(); assert.equal(p.calls.filter(c => c.options.method === "DELETE").length, 1);
  assert.equal(p.elements["journal-reader"].hidden, true); assert.equal(p.elements["journal-list"].children.length, 1);
  checks.push("delete requires confirmation; 204 closes the reader and refreshes the list");

  p = page(); await p.login(); await p.open(); await p.edit(); p.draft("Keep me", "Keep my writing");
  p.respond((url, options) => options.method === "PUT" ? reply(503, { detail: "Unavailable" }) : p.baseline(url, options)); await p.save();
  assert.equal(p.elements["journal-content"].value, "Keep my writing"); assert.equal(p.run("journalEditingId"), "entry-1");
  assert.equal(p.elements["journal-fields"].disabled, false); assert.match(p.elements["journal-message"].textContent, /could not confirm/);
  checks.push("failed update preserves edit mode and the complete draft");

  p.respond((url, options) => options.method === "DELETE" ? reply(503, {}) : p.baseline(url, options)); await p.remove();
  assert.equal(p.elements["journal-reader"].hidden, false); assert.equal(p.elements["journal-content"].value, "Keep my writing");
  checks.push("failed deletion preserves the reader and any edit draft");

  p = page(); await p.login(); await p.open(); await p.edit(); p.draft("Pending", "Pending update"); let complete;
  p.respond((url, options) => options.method === "PUT" ? new Promise(resolve => { complete = () => resolve(reply(200, entry("entry-1", "Pending", "Pending update"))); }) : p.baseline(url, options));
  const saving = p.save(); await tick(); await p.save(); await p.remove();
  assert.equal(p.calls.filter(c => c.options.method === "PUT").length, 1); assert.equal(p.calls.filter(c => c.options.method === "DELETE").length, 0);
  assert.equal(p.elements["journal-fields"].disabled, true);
  checks.push("duplicate saves and competing deletes are blocked during a save");
  p.run('endSession(); accessToken = "another-token"; setupJournalPanel({wellness_consent_current:true})'); await tick(); complete(); await saving;
  assert.equal(p.elements["journal-message"].textContent, ""); assert.equal(p.elements["journal-title"].value, "");
  checks.push("a late update from the old login cannot alter the new session");

  for (const status of [401, 403]) {
    p = page(); await p.login(); await p.open(); await p.edit();
    p.respond(() => reply(status, { detail: "Denied" })); await p.save();
    assert.equal(p.elements["journal-reader"].hidden, true); assert.equal(p.elements["journal-title"].value, "");
    assert.equal(p.elements["journal-fields"].disabled, true);
    checks.push(`${status} clears private journal state and disables editing`);
  }

  p = page(); await p.login(); p.draft("   ", "   "); await p.save();
  assert.equal(p.calls.filter(c => c.options.method === "POST").length, 0);
  checks.push("blank drafts are rejected before a write request");

  p = page(); await p.login(); await p.open(); p.draft("Unrelated draft", "Keep this new entry"); await p.remove();
  assert.equal(p.elements["journal-content"].value, "Keep this new entry");
  checks.push("deleting a saved entry preserves an unrelated new draft");

  p = page(); await p.login(); p.respond((url, options) => options.method === "GET" && !url.includes("?")
    ? reply(200, entry("entry-1", '<img src=x onerror="bad()">', "<script>bad()</script>")) : p.baseline(url, options));
  await p.open(); assert.equal(p.elements["journal-reader-content"].textContent, "<script>bad()</script>");
  assert.equal(p.elements["journal-reader-content"].children.length, 0);
  checks.push("user-written markup remains plain text");

  p = page({ app: true }); await p.login(); await p.run("loadMoodHistory()");
  let viewport = walk(p.root).find(n => n.className === "enwen-trend-scroll"); assert.equal(viewport.hidden, true);
  checks.push("empty mood history has an empty state, not invented graph points");
  p.respond((url, options) => url.startsWith("/moods") ? reply(200, [
    { mood_score: 10, scale_max: 10, created_at: "2026-11-04T12:00:00+03:00" },
    { mood_score: 1, scale_max: 10, created_at: "2026-11-01T12:00:00+03:00" },
    { mood_score: 5, scale_max: 10, created_at: "2026-11-03T12:00:00+03:00" },
  ]) : p.baseline(url, options)); await p.run("loadMoodHistory()");
  const circles = walk(viewport).filter(n => n.tagName === "circle"); assert.equal(circles.length, 3);
  const positions = circles.map(n => Number(n.attrs.cx)); assert.ok(positions[0] < positions[1] && positions[1] < positions[2]);
  assert.ok((positions[1] - positions[0]) > (positions[2] - positions[1]), "x axis uses elapsed time, not array index");
  assert.match(circles[0].children[0].textContent, /12:00/);
  assert.equal(p.elements["mood-history-list"].children.length, 3);
  checks.push("real history request renders three chronological points with time-proportional spacing and EAT labels");

  p.respond((url, options) => url.startsWith("/moods") ? reply(200, [{ mood_score: 5, scale_max: 10, created_at: "2026-11-04T09:00:00Z" }]) : p.baseline(url, options)); await p.run("loadMoodHistory()");
  assert.equal(walk(viewport).filter(n => n.tagName === "circle").length, 1);
  assert.equal(walk(viewport).filter(n => n.tagName === "polyline").length, 0);
  checks.push("one check-in renders one point without implying a trend");

  p.context.window.enwenMoodChart.render([{ mood_score: 11, scale_max: 10, created_at: "not-a-date" }]);
  assert.equal(viewport.hidden, true); assert.equal(viewport.children.length, 0);
  checks.push("invalid scores or dates do not produce a misleading graph");

  p.respond(() => reply(503, { detail: "Unavailable" })); await p.run("loadMoodHistory()");
  assert.equal(viewport.children.length, 0); assert.equal(p.elements["mood-history-list"].children.length, 0);
  checks.push("history errors clear the graph rather than retaining stale points");

  p.context.window.enwenMoodChart.render([{ mood_score: 2, scale_max: 10, created_at: "2026-11-04T09:00:00Z" }]); p.run("endSession()");
  assert.equal(viewport.children.length, 0); assert.equal(viewport.hidden, true);
  checks.push("logout clears the graph and journal content");

  const radioValues = [...html.matchAll(/name="mood_score" value="(\d+)"/g)].map(match => Number(match[1]));
  assert.deepEqual(radioValues, [1,2,3,4,5,6,7,8,9,10]);
  checks.push("form exposes exactly ten explicitly numbered choices");
  p = page({ app: true }); await p.login();
  p.respond((url, options) => url.startsWith("/moods") ? reply(200, [
    { mood_score: 5, scale_max: 5, created_at: "2026-09-21T12:00:00+03:00" },
    { mood_score: 5, scale_max: 10, created_at: "2026-11-04T12:00:00+03:00" },
  ]) : p.baseline(url, options)); await p.run("loadMoodHistory()");
  viewport = walk(p.root).find(n => n.className === "enwen-trend-scroll");
  assert.equal(walk(viewport).filter(n => n.tagName === "circle").length, 2);
  assert.match(p.elements["mood-history-list"].children[0].children[0].textContent, /10\/10/);
  assert.match(p.elements["mood-history-list"].children[1].children[0].textContent, /5\/10/);
  checks.push("mixed history uses a common ten-point display");
  p.respond(() => reply(200, [{ mood_score: 5, scale_max: 5, created_at: "2026-11-03T12:00:00+03:00" }]));
  await p.run("loadMoodHistory()"); assert.equal(viewport.hidden, false);
  assert.equal(walk(viewport).filter(n => n.tagName === "svg").length,1);
  assert.equal(p.context.window.enwenMoodChart.score({mood_score:4,scale_max:5}),8);
  assert.equal(p.run("historyEntries[0].scale_max"),5);
  checks.push("legacy history converts proportionally without rewriting raw records");
  p = page({ app: true }); await p.login();
  p.elements["mood-form"].querySelector = () => ({ value: "10" });
  p.elements["mood-note"].value = "Fictional form check";
  p.respond((url, options) => url === "/moods" && options.method === "POST"
    ? reply(201, { mood_score: 10, scale_max: 10, created_at: "2026-11-04T12:00:00+03:00" }) : p.baseline(url, options));
  await p.elements["mood-form"].fire("submit"); await tick();
  const moodPost = p.calls.find(c => c.url === "/moods" && c.options.method === "POST");
  assert.deepEqual(JSON.parse(moodPost.options.body), { mood_score: 10, scale_max: 10, note: "Fictional form check", contexts: [] });
  checks.push("actual form handler submits an explicitly labelled 10-point score");

  p = page({app:true}); await p.login();
  p.context.window.enwenMoodInsights={selection:()=>['exams','finances']};
  p.elements['mood-form'].querySelector=()=>({value:'7'});
  p.elements['mood-note'].value='Keep my unsaved day';let moodResets=0;
  p.elements['mood-form'].reset=()=>{moodResets++;};
  p.respond((url,options)=>url==='/moods'&&options.method==='POST'?reply(503,{detail:'Synthetic save failure'}):p.baseline(url,options));
  await p.elements['mood-form'].fire('submit');
  const failedMood=p.calls.find(c=>c.url==='/moods'&&c.options.method==='POST');
  assert.deepEqual(JSON.parse(failedMood.options.body).contexts,['exams','finances']);
  assert.equal(p.elements['mood-note'].value,'Keep my unsaved day');assert.equal(moodResets,0);
  checks.push('structured factors submitted and unsaved draft preserved when mood save fails');

  p = page({app:true}); await p.login();
  const fullHistory = Array.from({length:101}, (_, i) => ({mood_id: "mood-"+i, mood_score: 5, scale_max: i < 40 ? 10 : 5, created_at: new Date(Date.UTC(2026,10,5,12,0)-i*86400000).toISOString()}));
  p.respond((url, options) => url.startsWith("/moods") ? reply(200, url.includes("offset=100") ? fullHistory.slice(100) : fullHistory.slice(0,100)) : p.baseline(url,options));
  await p.run("loadMoodHistory()");
  assert.equal(p.calls.filter(call=>call.url.startsWith("/moods")).length,2);
  assert.equal(p.elements["mood-history-list"].children.length,20);
  assert.equal(walk(p.root).filter(n=>n.tagName==="circle").length,101);
  await p.elements["history-next"].fire("click"); assert.equal(p.run("historyOffset"),20);
  await p.elements["history-prev"].fire("click"); assert.equal(p.run("historyOffset"),0);
  checks.push("complete multi-page history is charted while the dated list stays paginated");

  console.log(JSON.stringify({ passed: checks.length, checks, scope: "Synthetic DOM/API; no real account, journal or database was changed." }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
