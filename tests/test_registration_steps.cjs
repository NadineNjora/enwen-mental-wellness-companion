// Two-step registration checks with synthetic DOM/API only. No accounts are created.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const html = fs.readFileSync(path.join(__dirname, "../frontend/register.html"), "utf8");
const source = fs.readFileSync(path.join(__dirname, "../frontend/register.js"), "utf8");
const inputTags = Object.fromEntries([...html.matchAll(/<input\b[^>]*\bid="([^"]+)"[^>]*>/g)].map(m => [m[1], m[0]]));
const tick = () => new Promise(resolve => setImmediate(resolve));
const reply = (status, data) => ({ status, ok: status >= 200 && status < 300, json: async () => data });
const wellness = { version: "prototype-1", text: "Synthetic wellness notice." };
const contact = { version: "contact-test-1", text: "Synthetic contact notice.", delivery_mode: "simulation_only" };
const baseline = url => reply(200, url === "/auth/consent" ? wellness : contact);

async function page(responder = baseline) {
  const tags = [...html.matchAll(/<[a-z][^>]*\bid="([^"]+)"[^>]*>/g)];
  assert.equal(new Set(tags.map(m => m[1])).size, tags.length, "Unique HTML ids");
  assert.match(html, /<form[^>]*\bnovalidate\b/);
  const elements = Object.fromEntries(tags.map(m => [m[1], {
    value: "", checked: false, textContent: "", hidden: /\bhidden\b/.test(m[0]),
    disabled: /\bdisabled\b/.test(m[0]), handlers: {}, attrs: {}, classes: new Set(),
    addEventListener(type, fn) { this.handlers[type] = fn; },
    setAttribute(name, value) { this.attrs[name] = value; },
    removeAttribute(name) { delete this.attrs[name]; },
    focus() { focused = m[1]; }, scrollIntoView() {},
    checkValidity() {
      const tag = inputTags[m[1]];
      if (!tag) return true;
      if (tag.includes('type="checkbox"')) return !tag.includes("required") || this.checked;
      if (tag.includes("required") && !this.value) return false;
      const min = tag.match(/minlength="(\d+)"/), max = tag.match(/maxlength="(\d+)"/);
      if (min && this.value.length < Number(min[1])) return false;
      if (max && this.value.length > Number(max[1])) return false;
      return !tag.includes('type="email"') || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.value);
    },
    reportValidity() { if (!this.checkValidity()) this.focus(); return this.checkValidity(); },
    reset() { for (const id of Object.keys(inputTags)) { elements[id].value = ""; elements[id].checked = false; } },
  }]));
  for (const el of Object.values(elements)) el.classList = {
    add(name) { el.classes.add(name); },
    toggle(name, on) { on ? el.classes.add(name) : el.classes.delete(name); },
  };
  let focused = null;
  const calls = [], events = {};
  const context = vm.createContext({
    document: { getElementById(id) { assert.ok(elements[id], id); return elements[id]; } },
    window: { addEventListener(type, fn) { events[type] = fn; } },
    AbortController, setTimeout, clearTimeout,
    fetch: async (url, options) => { calls.push({ url, options }); return responder(url, options); },
  });
  vm.runInContext(source, context);
  await tick();
  return { elements, calls, events, context, focused: () => focused,
    submit: () => elements["register-form"].handlers.submit({ preventDefault() {} }),
    account() {
      elements["register-name"].value = "  Preview Student  ";
      elements["register-email"].value = "student@example.com";
      elements["register-password"].value = elements["register-confirm-password"].value = "Synthetic-Password-Only";
      elements["register-consent"].checked = true;
    },
    contact() {
      elements["contact-name"].value = " Fictional Friend ";
      elements["contact-email"].value = "friend@example.com";
      elements["contact-relationship"].value = "Friend";
      elements["contact-consent"].checked = true;
    },
    posts: () => calls.filter(call => call.options.method === "POST"),
  };
}

