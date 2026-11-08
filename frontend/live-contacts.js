"use strict";
(() => {
  const by=id=>document.getElementById("live-contact-"+id);
  const form=by("form"),fields=by("fields"),message=by("message"),details=by("details"),revoke=by("revoke");
  let generation=0,busy=false,notice=null,record=null,attempt=null;
  const jobs=new Set();
  function reset(){generation++;for(const c of jobs)c.abort();jobs.clear();busy=false;notice=record=attempt=null;form.reset();fields.disabled=true;details.textContent="";message.textContent="";revoke.hidden=true;by("notice").textContent="";}
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
  function controls(){fields.disabled=!accessToken||busy||!notice?.ready;by("refresh").disabled=busy||!accessToken;revoke.disabled=busy;}
  async function load(){
    if(!accessToken||busy)return;const session=generation;busy=true;controls();
    try{
      const n=await request("/notice"),r=await request("");if(session!==generation)return;
      notice=n;record=r;by("notice").textContent=n.text;
      message.textContent=n.reason;
      details.textContent=r?`${r.full_name} · ${r.email} · ${r.status}. Email: ${r.delivery_status}. Automatic alerts are off.`:"No real email enrollment yet. Local practice contacts stay separate.";
      revoke.hidden=!r||r.status==="revoked";
    }catch(e){if(session===generation)message.textContent=e.message;}
    finally{if(session===generation){busy=false;controls();}}
  }
  form.addEventListener("submit",async event=>{
    event.preventDefault();if(fields.disabled||!form.reportValidity())return;
    const name=by("name").value.trim(),email=by("email").value.trim();
    if(!by("ack").checked)return;
    if(!window.confirm(`Send one real ENWEN invitation email to ${email}? It shares your display name and response links, not your private entries.`))return;
    if(!attempt||attempt.full_name!==name||attempt.email!==email){
      if(!window.crypto?.randomUUID){message.textContent="Secure request identifiers are unavailable.";return;}
      attempt={request_id:window.crypto.randomUUID(),full_name:name,email};
    }
    const session=generation;busy=true;controls();
    try{
      const result=await request("",{method:"POST",body:{...attempt,notice_version:notice.notice_version,acknowledged:true}});
      if(session!==generation)return;
      record=result;message.textContent=result.delivery_status==="provider_accepted"?"Brevo accepted the invitation; this is not proof it reached their inbox. They must choose Accept or Decline.":"Sending is uncertain. Refresh status and check Brevo before considering a replacement. No automatic resend occurred.";
      details.textContent=`${result.full_name} · ${result.email} · ${result.status}. Email: ${result.delivery_status}. Automatic alerts are off.`;
      revoke.hidden=false;by("ack").checked=false;
    }catch(e){if(session===generation)message.textContent=e.status?e.message:"Outcome unconfirmed. Your form and request identifier are kept. Refresh status before retrying; nothing was automatically resent.";}
    finally{if(session===generation){busy=false;controls();}}
  });
  revoke.addEventListener("click",async()=>{
    if(busy||!record||!window.confirm("Withdraw this real contact enrollment and invalidate its response links?"))return;
    const session=generation;busy=true;controls();
    try{await request("/"+record.invitation_id,{method:"DELETE"});if(session===generation){record.status="revoked";revoke.hidden=true;details.textContent="Enrollment withdrawn. Earlier sent emails cannot be recalled.";}}
    catch(e){if(session===generation)message.textContent=e.message;}
    finally{if(session===generation){busy=false;controls();}}
  });
  by("refresh").addEventListener("click",()=>void load());
  window.enwenLiveContacts={reset,load};
  reset();
})();
