(function(root){
  'use strict';
  const C=typeof module!=='undefined'&&module.exports?require('./core.js'):root.ChordCore;
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
    const $=id=>document.getElementById(id);let bridge=null,result=null;
    if(root.qt?.webChannelTransport){
      await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='qrc:///qtwebchannel/qwebchannel.js';script.onload=resolve;script.onerror=reject;document.head.append(script);});
      bridge=await new Promise(resolve=>new QWebChannel(qt.webChannelTransport,ch=>resolve(ch.objects.explorer)));
      $('explorer-back').onclick=()=>bridge.back();
    }else{
      $('explorer-back').textContent='Chord Painter';$('explorer-back').onclick=()=>{location.href='./';};
    }
    function draw(){
      try{result=lookup($('lookup-name').value,$('lookup-kind').value,$('lookup-range').value);}
      catch(error){result=null;$('lookup-error').textContent=error.message;$('lookup-result').hidden=true;$('find-everywhere').hidden=true;return;}
      $('lookup-error').textContent='';$('lookup-result').hidden=false;
      $('lookup-title').textContent=result.title;$('lookup-description').textContent=result.description;
      $('lookup-tones').replaceChildren();
      for(const tone of result.tones){const chip=document.createElement('span');chip.className='tone-chip';const name=document.createElement('b'),degree=document.createElement('small');name.textContent=tone.note;degree.textContent=tone.degree;chip.append(name,degree);$('lookup-tones').append(chip);}
      $('lookup-help').textContent=result.kind==='note'?`${result.positions.length} positions · standard tuning · open strings through fret ${result.lastFret}.`:'Each dot is an available chord tone. Choose one position per string when building a voicing.'+(result.bass===null?'':' The note after / is the required lowest note.');
      $('find-everywhere').hidden=!bridge||result.kind!=='note';
      $('lookup-detail').textContent='Select a dot for its string, fret and sounding pitch.';
      const table=$('lookup-board');table.replaceChildren();
      const head=document.createElement('thead'),header=document.createElement('tr'),corner=document.createElement('th');corner.textContent='String';header.append(corner);
      for(let fret=0;fret<=result.lastFret;fret++){const th=document.createElement('th');th.scope='col';th.textContent=fret===0?'Open':fret;header.append(th);}head.append(header);table.append(head);
      const body=document.createElement('tbody'),names=['high E','B','G','D','A','low E'];
      for(let string=1;string<=6;string++){
        const row=document.createElement('tr'),label=document.createElement('th');label.scope='row';label.textContent=`${string} · ${names[string-1]}`;row.append(label);
        for(let fret=0;fret<=result.lastFret;fret++){
          const cell=document.createElement('td'),p=result.positions.find(p=>p.string===string&&p.fret===fret);
          if(p){const dot=document.createElement('button');dot.type='button';dot.className='lookup-dot'+(p.root?' root':'');dot.textContent=p.note;
            // Octave names use sounding scientific pitch; enharmonic notation can cross octave boundaries.
            const pitch=C.NOTES[C.mod(p.midi)]+(Math.floor(p.midi/12)-1);
            const detail=`${p.note}${result.kind==='chord'?' · interval '+p.degree:''} · string ${string} (${names[string-1]}) · ${fret===0?'open':'fret '+fret} · sounds ${pitch} · ${p.hz.toFixed(2)} Hz`;
            dot.setAttribute('aria-label',detail);dot.title=detail;dot.onclick=()=>{table.querySelectorAll('[aria-pressed]').forEach(b=>b.removeAttribute('aria-pressed'));dot.setAttribute('aria-pressed','true');$('lookup-detail').textContent=detail;};cell.append(dot);
          }row.append(cell);
        }body.append(row);
      }table.append(body);
    }
    $('lookup-form').onsubmit=event=>{event.preventDefault();draw();};
    $('lookup-range').onchange=draw;
    $('lookup-kind').onchange=()=>{$('lookup-name').placeholder=$('lookup-kind').value==='note'?'B, F#, B♭':'Cmaj7, Am, F#7';draw();};
    $('find-everywhere').onclick=()=>{if(result?.kind==='note')bridge.findEverywhere(result.root);};
    $('supported-chords').textContent=C.TYPES.map(t=>C.name(0,t.id)+' — '+t.title).join(' · ');
    draw();document.documentElement.dataset.ready='true';
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={lookup};
  else{root.FretboardExplorer={lookup};setup();}
})(typeof window==='undefined'?globalThis:window);
