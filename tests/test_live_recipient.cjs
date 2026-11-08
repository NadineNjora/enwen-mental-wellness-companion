const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/live-contact-response.js'),'utf8');
const token='A'.repeat(43);const tick=()=>new Promise(r=>setImmediate(r));
async function page(hash,fail=false){
  const nodes={},calls=[];let handler;for(const id of ['recipient-fields','recipient-status','recipient-accept','recipient-decline','recipient-withdraw','recipient-notice','recipient-form','recipient-ack'])nodes[id]={disabled:true,hidden:false,checked:false,textContent:'',addEventListener(n,h){handler=h;}};
  const location={hash,pathname:'/static/live-contact-response.html'},history={replaceState(a,b,url){location.hash='';this.url=url;}};
  const context=vm.createContext({document:{getElementById:id=>nodes[id]},URLSearchParams,location,history,AbortController,setTimeout,clearTimeout,
    fetch:async(url,options={})=>{calls.push({url,options});if(options.method==='POST'){if(fail)throw new TypeError('Synthetic disconnect');return {ok:true,json:async()=>({status:'accepted'})};}return {ok:true,json:async()=>({recipient_text:'Synthetic recipient notice',recipient_notice_version:'version'})};}});
  vm.runInContext(source,context);await tick();return {nodes,calls,location,history,async send(value){await handler({preventDefault(){},submitter:{value}});await tick();}};
}
(async()=>{
  let checks=0,p=await page('');assert.equal(p.calls.length,0);assert.equal(p.nodes['recipient-fields'].disabled,true);checks++;
  p=await page('#token='+token);assert.equal(p.calls.length,1);assert.equal(p.location.hash,'');assert.equal(p.nodes['recipient-fields'].disabled,false);checks++;
  await p.send('accepted');assert.equal(p.calls.length,1);checks++;
  p.nodes['recipient-ack'].checked=true;await p.send('accepted');const call=p.calls[1];assert.equal(call.options.method,'POST');assert.equal(call.options.credentials,'omit');assert.equal(JSON.parse(call.options.body).token,token);assert.equal(p.nodes['recipient-fields'].disabled,true);checks++;
  p=await page('#withdraw='+token);assert.equal(p.nodes['recipient-accept'].hidden,true);assert.equal(p.nodes['recipient-withdraw'].hidden,false);assert.equal(p.calls.length,1);checks++;
  p.nodes['recipient-ack'].checked=true;await p.send('withdraw');assert.equal(JSON.parse(p.calls[1].options.body).decision,'withdraw');checks++;
  p=await page('#token='+token,true);p.nodes['recipient-ack'].checked=true;await p.send('declined');assert.equal(p.calls.length,2);assert.equal(p.nodes['recipient-fields'].disabled,false);checks++;
  assert.ok(!source.includes('innerHTML'));assert.ok(!source.includes('localStorage'));checks++;
  console.log('Passed '+checks+' recipient-page checks. Synthetic browser/API only.');
})().catch(e=>{console.error(e);process.exitCode=1;});
