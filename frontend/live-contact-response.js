"use strict";
(() => {
  const params=new URLSearchParams(location.hash.slice(1)),withdraw=params.has("withdraw");
  let token=params.get(withdraw?"withdraw":"token"),version=null,busy=false;
  history.replaceState(null,"",location.pathname);
  const fields=document.getElementById("recipient-fields"),status=document.getElementById("recipient-status");
  document.getElementById("recipient-accept").hidden=withdraw;document.getElementById("recipient-decline").hidden=withdraw;document.getElementById("recipient-withdraw").hidden=!withdraw;
  if(!token||!/^[A-Za-z0-9_-]{43}$/.test(token)){status.textContent="This invitation link is missing or invalid. Open the complete link from your email.";return;}
  fetch("/trusted-contact/live/notice",{cache:"no-store",credentials:"omit"}).then(async response=>{
    if(!response.ok)throw new Error("The notice could not be loaded.");const data=await response.json();
    document.getElementById("recipient-notice").textContent=data.recipient_text;version=data.recipient_notice_version;fields.disabled=false;
  }).catch(()=>{status.textContent="The recipient notice could not be loaded. Reopen the email link after reconnecting. No decision was recorded.";});
  document.getElementById("recipient-form").addEventListener("submit",async event=>{
    event.preventDefault();if(busy||!token||!version||!document.getElementById("recipient-ack").checked)return;
    const decision=event.submitter?.value;if(!["accepted","declined","withdraw"].includes(decision))return;
    busy=true;fields.disabled=true;const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    try{
      const response=await fetch("/trusted-contact/live/respond",{method:"POST",cache:"no-store",credentials:"omit",signal:controller.signal,
        headers:{"Content-Type":"application/json"},body:JSON.stringify({token,decision,notice_version:version,acknowledged:true})});
      const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:"Decision could not be confirmed.");
      status.textContent=`Your choice is recorded: ${data.status}. Check-in emails also need the student’s permission. Keep your withdrawal link if you later change your mind.`;token=null;
    }catch(e){status.textContent=e.name==="AbortError"?"Outcome unconfirmed. No automatic retry was made. Contact the student before retrying.":e.message;fields.disabled=false;}
    finally{clearTimeout(timer);busy=false;}
  });
})();
