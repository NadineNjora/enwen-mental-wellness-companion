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
 const baseline=(url,options)=>url.endsWith('/notice')?reply(notice):url.endsWith('/activity')?reply({unread_count:0,items:[]}):url.includes('/feed?')?reply([post]):url.includes('/mine?')?reply({posts:[],feedback:[]}):url.includes('/moderation/queue')?reply({items:[],text:'Review before publication.',notice_version:notice.review_version}):reply({post,feedback:[]});responder=baseline;
 const context=vm.createContext({document:{getElementById:id=>nodes[id],createElement:tag=>new Element(tag)},window:{crypto:{randomUUID:()=>`synthetic-request-${++sequence}`},confirm:()=>true,addEventListener:(name,fn)=>events[name]=fn,setInterval:fn=>{events.poll=fn;return 1;},clearInterval:()=>{delete events.poll;}},location:{hash:'#/community'},accessToken:'synthetic-token',AbortController,setTimeout,clearTimeout,TypeError,
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
 f=fixture();f.respond((url,options)=>url.includes('/feed?')?reply(url.includes('offset=12')?[post]:Array.from({length:13},(_,i)=>({...post,id:'synthetic-'+i}))):f.baseline(url,options));await f.setup();
 check('feed displays twelve items and enables Older only with a lookahead result',f.nodes['community-feed'].children.length===12&&!f.nodes['community-feed-next'].disabled);
 await f.nodes['community-feed-next'].fire('click');
 check('Older loads the next page and keeps Newer usable',f.nodes['community-feed'].children.length===1&&!f.nodes['community-feed-prev'].disabled&&f.nodes['community-feed-next'].disabled);
 await f.nodes['community-feed-prev'].fire('click');check('Newer returns to the first page',f.calls.at(-1).url.includes('offset=0')&&f.nodes['community-feed'].children.length===12);
 f=fixture();f.respond((url,options)=>url.includes('/feed?')?reply(Array.from({length:12},()=>post)):f.baseline(url,options));await f.setup();
 check('an exact full last page has no phantom Older page',f.nodes['community-feed-next'].disabled&&f.nodes['community-feed-next'].hidden);
 f=fixture();let published=false;f.respond((url,options)=>url.includes('/feed?')?reply(published?[post]:[]):f.baseline(url,options));await f.setup();published=true;f.events.poll();await flush();
 check('published reflections arrive on the visible feed without manual refresh',f.nodes['community-feed'].children.length===1);
 const working=f.baseline;f.respond((url,options)=>url.includes('/feed?')?reply({detail:'Connection lost'},503):working(url,options));await f.ui.load();check('manual refresh failure reports the connection problem',f.nodes['community-status'].textContent==='Connection lost');
 f.respond(working);f.events.poll();await flush();check('background reconnection restores the view and clears its error',f.nodes['community-feed'].children.length===1&&f.nodes['community-status'].textContent==='');
 await f.nodes['community-write-tab'].fire('click');f.nodes['community-post-content'].value='My ongoing draft';f.events.poll();await flush();check('background updates leave a writing draft intact',f.nodes['community-post-content'].value==='My ongoing draft');
 f.ui.reset();check('logout cancels polling and clears new-petal notices',!f.events.poll&&f.nodes['community-activity'].hidden&&f.nodes['community-activity-list'].children.length===0);
 f=fixture();let seen=false;const note={id:'reply-1',post_id:post.id,post_title:post.title,author_label:'A petal from Daisy 🌸',offset:20};
 f.respond((url,options)=>url.endsWith('/activity')?reply({unread_count:seen?0:1,items:seen?[]:[note]}):url.endsWith('/read')?(seen=true,reply({recorded:true})):url.includes('/posts/')?reply({post:{...post,is_mine:true},feedback:[{...post,id:'reply-1'}]}):f.baseline(url,options));await f.setup();
 check('author sees a flower-labelled new-reply notice',!f.nodes['community-activity'].hidden&&walk(f.nodes['community-activity-list']).some(n=>n.textContent.includes('Daisy')));
 await f.buttons().find(b=>b.textContent==='Read this petal →').fire('click');check('petal opens the correct reply page and records only displayed replies',f.calls.some(c=>c.url.includes('/posts/'+post.id+'?limit=21&offset=20'))&&f.calls.some(c=>c.url.endsWith('/read')&&JSON.parse(c.options.body).feedback_ids[0]==='reply-1'));
 check('read petal disappears after persisted acknowledgement',f.nodes['community-activity'].hidden);
 f=fixture();const pendingRow={kind:'post',id:'ordinary',title:'A rest',content:'Synthetic text',status:'pending',support_required:false,privacy_flag:false,reports:[],revision:1};let extra=false;
 f.respond((url,options)=>url.endsWith('/notice')?reply({...notice,is_moderator:true}):url.includes('/moderation/queue')?reply({notice_version:notice.review_version,text:notice.review_text,own_pending:2,items:extra?[pendingRow,{...pendingRow,id:'new'}]:[pendingRow]}):f.baseline(url,options));await f.setup();await f.nodes['community-review-tab'].fire('click');
 const retainedAck=walk(f.nodes['community-queue']).find(n=>n.tag==='input');retainedAck.checked=true;await retainedAck.fire('change');extra=true;f.events.poll();await flush();
 check('incoming queue item preserves an unchanged review checklist',f.nodes['community-queue'].children.length===2&&walk(f.nodes['community-queue']).includes(retainedAck)&&retainedAck.checked);
 check('own submissions explain why a different moderator is needed',f.nodes['community-review-count'].textContent.includes('2 of your own'));
 console.log(`Passed ${checks.length} community UI checks; synthetic browser/API only.`);for(const name of checks)console.log('PASS:',name);
})().catch(e=>{console.error(e);process.exitCode=1;});
