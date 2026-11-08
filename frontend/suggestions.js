"use strict";
(() => {
  const panel=document.getElementById('wellness-suggestions'),message=document.getElementById('suggestion-message'),list=document.getElementById('suggestion-links');
  let generation=0,busy=false,controller=null;
  function reset(){generation++;controller?.abort();busy=false;list.replaceChildren();message.textContent='';panel.hidden=true;}
  async function load(){
    if(!accessToken||busy)return;const session=generation,token=accessToken;controller=new AbortController();busy=true;const timer=setTimeout(()=>controller.abort(),12000);
    try{
      const response=await fetch('/wellness/suggestions',{cache:'no-store',signal:controller.signal,headers:{Authorization:'Bearer '+token}});
      const data=await response.json();if(session!==generation||token!==accessToken)return;
      if(!response.ok)throw new Error('Your suggestions could not be loaded. Your check-ins are unchanged.');
      list.replaceChildren();message.textContent=data.basis;panel.hidden=false;
      for(const step of data.steps||[]){if(!['#/check-in','#/journal','#/pause','#/resources','#/mood-history'].includes(step.href))continue;
        const item=document.createElement('li'),link=document.createElement('a');link.href=step.href;link.textContent=step.title;item.append(link);list.append(item);}
      for(const resource of data.resources||[]){let url;try{url=new URL(resource.url);}catch{continue;}if(url.protocol!=='https:'||url.username||url.password)continue;
        const item=document.createElement('li'),link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=resource.title+' · '+resource.publisher;item.append(link);list.append(item);}
    }catch(e){if(session===generation){panel.hidden=false;message.textContent='Suggestions are temporarily unavailable. You can still choose a check-in, journal or pause.';list.replaceChildren();}}
    finally{clearTimeout(timer);if(session===generation)busy=false;}
  }
  window.enwenSuggestions={load,reset};reset();
})();
