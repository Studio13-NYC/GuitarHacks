const test=require('node:test'),assert=require('node:assert/strict');
const C=require('./chord_painter/core.js'),{lookup,chordShapes}=require('./chord_painter/explorer.js');
test('a note lookup includes every matching string/fret including open B',()=>{
  const r=lookup('B','note',24);
  const expected=C.OPEN.flatMap((m,i)=>Array.from({length:25},(_,f)=>({string:6-i,fret:f,midi:m+f})).filter(p=>p.midi%12===11));
  assert.deepEqual(r.positions.map(({string,fret,midi})=>({string,fret,midi})),expected);
  assert.ok(r.positions.some(p=>p.string===2&&p.fret===0));
  assert.deepEqual(lookup('B','chord').tones.map(t=>t.note),['B','D♯','F♯']);
});
test('chord lookups reuse the full supported library and preserve flat spelling',()=>{
  for(const type of C.TYPES)for(let root=0;root<12;root++){
    const result=lookup(C.name(root,type.id),'chord',14);
    assert.deepEqual(result.tones.map(t=>t.pc),type.intervals.map(n=>C.mod(root+n)));
    assert.ok(result.positions.every(p=>type.intervals.includes(C.mod(p.midi-root))));
  }
  assert.deepEqual(lookup('Bbmaj7','chord').tones.map(t=>t.note),['B♭','D','F','A']);
  assert.deepEqual(lookup('Cdim7','chord').tones.map(t=>t.note),['C','E♭','G♭','B♭♭']);
  assert.equal(lookup('Cb','note').positions[0].pc,11);
});
test('slash bass and invalid names are handled explicitly',()=>{
  assert.equal(lookup('C/E','chord').bass,4);
  assert.equal(lookup('C/D','chord').tones.at(-1).degree,'Bass');
  for(const [text,kind] of [['H','note'],['Cmaj7','note'],['C13','chord'],['','note']])assert.throws(()=>lookup(text,kind));
});
test('C major E and A choices return complete familiar movable voicings',()=>{
  const r=lookup('C','chord');
  assert.deepEqual(chordShapes(r,['E']).voicings.map(v=>v.frets),[[8,10,10,9,8,8]]);
  assert.deepEqual(chordShapes(r,['A']).voicings.map(v=>v.frets),[[null,3,5,5,5,3]]);
  const all=chordShapes(r,['C','A','G','E','D']);
  assert.equal(all.voicings.length,5);
  assert.deepEqual(all.unavailable,[]);assert.deepEqual(all.outside,[]);
  assert.deepEqual(chordShapes(r,[]).voicings,[]);
});
test('every supplied shape transposes with required tones, one note per sounding string and no off-chord notes',()=>{
  for(const type of C.TYPES)for(let root=0;root<12;root++){
    const r=lookup(C.name(root,type.id),'chord',24);
    const shapes=chordShapes(r,['C','A','G','E','D']);
    assert.ok(shapes.voicings.some(v=>v.family==='E'));
    assert.ok(shapes.voicings.some(v=>v.family==='A'));
    for(const v of shapes.voicings){
      const omittedFifth=v.family==='C'&&['7','m7'].includes(type.id);
      assert.deepEqual(C.pitches(v.frets),C.chordPitches(root,type.id).filter(pc=>!omittedFifth||pc!==C.mod(root+7)),`${r.title} ${v.family}`);
      assert.deepEqual(v.omitted,omittedFifth?['5']:[]);
      assert.ok(v.positions.every(Boolean));
      assert.equal(v.positions.length,v.frets.filter(f=>f!==null).length);
      assert.ok(v.positions.every(p=>p.fret>=0&&p.fret<=24));
    }
  }
});
test('range, slash bass, unavailable patterns and note mode are explicit',()=>{
  assert.deepEqual(chordShapes(lookup('C','chord',12),['D']).outside,['D']);
  assert.deepEqual(chordShapes(lookup('Cdim','chord'),['C']).unavailable,['C']);
  assert.equal(chordShapes(lookup('C/E','chord'),['E','A']).voicings.length,0);
  assert.deepEqual(chordShapes(lookup('B','note')).voicings,[]);
  const doubled=chordShapes(lookup('C','chord',24),['E']).voicings;
  assert.deepEqual(doubled.map(v=>v.offset),[8,20]);
});
