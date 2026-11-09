"use strict";
(() => {
  const by=id=>document.getElementById("live-contact-"+id);
  const form=by("form"),fields=by("fields"),message=by("message"),details=by("details"),revoke=by("revoke");
  let generation=0,busy=false,notice=null,record=null,attempt=null,alertNotice=null;
  const jobs=new Set();
  function reset(){generation++;for(const c of jobs)c.abort();jobs.clear();busy=false;notice=record=attempt=alertNotice=null;form.reset();fields.disabled=true;details.textContent="";message.textContent="";revoke.hidden=true;by("notice").textContent="";by('alert-notice').textContent='';by('alert-status').textContent='';by('alert-ack').checked=false;by('alert-allow').disabled=by('alert-off').disabled=true;}
  async function request(path,options={}){
    const session=generation,token=accessToken,c=new AbortController();jobs.add(c);const timer=setTimeout(()=>c.abort(),25000);
    try{
      const response=await fetch("/trusted-contact/live"+path,{method:options.method||"GET",cache:"no-store",signal:c.signal,
        headers:{Accept:"application/json",Authorization:"Bearer "+token,...(options.body?{"Content-Type":"application/json"}:{})},body:options.body?JSON.stringify(options.body):undefined});
      const data=response.status===204?null:await response.json();
      if(session!==generation||token!==accessToken)throw new Error("Previous session ignored.");
      if(response.status===401){endSession("Please log in again.");throw new Error("Please log in again.");}
      if(!response.ok){const e=new Error(typeof data.detail==="string"?data.detail:"Request could not be confirmed.");e.status=response.status;throw e;}
      return data;
    }finally{clearTimeout(timer);jobs.delete(c);}
  }
  function controls(){fields.disabled=!accessToken||busy||!notice;by("refresh").disabled=busy||!accessToken;revoke.disabled=busy;by('alert-allow').disabled=busy||!alertNotice||record?.status!=='accepted'||!by('alert-ack').checked;by('alert-off').disabled=busy||!alertNotice?.accepted;}
  async function load(){
    if(!accessToken||busy)return;const session=generation;busy=true;controls();
    try{
      const [n,r,a]=await Promise.all([request("/capability"),request(""),request('/alert-permission')]);if(session!==generation)return;
      alertNotice=a;by('alert-notice').textContent=a.short_text||a.text;by('alert-ack').checked=false;by('alert-status').textContent=(a.accepted?'Check-in email permission is on.':'Check-in email permission is off.')+(!a.delivery_enabled?' Sending is not available yet.':'');
      notice=n;record=r;by("notice").textContent=n.short_text||n.text;
      message.textContent=n.ready?'':n.reason;
      details.textContent=r?`${r.full_name} · ${r.email} · ${r.status==='accepted'?'Invitation accepted':r.status==='pending'?'Waiting for their reply':r.status}`:"Choose someone you trust and send an invitation below.";
      const home=document.getElementById('contact-home-status');if(home)home.textContent=r?`${r.full_name} · ${r.status==='accepted'?'In your corner':r.status==='pending'?'Invitation awaiting a reply':r.status}`:'Invite someone to be in your corner.';
      if(!by('name').value&&!by('email').value){
        if(r){by('name').value=r.full_name;by('email').value=r.email;}
        else{try{const profile=await fetch('/trusted-contact',{cache:'no-store',headers:{Authorization:'Bearer '+accessToken}});const saved=profile.ok?await profile.json():null;if(session===generation&&saved&&!by('name').value&&!by('email').value){by('name').value=saved.full_name;by('email').value=saved.email;}}catch{/* Invitation form remains editable. */}}
      }
      revoke.hidden=!r||r.status==="revoked";
    }catch(e){if(session===generation)message.textContent=e.message;}
    finally{if(session===generation){busy=false;controls();}}
  }
  form.addEventListener("submit",async event=>{
    event.preventDefault();if(fields.disabled||!form.reportValidity())return;
    const name=by("name").value.trim(),email=by("email").value.trim();
    if(!by("ack").checked)return;
    if(!notice?.ready){message.textContent=notice?.reason||'Invitation sending is not available yet.';return;}
    const dialog=document.getElementById('invitation-confirm'),dialogSession=generation;
    let confirmed;
    if(dialog?.showModal){busy=true;controls();document.getElementById('invitation-confirm-message').textContent='Send an ENWEN invitation to '+email+'?';dialog.returnValue='cancel';const choice=new Promise(resolve=>dialog.addEventListener('close',()=>resolve(dialog.returnValue==='send'),{once:true}));dialog.showModal();confirmed=await choice;if(dialogSession!==generation||!accessToken)return;busy=false;controls();}
    else confirmed=window.confirm(`Send an ENWEN invitation to ${email}? Your private entries are not shared.`);
    if(!confirmed||dialogSession!==generation||!accessToken)return;
    if(!attempt||attempt.full_name!==name||attempt.email!==email){
      if(!window.crypto?.randomUUID){message.textContent="Secure request identifiers are unavailable.";return;}
      attempt={request_id:window.crypto.randomUUID(),full_name:name,email};
    }
    const session=generation;busy=true;controls();
    try{
      const result=await request("",{method:"POST",body:{...attempt,notice_version:notice.notice_version,acknowledged:true}});
      if(session!==generation)return;
      record=result;message.textContent=result.delivery_status==="provider_accepted"?"Your invitation has been submitted by email. Your person can choose Accept or Decline.":"We couldn’t confirm the send. Refresh the status before trying again.";
      details.textContent=`${result.full_name} · ${result.email} · Waiting for their reply`;
      revoke.hidden=false;by("ack").checked=false;
    }catch(e){if(session===generation)message.textContent=e.status?e.message:"Outcome unconfirmed. Your form and request identifier are kept. Refresh status before retrying; nothing was automatically resent.";}
    finally{if(session===generation){busy=false;controls();}}
  });
  revoke.addEventListener("click",async()=>{
    if(busy||!record||!window.confirm("Remove this trusted person and cancel their invitation links?"))return;
    const session=generation;busy=true;controls();
    try{await request("/"+record.invitation_id,{method:"DELETE"});if(session===generation){record.status="revoked";revoke.hidden=true;details.textContent="Enrollment withdrawn. Earlier sent emails cannot be recalled.";}}
    catch(e){if(session===generation)message.textContent=e.message;}
    finally{if(session===generation){busy=false;controls();}}
  });
  by("refresh").addEventListener("click",()=>void load());
  by('alert-ack').addEventListener('change',controls);
  async function permission(accepted){
    if(busy||!alertNotice||(accepted&&!by('alert-ack').checked))return;const session=generation;busy=true;controls();
    try{const result=await request('/alert-permission',{method:'POST',body:{accepted,notice_version:alertNotice.notice_version}});if(session===generation){alertNotice.accepted=result.accepted;by('alert-ack').checked=false;by('alert-status').textContent=accepted?'Your choice is saved. ENWEN may ask your accepted person to check in when the chat flags a concern.':'Permission is off. No new check-in emails are authorised.';}}
    catch(e){if(session===generation)by('alert-status').textContent=e.message;}
    finally{if(session===generation){busy=false;controls();}}
  }
  by('alert-allow').addEventListener('click',()=>void permission(true));by('alert-off').addEventListener('click',()=>void permission(false));
  window.enwenLiveContacts={reset,load};
  reset();
})();
