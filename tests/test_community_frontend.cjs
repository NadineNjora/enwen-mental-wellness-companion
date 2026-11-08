const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const tick=()=>new Promise(r=>setImmediate(r)),flush=async()=>{await tick();await tick();await tick();};
const html=fs.readFileSync(path.join(__dirname,'../frontend/index.html'),'utf8'),script=fs.readFileSync(path.join(__dirname,'../frontend/community.js'),'utf8');
const reply=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
const notice={notice_version:'community-sharing-1',text:'Pseudonymous, deliberate sharing only.',is_moderator:false,review_version:'community-review-1',review_text:'Review before publication.'};
const post={id:'synthetic-post',title:'<b>Plain text title</b>',content:'A fictional study break.',author_label:'A fellow student 🌱',published_at:'2026-11-08T10:00:00Z',is_mine:false};
function fixture(){
 const nodes={},calls=[],events={};let sequence=0,responder;
 class Element{
  constructor(tag='div'){this.tag=tag;this.children=[];this.textContent='';this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.dataset={};this.handlers={};this.attrs={};}
  append(...items){this.children.push(...items);if(this.tag==='select'&&!this.value&&items.length)this.value=items[0].value;}replaceChildren(...items){this.children=[...items];}
  setAttribute(k,v){this.attrs[k]=v;}addEventListener(t,f){(this.handlers[t]??=[]).push(f);}focus(){}
  querySelectorAll(){return walk(this).filter(n=>n.tag==='button'&&Object.hasOwn(n.dataset,'communityAction'));}
  reset(){for(const suffix of this.id==='community-post-form'?['post-title','post-content','post-ack']:this.id==='community-feedback-form'?['feedback-content','feedback-ack']:['report-reason']){nodes['community-'+suffix].value='';nodes['community-'+suffix].checked=false;}}
  reportValidity(){if(this.id==='community-post-form')return Boolean(nodes['community-post-title'].value&&nodes['community-post-content'].value&&nodes['community-post-ack'].checked);if(this.id==='community-feedback-form')return Boolean(nodes['community-feedback-content'].value&&nodes['community-feedback-ack'].checked);return Boolean(nodes['community-report-reason'].value);}
  async fire(type){for(const f of this.handlers[type]||[])await f({preventDefault(){}});await flush();}
 }
 for(const m of html.matchAll(/<([a-z][\w-]*)[^>]*\bid="([^"]+)"/g)){if(m[2].startsWith('community-')||m[2]==='page-community'){const n=new Element(m[1]);n.id=m[2];nodes[n.id]=n;}}
 nodes['page-community'].children=Object.values(nodes).filter(n=>n.id!=='page-community');
 const baseline=(url,options)=>url.endsWith('/notice')?reply(notice):url.includes('/feed?')?reply([post]):url.includes('/mine?')?reply({posts:[],feedback:[]}):url.includes('/moderation/queue')?reply({items:[],text:'Review before publication.',notice_version:notice.review_version}):reply({post,feedback:[]});responder=baseline;
 const context=vm.createContext({document:{getElementById:id=>nodes[id],createElement:tag=>new Element(tag)},window:{crypto:{randomUUID:()=>`synthetic-request-${++sequence}`},confirm:()=>true,addEventListener:(name,fn)=>events[name]=fn},location:{hash:'#/community'},accessToken:'synthetic-token',AbortController,setTimeout,clearTimeout,TypeError,
  fetch:(url,options)=>{calls.push({url,options});return responder(url,options);},endSession(){context.accessToken=null;context.window.enwenCommunity.reset();}});
 vm.runInContext(script,context);return {nodes,calls,events,context,ui:context.window.enwenCommunity,baseline,respond:fn=>responder=fn,buttons:()=>walk(nodes['page-community']).filter(n=>n.tag==='button'),async setup(){await this.ui.setup({wellness_consent_current:true});await flush();}};
}
function walk(node){return [node,...node.children.flatMap(walk)];}
const checks=[],check=(name,ok)=>{assert.ok(ok,name);checks.push(name);};
(async()=>{
 let f=fixture();await f.setup();
 check('ordinary students do not see moderation control',f.nodes['community-review-tab'].hidden);
 check('feed text is rendered as text, without interpreting markup',walk(f.nodes['community-feed']).some(n=>n.textContent==='<b>Plain text title</b>'));
 await f.nodes['community-write-tab'].fire('click');f.nodes['community-post-title'].value='Keep my title';f.nodes['community-post-content'].value='Keep my full fictional draft';
 await f.nodes['community-post-form'].fire('submit');check('explicit acknowledgement required before form sends',!f.calls.some(x=>x.options.method==='POST'));
 f.nodes['community-post-ack'].checked=true;let fail=true;
 f.respond((url,options)=>options.method==='POST'?(fail?reply({detail:'Synthetic save failure'},503):reply({id:'new',status:'pending',support_required:false},201)):f.baseline(url,options));
 await f.nodes['community-post-form'].fire('submit');check('failed sharing preserves complete draft and agreement',f.nodes['community-post-title'].value==='Keep my title'&&f.nodes['community-post-content'].value==='Keep my full fictional draft'&&f.nodes['community-post-ack'].checked);
 const first=JSON.parse(f.calls.find(x=>x.options.method==='POST').options.body);fail=false;await f.nodes['community-post-form'].fire('submit');
 const second=JSON.parse(f.calls.filter(x=>x.options.method==='POST')[1].options.body);
 check('deliberate retry keeps same submission identifier',first.request_id===second.request_id);
 check('successful sharing clears form and explains review',!f.nodes['community-post-content'].value&&f.nodes['community-status'].textContent.includes('moderation'));
 await f.nodes['community-feed-tab'].fire('click');await f.buttons().find(b=>b.textContent==='Read reflection →').fire('click');
 check('reader opens only the selected shared reflection',walk(f.nodes['community-detail']).some(n=>n.textContent===post.content));
 check('peer response form available for another student',!f.nodes['community-feedback-fields'].disabled&&!f.nodes['community-feedback-form'].hidden);
 f.nodes['community-feedback-content'].value='My unsent encouragement';f.nodes['community-feedback-ack'].checked=true;
 f.respond((url,options)=>options.method==='POST'?reply({detail:'Synthetic feedback failure'},503):f.baseline(url,options));await f.nodes['community-feedback-form'].fire('submit');
 check('failed feedback keeps the draft',f.nodes['community-feedback-content'].value==='My unsent encouragement');
 f=fixture();f.respond((url,options)=>url.endsWith('/notice')?reply({...notice,is_moderator:true}):url.includes('/moderation/queue')?reply({notice_version:notice.review_version,text:notice.review_text,items:[{kind:'post',id:'flagged',title:'Held reflection',content:'Synthetic flagged text',status:'flagged',support_required:true,privacy_flag:false,reports:[],revision:1},{kind:'post',id:'ordinary',title:'A small rest',content:'Synthetic unflagged text',status:'pending',support_required:false,privacy_flag:false,reports:[],revision:1}]}):f.baseline(url,options));
 await f.setup();await f.nodes['community-review-tab'].fire('click');const publish=f.buttons().find(b=>b.textContent==='Approve for sharing'),reject=f.buttons().find(b=>b.textContent==='Decline submission');
 check('moderation decision requires checklist acknowledgement',publish.disabled&&reject.disabled);
 const checkbox=walk(f.nodes['community-queue']).find(n=>n.tag==='input'&&n.type==='checkbox');checkbox.checked=true;await checkbox.fire('change');
 check('flagged submission cannot be approved from interface',publish.disabled&&!reject.disabled);
 const ordinaryPublish=f.buttons().filter(b=>b.textContent==='Approve for sharing')[1],ordinaryAck=walk(f.nodes['community-queue']).filter(n=>n.tag==='input'&&n.type==='checkbox')[1];ordinaryAck.checked=true;await ordinaryAck.fire('change');assert.equal(ordinaryPublish.disabled,false);
 const reason=walk(f.nodes['community-queue']).filter(n=>n.tag==='select')[1];reason.value='unsafe';await reason.fire('change');check('an unsafe reason disables approval of otherwise eligible content',ordinaryPublish.disabled);
 f=fixture();await f.setup();let finish;f.respond(()=>new Promise(r=>finish=r));const pending=f.ui.load();f.ui.reset();f.context.accessToken=null;finish(reply([post]));await pending;
 check('logout clears community records and ignores late response',f.nodes['community-feed'].children.length===0&&f.nodes['community-post-content'].value==='');
 check('logout hides moderator controls and disables writing',f.nodes['community-review-tab'].hidden&&f.nodes['community-post-fields'].disabled);
 check('community code never accesses private journal storage',!script.includes('/journals')&&!script.includes('localStorage'));
 console.log(`Passed ${checks.length} community UI checks; synthetic browser/API only.`);for(const name of checks)console.log('PASS:',name);
})().catch(e=>{console.error(e);process.exitCode=1;});
