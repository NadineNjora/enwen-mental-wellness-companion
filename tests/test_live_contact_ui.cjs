// Student invitation page only: fake API/DOM, no email transport.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const script=fs.readFileSync(path.join(__dirname,'../frontend/live-contacts.js'),'utf8'),html=fs.readFileSync(path.join(__dirname,'../frontend/index.html'),'utf8');
const tick=()=>new Promise(r=>setImmediate(r));
function fixture(ready=true){
 const nodes={},calls=[];let respond,confirm=true;
 class Element{
  constructor(){this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.textContent='';this.handlers={};}
  addEventListener(type,fn,options){(this.handlers[type]??=[]).push({fn,once:options?.once});}
  async fire(type){for(const h of [...this.handlers[type]||[]]){if(h.once)this.handlers[type]=this.handlers[type].filter(x=>x!==h);await h.fn({preventDefault(){}});}}
  reset(){for(const n of Object.values(nodes)){if(n!==this&&['live-contact-name','live-contact-email','live-contact-ack'].includes(n.id)){n.value='';n.checked=false;}}}
  reportValidity(){return true;}
 }
 for(const m of html.matchAll(/\bid="([^"]+)"/g)){const n=new Element();n.id=m[1];nodes[n.id]=n;}
 const response=(data,status=200)=>({status,ok:status>=200&&status<300,json:async()=>data});
 const baseline=url=>url.endsWith('/capability')?response({ready,reason:ready?'Ready':'Public address not configured',notice_version:'v1',text:'Long canonical notice',short_text:'Short invitation choice'}):url.endsWith('/alert-permission')?response({notice_version:'a1',text:'Full',short_text:'Separate check-in choice',accepted:false,delivery_enabled:true}):url==='/trusted-contact'?response({full_name:'Saved person',email:'friend@example.com'}):response(null);
 respond=(url,options)=>baseline(url);
 const context=vm.createContext({document:{getElementById:id=>nodes[id]},window:{confirm:()=>confirm,crypto:{randomUUID:()=> 'synthetic-id'}},accessToken:'synthetic-token',setTimeout,clearTimeout,AbortController,fetch:(url,options={})=>{calls.push({url,options});return respond(url,options);},endSession(){context.accessToken=null;context.window.enwenLiveContacts.reset();}});
 vm.runInContext(script,context);
 return {nodes,calls,context,ui:context.window.enwenLiveContacts,response,baseline,respond:fn=>respond=fn,setConfirm:v=>confirm=v};
}
(async()=>{
 let f=fixture(false);await f.ui.load();assert.equal(f.nodes['live-contact-fields'].disabled,false);assert.equal(f.nodes['live-contact-name'].value,'Saved person');assert.equal(f.nodes['live-contact-notice'].textContent,'Short invitation choice');
 f.nodes['live-contact-ack'].checked=true;await f.nodes['live-contact-form'].fire('submit');assert.equal(f.calls.filter(c=>c.options.method==='POST').length,0);
 f=fixture();await f.ui.load();f.nodes['live-contact-name'].value='Keep my draft';await f.ui.load();assert.equal(f.nodes['live-contact-name'].value,'Keep my draft');
 f.nodes['live-contact-ack'].checked=true;f.setConfirm(false);await f.nodes['live-contact-form'].fire('submit');assert.equal(f.calls.filter(c=>c.options.method==='POST').length,0);
 f.setConfirm(true);let finish;const dialog=f.nodes['invitation-confirm'];dialog.showModal=()=>dialog.open=true;
 const choosing=f.nodes['live-contact-form'].fire('submit');await tick();assert.equal(dialog.open,true);assert.equal(f.calls.filter(c=>c.options.method==='POST').length,0);
 f.ui.reset();f.context.accessToken='another-login';dialog.returnValue='send';await dialog.fire('close');await choosing;assert.equal(f.calls.filter(c=>c.options.method==='POST').length,0);
 f=fixture();await f.ui.load();f.nodes['live-contact-ack'].checked=true;f.respond((url,options)=>options.method==='POST'?f.response({invitation_id:'synthetic-invite',full_name:'Saved person',email:'friend@example.com',status:'pending',delivery_status:'provider_accepted'},201):f.baseline(url));await f.nodes['live-contact-form'].fire('submit');assert.equal(f.calls.filter(c=>c.options.method==='POST').length,1);assert.match(f.nodes['live-contact-message'].textContent,/submitted by email/);assert.doesNotMatch(f.nodes['live-contact-message'].textContent,/delivered|will respond/);
 assert.ok(!html.includes('contact-invite-form')&&!html.includes('open <a href="http://127.0.0.1:8025/'));
 console.log('Passed 8 invitation UI scenarios: editable setup, concise notice, configuration gate, draft preservation, cancellation, modal/logout race, truthful send receipt and one contact form. No messages sent.');
})().catch(e=>{console.error(e);process.exitCode=1;});
