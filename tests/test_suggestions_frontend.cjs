const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/suggestions.js'),'utf8');
const tick=()=>new Promise(r=>setImmediate(r));
function page(){
 class Node{constructor(){this.children=[];this.textContent='';this.hidden=false;}append(x){this.children.push(x);}replaceChildren(){this.children=[];}set innerHTML(v){throw new Error('Unsafe HTML');}}
 const nodes=Object.fromEntries(['wellness-suggestions','suggestion-message','suggestion-links'].map(id=>[id,new Node()]));let reply=async()=>({ok:true,json:async()=>({basis:'Synthetic own check-in',steps:[{title:'Reflect',href:'#/journal'},{title:'Bad',href:'javascript:bad()'}],resources:[{title:'Reading',publisher:'Source',url:'https://example.com/'},{title:'Unsafe',publisher:'Source',url:'javascript:bad()'}]})});
 const calls=[],window={},context=vm.createContext({document:{getElementById:id=>nodes[id],createElement:()=>new Node()},window,accessToken:'synthetic',URL,AbortController,setTimeout,clearTimeout,fetch:async(...args)=>{calls.push(args);return reply();}});vm.runInContext(source,context);
 return {nodes,calls,window,context,respond(fn){reply=fn;}};
}
(async()=>{let checks=0,p=page();await p.window.enwenSuggestions.load();assert.equal(p.nodes['suggestion-links'].children.length,2);assert.equal(p.nodes['wellness-suggestions'].hidden,false);checks++;
 assert.equal(p.calls[0][0],'/wellness/suggestions');assert.equal(p.calls[0][1].cache,'no-store');assert.equal(p.calls[0][1].headers.Authorization,'Bearer synthetic');checks++;
 p.window.enwenSuggestions.reset();assert.equal(p.nodes['suggestion-links'].children.length,0);assert.equal(p.nodes['wellness-suggestions'].hidden,true);checks++;
 p=page();let release;p.respond(()=>new Promise(r=>{release=()=>r({ok:true,json:async()=>({basis:'Old account',steps:[],resources:[]})});}));const old=p.window.enwenSuggestions.load();await tick();p.window.enwenSuggestions.reset();p.context.accessToken='other';release();await old;assert.equal(p.nodes['suggestion-message'].textContent,'');assert.equal(p.nodes['wellness-suggestions'].hidden,true);checks++;
 p=page();p.respond(async()=>({ok:false,json:async()=>({})}));await p.window.enwenSuggestions.load();assert.equal(p.nodes['suggestion-links'].children.length,0);assert.match(p.nodes['suggestion-message'].textContent,/temporarily unavailable/);checks++;
 console.log('Passed '+checks+' personalised suggestion UI checks; synthetic requests only.');
})().catch(e=>{console.error(e);process.exitCode=1;});
