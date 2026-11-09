const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const tick=()=>new Promise(r=>setImmediate(r));
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.textContent='';this.handlers={};this.value='30';this.checked=false;this.hidden=false;}
 append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=[...nodes];}setAttribute(){}
 addEventListener(type,fn){(this.handlers[type]??=[]).push(fn);}fire(type){for(const fn of this.handlers[type]||[])fn();}
}
const ids=['mood-context-choices','mood-context-status','mood-insights-period','mood-insights-status','mood-insights-content','mood-insights-metrics','mood-insights-factors','mood-insights-times','mood-insights-unlabelled','mood-insights-explanation','mood-form'];
const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));
const options=['coursework','exams','finances','sleep','weather','commute','rest'].map(key=>({key,label:key,emoji:'🌼'}));
const response=data=>({ok:true,status:200,json:async()=>data});let responder=async()=>response({maximum:6,options});
const context=vm.createContext({document:{getElementById:id=>nodes[id],createElement:tag=>new Element(tag)},window:{},accessToken:'synthetic-token',AbortController,setTimeout,clearTimeout,
 fetch:(...args)=>responder(...args),endSession(){context.window.enwenMoodInsights.reset();context.accessToken=null;},pauseWellnessFeatures(){context.window.enwenMoodInsights.reset();}});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../frontend/mood-insights.js'),'utf8'),context);
const ui=context.window.enwenMoodInsights,checks=[];const check=(name,ok)=>{assert.ok(ok,name);checks.push(name);};
const data=(count=2)=>({total_checkins:count,days_with_checkins:2,normalised_summary:{scale_max:10,count,average_score:7.5},scale_summaries:[{scale_max:10,count:1,average_score:7},{scale_max:5,count:1,average_score:4}],contexts:[{key:'exams',emoji:'📚',label:'Exams',count:1}],unlabelled_checkins:1,times:[{label:'Morning',count:1}],weekdays:[{label:'Mon',count:1}],explanation:'Separate original scales, no causation.',start_date:'2026-11-01',end_date:'2026-11-07'});
(async()=>{
 await ui.setup({wellness_consent_current:true});check('catalog rendered as accessible checkbox labels',nodes['mood-context-choices'].children.length===7&&nodes['mood-context-choices'].children[0].children[0].type==='checkbox');
 for(const o of options.slice(0,6))ui.choose(o.key);
 check('six-factor cap enforced',ui.selection().length===6&&!ui.choose('rest'));
 const first=nodes['mood-context-choices'].children[0].children[0];first.checked=false;first.fire('change');
 check('unselecting permits another factor',ui.choose('rest')&&ui.selection().includes('rest'));
 responder=async()=>response(data());await ui.load();
 check('one combined ten-point average rendered',nodes['mood-insights-metrics'].children.length===3&&nodes['mood-insights-metrics'].children[2].children[0].textContent==='7.5/10');
 check('selected factors remain while verbose notices are removed',nodes['mood-insights-factors'].children[0].textContent.includes('Exams')&&nodes['mood-insights-unlabelled'].textContent===''&&nodes['mood-insights-explanation'].textContent==='');
 check('time bars have accessible labels and bounded totals',nodes['mood-insights-times'].children[0].children[0].max===2);
 responder=async()=>{throw new TypeError('Synthetic offline');};await ui.load();
 check('network failure hides old private summary',nodes['mood-insights-content'].hidden&&nodes['mood-insights-status'].textContent==='Synthetic offline');
 check('failed summary refresh preserves check-in factor draft',ui.selection().length===6);
 let old,newer;responder=()=>new Promise(r=>{if(!old)old=r;else newer=r;});
 const a=ui.load();nodes['mood-insights-period'].value='7';const b=ui.load();
 newer(response(data(3)));await b;old(response(data(99)));await a;
 check('late period response cannot replace current summary',nodes['mood-insights-metrics'].children[0].children[0].textContent==='3');
 let finish;responder=()=>new Promise(r=>finish=r);const pending=ui.load();ui.reset();context.accessToken=null;finish(response(data(100)));await pending;
 check('logout clears factors and private metrics',ui.selection().length===0&&nodes['mood-insights-metrics'].children.length===0&&nodes['mood-insights-content'].hidden);
 check('late response after logout ignored',nodes['mood-insights-status'].textContent==='');
 check('logged-out period control disabled',nodes['mood-insights-period'].disabled);
 console.log(`Passed ${checks.length} mood insight UI checks; synthetic DOM/API only.`);for(const name of checks)console.log('PASS:',name);
})().catch(e=>{console.error(e);process.exitCode=1;});
