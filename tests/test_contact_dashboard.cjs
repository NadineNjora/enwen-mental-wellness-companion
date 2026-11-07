// Node's built-in runner; synthetic DOM and API, no accounts or emails changed.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../frontend/trusted-contact.js"), "utf8");
const html = fs.readFileSync(path.join(__dirname, "../frontend/index.html"), "utf8");
const tick = () => new Promise(resolve => setImmediate(resolve));
const reply = (status, data) => ({ status, ok: status >= 200 && status < 300, json: async () => data });
const contact = {
  full_name: "Fictional Friend", email: "friend@example.com", relationship_label: "Friend",
  confirmation_status: "pending", delivery_mode: "local_test", live_notifications_enabled: false,
  can_invite: true, retry_after_seconds: 0, latest_invitation: null,
};
const notice = { notice_version: "local-invite-1", text: "Fictional local test.", delivery_mode: "local_test" };
const baseline = url => reply(200, url.endsWith("invitation-notice") ? notice : contact);

async function page(responder = baseline) {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(new Set(ids).size, ids.length, "No duplicate HTML ids");
  const elements = Object.fromEntries(ids.map(id => [id, {
    textContent: "", disabled: false, checked: false, hidden: false, dataset: {}, handlers: {},
    classList: { toggle() {} },
    removeAttribute(name) { if (name === "data-state") delete this.dataset.state; },
    addEventListener(type, fn) { this.handlers[type] = fn; },
    reset() { elements["contact-test-ack"].checked = false; },
    reportValidity() { return elements["contact-test-ack"].checked; },
  }]));
  const calls = [], timers = new Map();
  let timer = 0;
  const ctx = vm.createContext({
    accessToken: "synthetic-token", AbortController, Date,
    setTimeout(fn, delay) { timers.set(++timer, { fn, delay }); return timer; },
    clearTimeout(id) { timers.delete(id); },
    document: { getElementById(id) { assert.ok(elements[id], id); return elements[id]; } },
    window: { addEventListener() {} }, location: { hash: "#/trusted-contact" },
    fetch: async (url, options) => { calls.push({ url, options }); return responder(url, options); },
    endSession() { vm.runInContext("resetTrustedContactPanel(); accessToken = null;", ctx); },
  });
  vm.runInContext(source, ctx);
  vm.runInContext("setupTrustedContactPanel()", ctx);
  await tick();
  return { elements, calls, timers, ctx,
    ack() { elements["contact-test-ack"].checked = true; elements["contact-test-ack"].handlers.change(); },
    submit() { return elements["contact-invite-form"].handlers.submit({ preventDefault() {} }); },
  };
}

(async () => {
  const checks = [];
  let p = await page();
  assert.match(p.elements["contact-home-status"].textContent, /Fictional Friend/);
  assert.equal(p.calls.length, 2);
  assert.equal(p.elements["contact-send"].disabled, true);
  await p.submit();
  assert.equal(p.calls.length, 2);
  p.ack(); assert.equal(p.elements["contact-send"].disabled, false);
  checks.push("status loads without sending; explicit acknowledgement required");

  let sent = false, finishSend;
  p = await page((url, options) => {
    if (options.method === "POST") return new Promise(resolve => { finishSend = () => {
      sent = true; resolve(reply(201, { invitation_id: "fake", delivery_mode: "local_test" }));
    }; });
    return url.endsWith("invitation-notice") ? reply(200, notice) : reply(200, sent
      ? { ...contact, can_invite: false, retry_after_seconds: 60, latest_invitation: {
        status: "awaiting_response", expires_at: "2030-01-01T00:00:00Z",
      } } : contact);
  });
  p.ack(); const sending = p.submit(); await tick(); await p.submit();
  assert.equal(p.calls.filter(c => c.options.method === "POST").length, 1);
  finishSend(); await sending;
  const posted = JSON.parse(p.calls.find(c => c.options.method === "POST").options.body);
  assert.deepEqual(posted, { notice_version: "local-invite-1", test_only_acknowledged: true });
  assert.equal(p.elements["contact-send"].disabled, true);
  assert.equal(p.elements["contact-test-ack"].checked, false);
  assert.match(p.elements["contact-invitation-summary"].textContent, /waiting in the local inbox/);
  assert.equal(p.elements["contact-replacement-note"].hidden, false);
  checks.push("send payload correct; double click blocked; cooldown and replacement warning shown");

  for (const state of ["confirmed", "declined", "revoked"]) {
    p = await page(() => reply(200, { ...contact, confirmation_status: state, can_invite: false }));
    assert.equal(p.elements["contact-invite-form"].hidden, true);
    assert.equal(p.elements["contact-send"].disabled, true);
    checks.push(state + " disables invitations");
  }

  p = await page(() => reply(404, { detail: "No contact" }));
  assert.match(p.elements["contact-message"].textContent, /Add your trusted person/);
  assert.equal(p.elements["contact-invite-form"].hidden, true);
  checks.push("older accounts show an explanation without changing their data");

  p = await page(() => reply(401, { detail: "Expired" }));
  assert.equal(p.ctx.accessToken, null);
  assert.equal(p.elements["contact-name"].textContent, "");
  checks.push("expired session clears contact details");

  let resolveOld;
  p = await page(() => new Promise(resolve => { resolveOld = resolve; }));
  vm.runInContext("resetTrustedContactPanel(); accessToken = null", p.ctx);
  resolveOld(reply(200, contact)); await tick();
  assert.equal(p.elements["contact-name"].textContent, "");
  assert.equal(p.elements["contact-details"].hidden, true);
  checks.push("late responses cannot repopulate a logged-out session");

  p = await page(url => url.endsWith("invitation-notice") ? reply(503, {}) : reply(200, contact));
  assert.equal(p.elements["contact-send"].disabled, true);
  assert.equal(p.elements["contact-refresh"].disabled, false);
  checks.push("notice failure blocks sending and allows refresh");

  p = await page(url => url.endsWith("invitation-notice") ? reply(200, notice)
    : reply(200, { ...contact, can_invite: false, invitation_block_reason: "Use @example.com only" }));
  p.ack(); assert.equal(p.elements["contact-send"].disabled, true);
  assert.match(p.elements["contact-message"].textContent, /@example.com/);
  checks.push("server eligibility and blocked-delivery explanation respected");

  p = await page((url, options) => options.method === "POST"
    ? Promise.reject(new TypeError("offline")) : baseline(url));
  p.ack(); await p.submit();
  assert.equal(p.calls.filter(c => c.options.method === "POST").length, 1);
  assert.match(p.elements["contact-send-message"].textContent, /No automatic resend/);
  assert.equal(p.elements["contact-test-ack"].checked, false);
  checks.push("uncertain delivery prompts verification; no automatic resend");

  console.log(JSON.stringify({ passed: checks.length, checks }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
