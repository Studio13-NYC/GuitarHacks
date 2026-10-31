const test=require('node:test'),assert=require('node:assert/strict');
const C=require('./chord_painter/core.js'),{lookup}=require('./chord_painter/explorer.js');
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
