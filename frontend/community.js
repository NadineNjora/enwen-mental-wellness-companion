"use strict";
(() => {
  const by=id=>document.getElementById('community-'+id),page=document.getElementById('page-community');
  const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;};
  let generation=0,loadId=0,notice=null,wellness=false,busy=false,view='feed',post=null,reportTarget=null,postAttempt=null,feedbackAttempt=null;
  let feedOffset=0,mineOffset=0,feedbackOffset=0,feedCount=0,mineCount=0,feedbackCount=0;
  const requests=new Set();
  function message(text=''){by('status').textContent=text;}
  function reset(){
    generation++;loadId++;for(const c of requests)c.abort();requests.clear();notice=null;wellness=busy=false;view='feed';post=reportTarget=postAttempt=feedbackAttempt=null;
    feedOffset=mineOffset=feedbackOffset=feedCount=mineCount=feedbackCount=0;
    for(const id of ['post-form','feedback-form','report-form'])by(id).reset();
    for(const id of ['feed','mine','detail','feedback','queue'])by(id).replaceChildren();
    for(const id of ['post-notice','feedback-notice','review-notice'])by(id).textContent='';
    by('report-form').hidden=by('support').hidden=true;message();panels();controls();
  }
  function panels(){for(const name of ['feed','write','mine','detail','review'])by(name+'-view').hidden=name!==view;for(const name of ['feed','write','mine','review'])by(name+'-tab').setAttribute('aria-pressed',String(view===name));}
  function controls(){
    by('post-fields').disabled=busy||!notice||!wellness;
    by('feedback-fields').disabled=busy||!notice||!wellness||!post||post.is_mine;
    by('feedback-form').hidden=Boolean(post?.is_mine);
    by('review-tab').hidden=!notice?.is_moderator;
    for(const name of ['feed-tab','write-tab','mine-tab','review-tab','refresh','mine-refresh','review-refresh','back','report-cancel'])by(name).disabled=busy||!accessToken;
    by('feed-tab').disabled ||= !wellness;by('write-tab').disabled ||= !wellness;
    by('feed-prev').disabled=busy||feedOffset===0;by('feed-next').disabled=busy||feedCount<=12;
    by('mine-prev').disabled=busy||mineOffset===0;by('mine-next').disabled=busy||mineCount<=12;
    by('feedback-prev').disabled=busy||feedbackOffset===0;by('feedback-next').disabled=busy||feedbackCount<=20;
    for(const name of ['feed','mine','feedback']) {
      const offset=name==='feed'?feedOffset:name==='mine'?mineOffset:feedbackOffset;
      const count=name==='feed'?feedCount:name==='mine'?mineCount:feedbackCount, size=name==='feedback'?20:12;
      by(name+'-prev').hidden=by(name+'-next').hidden=offset===0&&count<=size;
    }
    for(const b of page.querySelectorAll('button[data-community-action]'))b.disabled=busy||b.dataset.locked==='true';
  }
  async function request(path,method='GET',body){
    const session=generation,token=accessToken,c=new AbortController();requests.add(c);const timer=setTimeout(()=>c.abort(),20000);
    try{
      const r=await fetch('/community'+path,{method,cache:'no-store',signal:c.signal,headers:{Accept:'application/json',Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});
      const data=await r.json();if(session!==generation||token!==accessToken)throw new Error('Previous session ignored.');
      if(r.status===401){endSession('Please log in again.');throw new Error('Please log in again.');}
      if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'The community request could not be confirmed.');return data;
    }finally{clearTimeout(timer);requests.delete(c);}
  }
  async function setup(user){
    reset();wellness=user.wellness_consent_current===true;const session=generation;
    try{const n=await request('/notice');if(session!==generation)return;notice=n;by('post-notice').textContent=by('feedback-notice').textContent=n.text;by('review-notice').textContent=n.review_text;controls();if(location.hash==='#/community')void load();}
    catch(e){if(session===generation)message(e.message);}
  }
  function button(text,fn,locked=false){const b=make('button',text);b.type='button';b.dataset.communityAction='true';b.dataset.locked=String(locked);b.disabled=busy||locked;b.addEventListener('click',()=>{if(!busy&&!b.disabled)void fn();});return b;}
  function date(value){const d=new Date(value);return Number.isNaN(d.getTime())?'Date unavailable':d.toLocaleDateString('en-KE',{dateStyle:'medium',timeZone:'Africa/Nairobi'});}
  function publicCard(row,detail=false){
    const card=make('article',undefined,detail?'community-detail':'community-card');
    card.append(make('p',row.author_label+' · '+date(row.published_at),'community-meta'),make(detail?'h3':'h4',row.title),make('p',detail?row.content:row.content.slice(0,220)+(row.content.length>220?'…':''),'community-body'));
    const actions=make('div',undefined,'community-actions');
    if(!detail)actions.append(button('Read reflection →',()=>open(row.id)));
    else actions.append(button('Report this reflection',()=>openReport('post',row.id)));
    card.append(actions);return card;
  }
  function renderFeed(rows){const target=by('feed');target.replaceChildren();for(const row of rows.slice(0,12))target.append(publicCard(row));if(!rows.length)target.append(make('p','No reviewed reflections on this page yet. A first shared thought can be a gentle place to begin.'));feedCount=rows.length;}
  function renderMine(data){
    const target=by('mine');target.replaceChildren();const rows=[...data.posts.slice(0,12),...data.feedback.slice(0,12)];mineCount=Math.max(data.posts.length,data.feedback.length);
    by('support').hidden=!rows.some(r=>r.support_required&&r.status==='flagged');
    for(const row of rows){
      const card=make('article',undefined,'community-card');card.append(make('span',row.status,'community-status-chip'),make('h4',row.title||'Your peer encouragement'),make('p',date(row.created_at),'community-meta'),make('p',row.content,'community-body'));
      if(row.review_reason)card.append(make('p','Review reason: '+row.review_reason.replaceAll('_',' '),'small-note'));
      const actions=make('div',undefined,'community-actions');
      if(row.kind==='post'&&row.status==='published')actions.append(button('Read shared reflection',()=>open(row.id)));
      if(row.status!=='withdrawn')actions.append(button('Withdraw sharing',()=>withdraw(row)));
      card.append(actions);target.append(card);
    }
    if(!rows.length)target.append(make('p','Your community submissions will appear here. Your private journal is kept separately.'));
  }
  function renderDetail(data){
    post=data.post;by('detail').replaceChildren(publicCard(post,true));by('feedback').replaceChildren();feedbackCount=data.feedback.length;
    for(const row of data.feedback.slice(0,20)){const card=make('article',undefined,'community-feedback-card');card.append(make('p',row.author_label+' · '+date(row.published_at),'community-meta'),make('p',row.content,'community-body'),button('Report response',()=>openReport('feedback',row.id)));by('feedback').append(card);}
    if(!data.feedback.length)by('feedback').append(make('p','No reviewed responses on this page yet. A little encouragement can go a long way.'));
  }
  function renderQueue(data){
    const target=by('queue');target.replaceChildren();by('review-notice').textContent=data.text;
    for(const row of data.items){
      const card=make('article',undefined,'community-card');card.append(make('span',row.kind+' · '+row.status,'community-status-chip'),make('h4',row.title||'Peer encouragement'),make('p',row.content,'community-body'));
      const flags=[];if(row.support_required)flags.push('Needs support review');if(row.privacy_flag)flags.push('Possible identifying details');if(row.reports.length)flags.push('Reports: '+row.reports.join(', '));
      if(flags.length)card.append(make('p',flags.join(' · '),'community-review-flags'));
      const reason=make('select');reason.setAttribute('aria-label','Reason for this moderation decision');
      for(const [value,text] of [['community_fit','Community suitability'],['privacy','Privacy'],['unsafe','Unsafe content or advice'],['harassment','Harassment'],['needs_support','Needs human support'],['other','Other community concern']]){const o=make('option',text);o.value=value;reason.append(o);}
      const ack=make('input');ack.type='checkbox';const label=make('label',undefined,'community-ack');label.append(ack,make('span','I have reviewed this submission against the checklist above.'));
      const canPublish=!row.support_required&&!row.privacy_flag&&row.status==='pending';
      const publish=button('Approve for sharing',()=>moderate(row,'publish',reason.value,data.notice_version),true);
      const reject=button(row.status==='published'?'Remove from feed':'Decline submission',()=>moderate(row,'reject',reason.value,data.notice_version),true);
      const reviewControls=()=>{publish.dataset.locked=String(!ack.checked||!canPublish||reason.value!=='community_fit');reject.dataset.locked=String(!ack.checked);controls();};
      ack.addEventListener('change',reviewControls);reason.addEventListener('change',reviewControls);
      const actions=make('div',undefined,'community-actions');actions.append(publish,reject);card.append(reason,label,actions);target.append(card);
    }
    if(!data.items.length)target.append(make('p','No submissions you can review right now. Your own sharing requires another moderator.'));
  }
  async function load(){
    if(!accessToken)return;if(!notice){message('Connecting to the community…');return;}
    if(view==='write'){controls();return;}
    if(!wellness&&!['mine','review'].includes(view)){message('Current wellness consent is needed to read and share. You can still withdraw your earlier sharing under My sharing.');return;}
    const session=generation,id=++loadId,target=view;message('Loading this community view…');
    try{
      const data=await request(target==='feed'?'/feed?limit=13&offset='+feedOffset:target==='mine'?'/mine?limit=13&offset='+mineOffset:target==='review'?'/moderation/queue':'/posts/'+post.id+'?limit=21&offset='+feedbackOffset);
      if(session!==generation||id!==loadId||view!==target)return;
      if(target==='feed')renderFeed(data);else if(target==='mine')renderMine(data);else if(target==='review')renderQueue(data);else renderDetail(data);message();
    }catch(e){if(session===generation&&id===loadId){for(const name of ['feed','mine','queue','detail','feedback'])by(name).replaceChildren();message(e.name==='AbortError'?'This view took too long. Please refresh.':e.message);}}
    finally{if(session===generation)controls();}
  }
  async function show(name){if(busy)return;loadId++;view=name;by('report-form').hidden=true;by('support').hidden=true;panels();message();await load();}
  async function open(id){
    if(post?.id!==id&&by('feedback-content').value.trim()&&!window.confirm('Replace the unsent response for the previous reflection?'))return;
    if(post?.id!==id){by('feedback-form').reset();feedbackAttempt=null;}post={id};feedbackOffset=0;await show('detail');
  }
  function attempt(previous,payload){if(!previous||Object.entries(payload).some(([k,v])=>previous[k]!==v)){if(!window.crypto?.randomUUID)throw new Error('Secure submission identifiers are unavailable.');return {...payload,request_id:window.crypto.randomUUID()};}return previous;}
  async function write(fn,uncertain='Outcome unconfirmed. Your draft and request identifier are kept. Refresh My sharing before retrying; nothing was automatically resent.'){if(busy)return;const session=generation;busy=true;controls();try{await fn(session);}catch(e){if(session===generation)message(e.name==='AbortError'||e instanceof TypeError?uncertain:e.message);}finally{if(session===generation){busy=false;controls();}}}
  by('post-form').addEventListener('submit',event=>{
    event.preventDefault();if(by('post-fields').disabled||!by('post-form').reportValidity())return;
    void write(async session=>{postAttempt=attempt(postAttempt,{title:by('post-title').value.trim(),content:by('post-content').value.trim()});const result=await request('/posts','POST',{...postAttempt,notice_version:notice.notice_version,acknowledged:by('post-ack').checked});if(session!==generation)return;by('post-form').reset();postAttempt=null;view='mine';mineOffset=0;panels();await load();by('support').hidden=!result.support_required;message(result.status==='flagged'?'Submission held for review; it has not been published.':'Reflection submitted for moderation. It will appear in Read together after approval.');});
  });
  by('feedback-form').addEventListener('submit',event=>{
    event.preventDefault();if(by('feedback-fields').disabled||!by('feedback-form').reportValidity())return;
    void write(async session=>{feedbackAttempt=attempt(feedbackAttempt,{post_id:post.id,content:by('feedback-content').value.trim()});const {post_id,...payload}=feedbackAttempt;const result=await request('/posts/'+post_id+'/feedback','POST',{...payload,notice_version:notice.notice_version,acknowledged:by('feedback-ack').checked});if(session!==generation)return;by('feedback-form').reset();feedbackAttempt=null;by('support').hidden=!result.support_required;message('Response saved for moderation. It is not publicly visible yet; check My sharing.');});
  });
  async function withdraw(row){if(!window.confirm('Withdraw this submission from the community feed? The submission and review history will remain in your account.'))return;await write(async session=>{await request('/'+row.kind+'/'+row.id+'/withdraw','POST');if(session===generation){await load();message('Sharing withdrawn. It no longer appears in the community feed.');}},'Withdrawal outcome unconfirmed. Refresh My sharing before trying again.');}
  function openReport(kind,id){reportTarget={kind,id};by('report-title').textContent=kind==='post'?'Report this shared reflection':'Report this shared response';by('report-form').reset();by('report-form').hidden=false;by('report-reason').focus();}
  by('report-cancel').addEventListener('click',()=>{by('report-form').hidden=true;reportTarget=null;});
  by('report-form').addEventListener('submit',event=>{event.preventDefault();if(!reportTarget||!by('report-form').reportValidity())return;void write(async session=>{await request('/'+reportTarget.kind+'/'+reportTarget.id+'/report','POST',{reason:by('report-reason').value});if(session===generation){by('report-form').hidden=true;reportTarget=null;message('Report saved for community review. This is not an emergency alert or a confirmed human response.');}});});
  async function moderate(row,action,reason,version){await write(async session=>{await request('/moderation/'+row.kind+'/'+row.id,'POST',{action,reason,expected_revision:row.revision,notice_version:version,acknowledged:true});if(session===generation){await load();message(action==='publish'?'Approved reflection or response is now shared.':'Submission declined or removed from the feed.');}},'Review outcome unconfirmed. Refresh the moderation queue before another decision. Nothing was automatically retried.');}
  for(const name of ['feed','write','mine','review'])by(name+'-tab').addEventListener('click',()=>void show(name));
  for(const id of ['refresh','mine-refresh','review-refresh'])by(id).addEventListener('click',()=>void load());
  by('back').addEventListener('click',()=>void show('feed'));
  for(const [name,size] of [['feed',12],['mine',12],['feedback',20]])for(const [direction,sign] of [['prev',-1],['next',1]])by(name+'-'+direction).addEventListener('click',()=>{if(busy)return;if(name==='feed')feedOffset=Math.max(0,feedOffset+sign*size);else if(name==='mine')mineOffset=Math.max(0,mineOffset+sign*size);else feedbackOffset=Math.max(0,feedbackOffset+sign*size);void load();});
  window.addEventListener('beforeunload',event=>{if(by('post-title').value.trim()||by('post-content').value.trim()||by('feedback-content').value.trim()){event.preventDefault();event.returnValue='';}});
  window.enwenCommunity={reset,setup,load};reset();
})();
