/* Pure local analysis. GPT can influence practice priorities, never scores. */
(function(scope){
  'use strict';
  const C=scope.ChordCore||require('./core.js');
  const empty=()=>({correct:0,failed:0,misses:0,timeouts:0,retries:0,questions:0});
  function color(s){
    if(!s||!s.correct&&!s.failed)return 'untested';
    if(!s.failed&&!s.misses&&!s.retries)return 'green';
    return s.correct/(s.correct+s.failed)>=.5?'yellow':'red';
  }
  function rounds(data,mode){return (data.rounds||[]).filter(r=>r.mode===mode).sort((a,b)=>a.started.localeCompare(b.started));}
  function analyze(data,mode){
    const history=rounds(data,mode),recent=history.slice(-5);
    return C.TYPES.map(type=>{
      const s=empty();let testedRounds=0,last=-1;
      history.forEach((r,i)=>{if(r.byType[type.id])last=i;});
      recent.forEach(r=>{const row=r.byType[type.id];if(row){testedRounds++;for(const k of Object.keys(s))s[k]+=row[k]||0;}});
      const total=s.correct+s.failed;
      // All-time totals also contain legacy results with no reliable round boundaries.
      const lifetime=empty();
      for(const [key,row] of Object.entries(data.stats))if(key.startsWith(mode+':')&&key.split(':')[2]===type.id){
        lifetime.correct+=row.correct||0;lifetime.failed+=row.failed||0;lifetime.misses+=row.misses||0;
      }
      const evidence=total?s:lifetime,n=evidence.correct+evidence.failed;
      const weakness=n?Math.min(3,(evidence.failed*2+evidence.misses)/(n+1)):1;
      const gap=last<0?history.length+1:history.length-1-last;
      const reason=n?`${evidence.correct} correct, ${evidence.failed} failed; ${evidence.misses} missed guesses${total?' in the last 5 rounds':' in earlier history'}.`:'Not tested yet.';
      return {...type,...s,lifetime,testedRounds,gap,weight:1+weakness+Math.min(1,gap*.15),problem:n>0&&(evidence.failed>0||evidence.misses>0),reason};
    });
  }
  function plan(data,mode,targets,count,preferences={},suggestions=[]){
    if(!targets.length)return [];
    const rows=analyze(data,mode),uses={},typeUses={},output=[];
    const priorities=Object.fromEntries(suggestions.filter(s=>C.quality(s.id)).map(s=>[s.id,Math.max(-1,Math.min(1,Number(s.priority)||0))]));
    const types=new Set(targets.map(t=>t.id));
    const cap=types.size>=3?Math.max(1,Math.ceil(count*.4)):count;
    for(let i=0;i<count;i++){
      let options=targets.filter(t=>!output.length||t.id!==output.at(-1).id||t.root!==output.at(-1).root);
      if(!options.length)options=targets;
      const uncapped=options.filter(t=>(typeUses[t.id]||0)<cap);if(uncapped.length)options=uncapped;
      const ranked=options.map(t=>{
        const row=rows.find(r=>r.id===t.id),pref=Math.max(-1,Math.min(1,Number(preferences[t.id])||0));
        const score=row.weight*(1+pref*.3)*(1+(priorities[t.id]||0)*.25)/(1+(typeUses[t.id]||0));
        const stats=data.stats[mode+':'+t.root+':'+t.id];
        const rootWeight=stats?1+Math.min(1,(stats.failed+stats.misses)/(stats.correct+1)):1.2;
        return {target:t,score,rootScore:rootWeight/(1+(uses[t.root+':'+t.id]||0)),reason:row.reason};
      }).sort((a,b)=>b.score-a.score||b.rootScore-a.rootScore||a.target.id.localeCompare(b.target.id)||a.target.root-b.target.root);
      const chosen=ranked[0],t=chosen.target;
      output.push({...t,reason:chosen.reason});typeUses[t.id]=(typeUses[t.id]||0)+1;uses[t.root+':'+t.id]=(uses[t.root+':'+t.id]||0)+1;
    }
    return output;
  }
  const api={color,rounds,analyze,plan};scope.PainterCareer=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(globalThis);