(async () => {
  const checks = [];
  let p = await page();
  assert.equal(p.elements["account-step"].hidden, false);
  assert.equal(p.elements["contact-step"].hidden, true);
  assert.equal(p.elements["register-fields"].disabled, false);
  await p.submit();
  assert.equal(p.focused(), "register-name"); assert.equal(p.posts().length, 0);
  checks.push("starts on step 1; empty fields block advancing and never post");

  p.account(); p.elements["register-confirm-password"].value = "Different-Password";
  await p.submit(); assert.equal(p.focused(), "register-confirm-password");
  assert.equal(p.elements["contact-step"].hidden, true);
  checks.push("password mismatch stays on the account screen");

  p.account(); p.elements["register-consent"].checked = false;
  await p.submit(); assert.equal(p.posts().length, 0); assert.equal(p.focused(), "register-consent");
  checks.push("wellness acknowledgement required before step 2");

  p.account(); await p.submit();
  assert.equal(p.elements["account-step"].hidden, true); assert.equal(p.elements["contact-step"].hidden, false);
  assert.equal(p.elements["register-button"].textContent, "Create my account");
  assert.equal(p.posts().length, 0); assert.equal(p.elements["register-account-summary"].textContent, "Preview Student");
  checks.push("Continue changes screens without creating a partial account");

  p.contact(); p.elements["register-back"].handlers.click();
  assert.equal(p.elements["account-step"].hidden, false);
  assert.equal(p.elements["contact-name"].value, " Fictional Friend ");
  assert.equal(p.elements["register-password"].value, "Synthetic-Password-Only");
  await p.submit(); p.elements["edit-account"].handlers.click();
  assert.equal(p.elements["account-step"].hidden, false); await p.submit();
  checks.push("Back and Edit preserve entered details and consent choices");

  p.elements["contact-email"].value = "STUDENT@example.com";
  await p.submit(); assert.equal(p.focused(), "contact-email"); assert.equal(p.posts().length, 0);
  p.contact(); p.elements["contact-consent"].checked = false;
  await p.submit(); assert.equal(p.focused(), "contact-consent"); assert.equal(p.posts().length, 0);
  checks.push("same email and missing contact acknowledgement block saving");

  let finish;
  p = await page((url, options) => options.method === "POST" ? new Promise(resolve => {
    finish = () => resolve(reply(201, { user_id: "synthetic-id", email: "student@example.com" }));
  }) : baseline(url));
  p.account(); await p.submit(); p.contact(); const sending = p.submit(); await tick(); await p.submit();
  assert.equal(p.posts().length, 1); assert.equal(p.elements["register-fields"].disabled, true);
  assert.deepEqual(JSON.parse(p.posts()[0].options.body), {
    email: "student@example.com", display_name: "Preview Student", password: "Synthetic-Password-Only",
    consent_accepted: true, consent_version: "prototype-1",
    trusted_contact: { full_name: "Fictional Friend", relationship_label: "Friend", email: "friend@example.com" },
    contact_consent_accepted: true, contact_consent_version: "contact-test-1",
    invite_contact_by_email: false, invitation_notice_version: null,
  });
  finish(); await sending;
  assert.equal(p.elements["register-form"].hidden, true);
  assert.equal(p.elements["registration-success"].hidden, false);
  assert.equal(p.elements["registration-login-link"].hidden, false);
  assert.equal(p.elements["register-password"].value, ""); await p.submit(); assert.equal(p.posts().length, 1);
  checks.push("one complete payload only; success screen and cleared secrets; duplicate submit prevented");

  for (const [status, detail] of [[409, "This email is already registered."], [503, "Unavailable"]]) {
    p = await page((url, options) => options.method === "POST" ? reply(status, { detail }) : baseline(url));
    p.account(); await p.submit(); p.contact(); await p.submit();
    assert.equal(p.elements["account-step"].hidden, false);
    assert.equal(p.elements["register-password"].value, "");
    assert.equal(p.elements["contact-name"].value, " Fictional Friend ");
    assert.equal(p.elements["registration-check-login"].hidden, false);
    assert.equal(p.elements["registration-success"].hidden, true);
    assert.equal(p.posts().length, 1);
    checks.push(status + ": error returns to account step, preserves non-secret fields, and offers login");
  }

  p = await page((url, options) => options.method === "POST" ? reply(409, { detail: "Consent notice changed." }) : baseline(url));
  p.account(); await p.submit(); p.contact(); await p.submit();
  assert.equal(p.elements["register-consent"].checked, false);
  assert.equal(p.elements["contact-consent"].checked, false);
  assert.match(p.elements["registration-status"].textContent, /notice changed/i);
  checks.push("changed notices are reloaded and require fresh acknowledgement");

  p = await page(() => reply(503, {}));
  assert.equal(p.elements["register-fields"].disabled, true);
  assert.equal(p.elements["reload-notices"].hidden, false);
  p.account(); await p.submit(); assert.equal(p.posts().length, 0);
  checks.push("unavailable notices keep both steps blocked");

  p = await page(); p.account(); await p.submit(); p.contact();
  p.events.pageshow({ persisted: true }); await tick();
  assert.equal(p.elements["account-step"].hidden, false);
  assert.equal(p.elements["register-password"].value, "");
  assert.equal(p.elements["register-consent"].checked, false);
  checks.push("browser restore clears passwords and refreshes consent instead of resubmitting");

  p = await page((url,options)=>url==='/auth/signup-invitation-notice'?reply(200,{notice_version:'signup-invite-1',text:'Separate synthetic signup invitation choice',ready:true}):options.method==='POST'?reply(201,{user_id:'synthetic',email:'student@example.com',contact_invitation_status:'provider_accepted'}):baseline(url));
  assert.equal(p.elements['signup-invitation-ack'].checked,false);
  p.account();await p.submit();p.contact();p.elements['signup-invitation-ack'].checked=true;await p.submit();
  assert.equal(JSON.parse(p.posts()[0].options.body).invite_contact_by_email,true);
  assert.equal(JSON.parse(p.posts()[0].options.body).invitation_notice_version,'signup-invite-1');
  assert.match(p.elements['registration-status'].textContent,/submitted by email/);
  checks.push('signup invitation is separately unticked and sends only the explicit current choice');
  console.log(JSON.stringify({ passed: checks.length, checks, requests: "simulated; no database writes" }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
