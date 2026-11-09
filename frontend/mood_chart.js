"use strict";
(() => {
  const list=document.querySelector('#mood-history-list'); if(!list)return;
  const ns='http://www.w3.org/2000/svg',panel=document.createElement('section');
  panel.className='enwen-trend';panel.setAttribute('aria-labelledby','mood-trend-title');
  const heading=document.createElement('h4');heading.id='mood-trend-title';heading.textContent='Your moods, over time 🌱';
  const summary=document.createElement('p');summary.className='muted';
  const viewport=document.createElement('div');viewport.className='enwen-trend-scroll';
  const detail=document.createElement('p');detail.className='trend-selected';detail.setAttribute('role','status');
  let lastEntries=null,lastWidth=0;
  panel.append(heading,summary,viewport,detail);list.before(panel);
  const score=entry=>Math.round(entry.mood_score*10/entry.scale_max*10)/10;
  function node(tag,attrs={},text){const n=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n;}
  function date(time,full=false){return new Date(time).toLocaleString('en-KE',{timeZone:'Africa/Nairobi',day:'numeric',month:'short',...(full?{year:'numeric',hour:'2-digit',minute:'2-digit'}:{})});}
  function clear(message='Your first check-in will start your story here.'){lastEntries=null;lastWidth=0;viewport.replaceChildren();viewport.hidden=true;detail.hidden=true;summary.textContent=message;}
  function render(entries){
    if(entries.some(e=>![5,10].includes(e.scale_max)||!Number.isInteger(e.mood_score)||e.mood_score<1||e.mood_score>e.scale_max||!Number.isFinite(Date.parse(e.created_at)))){clear('Your graph could not load. Try refreshing your history.');return;}
    const points=entries.map(e=>({score:score(e),time:Date.parse(e.created_at)})).sort((a,b)=>a.time-b.time);
    if(!points.length){clear();return;}
    lastEntries=entries;lastWidth=viewport.clientWidth||900;
    const start=points[0].time,end=points[points.length-1].time,w=Math.max(440,Math.min(1000,viewport.clientWidth||900)),h=330,l=42,r=w-22,t=28,b=270;
    const x=time=>start===end?(l+r)/2:l+(time-start)/(end-start)*(r-l),y=value=>b-value/10*(b-t);
    const svg=node('svg',{viewBox:`0 0 ${w} ${h}`,role:'img','aria-labelledby':'mood-chart-title mood-chart-description'});
    svg.append(node('title',{id:'mood-chart-title'},'Your check-ins out of ten'),node('desc',{id:'mood-chart-description'},'All saved check-ins on a shared ten-point display. Focus a point to hear its score and date. Lines join recorded moments.'));
    const defs=node('defs'),gradient=node('linearGradient',{id:'mood-area',x1:'0',y1:'0',x2:'0',y2:'1'});
    gradient.append(node('stop',{offset:'0%','stop-color':'#a68ad5','stop-opacity':'.32'}),node('stop',{offset:'100%','stop-color':'#a68ad5','stop-opacity':'.02'}));defs.append(gradient);svg.append(defs);
    for(const value of [0,2,4,6,8,10])svg.append(node('line',{x1:l,x2:r,y1:y(value),y2:y(value),class:'trend-grid'}),node('text',{x:l-15,y:y(value)+4,'text-anchor':'end',class:'trend-label'},value));
    const coords=points.map(p=>`${x(p.time)},${y(p.score)}`).join(' ');
    if(points.length>1)svg.append(node('polygon',{points:`${l},${b} ${coords} ${r},${b}`,fill:'url(#mood-area)'}),node('polyline',{points:coords,fill:'none',class:'trend-line'}));
    const select=p=>{detail.textContent=`${date(p.time,true)} · ${p.score}/10`;};
    for(const p of points){const label=`${date(p.time,true)}: ${p.score} out of 10`,dot=node('circle',{cx:x(p.time),cy:y(p.score),r:5,class:'trend-dot',tabindex:0,'aria-label':label});dot.append(node('title',{},label));dot.addEventListener('focus',()=>select(p));dot.addEventListener('mouseenter',()=>select(p));dot.addEventListener('click',()=>select(p));svg.append(dot);}
    const ticks=start===end?[start]:Array.from({length:5},(_,i)=>start+(end-start)*i/4);
    ticks.forEach((time,i)=>svg.append(node('text',{x:x(time),y:b+30,'text-anchor':i===0?'start':i===ticks.length-1?'end':'middle',class:'trend-label'},date(time))));
    svg.append(node('text',{x:r,y:15,'text-anchor':'end',class:'trend-label'},'Mood / 10'));
    summary.textContent=`${points.length} moments · ${date(start)} — ${date(end)}`;
    viewport.replaceChildren(svg);viewport.hidden=false;detail.hidden=false;select(points[points.length-1]);
  }
  window.enwenMoodChart=Object.freeze({clear,render,score});clear();
  // History may arrive while its page is hidden. Refit once visible, and on resize.
  if(typeof ResizeObserver==='function')new ResizeObserver(()=>{
    const width=viewport.clientWidth;
    if(lastEntries&&width>0&&Math.round(width)!==Math.round(lastWidth))render(lastEntries);
  }).observe(viewport);
})();
