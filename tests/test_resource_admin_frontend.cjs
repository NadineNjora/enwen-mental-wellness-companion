const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const tick=()=>new Promise(r=>setImmediate(r)),flush=async()=>{await tick();await tick();await tick();};
const html=fs.readFileSync(path.join(__dirname,'../frontend/index.html'),'utf8'),code=fs.readFileSync(path.join(__dirname,'../frontend/resource-admin.js'),'utf8');
const reply=(data,status=200)=>({status,ok:status>=200&&status<300,json:async()=>data});
const notice={can_curate:true,today:'2026-11-09',text:'Check the source before publication.',notice_version:'resource-review-1',retire_text:'Retain bookmarks and citations.',retire_version:'resource-retire-1',sources:[{host:'www.nhs.uk',publisher:'NHS'}]};
const resource={resource_id:'sample-source',title:'A source to review',publisher:'NHS',summary:'A synthetic public summary.',url:'https://www.nhs.uk/test-source/',audience_note:'Synthetic UK audience note.',category:'studies',source_checked_on:'2026-11-09',active:true,revision:1};
function walk(n){return [n,...n.children.flatMap(walk)];}
function fixture(){
 const nodes={},calls=[],events={};let responder,serial=0,confirmation=true,libraryRefreshes=0;
 class Element{
  constructor(tag='div'){this.tag=tag;this.children=[];this.value='';this.textContent='';this.checked=false;this.disabled=false;this.hidden=false;this.dataset={};this.attrs={};this.handlers={};}
  append(...items){this.children.push(...items);if(this.tag==='select'&&!this.value&&items.length)this.value=items[0].value;}replaceChildren(...items){this.children=[...items];}setAttribute(k,v){this.attrs[k]=v;}addEventListener(t,f){(this.handlers[t]??=[]).push(f);}focus(){}
  querySelectorAll(){return walk(this).filter(n=>n.tag==='button'&&Object.hasOwn(n.dataset,'resourceAdminAction'));}
  reset(){for(const id of this.id==='resource-admin-form'?['key','name','category','summary','url','audience','checked']:['retire-reason','retire-ack']){nodes['resource-admin-'+id].value=id==='category'?'stress':'';nodes['resource-admin-'+id].checked=false;}}
  reportValidity(){return this.id==='resource-admin-form'?['key','name','summary','url','audience','checked'].every(id=>nodes['resource-admin-'+id].value.trim()):Boolean(nodes['resource-admin-retire-reason'].value&&nodes['resource-admin-retire-ack'].checked);}
  async fire(type){for(const f of this.handlers[type]||[])await f({preventDefault(){}});await flush();}
 }
 for(const m of html.matchAll(/<([a-z][\w-]*)[^>]*\bid="([^"]+)"/g))if(m[2].startsWith('resource-admin-')||m[2]==='page-resource-admin'){const n=new Element(m[1]);n.id=m[2];nodes[n.id]=n;}
 nodes['page-resource-admin'].children=Object.values(nodes).filter(n=>n.id!=='page-resource-admin');nodes['resource-admin-category'].value='stress';
 const baseline=url=>url.endsWith('/notice')?reply(notice):url.includes('/resources?')?reply([resource]):reply([]);responder=baseline;
 const context=vm.createContext({document:{getElementById:id=>nodes[id],createElement:tag=>new Element(tag)},window:{crypto:{randomUUID:()=>`request-${++serial}`},confirm:()=>confirmation,addEventListener:(name,f)=>events[name]=f,enwenResources:{load:()=>libraryRefreshes++}},location:{hash:'#/resource-admin'},URL,AbortController,setTimeout,clearTimeout,TypeError,accessToken:'synthetic-token',
 fetch:(url,options)=>{calls.push({url,options});return responder(url,options);},endSession(){context.accessToken=null;context.window.enwenResourceAdmin.reset();}});
 vm.runInContext(code,context);return{nodes,calls,context,ui:context.window.enwenResourceAdmin,baseline,respond:f=>responder=f,confirm:v=>confirmation=v,buttons:()=>walk(nodes['page-resource-admin']).filter(n=>n.tag==='button'),libraryRefreshes:()=>libraryRefreshes,async setup(){await this.ui.setup();await flush();}};
}
const checks=[],check=(name,ok)=>{assert.ok(ok,name);checks.push(name);};
(async()=>{
 let f=fixture();f.respond(url=>url.endsWith('/notice')?reply({...notice,can_curate:false}):f.baseline(url));await f.setup();check('ordinary account has no resource desk entry',f.nodes['resource-admin-open'].hidden&&f.nodes['resource-admin-fields'].disabled&&f.calls.length===1);
 f=fixture();await f.setup();check('curator entry enabled by server capability',!f.nodes['resource-admin-open'].hidden&&!f.nodes['resource-admin-fields'].disabled);
 check('library separates public metadata and resource revision',walk(f.nodes['resource-admin-library']).some(n=>n.textContent==='Published · revision 1'));
 await f.buttons().find(b=>b.textContent==='Prepare update').fire('click');
 check('update keeps resource identity and requires an explicit source-check date',f.nodes['resource-admin-key'].readOnly&&f.nodes['resource-admin-key'].value==='sample-source'&&f.nodes['resource-admin-checked'].value==='');
 f.nodes['resource-admin-name'].value='Keep this edited title';f.confirm(false);await f.nodes['resource-admin-new'].fire('click');check('declining replacement preserves the public-source draft',f.nodes['resource-admin-name'].value==='Keep this edited title');
 f.nodes['resource-admin-checked'].value=notice.today;let failed=true,published=false;let draft;
 f.respond((url,options)=>{
  if(url==='/resource-admin/drafts'&&options.method==='POST'){const body=JSON.parse(options.body);draft={draft_id:'draft-one',base_revision:1,payload:{...body,publisher:'NHS'},status:'draft'};return failed?reply({detail:'Synthetic save failure'},503):reply(draft,201);}
  if(url.includes('/drafts?'))return reply(published?[]:[draft]);
  if(url.endsWith('/publish')){published=true;return reply({recorded_revision:2,current_revision:2,active:true});}
  return f.baseline(url);
 });
 await f.nodes['resource-admin-form'].fire('submit');check('failed draft save preserves every entered field',f.nodes['resource-admin-name'].value==='Keep this edited title'&&f.nodes['resource-admin-checked'].value===notice.today);
 failed=false;await f.nodes['resource-admin-form'].fire('submit');const saves=f.calls.filter(x=>x.options.method==='POST'&&x.url==='/resource-admin/drafts');
 check('save retry reuses the original request identity',JSON.parse(saves[0].options.body).request_id===JSON.parse(saves[1].options.body).request_id);
 check('draft save does not refresh public library or publish',f.libraryRefreshes()===0&&!published&&f.nodes['resource-admin-name'].value==='');
 const publish=f.buttons().find(b=>b.textContent==='Publish reviewed draft');check('publication waits for source review checkbox',publish.disabled);
 const ack=walk(f.nodes['resource-admin-drafts']).find(n=>n.tag==='input');ack.checked=true;await ack.fire('change');await publish.fire('click');
 check('reviewed publication refreshes library and records success',published&&f.libraryRefreshes()===1&&f.nodes['resource-admin-message'].textContent.includes('revision 2'));
 f=fixture();f.respond(url=>url.includes('/drafts?')?reply([{draft_id:'old',base_revision:1,payload:{...resource,source_checked_on:'2026-11-08'}}]):f.baseline(url));await f.setup();await f.nodes['resource-admin-drafts-tab'].fire('click');
 const oldAck=walk(f.nodes['resource-admin-drafts']).find(n=>n.tag==='input');oldAck.checked=true;await oldAck.fire('change');check('old source-check date cannot unlock publication',f.buttons().find(b=>b.textContent==='Publish reviewed draft').disabled);
 f=fixture();await f.setup();let finish;f.respond(()=>new Promise(r=>finish=r));const pending=f.ui.load();f.ui.reset();f.context.accessToken=null;finish(reply([resource]));await pending;
 check('logout clears source drafts and rejects late data',f.nodes['resource-admin-library'].children.length===0&&f.nodes['resource-admin-open'].hidden&&f.nodes['resource-admin-name'].value==='');
 f=fixture();await f.setup();f.respond(()=>reply({detail:'Public-resource curator access is required.'},403));await f.ui.load();check('permission revocation clears curation data and stops loading state',f.nodes['resource-admin-open'].hidden&&f.nodes['resource-admin-fields'].disabled&&f.nodes['resource-admin-library'].children.length===0&&f.nodes['resource-admin-message'].textContent.includes('curator access'));
 check('resource editor stores no student records or browser tokens',!code.includes('localStorage')&&!code.includes('/journals')&&!code.includes('/moods'));
 console.log(`Passed ${checks.length} resource desk UI checks. Synthetic DOM/API only.`);for(const name of checks)console.log('PASS:',name);
})().catch(e=>{console.error(e);process.exitCode=1;});
