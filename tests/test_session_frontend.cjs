const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/app.js'),'utf8');
const functions=source.slice(source.indexOf('function installAccessToken('),source.indexOf('// Mood check-in elements.'));
const checks=[];
function page(responder) {
  let token=null, authGeneration=0, renders=0, setups=0, requestNumber=0;
  const timers=new Map(), nodes={};
  const element=()=>({textContent:'',hidden:true,disabled:false});
  const context=vm.createContext({
    accessToken:null, authGeneration:0, renewalTimer:null, expiryTimer:null, renewalRequest:null,
    loginButton:element(), loginPanel:element(), accountPanel:element(),welcomeTitle:element(),accountEmail:element(),consentStatus:element(),
    document:{querySelector:id=>nodes[id] ||= element()},
    window:{}, AbortController,
    setTimeout(fn,delay){timers.set(++requestNumber,{fn,delay});return requestNumber;},clearTimeout(id){timers.delete(id);},
    fetch:async(url,options)=>responder(url,options),
    apiRequest:async()=>({display_name:'Fictional Student',email:'fictional@example.com',wellness_consent_current:true}),
    showStatus(){},setupMoodPanel(){setups++;},setupJournalPanel(){setups++;},setupTrustedContactPanel(){setups++;},
    renderPage(){renders++;},endSession(){context.authGeneration++;context.accessToken=null;}
  });
  vm.runInContext(functions,context);
  return {context,timers,nodes,get setups(){return setups;},get renders(){return renders;}};
}
(async()=>{
  let p=page(async()=>({ok:true,status:200,json:async()=>({access_token:'synthetic-access',expires_in:900})}));
  await vm.runInContext('restoreSavedLogin()',p.context);
  assert.equal(p.context.accessToken,'synthetic-access');assert.equal(p.context.accountPanel.hidden,false);assert.equal(p.setups,3);assert.equal(p.renders,1);
  assert.equal(p.nodes['#student-badge'].textContent,'Fictional Student'); checks.push('refresh restores account and personal name');
  assert.ok([...p.timers.values()].some(timer=>timer.delay===840000));checks.push('renewal scheduled before access-token expiry');
  p=page(async()=>({ok:false,status:401}));await vm.runInContext('restoreSavedLogin()',p.context);assert.equal(p.context.accessToken,null);assert.equal(p.setups,0);checks.push('missing cookie leaves account screens closed');
  p=page(async()=>{throw new TypeError('offline');});await vm.runInContext('restoreSavedLogin()',p.context);assert.equal(p.context.loginButton.disabled,false);assert.equal(p.setups,0);checks.push('offline restoration enables manual login without revealing account');
  let resolve;
  p=page(()=>new Promise(done=>{resolve=done;}));const pending=vm.runInContext('restoreSavedLogin()',p.context);
  vm.runInContext('endSession()',p.context);resolve({ok:true,status:200,json:async()=>({access_token:'stale',expires_in:900})});await pending;
  assert.equal(p.context.accessToken,null);assert.equal(p.setups,0);checks.push('late restoration cannot undo logout');
  console.log(JSON.stringify({passed:checks.length,checks},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
