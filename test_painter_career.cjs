const {test}=require('node:test'),assert=require('node:assert/strict');
const C=require('./chord_painter/core.js'),A=require('./chord_painter/career.js');
const result=(id,status='correct',mode='guess')=>({name:C.name(0,id),root:0,id,mode,result:status,used:1,seconds:20,limit:3,events:[{result:status==='correct'?'correct':'wrong'}]});
test('Career archive keeps one column per round including retries and survives detailed-history truncation',()=>{
 const data={history:[],stats:{}};
 for(let i=0;i<305;i++){const p=new C.PracticeRound(1);p.add(result('major','failed'));p.commit(data);p.retryLast();p.add(result('major'));p.commit(data);}
 assert.equal(data.rounds.length,305);assert.equal(data.history.length,300);
 const r=data.rounds[0];assert.equal(r.byType.major.failed,1);assert.equal(r.byType.major.correct,1);assert.equal(r.byType.major.retries,1);assert.equal(r.byType.major.questions,1);
 const copy=JSON.parse(JSON.stringify(data));assert.equal(A.rounds(copy,'guess').length,305);assert.equal(A.rounds(copy,'paint').length,0);
});
test('Chart colors distinguish clean, recovered, unsuccessful, and untested',()=>{
 assert.equal(A.color(), 'untested');assert.equal(A.color({correct:2,failed:0,misses:0,retries:0}),'green');
 assert.equal(A.color({correct:1,failed:1,misses:1,retries:1}),'yellow');assert.equal(A.color({correct:1,failed:2,misses:2,retries:2}),'red');
 assert.equal(A.color({correct:1,failed:0,misses:1,retries:0}),'yellow');
});
test('Rounds sort chronologically, modes stay separate and legacy stats do not invent rounds',()=>{
 const data={history:[],stats:{'guess:0:minor':{mode:'guess',correct:0,failed:4,misses:8}},rounds:[{mode:'guess',started:'2026-10-31T12:00:00Z',byType:{}},{mode:'paint',started:'2026-10-31T10:00:00Z',byType:{}},{mode:'guess',started:'2026-10-31T09:00:00Z',byType:{}}]};
 assert.equal(A.rounds(data,'guess')[0].started,'2026-10-31T09:00:00Z');assert.equal(A.rounds(data,'guess').length,2);
 assert.equal(A.analyze(data,'guess').find(r=>r.id==='minor').problem,true);assert.equal(A.analyze(data,'paint').find(r=>r.id==='minor').problem,false);
});
test('Planner prioritizes difficulty while preferences are bounded and selected types stay eligible',()=>{
 const data={stats:{'guess:0:minor':{mode:'guess',correct:0,failed:10,misses:10}}};
 const targets=['major','minor','dim'].map(id=>({id,root:0,fret:8}));
 const base=A.plan(data,'guess',targets,20),adjusted=A.plan(data,'guess',targets,20,{minor:-1},[{id:'minor',priority:-100},{id:'major',priority:100}]);
 assert.equal(base.length,20);assert.ok(base.filter(t=>t.id==='minor').length>=base.filter(t=>t.id==='major').length);
 assert.ok(adjusted.some(t=>t.id==='minor'));assert.ok(adjusted.filter(t=>t.id==='major').length>=base.filter(t=>t.id==='major').length);
 assert.ok(base.every((t,i)=>!i||t.id!==base[i-1].id));assert.ok(base.filter(t=>t.id==='minor').length<=8);
 assert.equal(A.plan(data,'guess',[targets[0]],3).length,3);
});
