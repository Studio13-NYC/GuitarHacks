const test=require('node:test');
const assert=require('node:assert/strict');
const C=require('./chord_painter/core.js');
test('Every E-shape preset in every key contains exactly the named chord tones',()=>{
  for(let fret=0;fret<=12;fret++)for(const q of C.TYPES){
    const root=C.rootAt(fret),frets=C.shape(fret,q.id);
    assert.deepEqual(C.pitches(frets),C.chordPitches(root,q.id),C.name(root,q.id));
    assert.ok(C.identify(frets,root).some(m=>m.root===root&&m.id===q.id));
    assert.ok(C.accepts(C.name(root,q.id),frets));
  }
});
test('Aliases preserve major versus minor and accept enharmonic spellings',()=>{
  for(const text of ['Cmaj7','CM7','C major 7','CΔ7'])assert.ok(C.accepts(text,C.shape(8,'maj7')),text);
  assert.equal(C.accepts('Cm7',C.shape(8,'maj7')),false);
  for(const text of ['Cdim7','C°7','Co7'])assert.ok(C.accepts(text,C.shape(8,'dim7')),text);
  assert.ok(C.accepts('C# major',C.shape(9,'major')));
  assert.ok(C.accepts('Cø7',C.shape(8,'m7b5')));
  assert.equal(C.parse('nonsense'),null);
});
test('Ambiguous chord names and correct slash bass are accepted',()=>{
  const frets=C.shape(8,'6');
  assert.ok(C.accepts('C6',frets));assert.ok(C.accepts('Am7/C',frets));assert.ok(C.accepts('Am7',frets));
  assert.equal(C.accepts('Am7/E',frets),false);
  for(const text of ['Cdim7','Ebdim7','Gbdim7','Adim7'])assert.ok(C.accepts(text,C.shape(8,'dim7')));
});

test('Half-diminished fractions work without breaking slash-bass answers',()=>{
  const frets=C.shape(8,'m7b5');
  for(const answer of ['c 1/2 dim 7','C 1 / 2 diminished 7','C½dim7','C half dim 7','C min 7 b5','C minor 7 b5','C1/2dim7/C']){
    assert.ok(C.accepts(answer,frets),answer);
  }
  for(const answer of ['C1/2dim7/Eb','C1/2','Cdim7','D1/2dim7'])assert.equal(C.accepts(answer,frets),false,answer);
});
test('Intervals use musical spelling, including the diminished seventh',()=>{
  assert.deepEqual(C.tone(0,9,'dim7'),{note:'B♭♭',degree:'♭♭7'});
  assert.deepEqual(C.tone(6,10,'major'),{note:'B♭',degree:'3'});
  assert.deepEqual(C.tone(0,3,'minor'),{note:'E♭',degree:'♭3'});
});
const make=mode=>new C.Round({mode,root:0,id:'major',frets:C.shape(8,'major'),seconds:20,limit:3},1000);
test('Wrong answers and each timeout consume a guess and reset the timer',()=>{
  const r=make('guess');assert.equal(r.submit('Cm',2000),'wrong');assert.equal(r.deadline,22000);
  assert.equal(r.tick(22000),'timeout');assert.equal(r.used,2);assert.equal(r.deadline,42000);
  assert.equal(r.submit('C',42000),'timeout');assert.equal(r.status,'failed');
  assert.equal(r.submit('C',42001),'inactive');assert.equal(r.used,3);
});
test('Correct answers end once; incomplete or extra pitches fail in reverse mode',()=>{
  const r=make('paint');assert.equal(r.submit([8,null,null,null,null,null],2000),'wrong');
  assert.equal(r.submit([8,10,10,10,8,8],3000),'wrong');
  assert.equal(r.submit([null,3,5,5,5,null],4000),'correct');assert.equal(r.status,'correct');
  assert.equal(r.submit(C.shape(8,'major'),5000),'inactive');
});
test('Pausing preserves remaining time and prevents grading',()=>{
  const r=make('guess');r.pause(6000);assert.equal(r.remaining,15000);
  assert.equal(r.tick(90000),null);assert.equal(r.submit('C',90000),'inactive');
  r.resume(100000);assert.equal(r.deadline,115000);assert.equal(r.submit('C',114999),'correct');
});
const result=(status='correct')=>({name:'C',mode:'guess',root:0,id:'major',result:status,events:[{result:status==='correct'?'correct':'wrong'}]});
test('An unfinished round can be discarded without affecting saved history or mistakes',()=>{
  const data={history:[{name:'Am',result:'correct'}],stats:{older:{name:'Am',correct:1,failed:0,misses:0}}};
  const before=structuredClone(data);
  let practice=new C.PracticeRound(3);
  practice.add(result('failed'));practice.add(result());
  assert.equal(practice.commit(data),false);
  assert.deepEqual(data,before);
  practice=new C.PracticeRound(3); // Reset starts a fresh round with the same settings.
  assert.equal(practice.results.length,0);assert.equal(practice.correct,0);assert.equal(practice.failed,0);
  assert.equal(practice.complete,false);assert.equal(practice.count,3);
  assert.deepEqual(data,before);
});
test('A round ends at the configured question count and saves its results exactly once',()=>{
  for(const count of [1,3,10,100]){
    const data={history:[],stats:{}},practice=new C.PracticeRound(count);
    for(let i=0;i<count;i++){
      assert.equal(practice.complete,false);
      practice.add(result(i===0?'failed':'correct'));
    }
    assert.equal(practice.complete,true);practice.add(result());
    assert.equal(practice.results.length,count);assert.equal(practice.correct,count-1);assert.equal(practice.failed,1);
    assert.equal(practice.commit(data),true);assert.equal(practice.commit(data),false);
    assert.equal(data.history.length,count);assert.deepEqual(data.stats['guess:0:major'],{name:'C',mode:'guess',correct:count-1,failed:1,misses:1});
    const next=new C.PracticeRound(count);next.add(result());next.commit(data);
    assert.equal(data.history.length,count+(count===1?1:0));
  }
});

