(async function () {
  'use strict';
  const C=ChordCore, $=id=>document.getElementById(id);
  let bridge=null, installPrompt=null;
  if(window.qt?.webChannelTransport){
    await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='qrc:///qtwebchannel/qwebchannel.js';s.onload=resolve;s.onerror=reject;document.head.appendChild(s);});
    bridge=await new Promise(resolve=>new QWebChannel(qt.webChannelTransport,ch=>resolve(ch.objects.painter)));
    $('back').hidden=false;$('back').textContent='← Home';$('back').onclick=()=>bridge.back();
  }
  function warn(message){$('storage-warning').hidden=false;$('storage-warning').textContent=message;}
  const defaults={rootFret:8,quality:'major',pool:'all',keys:'current',limit:3,seconds:20,questions:10,showNotes:true,showIntervals:true};
  let data={version:1,config:{...defaults},history:[],stats:{}};
  try{
    const raw=bridge ? await new Promise(resolve=>bridge.load(resolve)) : localStorage.getItem('chord-painter-v1');
    if(raw){const saved=JSON.parse(raw);if(saved.version!==1||!Array.isArray(saved.history)||!saved.stats)throw new Error('Unsupported saved data');data=saved;data.config={...defaults,...data.config};}
  }catch(e){warn('Saved practice could not be loaded. New results will not overwrite it. '+e.message);data.readOnly=true;}
  if(bridge)bridge.error.connect(warn);
  function save(){
    if(data.readOnly)return;
    try{const value=JSON.stringify(data);if(bridge)bridge.save(value);else localStorage.setItem('chord-painter-v1',value);}
    catch(e){warn('Progress could not be saved on this device. '+e.message);}
  }
  for(const name of ['settings','audio']){
    $('open-'+name).onclick=() => $(name+'-dialog').showModal();
    $('close-'+name).onclick=() => $(name+'-dialog').close();
  }
  function closeSetup(){ $('settings-dialog').close();$('audio-dialog').close(); }
  for(const id of ['reset-round','pause','reveal'])$(id).addEventListener('click',closeSetup);
  const clamp=(value,min,max,fallback)=>Number.isFinite(Number(value))?Math.min(max,Math.max(min,Math.round(Number(value)))):fallback;
  data.config.rootFret=clamp(data.config.rootFret,0,12,8);
  data.config.limit=clamp(data.config.limit,1,10,3);data.config.seconds=clamp(data.config.seconds,5,120,20);
  data.config.questions=clamp(data.config.questions,1,100,10);
  if(!C.quality(data.config.quality))data.config.quality='major';
  let mode='instant',frets=C.shape(data.config.rootFret,data.config.quality),round=null,practice=null,recorded=false,revealed=false,lastTarget='',paintedTarget=null;
  let referenceRoot=C.rootAt(data.config.rootFret),anchorFret=data.config.rootFret;
  let preferredInputMode=bridge?'play':'click';
  let inputMode=preferredInputMode,listeningBusy=false,listenState=null,listeningRound=null,resumeAfterListen=false,playActive=false,calibrated=false;
  // The root anchors transposition; scrolling the five-fret window never moves notes.
  let firstFret=1;
  function frameChord(){
    firstFret=Math.max(1,anchorFret-2);
    const played=frets.filter(f=>f>0);
    if(!played.length)return;
    const low=Math.min(...played),high=Math.max(...played);
    firstFret=high-low<5?Math.max(1,Math.min(low,Math.max(firstFret,high-4))):Math.min(firstFret,low);
  }
  frameChord();
  C.TYPES.forEach(t=>{const option=document.createElement('option');option.value=t.id;option.textContent=t.title;$('quality').appendChild(option);});
  const settings=[['root-fret','rootFret'],['quality','quality'],['pool','pool'],['keys','keys'],['limit','limit'],['seconds','seconds'],['questions','questions']];
  for(const [id,key] of settings)$(id).value=data.config[key];
  for(const [id,key] of [['show-notes','showNotes'],['show-intervals','showIntervals']]){
    $(id).checked=data.config[key]!==false;
    $(id).onchange=()=>{data.config[key]=$(id).checked;save();renderGrid();renderHearing();};
  }
  function toneLabels(tone){
    return [data.config.showIntervals!==false?'interval '+tone.degree:'',data.config.showNotes!==false?tone.note:''].filter(Boolean).join(', ');
  }
  function message(text,kind=''){$('feedback').textContent=text;$('feedback').className='feedback '+kind;}
  function completed(){return round&&round.status!=='active';}
  function locked(){return !!(round&&round.status==='active');}
  function inRound(){return !!(practice&&!practice.complete);}
  function canEdit(){return !listeningBusy&&(mode==='instant'||(mode==='paint'&&locked()&&!round.paused));}
  function renderHearing(){
    const p=listenState?.heard,setup=listenState?.stage?.startsWith('calibration');
    if(!p){$('listen-heard').textContent=playActive&&listeningBusy?'Waiting for a clear note…':'';return;}
    const parts=[];
    if(setup||!inRound()||data.config.showNotes!==false)parts.push(`${p.note} · ${p.hz.toFixed(1)} Hz`);
    if(!setup&&inRound()&&data.config.showIntervals!==false)parts.push('interval '+C.tone(referenceRoot,C.mod(p.midi),null).degree);
    const tuning=Math.abs(p.cents)<=5?'in tune':`${Math.round(Math.abs(p.cents))} cents ${p.cents<0?'flat':'sharp'}`;
    $('listen-heard').textContent=(parts.length?parts.join(' · '):'Pitch detected')+' · '+tuning;
  }
  function syncListening(){
    $('listening-panel').hidden=mode==='guess'||inputMode!=='play';
    const setup=inputMode==='play'&&playActive&&(!calibrated||listenState?.stage?.startsWith('calibration'));
    document.body.classList.toggle('calibrating',setup);
    document.body.classList.toggle('playing',inputMode==='play');
    $('chord-prompt').hidden=setup;
    $('open-audio').hidden=inputMode!=='play';
    $('listen-heading').textContent=setup?'GUITAR CHECK':listeningBusy?'LISTENING':'GUITAR';
    const names=['E','A','D','G','B','e'],stage=listenState?.stage;
    const index=listenState?.index??0;
    const progressKey=JSON.stringify([stage,index,calibrated,listenState?.kinds]);
    if($('string-progress').dataset.state!==progressKey){
      $('string-progress').dataset.state=progressKey;$('string-progress').replaceChildren();
      names.forEach((name,i)=>{
        const chip=document.createElement('span');
        const done=stage==='calibration-note'?i<index:stage==='strings'||stage==='complete'?listenState.kinds?.[i]!=='pending':calibrated;
        const current=(stage==='calibration-note'||stage==='strings')&&i===index;
        chip.className=current?'current':done?'done':'';chip.textContent=name;
        chip.setAttribute('aria-label',`String ${6-i}, ${name}: ${current?'play now':done?'checked':'waiting'}`);
        if(current)chip.setAttribute('aria-current','step');
        $('string-progress').append(chip);
      });
    }
    const voice=$('voice-status').textContent;
    $('voice-cue').textContent=voice.startsWith('Voice ready')?'Voice on · Go / Next / Quit':voice.includes('Opening')?'Starting voice…':playActive?'Voice unavailable · use the buttons':'';
    $('input-setting').hidden=mode==='guess';
    $('listen-availability').hidden=!!bridge;
    $('input-mode').disabled=!bridge||inRound();
    $('input-mode').value=inputMode;
    $('listen-details').hidden=inputMode!=='play';
    $('listen-start').disabled=!bridge;
    $('listen-stop').disabled=!playActive;
    $('play-again').hidden=!playActive||!calibrated||listeningBusy||(mode==='paint'&&!locked());
    $('play-again').textContent=mode==='instant'?'Go — play chord':'Play chord again';
    $('play-again').disabled=mode==='paint'&&!locked();
    $('listen-help').disabled=!playActive;
    $('listen-retry').hidden=listenState?.stage!=='strings';
    $('listen-muted').hidden=listenState?.stage!=='strings';
    $('listen-retry').disabled=!listeningBusy||listenState?.stage!=='strings'||listenState.index===0;
    $('listen-muted').disabled=!listeningBusy||listenState?.stage!=='strings';
    $('extra-check').hidden=inRound()||!calibrated;
    $('check-note').disabled=!playActive||listeningBusy;
    $('listen-results').textContent=listenState?.stage?.startsWith('calibration')?`Calibration · check ${listenState.index+1} of 6 · string ${6-listenState.index}`:listenState?.kinds?.some(k=>k!=='pending')?listenState.kinds.map((kind,i)=>`${6-i}: ${kind==='pending'?'…':kind==='note'?'fret '+listenState.frets[i]:'muted'}`).join(' · '):'';
    $('listen-level').textContent=listenState?.db!=null?`${listenState.input} · channel ${listenState.channel+1} · Level ${listenState.db.toFixed(0)} dB · Trigger ${listenState.gate.toFixed(0)} dB${listenState.clipped?' · CLIPPING':''}`:'';
    renderHearing();
  }
  function stopListening(resume=true){
    if(playActive)bridge?.listenStop();
    playActive=false;calibrated=false;listeningBusy=false;
    if(resume&&resumeAfterListen&&round===listeningRound&&locked()&&round.paused)round.resume(Date.now());
    resumeAfterListen=false;listenState=null;
    $('listen-status').textContent='Play stopped. Recalibrate to listen again.';
    $('voice-status').textContent='Voice stopped.';
  }
  function clearListeningReview(){
    if(!playActive){listenState=null;$('listen-status').textContent='Choose Play to calibrate.';}
  }
  function calibrate(){
    if(!bridge)return;
    closeSetup();
    if(locked()&&!round.paused)round.pause(Date.now());
    inputMode='play';playActive=true;calibrated=false;listeningBusy=true;listenState=null;
    $('listen-status').textContent='Opening input for calibration…';$('voice-status').textContent='Opening Windows default microphone…';render();bridge.listenStart();
  }
  function beginAnswer(){
    if(!playActive||!calibrated)return;
    listeningRound=round;resumeAfterListen=!!locked();
    if(locked()&&!round.paused)round.pause(Date.now());
    listeningBusy=true;render();bridge.listenBegin();
  }
  function quitPlay(){
    stopListening(false);round=null;practice=null;recorded=false;frets=[null,null,null,null,null,null];
    message('Round stopped. Earlier saved results are kept.');render();
  }
  $('input-mode').onchange=()=>{inputMode=preferredInputMode=$('input-mode').value;if(inputMode==='play')calibrate();else{stopListening();render();}};
  $('listen-start').onclick=calibrate;
  $('play-again').onclick=beginAnswer;
  $('listen-stop').onclick=()=>{stopListening(false);if(locked())round.pause(Date.now());render();};
  $('listen-help').onclick=()=>{closeSetup();calibrated=false;listeningBusy=true;if(locked())round.pause(Date.now());bridge?.listenHelp();render();};
  $('check-note').onclick=()=>{closeSetup();listeningBusy=true;bridge?.listenCheck(Number($('check-string').value),Number($('check-fret').value));render();};
  $('listen-retry').onclick=()=>bridge?.listenRetry();
  $('listen-muted').onclick=()=>bridge?.listenMuted();
  $('quit').onclick=quitPlay;
  if(bridge){
    bridge.voiceStatus.connect(text=>{if(playActive){$('voice-status').textContent=text;syncListening();}});
    bridge.voiceCommand.connect(word=>{
      if(!playActive||document.hidden||$('settings-dialog').open||$('audio-dialog').open)return;
      if(word==='quit')quitPlay();
      else if(word==='go'&&calibrated&&!listeningBusy){
        if(!inRound()&&mode==='paint')startRound();
        else if(mode==='instant'||locked())beginAnswer();
      }else if(word==='next'&&calibrated&&!listeningBusy){
        if(completed()&&inRound())startQuestion();
        else if(locked()&&!round.paused&&listenState?.stage==='complete')$('submit-paint').click();
      }
    });
    bridge.listening.connect(raw=>{
      if(!playActive)return;
      const state=JSON.parse(raw),oldStage=listenState?.stage,previous=JSON.stringify([frets,listenState?.index,oldStage]);
      listenState=state;calibrated=state.calibrated;
      listeningBusy=!['ready','complete','error','stopped'].includes(state.stage);
      if(['strum','strum-release','strings'].includes(state.stage)||(state.stage==='complete'&&oldStage!=='complete'))frets=[...state.frets];
      $('listen-status').textContent=state.message;
      if(['error','stopped'].includes(state.stage)){playActive=false;calibrated=false;$('voice-status').textContent='Voice stopped.';}
      if(state.stage==='complete'&&oldStage!=='complete'){
        if(resumeAfterListen&&round===listeningRound&&locked()&&round.paused)round.resume(Date.now());
        resumeAfterListen=false;frameChord();
      }
      if(state.stage==='ready'&&oldStage!=='ready'&&!inRound())message('Ready. Click or say Go to begin.');
      if(state.stage==='ready'&&oldStage!=='ready'&&locked()){beginAnswer();return;}
      if(oldStage!==state.stage)render();
      else{syncListening();if(previous!==JSON.stringify([frets,state.index,state.stage])){renderGrid();renderAnswer();}}
    });
  }
  function syncControls(){
    syncListening();
    document.querySelectorAll('[data-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.mode===mode);b.setAttribute('aria-pressed',b.dataset.mode===mode);});
    $('quality-field').hidden=mode!=='instant';$('pool-field').hidden=mode==='instant';$('keys-field').hidden=mode==='instant';$('limit-fields').hidden=mode==='instant';
    $('questions-field').hidden=mode==='instant';
    for(const [id] of settings)$(id).disabled=inRound()||listeningBusy;
    $('clear').hidden=mode==='guess';$('reset').hidden=mode!=='instant';$('clear').disabled=!canEdit();
    $('start').hidden=mode==='instant'||inRound();$('start').textContent=inputMode==='play'?'Go →':practice?.complete?'New round →':'Start round →';$('start').disabled=inputMode==='play'&&(!calibrated||listeningBusy);$('quit').hidden=!inRound()&&!playActive;
    $('next').hidden=!completed()||!!practice?.complete;
    $('reset-round').hidden=!practice;
    $('reset-round').disabled=listeningBusy;$('reset').disabled=listeningBusy;
    $('round-info').hidden=!practice;
    if(practice){
      $('question-progress').textContent=practice.complete?'Round complete':`Question ${practice.results.length+(locked()?1:0)} of ${practice.count}`;
      $('round-score').textContent=`${practice.correct} correct · ${practice.failed} failed`;
    }
    $('pause').hidden=!locked();$('pause').textContent=round?.paused?'Resume':'Pause';
    $('pause').disabled=listeningBusy;
    $('reveal').hidden=!locked();$('reveal').disabled=!!round?.paused;
    $('submit-paint').textContent=inputMode==='play'?'Next — check chord':'Submit chord ↵';
    $('submit-paint').hidden=mode!=='paint'||!locked();$('submit-paint').disabled=!!round?.paused;
    $('game-info').hidden=mode==='instant'||!round;
    $('guess-form').hidden=mode!=='guess'||!locked();$('guess-input').disabled=!!round?.paused;
    $('guess-form').querySelector('button').disabled=!!round?.paused;
    $('root-note').textContent=C.NOTES[C.rootAt(data.config.rootFret)];
    $('setup-note').textContent=inRound()?'Reset round clears this round and starts at question 1. Settings unlock when the round ends.':mode==='instant'?'Move the root fret to transpose the whole shape.':'Choose how many questions to play. Each question has its own guess limit; each guess gets a fresh timer.';
    $('grid-help').textContent=inputMode==='play'?(listenState?.stage==='complete'?'Review your dots. Click to correct a note.':'Follow the highlighted string. Mute between notes.'):mode==='guess'?'Read the shape. Name the chord.':'Click to place or erase a dot. X / O = muted / open.';
  }
  function renderGrid(){
    const grid=$('diagram'),focus=grid.contains(document.activeElement)?{...document.activeElement.dataset}:null;grid.replaceChildren();
    const checking=document.body.classList.contains('calibrating');
    const displayFrets=checking?[null,null,null,null,null,null]:frets;
    const root=referenceRoot;
    const hiddenAnswer=mode==='guess'&&!completed();
    const matches=C.identify(frets,root);
    const type=mode==='paint'&&round?round.id:matches[0]?.root===root?matches[0].id:null;
    const first=checking?1:firstFret, active=canEdit();
    $('fret-range').textContent=`Frets ${first}–${first+4}`;
    $('lower-frets').disabled=first===1;
    const outside=frets.flatMap((f,i)=>f>0&&(f<first||f>first+4)?[`${['low E','A','D','G','B','high e'][i]} · fret ${f}`]:[]);
    $('outside-view').hidden=!outside.length;
    $('outside-view').textContent=outside.length?'Notes outside view: '+outside.join(', '):'';
    const spacer=document.createElement('span');grid.append(spacer);
    const currentString=listeningBusy&&['strings','calibration-note'].includes(listenState?.stage)?listenState.index:-1;
    ['E','A','D','G','B','e'].forEach((s,i)=>{const el=document.createElement('span');el.className='string-label'+(i===currentString?' listening-string':'');el.textContent=s;el.title=(6-i)+' string';grid.append(el);});
    grid.append(document.createElement('span'));
    for(let i=0;i<6;i++){
      const b=document.createElement('button');b.type='button';b.className='open-cell'+(displayFrets[i]===0?' sounding':'');b.disabled=!active;
      const pc=C.mod(C.OPEN[i]),tone=C.tone(root,pc,type);
      b.textContent=checking?'·':frets[i]===null?'×':frets[i]===0?'○':'·';
      if(displayFrets[i]===0){const note=document.createElement('span');note.className='open-note';note.textContent=[data.config.showIntervals!==false?tone.degree:'',data.config.showNotes!==false?tone.note:''].filter(Boolean).join(' ');b.append(note);}
      b.setAttribute('aria-label',checking?`String ${6-i}: ${i===currentString?'play the requested note':'waiting'}`:`String ${6-i}: ${frets[i]===null?'muted':frets[i]===0?'open'+(toneLabels(tone)?', '+toneLabels(tone):''):'fretted'}. Toggle open or mute`);
      b.onclick=()=>{clearListeningReview();frets[i]=frets[i]===0?null:0;render();};grid.append(b);
    }
    for(let fret=first;fret<first+5;fret++){
      const label=document.createElement('span');label.className='fret-label'+(fret===anchorFret?' anchor':'');label.textContent=fret;grid.append(label);
      for(let i=0;i<6;i++){
        const pc=C.mod(C.OPEN[i]+fret),t=C.tone(root,pc,type),b=document.createElement('button');b.type='button';
        b.className='fret-cell'+(i===0?' edge-left':i===5?' edge-right':'')+(fret===first?' first':'')+(fret===1?' nut':'');
        if(i===currentString)b.classList.add('listening-string');
        b.style.setProperty('--string-width',(3-i*.35)+'px');b.disabled=!active;
        b.setAttribute('aria-label',`String ${6-i}, fret ${fret}`+(checking?'':toneLabels(t)?', '+toneLabels(t):''));b.setAttribute('aria-pressed',displayFrets[i]===fret);
        b.dataset.string=i;b.dataset.fret=fret;
        if(displayFrets[i]===fret){
          const dot=document.createElement('span');dot.className='dot'+(pc===root?' root':'');
          if(data.config.showIntervals!==false){const degree=document.createElement('b');degree.textContent=t.degree;dot.append(degree);}
          if(data.config.showNotes!==false){const note=document.createElement('small');note.textContent=t.note;dot.append(note);}
          b.append(dot);
        }
        b.onclick=()=>{clearListeningReview();frets[i]=frets[i]===fret?null:fret;render();};
        b.onkeydown=e=>{let ds=0,df=0;if(e.key==='ArrowLeft')ds=-1;if(e.key==='ArrowRight')ds=1;if(e.key==='ArrowUp')df=-1;if(e.key==='ArrowDown')df=1;if(ds||df){
          e.preventDefault();const nextFret=Math.max(1,fret+df);
          if(nextFret<first||nextFret>first+4){firstFret+=df;renderGrid();}
          grid.querySelector(`[data-string="${Math.max(0,Math.min(5,i+ds))}"][data-fret="${nextFret}"]`)?.focus();
        }};
        grid.append(b);
      }
    }
    $('root-tag').textContent=`ROOT ${C.NOTES[root]} · ${anchorFret===0?'OPEN E':'FRET '+anchorFret}`;
    if(focus?.fret)grid.querySelector(`[data-string="${focus.string}"][data-fret="${focus.fret}"]`)?.focus({preventScroll:true});
    $('canvas-caption').textContent=checking?'CHECK YOUR GUITAR':mode==='instant'?'E-SHAPE · STANDARD TUNING':mode==='guess'?'READ THE SHAPE':'BUILD THE SHAPE';
  }
  function renderAnswer(){
    const matches=C.identify(frets,referenceRoot), primary=matches[0];
    const hidden=mode==='guess'&&!completed();
    $('chord-name').hidden=hidden&&locked();
    $('answer-label').textContent=mode==='instant'?'YOUR CHORD':mode==='guess'?'NAME THIS CHORD':'PAINT THIS CHORD';
    let title,desc,root,id;
    if(mode!=='instant'&&!round){title=mode==='guess'?'Name it.':inputMode==='play'&&calibrated?'Ready.':'Make it.';desc=inputMode==='play'&&calibrated?'Your guitar is calibrated.':'Start when you’re ready.';}
    else if(mode==='paint'&&round){title=C.name(round.root,round.id);desc=C.quality(round.id).title;root=round.root;id=round.id;}
    else if(primary&&!hidden){title=primary.name;desc=C.quality(primary.id).title;root=primary.root;id=primary.id;}
    else if(hidden){title='?';desc='A chord name, such as C, Cm, or C7.';}
    else{title=C.pitches(frets).length?'Keep painting.':'Your canvas.';desc=C.pitches(frets).length?'No exact match in the chord library.':'Place a dot to begin.';}
    $('chord-name').textContent=title;$('chord-name').classList.toggle('long',title.length>5);
    $('chord-description').textContent=desc;$('tones').replaceChildren();
    // Reverse mode keeps the target name visible but does not give away all its tones.
    if(id&&!hidden&&(mode!=='paint'||completed())){
      const q=C.quality(id);q.intervals.forEach(pc=>{const t=C.tone(root,C.mod(root+pc),id),chip=document.createElement('span');chip.className='tone-chip';const n=document.createElement('b'),d=document.createElement('small');n.textContent=t.note;d.textContent=t.degree;chip.append(n,d);$('tones').append(chip);});
    }
    $('alternatives').textContent=mode==='instant'&&matches.length>1?'Also '+matches.slice(1,3).map(m=>m.name).join(' · '):'';
  }
  function render(){syncControls();renderGrid();renderAnswer();renderClock();}
  function renderClock(){
    if(!round)return;
    const remaining=round.paused?round.remaining:Math.max(0,round.deadline-Date.now());
    $('timer').textContent=completed()?'—':Math.ceil(remaining/1000)+'s';$('timer').classList.toggle('urgent',remaining<=5000&&!completed());
    $('attempts').textContent=round.used+' / '+round.limit;
  }
  function summary(){
    const values=Object.values(data.stats),correct=values.reduce((n,v)=>n+v.correct,0),failed=values.reduce((n,v)=>n+v.failed,0);
    $('correct-total').textContent=correct;$('failed-total').textContent=failed;$('accuracy').textContent=correct+failed?Math.round(correct/(correct+failed)*100)+'%':'—';
    const weak=Object.values(data.stats).filter(s=>s.misses>0).sort((a,b)=>b.misses-a.misses).slice(0,2);
    $('review-note').textContent=weak.length?'Worth revisiting: '+weak.map(s=>s.name+' · '+s.misses+' missed '+(s.misses===1?'guess':'guesses')).join('; ')+'.':'Your completed rounds will build a practice history here.';
  }
  function finish(){
    if(!completed()||recorded)return;recorded=true;
    practice.add({time:new Date().toISOString(),name:C.name(round.root,round.id),root:round.root,id:round.id,mode,result:round.status,used:round.used,limit:round.limit,seconds:round.seconds,events:[...round.events],revealed});
    if(practice.commit(data)){save();summary();}
  }
  function outcome(result){
    if(result==='inactive')return;
    if(round.status==='correct')message('Correct. '+C.name(round.root,round.id)+' — nicely done.','correct');
    else if(round.status==='failed')message('Question failed. The answer is '+C.name(round.root,round.id)+'.','failed');
    else message((result==='timeout'?'Time’s up for that guess.':'Not quite.')+' '+(round.limit-round.used)+' '+(round.limit-round.used===1?'guess':'guesses')+' left. Fresh timer started.','wrong');
    finish();
    if(practice.complete)$('feedback').textContent+=` Round complete: ${practice.correct} of ${practice.count} correct. Results saved.`;
    if(inputMode==='play'&&locked()&&playActive&&calibrated)beginAnswer();
    render();
  }
  function targets(){
    const ids=data.config.pool==='triads'?['major','minor','dim']:data.config.pool==='sevenths'?['7','maj7','m7','m7b5','dim7','mMaj7']:['major','minor','dim','7','maj7','m7','m7b5','dim7','mMaj7'];
    const frets=data.config.keys==='all'?Array.from({length:12},(_,i)=>i+1):[data.config.rootFret];
    return frets.flatMap(fret=>ids.map(id=>({fret,root:C.rootAt(fret),id})));
  }
  function choose(){
    const options=targets().filter(t=>t.fret+':'+t.id!==lastTarget);
    const weights=options.map(t=>{const s=data.stats[mode+':'+t.root+':'+t.id];return s?1+Math.min(4,(s.failed*2+s.misses)/(s.correct+1)):2;});
    let roll=Math.random()*weights.reduce((a,b)=>a+b,0),selected=options.at(-1);
    for(let i=0;i<options.length;i++){roll-=weights[i];if(roll<=0){selected=options[i];break;}}
    lastTarget=selected.fret+':'+selected.id;return selected;
  }
  function startQuestion(){
    clearListeningReview();
    const t=paintedTarget||choose();paintedTarget=null;referenceRoot=t.root;anchorFret=t.fret;
    round=new C.Round({mode,frets:t.frets||C.shape(t.fret,t.id),root:t.root,id:t.id,seconds:data.config.seconds,limit:data.config.limit},Date.now());
    recorded=false;revealed=false;frets=mode==='guess'?[...round.frets]:[null,null,null,null,null,null];frameChord();$('guess-input').value='';
    message(mode==='guess'?'Name the chord shown. Equivalent chord names count.':'Paint the chord tones, then Submit. You can use any complete voicing.');render();
    if(mode==='guess')$('guess-input').focus({preventScroll:true});
    if(mode==='paint'&&inputMode==='play')beginAnswer();
  }
  function startRound(){
    if(inputMode==='play'&&mode==='paint'&&(!calibrated||!playActive))return;
    practice=new C.PracticeRound(data.config.questions);lastTarget='';startQuestion();
  }
  document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{
    if(b.dataset.mode===mode)return;
    if(b.dataset.mode==='guess'||inputMode!=='play')stopListening();
    clearListeningReview();
    const current=mode==='instant'?C.identify(frets,referenceRoot)[0]:null;
    paintedTarget=b.dataset.mode==='guess'&&current?{root:current.root,id:current.id,fret:anchorFret,frets:[...frets]}:null;
    mode=b.dataset.mode;round=null;practice=null;referenceRoot=C.rootAt(data.config.rootFret);anchorFret=data.config.rootFret;
    inputMode=mode==='guess'?'click':preferredInputMode;
    frets=mode==='paint'?[null,null,null,null,null,null]:paintedTarget?[...paintedTarget.frets]:C.shape(anchorFret,data.config.quality);
    frameChord();
    message(mode==='instant'?'Move a dot. See what changes.':'Press Start round when you’re ready. Unfinished rounds are not scored.');render();
    if(inputMode==='play'&&mode!=='guess')calibrate();
  });
  for(const [id,key] of settings){
    $(id).onchange=()=>{
      if(inRound())return;
      clearListeningReview();
      paintedTarget=null;
      const old=data.config.rootFret;
      data.config[key]=['rootFret','limit','seconds','questions'].includes(key)?clamp($(id).value,Number($(id).min),Number($(id).max),defaults[key]):$(id).value;
      $(id).value=data.config[key];
      if(key==='rootFret'){
        const delta=data.config.rootFret-old;frets=frets.map(f=>f===null?null:f+delta<0?null:f+delta);
        referenceRoot=C.rootAt(data.config.rootFret);anchorFret=data.config.rootFret;
      }
      if(key==='quality')frets=C.shape(data.config.rootFret,data.config.quality);
      if(mode!=='instant'){round=null;practice=null;frets=mode==='paint'?[null,null,null,null,null,null]:C.shape(data.config.rootFret,data.config.quality);referenceRoot=C.rootAt(data.config.rootFret);anchorFret=data.config.rootFret;}
      frameChord();save();render();
    };
  }
  $('clear').onclick=()=>{if(canEdit()){clearListeningReview();frets=[null,null,null,null,null,null];render();}};
  $('lower-frets').onclick=()=>{firstFret=Math.max(1,firstFret-1);renderGrid();};
  $('higher-frets').onclick=()=>{firstFret++;renderGrid();};
  $('reset').onclick=()=>{clearListeningReview();frets=C.shape(data.config.rootFret,data.config.quality);frameChord();message('E-shape loaded. Make it your own.');render();};
  $('start').onclick=startRound;
  $('next').onclick=()=>{if(completed()&&inRound())startQuestion();};
  $('reset-round').onclick=()=>{paintedTarget=null;startRound();message('Round reset. Question 1, a fresh timer, and no guesses used.');};
  $('guess-form').onsubmit=e=>{e.preventDefault();if(!round||!$('guess-input').value.trim())return;outcome(round.submit($('guess-input').value,Date.now()));};
  $('submit-paint').onclick=()=>outcome(round.submit(frets,Date.now()));
  $('pause').onclick=()=>{if(!locked())return;if(inputMode==='play'&&!playActive){calibrate();return;}if(round.paused){round.resume(Date.now());message('Resumed. Take your next guess.');}else{round.pause(Date.now());message('Paused. Your remaining time is saved.','paused');}render();};
  $('reveal').onclick=()=>{if(!locked()||round.paused)return;revealed=true;round.status='failed';round.events.push({result:'revealed',at:Date.now()-round.started});frets=[...round.frets];frameChord();outcome('revealed');};
  function pauseForNavigation(){
    const wasListening=playActive;stopListening(false);
    if(locked()&&!round.paused)round.pause(Date.now());
    if(locked()){message('Paused while you were away. Press Resume when you’re ready.','paused');render();}
    else if(wasListening)render();
  }
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden)pauseForNavigation();
    else if(bridge&&inputMode==='play'&&mode!=='guess'&&!playActive&&!inRound())calibrate();
  });
  window.addEventListener('blur',pauseForNavigation);
  if(bridge)bridge.suspend.connect(pauseForNavigation);
  setInterval(()=>{if(!round)return;const event=round.tick(Date.now());if(event)outcome(event);else renderClock();},100);
  $('history-button').onclick=()=>{
    $('settings-dialog').close();
    pauseForNavigation();$('history-rows').replaceChildren();
    if(!data.history.length)$('history-rows').textContent='No completed rounds yet. Choose Guess or Paint the chord to begin.';
    for(const h of data.history.slice(-30).reverse()){
      const row=document.createElement('div');row.className='history-row';const left=document.createElement('div'),right=document.createElement('div');
      left.textContent=h.name+' · '+(h.mode==='guess'?'Name it':'Paint it');right.textContent=(h.result==='correct'?'Correct':'Failed')+' · '+h.used+'/'+h.limit+' guesses';row.append(left,right);$('history-rows').append(row);
    }
    $('history').showModal();
  };
  $('close-history').onclick=()=>$('history').close();
  window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();installPrompt=e;$('install').hidden=false;});
  $('install').onclick=async()=>{if(installPrompt){await installPrompt.prompt();installPrompt=null;$('install').hidden=true;}};
  summary();render();document.documentElement.dataset.ready='true';
  // Home preloads this page. Only acquire input when Painter is actually shown.
  if(bridge&&!document.hidden&&inputMode==='play')calibrate();
  // Caching must never hold the canvas hostage on a slow first connection.
  if(!bridge&&'serviceWorker' in navigator&&/^https?:$/.test(location.protocol)){
    $('offline-status').textContent='Preparing offline practice…';
    navigator.serviceWorker.register('./sw.js').then(()=>navigator.serviceWorker.ready)
      .then(()=>{$('offline-status').textContent='Ready for offline practice';})
      .catch(()=>{$('offline-status').textContent='Offline setup unavailable';});
  }
})();
