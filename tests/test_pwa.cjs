const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'../frontend'), handlers={}, writes=[],deletes=[],network=[];
const cache={async addAll(urls){writes.push(...urls);},async match(url){return cached;}};
let cached=new Response('PUBLIC OFFLINE PAGE'),online=true;
const context=vm.createContext({URL,Response,
 self:{location:{origin:'https://enwen.example'},clients:{async claim(){}},addEventListener(name,fn){handlers[name]=fn;}},
 caches:{async open(){return cache;},async keys(){return ['other-app-cache','enwen-public-offline-v0','enwen-public-offline-v1'];},async delete(name){deletes.push(name);}},
 fetch:async request=>{network.push(request.url);if(!online)throw new TypeError('offline');return new Response('network');}
});
vm.runInContext(fs.readFileSync(path.join(root,'sw.js'),'utf8'),context);
const checks=[];
async function lifecycle(name){let result;handlers[name]({waitUntil(p){result=p;}});await result;}
async function fetchEvent(url,method='GET',mode='cors'){
 let promise;handlers.fetch({request:{url,method,mode},respondWith(p){promise=p;}});return promise?await promise:null;
}
(async()=>{
 await lifecycle('install');assert.equal(writes.length,4);assert.ok(writes.every(url=>url==='/static/offline.html'||url.startsWith('/static/icons/')));checks.push('installation caches only public offline page and icons');
 await lifecycle('activate');assert.deepEqual(deletes,['enwen-public-offline-v0']);checks.push('updates remove only old ENWEN public caches');
 for(const url of ['/chat','/journals','/moods','/auth/me','/auth/session','/trusted-contact','/chat/conversations']){
   assert.equal(await fetchEvent('https://enwen.example'+url),null);
 }
 checks.push('private API GET requests never enter service-worker cache handling');
 assert.equal(await fetchEvent('https://enwen.example/chat','POST'),null);checks.push('submitted messages and other POST bodies are never cached or queued');
 assert.equal(await fetchEvent('https://other.example/','GET','navigate'),null);checks.push('worker does not intercept another origin');
 const live=await fetchEvent('https://enwen.example/','GET','navigate');assert.equal(await live.text(),'network');assert.equal(writes.length,4);checks.push('online navigation uses live server without saving private rendered state');
 online=false;
 let offline=await fetchEvent('https://enwen.example/','GET','navigate');assert.equal(await offline.text(),'PUBLIC OFFLINE PAGE');checks.push('unreachable server falls back only to public offline guidance');
 assert.equal(await fetchEvent('https://enwen.example/static/icons/enwen-192.png?private=anything'),null);checks.push('query-bearing assets cannot expand offline cache');
 cached=undefined;offline=await fetchEvent('https://enwen.example/','GET','navigate');assert.equal(offline.status,503);checks.push('missing offline cache fails honestly with 503');
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.webmanifest'),'utf8'));
 assert.equal(manifest.display,'standalone');assert.equal(manifest.scope,'/');assert.ok(manifest.icons.some(x=>x.sizes==='192x192')&&manifest.icons.some(x=>x.sizes==='512x512'));checks.push('manifest declares standalone launch and required icon sizes');
 for(const size of [180,192,512]){const png=fs.readFileSync(path.join(root,`icons/enwen-${size}.png`));assert.equal(png.readUInt32BE(16),size);assert.equal(png.readUInt32BE(20),size);}
 checks.push('generated PNG files have the declared pixel dimensions');
 console.log(JSON.stringify({passed:checks.length,checks},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