test('Retry keeps the same target, counts an abandoned try, and gives a fresh timer',()=>{
  const first=make('paint');first.pause(1500);
  const second=first.retry(5000);
  assert.equal(first.status,'failed');assert.equal(first.used,1);
  assert.equal(first.events[0].result,'retry');
  assert.equal(second.root,first.root);assert.equal(second.id,first.id);
  assert.deepEqual(second.frets,first.frets);assert.notEqual(second.frets,first.frets);
  assert.equal(second.used,0);assert.equal(second.paused,false);assert.equal(second.deadline,25000);
  assert.equal(second.submit(C.shape(8,'major'),6000),'correct');
  assert.equal(second.retry(7000),null);
});

test('Retry does not add a second miss to an already graded wrong answer',()=>{
  const r=make('guess');r.submit('Cm',2000);const next=r.retry(3000);
  assert.equal(r.used,1);assert.deepEqual(r.events.map(e=>e.result),['wrong']);
  assert.equal(next.status,'active');assert.equal(next.submit('C',4000),'correct');
});

test('Repeated retries keep all failed tries, the question number, and score a later success',()=>{
  const data={history:[],stats:{}},p=new C.PracticeRound(2);
  for(let attempt=1;attempt<=3;attempt++){
    p.add(result('failed'));assert.equal(p.results[0].attempt,attempt);
    assert.equal(p.retryLast(),true);assert.equal(p.complete,false);
    assert.equal(p.results.length,0);assert.equal(p.attemptNumber,attempt+1);
    assert.equal(p.commit(data),false);
  }
  p.add(result());assert.equal(p.results[0].attempt,4);
  assert.equal(p.retryLast(),false);p.add(result());
  assert.equal(p.complete,true);assert.equal(p.correct,2);assert.equal(p.failed,3);
  assert.equal(p.commit(data),true);assert.equal(p.commit(data),false);
  assert.deepEqual(data.history.map(r=>[r.question,r.attempt,r.result]),[[1,1,'failed'],[1,2,'failed'],[1,3,'failed'],[1,4,'correct'],[2,1,'correct']]);
  assert.equal(data.stats['guess:0:major'].failed,3);
  assert.equal(data.stats['guess:0:major'].correct,2);
});

test('Retry after the final saved failure appends only new results and never erases old scores',()=>{
  const data={history:[],stats:{}},p=new C.PracticeRound(1);
  p.add(result('failed'));p.commit(data);
  p.retryLast();assert.equal(p.complete,false);assert.equal(p.commit(data),false);
  assert.equal(data.history.length,1); // quitting the pending retry retains saved failure
  p.add(result('failed'));p.commit(data);assert.equal(data.history.length,2);
  p.retryLast();p.add(result());p.commit(data);
  assert.equal(data.history.length,3);assert.equal(p.commit(data),false);
  assert.equal(data.stats['guess:0:major'].failed,2);
  assert.equal(data.stats['guess:0:major'].correct,1);
});
