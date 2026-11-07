const assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname,"../frontend/contact_setup.js"),"utf8");
const reply = (status,data) => ({status,ok:status>=200&&status<300,json:async()=>data});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function page() {
  const ids=["contact-setup-panel","contact-setup-form","contact-setup-fields","setup-contact-name","setup-contact-relationship","setup-contact-email","contact-setup-notice","contact-setup-ack","contact-setup-message","contact-setup-retry"];
  const nodes=Object.fromEntries(ids.map(id=>[id,{value:"",textContent:"",checked:false,disabled:false,hidden:false,handlers:{},classList:{toggle(){}},addEventListener(type,fn){this.handlers[type]=fn;},
    reset(){for(const name of ["setup-contact-name","setup-contact-email","setup-contact-relationship"])nodes[name].value="";nodes["contact-setup-ack"].checked=false;},
    reportValidity(){return nodes["contact-setup-ack"].checked;}}]));
  const calls=[];let refreshed=0;
  let responder=()=>reply(200,{version:"contact-test-1",text:"Current consent notice",delivery_mode:"simulation_only"});
  const ctx=vm.createContext({document:{getElementById:id=>nodes[id]},window:{},accessToken:"synthetic-token",AbortController,setTimeout,clearTimeout,
    fetch:async(url,options)=>{calls.push({url,options});return responder(url,options);},
    loadTrustedContact:async()=>{refreshed++;},endSession(){ctx.window.enwenContactSetup.reset();ctx.accessToken=null;},pauseWellnessFeatures(){}});
  vm.runInContext(source,ctx);
  const p={ctx,nodes,calls,respond:fn=>responder=fn,refreshed:()=>refreshed,
    submit:()=>nodes["contact-setup-form"].handlers.submit({preventDefault(){}}),
    fill(){nodes["setup-contact-name"].value=" Fictional Friend ";nodes["setup-contact-email"].value="friend@example.com";nodes["setup-contact-relationship"].value="Friend";nodes["contact-setup-ack"].checked=true;}};
  await ctx.window.enwenContactSetup.show();return p;
}
(async()=>{
  const checks=[];let p=await page();
  assert.equal(p.calls.length,1);assert.equal(p.nodes["contact-setup-fields"].disabled,false);assert.equal(p.nodes["contact-setup-panel"].hidden,false);
  await p.submit();assert.equal(p.calls.length,1);checks.push("contact setup loads the real notice and requires explicit acknowledgement");
  p.fill();let finish;
  p.respond(()=>new Promise(resolve=>{finish=()=>resolve(reply(201,{contact_id:"new-id",confirmation_status:"pending"}));}));
  const sending=p.submit();await tick();await p.submit();assert.equal(p.calls.filter(c=>c.options.method==="POST").length,1);
  assert.deepEqual(JSON.parse(p.calls.at(-1).options.body),{trusted_contact:{full_name:"Fictional Friend",relationship_label:"Friend",email:"friend@example.com"},contact_consent_accepted:true,contact_consent_version:"contact-test-1"});
  finish();await sending;assert.equal(p.refreshed(),1);assert.equal(p.nodes["contact-setup-panel"].hidden,true);checks.push("one complete payload saves once and reloads the new pending contact");
  p=await page();p.fill();p.respond(()=>reply(503,{}));await p.submit();assert.equal(p.nodes["setup-contact-name"].value," Fictional Friend ");assert.match(p.nodes["contact-setup-message"].textContent,/could not confirm/i);checks.push("uncertain save preserves the draft and asks for a status refresh");
  p=await page();p.fill();p.respond(()=>reply(409,{detail:"Notice changed"}));await p.submit();assert.equal(p.nodes["contact-setup-ack"].checked,false);assert.equal(p.nodes["contact-setup-fields"].disabled,true);assert.equal(p.nodes["contact-setup-retry"].hidden,false);checks.push("conflict requires current notice and fresh acknowledgement");
  p=await page();p.fill();p.respond(()=>reply(403,{detail:"Consent required"}));await p.submit();assert.equal(p.nodes["contact-setup-fields"].disabled,true);checks.push("expired wellness permission disables setup");
  p=await page();p.fill();let complete;p.respond(()=>new Promise(resolve=>{complete=()=>resolve(reply(201,{contact_id:"old-id",confirmation_status:"pending"}));}));const pending=p.submit();await tick();p.ctx.window.enwenContactSetup.reset();p.ctx.accessToken="another-token";complete();await pending;assert.equal(p.refreshed(),0);assert.equal(p.nodes["setup-contact-email"].value,"");checks.push("old-session saves cannot populate another student's screen");
  p=await page();p.ctx.window.enwenContactSetup.reset();p.respond(()=>reply(503,{}));await p.ctx.window.enwenContactSetup.show();assert.equal(p.nodes["contact-setup-fields"].disabled,true);assert.equal(p.nodes["contact-setup-retry"].hidden,false);checks.push("missing notice keeps setup disabled and offers retry");
  console.log(JSON.stringify({passed:checks.length,checks,scope:"Synthetic requests only; no contact created"},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
