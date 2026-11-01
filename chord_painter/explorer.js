(function(root){
  'use strict';
  const C=typeof module!=='undefined'&&module.exports?require('./core.js'):root.ChordCore;
  // Frets run low E to high E; null means mute. These are explicit voicings,
  // not arbitrary chord-tone combinations. Move the entire pattern together.
  const SHAPES={
    C:{root:0,patterns:{major:[null,3,2,0,1,0],minor:[null,3,1,0,1,null],'7':[null,3,2,3,1,0],maj7:[null,3,2,0,0,0],m7:[null,3,1,3,1,null],mMaj7:[null,3,1,0,0,null]}},
    A:{root:9,patterns:{major:[null,0,2,2,2,0],minor:[null,0,2,2,1,0],dim:[null,0,1,2,1,null],'7':[null,0,2,0,2,0],maj7:[null,0,2,1,2,0],m7:[null,0,2,0,1,0],m7b5:[null,0,1,0,1,null],dim7:[null,0,1,2,1,2],mMaj7:[null,0,2,1,1,0],sus2:[null,0,2,2,0,0],sus4:[null,0,2,2,3,0],aug:[null,0,3,2,2,1],'6':[null,0,2,2,2,2],m6:[null,0,2,2,1,2],'5':[null,0,2,2,null,null]}},
    G:{root:7,patterns:{major:[3,2,0,0,0,3],minor:[3,1,0,0,3,3],'7':[3,2,0,0,0,1],maj7:[3,2,0,0,0,2],m7:[3,1,0,0,3,1],mMaj7:[3,1,0,0,3,2]}},
    E:{root:4,patterns:Object.fromEntries(C.TYPES.map(t=>[t.id,t.shape]))},
    D:{root:2,patterns:{major:[null,null,0,2,3,2],minor:[null,null,0,2,3,1],'7':[null,null,0,2,1,2],maj7:[null,null,0,2,2,2],m7:[null,null,0,2,1,1],mMaj7:[null,null,0,2,2,1],sus2:[null,null,0,2,3,0],sus4:[null,null,0,2,3,3]}}
  };
  function chordShapes(result,selected=['E','A']){
    if(result.kind!=='chord')return {voicings:[],unavailable:[],outside:[]};
    const voicings=[],unavailable=[],outside=[];
    for(const family of Object.keys(SHAPES).filter(f=>selected.includes(f))){
      const definition=SHAPES[family],pattern=definition.patterns[result.id];
      if(!pattern){unavailable.push(family);continue;}
      let count=0;
      for(let offset=C.mod(result.root-definition.root);offset<=result.lastFret;offset+=12){
        const frets=pattern.map(f=>f===null?null:f+offset);
        if(Math.max(...frets.filter(f=>f!==null))>result.lastFret)continue;
        const bass=C.mod(Math.min(...frets.flatMap((f,i)=>f===null?[]:[C.OPEN[i]+f])));
        if(result.bass!==null&&bass!==result.bass)continue;
        const positions=frets.flatMap((f,i)=>f===null?[]:[result.positions.find(p=>p.string===6-i&&p.fret===f)]);
        const omitted=result.tones.filter(t=>!positions.some(p=>p.pc===t.pc)).map(t=>t.degree);
        voicings.push({family,offset,frets,positions,omitted});count++;
      }
      if(!count)outside.push(family);
    }
    return {voicings,unavailable,outside};
  }
  function lookup(text,kind='note',lastFret=14){
    text=String(text).trim();
    if(!['note','chord'].includes(kind))throw Error('Choose Note or Chord.');
    if(kind==='note'&&!/^[A-Ga-g][#b♯♭]{0,2}$/.test(text))throw Error('Enter a note name, such as B, F# or B♭.');
    const parsed=C.parse(text);
    if(!parsed)throw Error('Try a name such as C, Cm, Cmaj7, C7, Cdim or C#m7♭5. See Supported chords below.');
    const match=text.match(/^([A-Ga-g])([#b♯♭]{0,2})/);
    const spelling=match[1].toUpperCase()+match[2].replace(/#/g,'♯').replace(/b/g,'♭');
    const type=C.quality(parsed.id);
    const tones=kind==='note'?[{pc:parsed.root,note:spelling,degree:'Note'}]:type.intervals.map(interval=>({pc:C.mod(parsed.root+interval),...C.tone(parsed.root,C.mod(parsed.root+interval),parsed.id,spelling)}));
    if(kind==='chord'&&parsed.bass!==null&&!tones.some(t=>t.pc===parsed.bass))tones.push({pc:parsed.bass,note:text.split('/')[1].trim().replace(/#/g,'♯').replace(/b/g,'♭').replace(/^[a-g]/,s=>s.toUpperCase()),degree:'Bass'});
    const positions=[];
    lastFret=[12,14,24].includes(Number(lastFret))?Number(lastFret):14;
    C.OPEN.forEach((opened,index)=>{
      for(let fret=0;fret<=lastFret;fret++){
        const midi=opened+fret,tone=tones.find(t=>t.pc===C.mod(midi));
        if(tone)positions.push({...tone,string:6-index,fret,midi,hz:440*2**((midi-69)/12),root:tone.pc===parsed.root});
      }
    });
    return {kind,root:parsed.root,id:parsed.id,bass:parsed.bass,title:kind==='note'?spelling:spelling+type.suffix+(parsed.bass===null?'':'/'+text.split('/')[1].trim()),description:kind==='note'?'Every occurrence in the selected fret range':type.title,tones,positions,lastFret};
  }
  async function setup(){
    const $=id=>document.getElementById(id);let bridge=null,result=null,boardKind=null;
    if(root.qt?.webChannelTransport){
      await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='qrc:///qtwebchannel/qwebchannel.js';script.onload=resolve;script.onerror=reject;document.head.append(script);});
      bridge=await new Promise(resolve=>new QWebChannel(qt.webChannelTransport,ch=>resolve(ch.objects.explorer)));
      $('explorer-back').onclick=()=>bridge.back();
    }else{
      $('explorer-back').textContent='← Home';$('explorer-back').onclick=()=>{location.href='./';};
    }
    function draw(){
      try{result=lookup($('lookup-name').value,$('lookup-kind').value,$('lookup-range').value);}
      catch(error){result=null;$('lookup-error').textContent=error.message;$('lookup-result').hidden=true;$('find-everywhere').hidden=true;$('shape-controls').hidden=$('lookup-kind').value!=='chord';return;}
      $('lookup-error').textContent='';$('lookup-result').hidden=false;
      $('lookup-title').textContent=result.title;$('lookup-description').textContent=result.description;
      $('lookup-tones').replaceChildren();
      for(const tone of result.tones){const chip=document.createElement('span');chip.className='tone-chip';const name=document.createElement('b'),degree=document.createElement('small');name.textContent=tone.note;degree.textContent=tone.degree;chip.append(name,degree);$('lookup-tones').append(chip);}
      $('shape-controls').hidden=result.kind!=='chord';
      $('shape-results').hidden=result.kind!=='chord';
      $('neck-summary').hidden=result.kind==='note';
      if(boardKind!==result.kind)$('neck-view').open=result.kind==='note';
      boardKind=result.kind;
      const selected=[...document.querySelectorAll('[name="chord-shape"]:checked')].map(input=>input.value);
      const shapes=chordShapes(result,selected);
      const visiblePositions=result.kind==='note'?result.positions:shapes.voicings.flatMap(v=>v.positions);
      $('lookup-help').textContent=result.kind==='note'?`${result.positions.length} positions · standard tuning · open strings through fret ${result.lastFret}.`:`${shapes.voicings.length} complete voicings · checked shapes only · open strings through fret ${result.lastFret}.`;
      const notices=[];
      if(!selected.length)notices.push('Check a shape to show its positions.');
      if(shapes.unavailable.length)notices.push(`No saved ${shapes.unavailable.join(', ')} shape for ${result.title}. Try E or A.`);
      if(shapes.outside.length)notices.push(`${shapes.outside.join(', ')}: no complete shape within this fret range${result.bass===null?'':' with the requested lowest note'}.`);
      $('shape-status').textContent=notices.join(' ');
      drawShapes(shapes.voicings);
      $('find-everywhere').hidden=result.kind!=='note';
      $('find-everywhere').disabled=!bridge;
      $('find-everywhere-availability').hidden=!!bridge||result.kind!=='note';
      $('lookup-detail').textContent='Select a dot for its string, fret and sounding pitch.';
      const table=$('lookup-board');table.replaceChildren();
      const head=document.createElement('thead'),header=document.createElement('tr'),corner=document.createElement('th');corner.textContent='String';header.append(corner);
      for(let fret=0;fret<=result.lastFret;fret++){const th=document.createElement('th');th.scope='col';th.textContent=fret===0?'Open':fret;header.append(th);}head.append(header);table.append(head);
      const body=document.createElement('tbody'),names=['high E','B','G','D','A','low E'];
      for(let string=1;string<=6;string++){
        const row=document.createElement('tr'),label=document.createElement('th');label.scope='row';label.textContent=`${string} · ${names[string-1]}`;row.append(label);
        for(let fret=0;fret<=result.lastFret;fret++){
          const cell=document.createElement('td'),p=visiblePositions.find(p=>p.string===string&&p.fret===fret);
          if(p){const dot=document.createElement('button');dot.type='button';dot.className='lookup-dot'+(p.root?' root':'');dot.textContent=p.note;
            // Octave names use sounding scientific pitch; enharmonic notation can cross octave boundaries.
            const pitch=C.NOTES[C.mod(p.midi)]+(Math.floor(p.midi/12)-1);
            const detail=`${p.note}${result.kind==='chord'?' · interval '+p.degree:''} · string ${string} (${names[string-1]}) · ${fret===0?'open':'fret '+fret} · sounds ${pitch} · ${p.hz.toFixed(2)} Hz`;
            dot.setAttribute('aria-label',detail);dot.title=detail;dot.onclick=()=>{table.querySelectorAll('[aria-pressed]').forEach(b=>b.removeAttribute('aria-pressed'));dot.setAttribute('aria-pressed','true');$('lookup-detail').textContent=detail;};cell.append(dot);
          }row.append(cell);
        }body.append(row);
      }table.append(body);
    }
    function drawShapes(voicings){
      const container=$('shape-diagrams');container.replaceChildren();
      for(const v of voicings){
        const card=document.createElement('article');card.className='shape-card';
        const title=document.createElement('h3');title.textContent=`${v.family} shape · ${result.title}`;
        const caption=document.createElement('p');caption.textContent=v.offset===0?'Open position':`Move the open shape up ${v.offset} fret${v.offset===1?'':'s'}`;
        if(v.omitted.length)caption.textContent+=` · ${v.omitted.join(', ')} omitted`;
        const table=document.createElement('table');table.className='shape-diagram';table.setAttribute('aria-label',`${result.title}, ${v.family} shape, ${v.frets.map(f=>f===null?'muted':f).join(' ')}, low E to high E`);
        const head=document.createElement('thead'),labels=document.createElement('tr');labels.append(document.createElement('th'));
        ['E','A','D','G','B','e'].forEach((name,i)=>{const th=document.createElement('th');th.scope='col';th.textContent=name+(v.frets[i]===null?' ×':v.frets[i]===0?' ○':'');labels.append(th);});head.append(labels);table.append(head);
        const body=document.createElement('tbody');
        const start=Math.max(1,Math.min(...v.frets.filter(f=>f!==null))),end=Math.max(start+3,...v.frets.filter(f=>f!==null));
        for(let fret=start;fret<=end;fret++){
          const row=document.createElement('tr'),label=document.createElement('th');label.scope='row';label.textContent=fret;row.append(label);
          v.frets.forEach((f,i)=>{const cell=document.createElement('td');if(f===fret){const p=v.positions.find(p=>p.string===6-i),dot=document.createElement('span');dot.className='shape-dot'+(p.root?' root':'');dot.textContent=p.note;dot.title=`${p.note} · interval ${p.degree} · string ${6-i} · fret ${fret}`;cell.append(dot);}row.append(cell);});body.append(row);
        }
        table.append(body);
        const frets=document.createElement('p');frets.className='shape-frets';frets.textContent=v.frets.map(f=>f===null?'×':f).join(' · ');
        card.append(title,caption,table,frets);container.append(card);
      }
    }
    $('lookup-form').onsubmit=event=>{event.preventDefault();draw();};
    $('lookup-range').onchange=draw;
    document.querySelectorAll('[name="chord-shape"]').forEach(input=>{input.onchange=draw;});
    $('lookup-kind').onchange=()=>{$('lookup-name').placeholder=$('lookup-kind').value==='note'?'B, F#, B♭':'Cmaj7, Am, F#7';draw();};
    $('find-everywhere').onclick=()=>{if(result?.kind==='note')bridge.findEverywhere(result.root);};
    $('supported-chords').textContent=C.TYPES.map(t=>C.name(0,t.id)+' — '+t.title).join(' · ');
    draw();document.documentElement.dataset.ready='true';
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={lookup,chordShapes};
  else{root.FretboardExplorer={lookup,chordShapes};setup();}
})(typeof window==='undefined'?globalThis:window);
