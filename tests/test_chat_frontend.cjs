// Isolated browser-like checks. No real chat records, AI requests or alerts.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const code = fs.readFileSync(path.join(__dirname, "../frontend/chat.js"), "utf8");
const tick = () => new Promise(resolve => setImmediate(resolve));
const uid = "11111111-1111-4111-8111-111111111111";
const cid = "22222222-2222-4222-8222-222222222222";
const other = "33333333-3333-4333-8333-333333333333";
const notice = {notice_version:"current-local",notice_text:"Synthetic local processing notice",consent_label:"Synthetic acknowledgement",configured:true,local:true};
const support = {level:"urgent",event_id:"synthetic-safety",message:"Synthetic support",resources:[],alert:{status:"not_requested",message:"No alert requested"}};
const response = (status, data) => ({status,ok:status>=200&&status<300,json:async()=>data});
const summary = (id=cid) => ({conversation_id:id,title:"Synthetic saved conversation",created_at:"2026-11-06T10:00:00Z",updated_at:"2026-11-06T10:00:00Z",safety_paused:false});
const saved = (id=cid) => ({...summary(id),messages:[{role:"user",content:"Earlier synthetic question",turn_id:other,status:"complete"},{role:"assistant",content:"Earlier synthetic reply",turn_id:other,status:"complete",sources:[]}],has_more:false,turn_count:1,turn_offset:0});
function page({selection=null}={}) {
  const nodes={}, calls=[], safetyCalls=[], storage=new Map(), events={}; let serial=0, active=false, confirm=true;
  if(selection)storage.set("enwen.chat.conversation."+uid,selection);
  class Node {
    constructor(tag="div"){this.tagName=tag;this.children=[];this.handlers={};this.attrs={};this.value="";this.checked=false;this.disabled=false;this.textContent="";this.hidden=false;this.classList={toggle(){}};}
    append(...children){for(const child of children){if(child.tagName==="fragment")this.append(...child.children);else this.children.push(child);}}
    replaceChildren(...children){this.children=[];this.append(...children);}
    addEventListener(name,handler){(this.handlers[name]||=[]).push(handler);}
    setAttribute(name,value){this.attrs[name]=value;}
    getAttribute(name){return this.attrs[name] ?? null;}
    removeAttribute(name){delete this.attrs[name];}
    focus(){this.focused=true;}
    querySelectorAll(tag){return this.children.flatMap(node=>[...(node.tagName===tag?[node]:[]),...node.querySelectorAll(tag)]);}
    reset(){nodes["chat-input"].value="";nodes["chat-consent"].checked=false;}
    async fire(name){for(const handler of this.handlers[name]||[])await handler({preventDefault(){}});}
    set innerHTML(value){throw new Error("HTML injection forbidden");}
  }
  const ids=["chat-form","chat-fields","chat-input","chat-messages","chat-status","chat-consent","chat-history-list","chat-history-message","chat-history-prev","chat-history-next","chat-history-refresh","chat-clear","chat-support","chat-active-title","chat-notice","chat-consent-label","chat-manage","chat-rename","chat-delete","chat-rename-form","chat-name","chat-name-save","chat-name-cancel"];
  for(const id of ids)nodes[id]=new Node(id.includes("list")?"ul":id.includes("form")?"form":"div");
  let responder=(url,options)=>{
    if(url==="/chat/notice")return response(200,notice);
    if(url.startsWith("/chat/conversations?"))return response(200,[]);
    if(url.startsWith("/chat/conversations/"))return response(200,saved(url.split("/")[3].split("?")[0]));
    if(url==="/safety/support")return response(200,support);
    if(url==="/chat")return response(200,{reply:"Synthetic AI reply",sources:[],conversation_id:cid,turn_id:other,request_id:JSON.parse(options.body).request_id,history_saved:true,safety:null});
    throw new Error("Unexpected endpoint "+url);
  };
  const window={confirm(){return confirm;},crypto:{randomUUID(){return "44444444-4444-4444-8444-"+String(++serial).padStart(12,"0");}},
    sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},
    enwenSafety:{show(data){active=true;safetyCalls.push(data);nodes["chat-fields"].disabled=true;},reset(){active=false;},active(){return active;}}};
  const context=vm.createContext({document:{getElementById:id=>nodes[id],createElement:tag=>new Node(tag),createDocumentFragment:()=>new Node("fragment")},window,
    accessToken:"synthetic-access",URL,AbortController,setTimeout,clearTimeout,
    fetch:async(url,options={})=>{calls.push({url,options});return responder(url,options);},
    endSession(){window.enwenChat.reset();context.accessToken=null;}});
  vm.runInContext(code,context);
  return {nodes,calls,safetyCalls,storage,context,api:window.enwenChat,
    baseline:(url,options)=>{if(url==="/chat/notice")return response(200,notice);if(url.startsWith("/chat/conversations?"))return response(200,[]);if(url.startsWith("/chat/conversations/"))return response(200,saved());if(url==="/safety/support")return response(200,support);throw new Error("No baseline "+url);},
    respond(fn){responder=fn;},confirm(value){confirm=value;},
    async setup(){await window.enwenChat.setup({user_id:uid,wellness_consent_current:true});await tick();},
    async send(text="Synthetic student message",ack=true){nodes["chat-input"].value=text;nodes["chat-consent"].checked=ack;await nodes["chat-form"].fire("submit");await tick();},
    async click(id){await nodes[id].fire("click");await tick();}};
}
const texts=node=>[node.textContent,...node.children.map(texts)].join(" ");
(async()=>{
  const checks=[];
  let p=page();await p.setup();await p.send();
  let send=p.calls.find(call=>call.url==="/chat"), body=JSON.parse(send.options.body);
  assert.equal(body.messages.length,1);assert.equal(body.messages[0].role,"user");assert.match(body.request_id,/^44444444-/);
  assert.equal(p.storage.get("enwen.chat.conversation."+uid),cid);assert.equal(p.nodes["chat-input"].value,"");
  assert.ok(texts(p.nodes["chat-messages"]).includes("Synthetic AI reply"));
  assert.ok(![...p.storage.values()].some(value=>value.includes("Synthetic")));
  checks.push("successful message sends only latest text with secure UUID and stores only conversation selection");

  p=page({selection:cid});await p.setup();assert.ok(texts(p.nodes["chat-messages"]).includes("Earlier synthetic reply"));
  assert.equal(p.nodes["chat-fields"].disabled,false);checks.push("refresh restores owner-checked conversation from private history");

  p=page({selection:cid});p.respond((url,options)=>url.startsWith("/chat/conversations/")?response(404,{detail:"Not found"}):p.baseline(url,options));await p.setup();
  assert.equal(p.storage.has("enwen.chat.conversation."+uid),false);assert.equal(p.nodes["chat-fields"].disabled,false);
  checks.push("unknown or another owner's saved selection is cleared without leaking history");

  p=page();await p.setup();p.nodes["chat-input"].value="Keep my unsaved draft";p.confirm(false);const before=p.calls.length;await p.api.openConversation(cid);
  assert.equal(p.calls.length,before);assert.equal(p.nodes["chat-input"].value,"Keep my unsaved draft");checks.push("declining a history switch preserves draft and avoids request");

  p=page();await p.setup();let attempt=0;
  p.respond((url,options)=>url==="/chat"?(attempt++,response(503,{detail:"Synthetic uncertain attempt"})):p.baseline(url,options));
  await p.send("Keep this exact attempt");await p.send("Keep this exact attempt");
  const ids=p.calls.filter(call=>call.url==="/chat").map(call=>JSON.parse(call.options.body).request_id);
  assert.equal(ids[0],ids[1]);assert.equal(attempt,2);assert.equal(p.nodes["chat-input"].value,"Keep this exact attempt");
  checks.push("manual retry of unchanged uncertain draft reuses UUID and retains draft without auto retry");

  p=page();await p.setup();p.respond((url,options)=>url==="/chat"?response(403,{detail:"Read the processing notice"}):p.baseline(url,options));
  await p.send("Synthetic ordinary question",false);assert.equal(p.nodes["chat-input"].value,"Synthetic ordinary question");assert.equal(p.nodes["chat-fields"].disabled,false);
  assert.equal(JSON.parse(p.calls.find(call=>call.url==="/chat").options.body).external_ai_consent,false);
  checks.push("unchecked acknowledgement reaches backend and ordinary rejection preserves draft for agreement");

  p=page();p.respond((url,options)=>url==="/chat/notice"?response(200,{...notice,configured:false}):url==="/chat"?response(200,{reply:"Synthetic support response",sources:[],safety:support,history_saved:false}):p.baseline(url,options));await p.setup();
  await p.send("Synthetic urgent test message",false);assert.equal(p.safetyCalls.length,1);assert.equal(p.nodes["chat-fields"].disabled,true);
  assert.ok(p.nodes["chat-status"].textContent.includes("not saved"));checks.push("urgent backend response is shown even without AI readiness or processing agreement and never claims a save");

  await p.click("chat-clear");assert.equal(p.nodes["chat-fields"].disabled,false);assert.equal(p.safetyCalls.length,1);checks.push("explicit New conversation clears support lock without deleting saved history");

  p=page();await p.setup();p.respond((url,options)=>url.startsWith("/chat/conversations/")?response(200,{...saved(),safety_paused:true,messages:[{role:"assistant",content:"Synthetic saved support",safety:support,turn_id:other,status:"crisis"}]}):p.baseline(url,options));
  await p.api.openConversation(cid);assert.equal(p.nodes["chat-fields"].disabled,true);assert.equal(p.safetyCalls.length,1);checks.push("reopening a saved paused conversation restores support panel and keeps composer locked");

  p=page();await p.setup();await p.click("chat-support");assert.equal(p.nodes["chat-fields"].disabled,true);assert.equal(p.calls.filter(call=>call.url==="/chat").length,0);
  assert.ok(p.nodes["chat-status"].textContent.includes("No alert was requested"));await p.api.openConversation(cid);assert.equal(p.nodes["chat-fields"].disabled,true);
  await p.click("chat-clear");assert.equal(p.nodes["chat-fields"].disabled,false);checks.push("manual help sends no alert and remains paused across history selection until New conversation");

  p=page();await p.setup();let resolve;
  p.respond((url,options)=>url==="/chat"?new Promise(done=>{resolve=()=>done(response(200,{reply:"Late normal reply",sources:[],conversation_id:cid,turn_id:other,history_saved:true}));}):p.baseline(url,options));
  const pending=p.send("Synthetic in-flight message");await tick();await p.click("chat-support");resolve();await pending;
  assert.equal(p.nodes["chat-fields"].disabled,true);assert.ok(!texts(p.nodes["chat-messages"]).includes("Late normal reply"));checks.push("late normal reply cannot overwrite human-support mode or re-enable composer");

  p=page();await p.setup();p.respond((url,options)=>url==="/chat"?new Promise(done=>{resolve=()=>done(response(200,{reply:"Old user's reply",sources:[],conversation_id:cid,turn_id:other,history_saved:true}));}):p.baseline(url,options));
  const old=p.send("Old user's synthetic question");await tick();p.api.reset();p.context.accessToken="another-session";resolve();await old;
  assert.equal(p.nodes["chat-messages"].children.length,0);assert.equal(p.nodes["chat-fields"].disabled,true);checks.push("logout invalidates late responses and clears private transcript and selected conversation");

  p=page();await p.setup();p.respond((url,options)=>url==="/chat"?response(200,{reply:'<img src=x onerror="bad()">',sources:[{title:"Synthetic",publisher:"Test",url:"javascript:bad()"}],conversation_id:cid,turn_id:other,history_saved:true}):p.baseline(url,options));
  await p.send();assert.ok(texts(p.nodes["chat-messages"]).includes('<img src=x onerror="bad()">'));
  assert.equal(p.nodes["chat-messages"].querySelectorAll("a").length,0);checks.push("model markup remains plain text and unsafe resource links are not created");

  p=page();await p.setup();p.context.window.crypto={};await p.send();assert.equal(p.calls.filter(call=>call.url==="/chat").length,0);
  assert.ok(p.nodes["chat-status"].textContent.includes("secure message identifier"));checks.push("missing secure UUID support fails before any message request");

  p=page();await p.setup();p.respond((url,options)=>{
    if(!url.startsWith("/chat/conversations/"))return p.baseline(url,options);
    return url.endsWith("offset=0")?response(200,{...saved(),messages:[{role:"user",content:"First history page",turn_id:other,status:"complete"}],turn_count:100,has_more:true})
      :response(200,{...saved(),messages:[{role:"assistant",content:"Final history page",turn_id:cid,status:"complete"}],turn_count:1,has_more:false,turn_offset:100});
  });await p.api.openConversation(cid);assert.ok(texts(p.nodes["chat-messages"]).includes("Final history page"));
  assert.ok(p.calls.some(call=>call.url.endsWith("offset=100")));checks.push("conversation history loads all turn pages before rendering");

  p=page();await p.setup();assert.equal(p.nodes["chat-manage"].hidden,true);await p.api.openConversation(cid);
  assert.equal(p.nodes["chat-manage"].hidden,false);await p.click("chat-rename");
  assert.equal(p.nodes["chat-rename-form"].hidden,false);assert.equal(p.nodes["chat-name"].focused,true);
  p.nodes["chat-name"].value="Unsaved new name";const renameBefore=p.calls.length;await p.click("chat-name-cancel");
  assert.equal(p.calls.length,renameBefore);assert.equal(p.nodes["chat-rename-form"].hidden,true);
  checks.push("management appears only for saved conversations and cancelling rename changes nothing");

  p.nodes["chat-input"].value="Keep my journal-like draft";
  await p.click("chat-rename");p.nodes["chat-name"].value="  My   exam week 🌷 ";
  p.respond((url,options)=>options.method==="PATCH"?response(200,{...summary(),title:JSON.parse(options.body).title}):p.baseline(url,options));
  await p.nodes["chat-rename-form"].fire("submit");await tick();
  assert.equal(p.nodes["chat-active-title"].textContent,"My exam week 🌷");assert.equal(p.nodes["chat-input"].value,"Keep my journal-like draft");
  assert.ok(texts(p.nodes["chat-messages"]).includes("Earlier synthetic reply"));assert.equal(p.nodes["chat-fields"].disabled,false);
  checks.push("rename saves normalised Unicode name while preserving transcript and unsent draft");

  await p.click("chat-rename");p.nodes["chat-name"].value="  ";const blankBefore=p.calls.length;await p.nodes["chat-rename-form"].fire("submit");
  assert.equal(p.calls.length,blankBefore);assert.match(p.nodes["chat-status"].textContent,/1 and 80/);
  checks.push("blank names rejected before any network request");

  p=page({selection:cid});await p.setup();await p.click("chat-rename");p.nodes["chat-name"].value="Keep this requested name";
  p.respond((url,options)=>options.method==="PATCH"?Promise.reject(new TypeError("Disconnected")):p.baseline(url,options));
  await p.nodes["chat-rename-form"].fire("submit");assert.equal(p.nodes["chat-rename-form"].hidden,false);
  assert.equal(p.nodes["chat-name"].value,"Keep this requested name");assert.equal(p.nodes["chat-active-title"].textContent,"Synthetic saved conversation");
  assert.equal(p.calls.filter(call=>call.options.method==="PATCH").length,1);assert.match(p.nodes["chat-status"].textContent,/could not be confirmed/);
  checks.push("uncertain rename retains requested name and never retries automatically");

  p=page({selection:cid});await p.setup();p.nodes["chat-input"].value="Please keep my draft";p.confirm(false);const deleteBefore=p.calls.length;await p.click("chat-delete");
  assert.equal(p.calls.length,deleteBefore);assert.equal(p.nodes["chat-input"].value,"Please keep my draft");assert.equal(p.storage.get("enwen.chat.conversation."+uid),cid);
  checks.push("declining deletion preserves selected conversation and makes no request");

  p.confirm(true);p.respond((url,options)=>options.method==="DELETE"?response(204,null):p.baseline(url,options));await p.click("chat-delete");
  assert.equal(p.nodes["chat-messages"].children.length,0);assert.equal(p.nodes["chat-input"].value,"Please keep my draft");
  assert.equal(p.storage.has("enwen.chat.conversation."+uid),false);assert.equal(p.nodes["chat-manage"].hidden,true);assert.equal(p.nodes["chat-fields"].disabled,false);
  assert.equal(p.calls.filter(call=>call.url==="/chat").length,0);checks.push("confirmed deletion clears selected saved text but retains draft without sending it");

  p=page({selection:cid});await p.setup();p.respond((url,options)=>options.method==="DELETE"?response(409,{detail:"Still processing"}):p.baseline(url,options));await p.click("chat-delete");
  assert.ok(texts(p.nodes["chat-messages"]).includes("Earlier synthetic reply"));assert.equal(p.storage.get("enwen.chat.conversation."+uid),cid);
  assert.match(p.nodes["chat-status"].textContent,/Still processing/);checks.push("pending-message refusal keeps visible transcript and selection");

  p=page({selection:cid});await p.setup();p.nodes["chat-input"].value="Keep this draft too";
  p.respond((url,options)=>options.method==="DELETE"?Promise.reject(new TypeError("Disconnected")):p.baseline(url,options));await p.click("chat-delete");
  assert.ok(texts(p.nodes["chat-messages"]).includes("Earlier synthetic reply"));assert.equal(p.nodes["chat-input"].value,"Keep this draft too");
  assert.equal(p.calls.filter(call=>call.options.method==="DELETE").length,1);assert.match(p.nodes["chat-status"].textContent,/could not be confirmed/);
  checks.push("uncertain deletion keeps draft and transcript with no automatic retry or false success");

  p=page({selection:cid});await p.setup();p.respond((url,options)=>options.method==="DELETE"?response(200,{unexpected:true}):p.baseline(url,options));await p.click("chat-delete");
  assert.ok(texts(p.nodes["chat-messages"]).includes("Earlier synthetic reply"));assert.match(p.nodes["chat-status"].textContent,/could not be confirmed/);
  checks.push("unexpected success payload does not falsely clear saved history");

  p=page({selection:cid});await p.setup();p.respond((url,options)=>options.method==="DELETE"?response(404,{detail:"Not found"}):p.baseline(url,options));await p.click("chat-delete");
  assert.equal(p.nodes["chat-messages"].children.length,0);assert.equal(p.storage.has("enwen.chat.conversation."+uid),false);
  checks.push("manual retry after already-removed conversation safely clears stale selection");

  p=page();p.respond((url,options)=>url.startsWith("/chat/conversations/")?response(200,{...saved(),safety_paused:true,messages:[{role:"assistant",content:"Synthetic support",safety:support,status:"crisis",turn_id:other}]})
    :options.method==="DELETE"?response(204,null):p.baseline(url,options));
  await p.setup();await p.api.openConversation(cid);
  p.respond((url,options)=>options.method==="DELETE"?response(204,null):p.baseline(url,options));await p.click("chat-delete");
  assert.equal(p.nodes["chat-messages"].children.length,0);assert.equal(p.nodes["chat-fields"].disabled,true);assert.equal(p.safetyCalls.length,1);
  assert.match(p.nodes["chat-status"].textContent,/Human-support options stay open/);checks.push("deleting a paused transcript keeps human-support mode open");

  p=page({selection:cid});await p.setup();let resolveDelete;
  p.respond((url,options)=>options.method==="DELETE"?new Promise(done=>{resolveDelete=()=>done(response(204,null));}):p.baseline(url,options));
  const removing=p.click("chat-delete");await tick();const mutateBefore=p.calls.length;await p.click("chat-delete");await p.api.openConversation(other);await p.send("Blocked while deleting");
  assert.equal(p.calls.length,mutateBefore);assert.equal(p.nodes["chat-fields"].disabled,true);
  await p.click("chat-support");resolveDelete();await removing;
  assert.equal(p.nodes["chat-fields"].disabled,true);assert.equal(p.safetyCalls.length,1);
  checks.push("mutation prevents duplicate deletion, switching and sending while human help stays accessible");

  p=page({selection:cid});await p.setup();p.respond((url,options)=>options.method==="DELETE"?new Promise(done=>{resolveDelete=()=>done(response(204,null));}):p.baseline(url,options));
  const logoutDelete=p.click("chat-delete");await tick();p.api.reset();p.context.accessToken="another-session";resolveDelete();await logoutDelete;
  assert.equal(p.nodes["chat-messages"].children.length,0);assert.equal(p.nodes["chat-status"].textContent,"");assert.equal(p.nodes["chat-manage"].hidden,true);
  checks.push("late deletion response after logout cannot alter the next account screen");

  p=page({selection:cid});await p.setup();await p.click("chat-rename");p.nodes["chat-name"].value='<img src=x onerror="bad()">';
  p.respond((url,options)=>options.method==="PATCH"?response(200,{...summary(),title:JSON.parse(options.body).title}):p.baseline(url,options));
  await p.nodes["chat-rename-form"].fire("submit");assert.equal(p.nodes["chat-active-title"].textContent,'<img src=x onerror="bad()">');
  assert.equal(p.nodes["chat-active-title"].children.length,0);checks.push("renamed markup is rendered as plain text");

  p=page();await p.setup();let finishUrgent;
  p.respond((url,options)=>url==='/chat/screen'?response(200,{urgent:true,support}):url==='/chat'?new Promise(resolve=>finishUrgent=()=>resolve(response(200,{reply:'Synthetic help',safety:support,history_saved:true,conversation_id:cid,turn_id:other}))):p.baseline(url,options));
  const urgentPending=p.send('Fictional test: I want to swallow poison');await tick();
  assert.equal(p.safetyCalls.length,1);assert.equal(p.nodes['chat-fields'].disabled,true);assert.ok(finishUrgent);
  finishUrgent();await urgentPending;assert.equal(p.safetyCalls.length,2);
  checks.push('human support appears before the chat and notification request completes');
  p=page();await p.setup();
  p.respond((url,options)=>url==='/chat/screen'?response(200,{urgent:true,support}):url==='/chat'?response(503,{detail:'Synthetic recording failure'}):p.baseline(url,options));
  await p.send('Fictional urgent test');assert.equal(p.nodes['chat-fields'].disabled,true);assert.equal(p.safetyCalls.at(-1).alert.status,'uncertain');
  checks.push('failed contact request replaces pending status with uncertainty while support stays open');

  console.log(JSON.stringify({passed:checks.length,checks,scope:"Synthetic DOM/API only; no private records, AI requests or notifications."},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
