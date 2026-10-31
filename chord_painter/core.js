/* Shared by the Windows view and the offline phone app. No audio required. */
(function (scope) {
  'use strict';
  const OPEN = [40,45,50,55,59,64];
  const NOTES = ['C','D♭','D','E♭','E','F','G♭','G','A♭','A','B♭','B'];
  const LETTERS = 'CDEFGAB';
  const NATURAL = {C:0,D:2,E:4,F:5,G:7,A:9,B:11};
  const mod = n => (n % 12 + 12) % 12;
  const TYPES = [
    {id:'major', suffix:'', title:'Major', intervals:[0,4,7], degrees:['1','3','5'], shape:[0,2,2,1,0,0]},
    {id:'minor', suffix:'m', title:'Minor', intervals:[0,3,7], degrees:['1','♭3','5'], shape:[0,2,2,0,0,0]},
    {id:'dim', suffix:'dim', title:'Diminished', intervals:[0,3,6], degrees:['1','♭3','♭5'], shape:[0,1,2,0,null,null]},
    {id:'7', suffix:'7', title:'Dominant 7', intervals:[0,4,7,10], degrees:['1','3','5','♭7'], shape:[0,2,0,1,0,0]},
    {id:'maj7', suffix:'maj7', title:'Major 7', intervals:[0,4,7,11], degrees:['1','3','5','7'], shape:[0,2,1,1,0,0]},
    {id:'m7', suffix:'m7', title:'Minor 7', intervals:[0,3,7,10], degrees:['1','♭3','5','♭7'], shape:[0,2,0,0,0,0]},
    {id:'m7b5', suffix:'m7♭5', title:'Half-diminished 7', intervals:[0,3,6,10], degrees:['1','♭3','♭5','♭7'], shape:[0,1,0,0,null,null]},
    {id:'dim7', suffix:'dim7', title:'Diminished 7', intervals:[0,3,6,9], degrees:['1','♭3','♭5','♭♭7'], shape:[0,1,2,0,2,0]},
    {id:'mMaj7', suffix:'m(maj7)', title:'Minor major 7', intervals:[0,3,7,11], degrees:['1','♭3','5','7'], shape:[0,2,1,0,0,0]},
    {id:'sus2', suffix:'sus2', title:'Suspended 2', intervals:[0,2,7], degrees:['1','2','5'], shape:[0,2,4,4,0,0]},
    {id:'sus4', suffix:'sus4', title:'Suspended 4', intervals:[0,5,7], degrees:['1','4','5'], shape:[0,2,2,2,0,0]},
    {id:'aug', suffix:'aug', title:'Augmented', intervals:[0,4,8], degrees:['1','3','♯5'], shape:[0,3,2,1,1,0]},
    {id:'6', suffix:'6', title:'Major 6', intervals:[0,4,7,9], degrees:['1','3','5','6'], shape:[0,2,2,1,2,0]},
    {id:'m6', suffix:'m6', title:'Minor 6', intervals:[0,3,7,9], degrees:['1','♭3','5','6'], shape:[0,2,2,0,2,0]},
    {id:'5', suffix:'5', title:'Power chord', intervals:[0,7], degrees:['1','5'], shape:[0,2,2,null,null,null]}
  ];
  const quality = id => TYPES.find(t => t.id === id);
  const rootAt = fret => mod(4 + fret);
  const name = (root, id) => NOTES[root] + quality(id).suffix;
  const shape = (fret, id) => quality(id).shape.map(n => n === null ? null : n + fret);
  const pitches = frets => [...new Set(frets.flatMap((f,i) => f === null ? [] : [mod(OPEN[i]+f)]))].sort((a,b)=>a-b);
  const equal = (a,b) => a.length === b.length && a.every((n,i) => n === b[i]);
  const chordPitches = (root,id) => quality(id).intervals.map(n=>mod(root+n)).sort((a,b)=>a-b);
  function identify(frets, preferredRoot) {
    const pcs = pitches(frets);
    const sounding = frets.flatMap((f,i)=>f===null ? [] : [OPEN[i]+f]);
    if (!sounding.length) return [];
    const bass = mod(Math.min(...sounding));
    const matches = [];
    for(let root=0;root<12;root++) for(const type of TYPES) {
      if(equal(pcs,chordPitches(root,type.id))) matches.push({root,id:type.id,bass,
        name:name(root,type.id)+(root===bass?'':'/'+NOTES[bass])});
    }
    return matches.sort((a,b) => (b.root===preferredRoot)-(a.root===preferredRoot) || (b.root===bass)-(a.root===bass));
  }
  function parse(text) {
    let s = String(text).trim().replace(/♭/g,'b').replace(/♯/g,'#').replace(/𝄫/g,'bb');
    const parts = s.split('/');
    if(parts.length>2) return null;
    const readNote = n => {const m=n.trim().match(/^([A-Ga-g])([#b]{0,2})$/);return m ? mod(NATURAL[m[1].toUpperCase()]+[...m[2]].reduce((v,a)=>v+(a==='#'?1:-1),0)):null;};
    const m = parts[0].match(/^([A-Ga-g][#b]{0,2})(.*)$/);
    if(!m)return null;
    let suffix=m[2].trim().replace(/^M(?=7|$)/,'maj').replace(/Δ/g,'maj').toLowerCase().replace(/[\s()_-]/g,'');
    const aliases={'':'major',maj:'major',major:'major',m:'minor',min:'minor',minor:'minor',
      diminished:'dim','°':'dim',o:'dim',dom7:'7',dominant7:'7',major7:'maj7',majorseventh:'maj7',
      min7:'m7',minor7:'m7',minorseventh:'m7',halfdim:'m7b5',halfdiminished:'m7b5',halfdiminished7:'m7b5',
      'ø':'m7b5','ø7':'m7b5',min7b5:'m7b5','°7':'dim7',o7:'dim7',diminished7:'dim7',
      mmaj7:'mMaj7',minmaj7:'mMaj7',minormajor7:'mMaj7',sus:'sus4','+':'aug',augmented:'aug',
      major6:'6',min6:'m6',minor6:'m6'};
    const id=aliases[suffix] || suffix;
    const root=readNote(m[1]), bass=parts[1]===undefined?null:readNote(parts[1]);
    return quality(id) && root!==null && (parts[1]===undefined || bass!==null) ? {root,id,bass}:null;
  }
  function accepts(text, frets) {
    const chord=parse(text);
    if(!chord || !equal(chordPitches(chord.root,chord.id),pitches(frets)))return false;
    const sounding=frets.flatMap((f,i)=>f===null?[]:[OPEN[i]+f]);
    return chord.bass===null || chord.bass===mod(Math.min(...sounding));
  }
  function tone(root, pc, id) {
    const interval=mod(pc-root), type=quality(id);
    const index=type ? type.intervals.indexOf(interval) : -1;
    const degree=index>=0?type.degrees[index]:['1','♭2','2','♭3','3','4','♭5','5','♭6','6','♭7','7'][interval];
    const rootName=NOTES[root], letter=LETTERS[(LETTERS.indexOf(rootName[0])+Number(degree.at(-1))-1)%7];
    let diff=mod(pc-NATURAL[letter]);if(diff>6)diff-=12;
    return {degree,note:letter+(diff>0?'♯'.repeat(diff):'♭'.repeat(-diff))};
  }
  class Round {
    constructor({mode,frets,root,id,seconds=20,limit=3}, now) {
      Object.assign(this,{mode,frets:[...frets],root,id,seconds,limit});
      this.used=0;this.status='active';this.deadline=now+seconds*1000;this.started=now;
      this.events=[];this.paused=false;this.remaining=seconds*1000;this.last='';
    }
    fail(reason,now) {
      this.used++; this.events.push({result:reason,at:now-this.started});this.last=reason;
      if(this.used>=this.limit)this.status='failed';
      else this.deadline=now+this.seconds*1000;
      return reason;
    }
    tick(now) {
      if(this.status!=='active'||this.paused)return null;
      if(now>=this.deadline)return this.fail('timeout',now);
      return null;
    }
    submit(answer,now) {
      if(this.status!=='active'||this.paused)return 'inactive';
      if(this.tick(now))return 'timeout';
      const ok=this.mode==='guess' ? accepts(answer,this.frets) : equal(pitches(answer),chordPitches(this.root,this.id));
      if(ok){this.used++;this.events.push({result:'correct',at:now-this.started});this.status='correct';this.last='correct';return 'correct';}
      return this.fail('wrong',now);
    }
    pause(now){if(this.status==='active'&&!this.paused){this.remaining=Math.max(0,this.deadline-now);this.paused=true;}}
    resume(now){if(this.paused){this.deadline=now+this.remaining;this.paused=false;}}
  }
  // Keep unfinished rounds separate from saved history so Reset can discard them.
  class PracticeRound {
    constructor(count=10) {
      this.count=Math.min(100,Math.max(1,Math.round(Number(count))||10));
      this.results=[];this.saved=false;
    }
    get complete(){return this.results.length===this.count;}
    get correct(){return this.results.filter(r=>r.result==='correct').length;}
    get failed(){return this.results.filter(r=>r.result==='failed').length;}
    add(result){if(!this.complete)this.results.push(result);}
    commit(data){
      if(!this.complete||this.saved)return false;
      for(const r of this.results){
        const key=r.mode+':'+r.root+':'+r.id;
        const stats=data.stats[key]||(data.stats[key]={name:r.name,mode:r.mode,correct:0,failed:0,misses:0});
        stats[r.result]++;stats.misses+=r.events.filter(e=>e.result!=='correct').length;
      }
      data.history=[...data.history,...this.results].slice(-300);
      this.saved=true;return true;
    }
  }
  const api={OPEN,NOTES,TYPES,mod,quality,rootAt,name,shape,pitches,chordPitches,identify,parse,accepts,tone,Round,PracticeRound};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  scope.ChordCore=api;
})(globalThis);
