/* Desktop round review and career chart. No network access from the web view. */
function createPainterReview({data,save,bridge,getMode,getTargets,start,retry,pauseForChart}){
  const C=ChordCore,A=PainterCareer,$=id=>document.getElementById(id);
  let mode='guess',queue=[],busy=false,request=0,roundId=null;
  data.rounds??=[];data.practicePreferences??={};
  const prefs=()=>data.practicePreferences[mode]??=( {types:{},comments:{},notes:'',advice:null} );
  const element=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
  function record(){
    const p=prefs(),r=data.rounds.find(r=>r.id===roundId);
    if(r)r.review=JSON.parse(JSON.stringify(p));save();
  }
  function makePlan(){return A.plan(data,mode,getTargets(),data.config.questions,prefs().types,prefs().advice?.priorities||[]);}
  function renderPlan(){
    queue=makePlan();const counts={};queue.forEach(t=>counts[t.id]=(counts[t.id]||0)+1);
    $('next-plan').replaceChildren();
    for(const row of A.analyze(data,mode))if(counts[row.id]){
      const li=element('li');li.append(element('strong',`${row.title} × ${counts[row.id]}`));
      const advice=prefs().advice?.priorities?.find(p=>p.id===row.id);
      const pref=prefs().types[row.id];
      li.append(element('span',row.reason+(pref===1?' You requested more.':pref===-1?' You requested less; still eligible.':'')+(advice?' '+advice.reason:'')));
      $('next-plan').append(li);
    }
    $('start-planned').disabled=busy||!queue.length;
    $('analyze-comments').disabled=busy||!bridge?.reviewPractice;
    $('review-local').hidden=!busy;
  }
  function changed(){
    request++;busy=false;prefs().advice=null;
    $('coach-status').textContent='Notes saved. Analyze comments to include their meaning in the plan.';
    bridge?.cancelReview?.();record();renderPlan();
  }
  function showRows(){
    $('review-types').replaceChildren();
    const eligible=new Set(getTargets().map(t=>t.id));
    const rows=A.analyze(data,mode).filter(r=>eligible.has(r.id));
    const problems=rows.filter(r=>r.problem).sort((a,b)=>b.weight-a.weight);
    $('round-analysis').textContent=problems.length?'Worth practicing: '+problems.slice(0,3).map(r=>r.title).join(', ')+'. Recent misses and failures carry more weight.':'No recurring difficulty found in the selected family yet. The next round balances coverage and retention.';
    for(const row of rows){
      const tr=element('tr'),name=element('th',row.title),evidence=element('td',row.reason);
      name.scope='row';tr.append(name,evidence);
      const cell=element('td'),select=element('select');select.setAttribute('aria-label',row.title+' practice preference');
      for(const [value,label] of [[0,'Balanced'],[1,'Test more'],[-1,'Test less']]){const opt=element('option',label);opt.value=value;select.append(opt);}
      select.value=prefs().types[row.id]||0;select.onchange=()=>{prefs().types[row.id]=Number(select.value);changed();};
      cell.append(select);tr.append(cell);
      const noteCell=element('td'),note=element('input');note.type='text';note.maxLength=500;note.placeholder='What felt difficult?';note.value=prefs().comments[row.id]||'';note.setAttribute('aria-label',row.title+' comment');
      note.oninput=()=>{prefs().comments[row.id]=note.value;changed();};noteCell.append(note);tr.append(noteCell);$('review-types').append(tr);
    }
  }
  function open({id=null,canRetry=false}={}){
    mode=getMode();if(mode==='instant')mode='guess';roundId=id;busy=false;request++;
    $('settings-dialog').close();$('review-title').textContent=(mode==='guess'?'Guess':'Paint the chord')+' · round review';
    $('review-notes').value=prefs().notes||'';
    $('review-retry').hidden=!canRetry;
    $('coach-status').textContent=prefs().advice?.summary||(bridge?.reviewPractice?'Local analysis is ready. Add comments, then Analyze comments for a GPT review.':'GPT is not connected yet. The local plan uses results and Test more / Test less; free-text comments are saved but not interpreted.');
    showRows();renderPlan();if(!$('review-dialog').open)$('review-dialog').showModal();
  }
  function close(){request++;busy=false;bridge?.cancelReview?.();$('review-dialog').close();}
  function startPlanned(){if(busy||!queue.length)return;record();const plan=queue.map(t=>({...t}));close();start(plan);}
  $('review-notes').oninput=()=>{prefs().notes=$('review-notes').value;changed();};
  $('close-review').onclick=close;$('review-dialog').addEventListener('cancel',()=>{request++;busy=false;bridge?.cancelReview?.();});
  $('review-retry').onclick=()=>{close();retry();};$('start-planned').onclick=startPlanned;
  $('review-local').onclick=()=>{request++;busy=false;bridge?.cancelReview?.();$('coach-status').textContent='Using the local plan. Free-text comments have not been interpreted.';renderPlan();};
  $('analyze-comments').onclick=()=>{
    if(busy||!bridge?.reviewPractice)return;
    record();busy=true;const token=String(++request);
    const rows=A.analyze(data,mode).filter(r=>getTargets().some(t=>t.id===r.id)).map(r=>({id:r.id,title:r.title,correct:r.correct,failed:r.failed,misses:r.misses,timeouts:r.timeouts,retries:r.retries,lifetime:r.lifetime,reason:r.reason}));
    const payload={mode,rows,preferences:prefs().types,comments:prefs().comments,notes:prefs().notes,
      earlierComments:A.rounds(data,mode).filter(r=>r.id!==roundId&&r.review).slice(-3).map(r=>({notes:r.review.notes,comments:r.review.comments})),questions:data.config.questions};
    $('coach-status').textContent='Reviewing your results and comments…';renderPlan();
    bridge.reviewPractice(token,JSON.stringify(payload));
  };
  if(bridge?.reviewReady)bridge.reviewReady.connect((token,raw)=>{
    if(token!==String(request)||!$('review-dialog').open)return;busy=false;
    try{const reply=JSON.parse(raw);if(reply.error)throw Error(reply.error);prefs().advice=reply;record();$('coach-status').textContent=reply.summary;}
    catch(e){$('coach-status').textContent=e.message+' Local analysis remains available.';}
    renderPlan();
  });
  function showCareer(){
    $('career-title').textContent=($('career-mode').value==='guess'?'Guess':'Paint the chord')+' · career';
    const selected=$('career-mode').value,history=A.rounds(data,selected);
    const all=Object.values(data.stats).filter(s=>s.mode===selected).reduce((n,s)=>n+s.correct+s.failed,0);
    const tracked=history.reduce((n,r)=>n+Object.values(r.byType).reduce((v,s)=>v+s.correct+s.failed,0),0),legacy=Math.max(0,all-tracked);
    $('career-note').textContent=history.length?`${history.length} recorded rounds · oldest on the left. Cells show correct tries / all tries.`:'No rounds recorded with this update yet. Finish a round to begin your trajectory.';
    if(legacy)$('career-note').textContent+=` ${legacy} earlier results remain in lifetime totals; their round boundaries were not recorded.`;
    $('career-chart').replaceChildren();$('career-detail').textContent='Select a cell for mistakes, retries and round settings.';
    const table=element('table'),head=element('thead'),header=element('tr');header.append(element('th','Chord type'));
    history.forEach((r,i)=>{const th=element('th',`R${i+1}`);th.scope='col';th.append(element('small',new Date(r.started).toLocaleDateString(undefined,{month:'short',day:'numeric'})));header.append(th);});head.append(header);table.append(head);
    const body=element('tbody');
    for(const type of C.TYPES){
      const tr=element('tr'),label=element('th',type.title);label.scope='row';tr.append(label);
      history.forEach((r,i)=>{
        const s=r.byType[type.id],status=A.color(s),cell=element('td'),button=element('button',s?`${s.correct}/${s.correct+s.failed}`:'—','career-cell '+status);
        const description=`${type.title}, round ${i+1}, ${new Date(r.started).toLocaleString()}: `+(s?`${s.correct} correct, ${s.failed} failed tries; ${s.misses} missed guesses, ${s.timeouts} timeouts, ${s.retries} retries. ${r.seconds||'?'} seconds per guess; ${r.limit||'?'} guesses per try.`:'Not tested.');
        button.title=description;button.setAttribute('aria-label',description);button.onclick=()=>{$('career-detail').textContent=description;};cell.append(button);tr.append(cell);
      });body.append(tr);
    }
    table.append(body);$('career-chart').append(table);
  }
  function openCareer(){ pauseForChart();$('career-mode').value=getMode()==='paint'?'paint':'guess';showCareer();$('career-dialog').showModal(); }
  $('career-mode').onchange=showCareer;$('close-career').onclick=()=>$('career-dialog').close();
  $('career-button').onclick=openCareer;$('review-career').onclick=openCareer;
  return {open,close,makePlan:()=>{mode=getMode();return makePlan();},startPlanned,isOpen:()=>$('review-dialog').open};
}
