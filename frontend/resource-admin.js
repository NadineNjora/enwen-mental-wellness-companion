"use strict";
(() => {
  const by=id=>document.getElementById('resource-admin-'+id),page=document.getElementById('page-resource-admin');
  const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;};
  const fields={resource_id:'key',title:'name',category:'category',summary:'summary',url:'url',audience_note:'audience',source_checked_on:'checked'};
  let generation=0,loadId=0,notice=null,busy=false,view='library',baseRevision=0,attempt=null,retireTarget=null,retireAttempt=null;
  const offsets={library:0,drafts:0,history:0},counts={library:0,drafts:0,history:0},requests=new Set();
  const allowed=()=>Boolean(accessToken&&notice?.can_curate);
  const message=text=>{by('message').textContent=text||'';};
  function panels(){for(const name of ['library','editor','drafts','history']){by(name+'-view').hidden=name!==view;by(name+'-tab').setAttribute('aria-pressed',String(name===view));}by('pagination').hidden=view==='editor';}
  function controls(){
    by('open').hidden=!allowed();by('fields').disabled=busy||!allowed();
    for(const name of ['library-tab','editor-tab','drafts-tab','history-tab','refresh','retire-cancel'])by(name).disabled=busy||!allowed();
    by('prev').disabled=busy||!allowed()||!offsets[view];by('next').disabled=busy||!allowed()||(counts[view]||0)<20;
    for(const b of page.querySelectorAll('button[data-resource-admin-action]'))b.disabled=busy||!allowed()||b.dataset.locked==='true';
  }
  function reset(){
    generation++;loadId++;for(const c of requests)c.abort();requests.clear();notice=null;busy=false;view='library';baseRevision=0;attempt=retireTarget=retireAttempt=null;
    for(const name of ['library','drafts','history']){offsets[name]=counts[name]=0;by(name).replaceChildren();}
    by('form').reset();by('key').readOnly=false;by('retire-form').reset();by('retire-form').hidden=true;
    by('sources').replaceChildren();by('review-notice').textContent=by('retire-notice').textContent='';message();panels();controls();
  }
  async function request(path,method='GET',body){
    const session=generation,token=accessToken,c=new AbortController();requests.add(c);const timer=setTimeout(()=>c.abort(),20000);
    try{
      const r=await fetch('/resource-admin'+path,{method,cache:'no-store',signal:c.signal,headers:{Accept:'application/json',Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});
      const data=await r.json();if(session!==generation||token!==accessToken)throw new Error('Previous session ignored.');
      if(r.status===401){endSession('Please log in again.');throw new Error('Please log in again.');}
      if(r.status===403){if(notice)notice.can_curate=false;loadId++;for(const name of ['library','drafts','history'])by(name).replaceChildren();controls();message(typeof data.detail==='string'?data.detail:'Public-resource curator access is required.');}
      if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'The resource decision could not be confirmed.');return data;
    }finally{clearTimeout(timer);requests.delete(c);}
  }
  async function setup(){
    reset();const session=generation;
    try{const data=await request('/notice');if(session!==generation)return;notice=data;by('review-notice').textContent=data.text;by('retire-notice').textContent=data.retire_text;by('checked').max=data.today;
      for(const item of data.sources)by('sources').append(make('li',item.publisher+' · '+item.host));controls();if(location.hash==='#/resource-admin')void load();
    }catch(e){if(session===generation)message(e.message);}
  }
  function button(label,fn,locked=false){const b=make('button',label);b.type='button';b.dataset.resourceAdminAction='true';b.dataset.locked=String(locked);b.disabled=busy||!allowed()||locked;b.addEventListener('click',()=>{if(!busy&&allowed()&&!b.disabled)void fn();});return b;}
  function sourceLink(row){
    try{const u=new URL(row.url);if(u.protocol!=='https:'||u.username||u.password||!notice.sources.some(s=>s.host===u.hostname))throw new Error();const link=make('a','Open public source ↗');link.href=u.href;link.target='_blank';link.rel='noopener noreferrer';link.referrerPolicy='no-referrer';return link;}
    catch{return make('span','Source link unavailable');}
  }
  function contentCard(row){const card=make('article',undefined,'resource-admin-card');card.append(make('p',row.resource_id+' · '+row.publisher+' · '+row.category,'resource-admin-meta'),make('h4',row.title),make('p',row.summary),make('p',row.audience_note,'resource-admin-meta'),make('p','Source link checked: '+row.source_checked_on,'resource-admin-meta'),sourceLink(row));return card;}
  function renderLibrary(rows){
    by('library').replaceChildren();for(const row of rows){const card=contentCard(row);card.append(make('p',(row.active?'Published':'Retired')+' · revision '+row.revision,'resource-admin-meta'));const actions=make('div',undefined,'resource-admin-actions');actions.append(button(row.active?'Prepare update':'Prepare fresh review to restore',()=>edit(row)));if(row.active)actions.append(button('Retire reading',()=>beginRetire(row)));card.append(actions);by('library').append(card);}if(!rows.length)by('library').append(make('p','No resources on this page. Prepare a source-linked draft to begin.'));
  }
  function renderDrafts(rows){
    by('drafts').replaceChildren();for(const draft of rows){const card=contentCard(draft.payload);card.append(make('p','Review draft · based on revision '+draft.base_revision,'resource-admin-meta'));
      const ack=make('input');ack.type='checkbox';const label=make('label',undefined,'resource-admin-ack');label.append(ack,make('span','I opened this source today and checked this draft against the review notice above.'));
      const ready=draft.payload.source_checked_on===notice.today;
      const publish=button('Publish reviewed draft',()=>publishDraft(draft),true);ack.addEventListener('change',()=>{publish.dataset.locked=String(!ack.checked||!ready);controls();});
      if(!ready)card.append(make('p','This source-check date is not today. Recheck the source and prepare a fresh dated draft.','resource-admin-meta'));
      const actions=make('div',undefined,'resource-admin-actions');actions.append(publish,button('Discard unpublished draft',()=>discardDraft(draft)));card.append(label,actions);by('drafts').append(card);
    }if(!rows.length)by('drafts').append(make('p','No review drafts waiting on this page. Published versions are recorded in Change history.'));
  }
  function renderHistory(rows){
    by('history').replaceChildren();for(const row of rows){const card=make('article',undefined,'resource-admin-card');card.append(make('h4',row.resource_id+' · revision '+row.revision),make('p',row.action+' · '+row.actor_label+' · '+new Date(row.recorded_at).toLocaleString('en-KE',{timeZone:'Africa/Nairobi'}),'resource-admin-meta'),make('p',row.reason));
      const detail=make('details');detail.append(make('summary','View the public metadata changes'));
      for(const key of ['title','publisher','category','summary','url','audience_note','source_checked_on','active'])detail.append(make('p',key.replaceAll('_',' ')+': '+(row.before?String(row.before[key]):'New resource')+' → '+String(row.after[key])));
      card.append(detail);by('history').append(card);
    }if(!rows.length)by('history').append(make('p','Publishing and retirement decisions will appear here. Preparing a draft alone does not change the public library.'));
  }
  async function load(){
    if(!accessToken)return;if(!notice){message('Connecting to the resource desk…');return;}if(!allowed()){message('A public-resource curator role is required to use this desk.');return;}if(view==='editor'){controls();return;}
    const session=generation,id=++loadId,target=view;message('Loading the resource desk…');
    try{const path=target==='library'?'/resources':target==='drafts'?'/drafts':'/history';const data=await request(path+'?limit=20&offset='+offsets[target]);if(session!==generation||id!==loadId||target!==view||!allowed())return;counts[target]=data.length;if(target==='library')renderLibrary(data);else if(target==='drafts')renderDrafts(data);else renderHistory(data);message();}
    catch(e){if(session===generation&&id===loadId){by(target).replaceChildren();message(e.name==='AbortError'?'This view took too long. Try Refresh.':e.message);}}
    finally{if(session===generation)controls();}
  }
  async function show(name){if(busy)return;view=name;loadId++;by('retire-form').hidden=true;panels();message();await load();}
  function dirty(){return ['key','name','summary','url','audience','checked'].some(id=>by(id).value.trim());}
  async function edit(row=null){
    if(dirty()&&!window.confirm('Replace the unsaved resource draft in the editor?'))return;
    by('form').reset();attempt=null;baseRevision=row?.revision||0;by('key').readOnly=Boolean(row);
    if(row)for(const [key,id] of Object.entries(fields))if(key!=='source_checked_on')by(id).value=row[key];
    by('editor-title').textContent=row?'Prepare a resource update':'Prepare a new resource';by('base').textContent=row?'Editing revision '+row.revision+(row.active?'. The current reading stays published until a reviewed draft replaces it.':'. A fresh reviewed publication will restore this retired reading.'):'New resources start with an unpublished draft.';
    await show('editor');
  }
  function uuid(){if(!window.crypto?.randomUUID)throw new Error('Secure request identifiers are unavailable.');return window.crypto.randomUUID();}
  function decisionAttempt(previous,data){if(!previous||Object.entries(data).some(([k,v])=>previous[k]!==v))return {...data,request_id:uuid()};return previous;}
  async function write(fn,uncertain){if(busy||!allowed())return;const session=generation;busy=true;controls();try{await fn(session);}catch(e){if(session===generation)message(e.name==='AbortError'||e instanceof TypeError?uncertain:e.message);}finally{if(session===generation){busy=false;controls();}}}
  by('form').addEventListener('submit',event=>{
    event.preventDefault();if(by('fields').disabled||!by('form').reportValidity())return;
    void write(async session=>{const data=Object.fromEntries(Object.entries(fields).map(([key,id])=>[key,by(id).value.trim()]));data.expected_revision=baseRevision;attempt=decisionAttempt(attempt,data);await request('/drafts','POST',attempt);if(session!==generation)return;by('form').reset();by('key').readOnly=false;attempt=null;baseRevision=0;view='drafts';offsets.drafts=0;panels();await load();message('Review draft saved. The student library and AI source have not changed yet.');},'Save outcome unconfirmed. Your draft and request identifier are kept. Refresh Review drafts before retrying; nothing was automatically resubmitted.');
  });
  async function publishDraft(draft){await write(async session=>{const r=await request('/drafts/'+draft.draft_id+'/publish','POST',{notice_version:notice.notice_version,acknowledged:true});if(session!==generation)return;await load();void window.enwenResources?.load();message('Publication recorded at revision '+r.recorded_revision+'. Current resource: '+(r.active?'published':'retired')+'. The library and AI summary are updated together.');},'Publication outcome unconfirmed. Refresh Review drafts and Change history before trying again. Nothing was automatically retried.');}
  async function discardDraft(draft){if(!window.confirm('Discard this unpublished draft? Published readings and bookmarks will stay as they are.'))return;await write(async session=>{await request('/drafts/'+draft.draft_id+'/discard','POST');if(session===generation){await load();message('Unpublished draft discarded. The public library is unchanged.');}},'Discard outcome unconfirmed. Refresh Review drafts before trying again.');}
  function beginRetire(row){retireTarget=row;retireAttempt=null;by('retire-form').reset();by('retire-title').textContent='Retire: '+row.title;by('retire-form').hidden=false;by('retire-reason').focus();}
  by('retire-cancel').addEventListener('click',()=>{by('retire-form').hidden=true;retireTarget=null;});
  by('retire-form').addEventListener('submit',event=>{event.preventDefault();if(!retireTarget||!by('retire-form').reportValidity())return;void write(async session=>{const data={resource_id:retireTarget.resource_id,expected_revision:retireTarget.revision,reason:by('retire-reason').value.trim()};retireAttempt=decisionAttempt(retireAttempt,data);const {resource_id,...payload}=retireAttempt;const r=await request('/resources/'+resource_id+'/retire','POST',{...payload,notice_version:notice.retire_version,acknowledged:by('retire-ack').checked});if(session!==generation)return;by('retire-form').hidden=true;retireTarget=retireAttempt=null;await load();void window.enwenResources?.load();message('Retirement recorded at revision '+r.recorded_revision+'. Current resource: '+(r.active?'published':'retired')+'. Bookmarks and old citations are retained.');},'Retirement outcome unconfirmed. The decision identifier is kept. Refresh the library and history before trying again.');});
  for(const name of ['library','editor','drafts','history'])by(name+'-tab').addEventListener('click',()=>void show(name));
  by('new').addEventListener('click',()=>void edit());by('refresh').addEventListener('click',()=>void load());
  for(const [name,delta] of [['prev',-20],['next',20]])by(name).addEventListener('click',()=>{if(busy||view==='editor')return;offsets[view]=Math.max(0,offsets[view]+delta);void load();});
  window.addEventListener('beforeunload',event=>{if(dirty()){event.preventDefault();event.returnValue='';}});
  window.enwenResourceAdmin={reset,setup,load};reset();
})();
