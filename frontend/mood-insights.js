"use strict";
(() => {
  const by=id=>document.getElementById(id),choices=by('mood-context-choices'),contextStatus=by('mood-context-status');
  const period=by('mood-insights-period'),status=by('mood-insights-status'),content=by('mood-insights-content');
  let generation=0,enabled=false,requestId=0,catalogController=null,insightController=null,options=new Map(),boxes=new Map();
  const element=(tag,text,className)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(className)n.className=className;return n;};
  function reset(){
    generation++;requestId++;catalogController?.abort();insightController?.abort();catalogController=insightController=null;enabled=false;
    options.clear();boxes.clear();choices.replaceChildren();contextStatus.textContent='';content.hidden=true;
    for(const id of ['mood-insights-metrics','mood-insights-factors','mood-insights-times'])by(id).replaceChildren();
    by('mood-insights-unlabelled').textContent='';by('mood-insights-explanation').textContent='';status.textContent='';period.disabled=true;
  }
  function selection(){return [...boxes].filter(([,box])=>box.checked).map(([key])=>key);}
  function count(){contextStatus.textContent=(selection().length?selection().length+' of 6 chosen · A little picture of your day.':'Choose what feels true for you today.');}
  function choose(key){const box=boxes.get(key);if(!enabled||!box)return false;if(!box.checked&&selection().length>=6){contextStatus.textContent='You’ve chosen six. Let one go to make room for another.';return false;}box.checked=true;count();return true;}
  function label(key){const o=options.get(key);return o?o.emoji+' '+o.label:key;}
  async function get(path,controller,session,token){
    const timeout=setTimeout(()=>controller.abort(),15000);
    try{
      const r=await fetch(path,{cache:'no-store',signal:controller.signal,headers:{Accept:'application/json',Authorization:'Bearer '+token}});
      const data=await r.json();if(session!==generation||token!==accessToken)throw new Error('Previous session ignored.');
      if(r.status===401){endSession('Please log in again.');throw new Error('Please log in again.');}
      if(r.status===403){pauseWellnessFeatures();throw new Error('Current wellness consent is required.');}
      if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'Your private summary is temporarily unavailable.');return data;
    }finally{clearTimeout(timeout);}
  }
  async function setup(user){
    enabled=user.wellness_consent_current===true;period.disabled=!enabled;if(!enabled)return;
    const session=generation,token=accessToken,c=new AbortController();catalogController=c;
    try{
      const data=await get('/moods/context-options',c,session,token);if(session!==generation||token!==accessToken)return;
      if(!Array.isArray(data.options)||data.maximum!==6)throw new Error('Student factors could not be loaded.');
      choices.replaceChildren();options.clear();boxes.clear();
      for(const o of data.options){
        options.set(o.key,o);const box=element('input');box.type='checkbox';box.name='mood_contexts';box.value=o.key;
        const item=element('label',undefined,'mood-context-choice');item.append(box,element('span',o.emoji+' '+o.label));
        box.addEventListener('change',()=>{if(selection().length>6){box.checked=false;contextStatus.textContent='Choose up to six factors.';}else count();});
        boxes.set(o.key,box);choices.append(item);
      }
      count();
      if(typeof renderMoodHistoryList==='function'&&typeof historyEntries!=='undefined'&&historyEntries.length)renderMoodHistoryList();
    }catch(e){if(session===generation&&token===accessToken)contextStatus.textContent='Factors could not be loaded. Your score and note can still be saved.';}
    finally{if(catalogController===c)catalogController=null;}
  }
  function render(data){
    const metrics=by('mood-insights-metrics');metrics.replaceChildren();
    const card=(value,label)=>{const n=element('div',undefined,'mood-insights-metric');n.append(element('strong',value),element('span',label));metrics.append(n);};
    card(data.total_checkins,'Saved check-ins');card(data.days_with_checkins,'Days you checked in');
    if(data.normalised_summary?.average_score!==null&&data.normalised_summary)card(data.normalised_summary.average_score+'/10','Your average check-in');
    const factors=by('mood-insights-factors');factors.replaceChildren();
    for(const factor of data.contexts)factors.append(element('li',factor.emoji+' '+factor.label+' · '+factor.count+' check-in'+(factor.count===1?'':'s')));
    if(!data.contexts.length)factors.append(element('li','No factors tagged in this period. Add a few to a future check-in if they feel useful.'));
    by('mood-insights-unlabelled').textContent='';
    const times=by('mood-insights-times');times.replaceChildren();
    for(const time of data.times){const row=element('li',time.label+' · '+time.count);const bar=element('progress');bar.max=Math.max(1,data.total_checkins);bar.value=time.count;bar.setAttribute('aria-label',time.label+': '+time.count+' check-ins');row.append(bar);times.append(row);}
    times.append(element('li',data.weekdays.map(day=>day.label+' '+day.count).join(' · ')));
    by('mood-insights-explanation').textContent='';
    status.textContent=data.start_date+' to '+data.end_date+' · Nairobi time · '+(data.total_checkins?'Your recorded moments, with a little perspective.':'Your next check-in can start this story.');
    content.hidden=false;
  }
  async function load(){
    if(!enabled||!accessToken)return;const session=generation,token=accessToken,id=++requestId;
    insightController?.abort();const c=new AbortController();insightController=c;content.hidden=true;status.textContent='Gathering your private check-in summary…';
    try{const data=await get('/moods/insights?days='+encodeURIComponent(period.value),c,session,token);if(session===generation&&id===requestId&&token===accessToken)render(data);}
    catch(e){if(session===generation&&id===requestId&&token===accessToken)status.textContent=e.name==='AbortError'?'Your summary took too long. Try Refresh.':e.message;}
    finally{if(insightController===c)insightController=null;}
  }
  period.addEventListener('change',()=>void load());
  by('mood-form').addEventListener('reset',()=>{contextStatus.textContent='';});
  window.enwenMoodInsights={reset,setup,load,selection,choose,label};reset();
})();
