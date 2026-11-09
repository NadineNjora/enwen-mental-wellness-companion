"use strict";
// One student contact journey. Local Mailpit test endpoints remain developer tools.
function resetTrustedContactPanel() {
  window.enwenLiveContacts?.reset();
  const home=document.getElementById('contact-home-status');
  if(home)home.textContent='';
}
function setupTrustedContactPanel(){resetTrustedContactPanel();void loadTrustedContact();}
async function loadTrustedContact(){await window.enwenLiveContacts?.load();}
window.addEventListener('focus',()=>{
  if(accessToken&&location.hash==='#/trusted-contact')void loadTrustedContact();
});
