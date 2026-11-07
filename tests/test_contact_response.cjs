const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "../frontend/contacts_response.html"), "utf8");
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(source);
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
assert.equal(new Set(ids).size, ids.length);
const notice = { notice_version: "local-invite-1", text: "Fictional local test only.", delivery_mode: "local_test" };
const response = (code, data) => ({ ok: code >= 200 && code < 300, status: code, json: async () => data });
const tick = () => new Promise(resolve => setImmediate(resolve));

async function makePage(token, responder) {
  const elements = Object.fromEntries(ids.map(id => [id, {
    textContent: "", disabled: id === "invitation-fields", checked: false,
    hidden: id === "retry-notice", handlers: {},
    classList: { toggle() {} },
    addEventListener(event, fn) { this.handlers[event] = fn; },
    reportValidity() { return elements["test-acknowledgement"].checked; },
  }]));
  const calls = [], historyCalls = [];
  const context = vm.createContext({
    document: { getElementById: id => { assert.ok(elements[id], id); return elements[id]; } },
    location: { hash: token ? "#token=" + token : "", pathname: "/static/contacts_response.html" },
    history: { replaceState: (...args) => historyCalls.push(args) },
    URLSearchParams, AbortController, setTimeout, clearTimeout,
    fetch: async (url, options) => {
      calls.push({ url, options });
      return responder(url, options, calls);
    },
  });
  vm.runInContext(source, context);
  await tick();
  return { elements, calls, historyCalls,
    submit: decision => elements["invitation-form"].handlers.submit({ preventDefault() {}, submitter: { value: decision } }),
  };
}

(async () => {
  const checks = [];
  let page = await makePage("", () => { throw Error("Must not fetch"); });
  assert.equal(page.calls.length, 0);
  assert.equal(page.elements["invitation-fields"].disabled, true);
  checks.push("missing token stays disabled and makes no API call");

  let succeed = false;
  page = await makePage("a".repeat(43), () => succeed ? response(200, notice) : Promise.reject(Error("offline")));
  assert.equal(page.elements["retry-notice"].hidden, false);
  assert.equal(page.elements["invitation-fields"].disabled, true);
  succeed = true;
  page.elements["retry-notice"].handlers.click(); await tick();
  assert.equal(page.elements["invitation-fields"].disabled, false);
  checks.push("notice failure blocks response and explicit retry works");

  for (const decision of ["accepted", "declined"]) {
    page = await makePage("a".repeat(43), (url, opts) => response(200,
      opts.method === "GET" ? notice : { decision, delivery_mode: "local_test" }));
    assert.equal(page.calls.length, 1); // Merely opening never accepts.
    assert.equal(page.historyCalls[0][2], "/static/contacts_response.html");
    page.elements["test-acknowledgement"].checked = true;
    await page.submit(decision);
    const request = page.calls[1];
    assert.deepEqual(JSON.parse(request.options.body), {
      token: "a".repeat(43), decision, notice_version: "local-invite-1", test_only_acknowledged: true,
    });
    assert.equal(request.options.credentials, "omit");
    assert.equal(request.options.cache, "no-store");
    assert.equal(page.elements["invitation-fields"].disabled, true);
    await page.submit(decision);
    assert.equal(page.calls.length, 2);
    checks.push(decision + ": correct POST, URL redacted, no automatic or repeated submission");
  }

  page = await makePage("a".repeat(43), (url, opts) => opts.method === "GET"
    ? response(200, notice) : response(410, { detail: "Already used" }));
  page.elements["test-acknowledgement"].checked = true;
  await page.submit("accepted");
  assert.equal(page.elements["invitation-fields"].disabled, true);
  assert.equal(page.elements["invitation-status"].textContent, "Already used");
  checks.push("expired or used link disables decisions");

  page = await makePage("a".repeat(43), (url, opts) => opts.method === "GET"
    ? response(200, notice) : response(409, { detail: "Notice changed" }));
  page.elements["test-acknowledgement"].checked = true;
  await page.submit("accepted");
  assert.equal(page.elements["test-acknowledgement"].checked, false);
  assert.equal(page.calls.length, 3);
  checks.push("notice change reloads text and resets acknowledgement");

  page = await makePage("a".repeat(43), (url, opts) => opts.method === "GET"
    ? response(200, notice) : Promise.reject(Error("lost response")));
  page.elements["test-acknowledgement"].checked = true;
  await page.submit("accepted");
  assert.match(page.elements["invitation-status"].textContent, /could not confirm/i);
  assert.equal(page.calls.length, 2);
  checks.push("uncertain network result is not silently retried");

  console.log(JSON.stringify({ passed: checks.length, checks, requests: "simulated; no records or messages changed" }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
