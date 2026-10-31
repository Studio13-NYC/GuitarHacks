const test=require('node:test');
const assert=require('node:assert/strict');
const {PracticeFile,parse}=require('./chord_painter/practice-file.js');
const value=n=>JSON.stringify({version:1,config:{},history:[{correct:n}],stats:{},rounds:[],practicePreferences:{}});
function disk(raw){
  return {raw,name:'practice.json',exists:true,writes:[],fail:false,
    async getFile(){if(!this.exists)throw Object.assign(new Error('missing'),{name:'NotFoundError'});const text=this.raw;return{text:async()=>text};},
    async createWritable(){const owner=this;let next;return{
      async write(raw){await new Promise(r=>setTimeout(r,5));if(owner.fail)throw new Error('Disk is full');next=raw;},
      async close(){owner.raw=next;owner.writes.push(next);},async abort(){owner.aborted=true;}
    };}};
}
test('saves are ordered and the final snapshot retains all career data',async()=>{
  const handle=disk(value(0)),statuses=[],file=new PracticeFile(handle,handle.raw,(s)=>statuses.push(s));
  await Promise.all([file.save(value(1)),file.save(value(2)),file.save(value(3))]);
  assert.deepEqual(handle.writes,[value(1),value(2),value(3)]);assert.equal(file.pending,0);
  assert.equal(statuses.at(-1),'Saved to practice.json');assert.deepEqual(parse(handle.raw).rounds,[]);
});
test('deleted file stays deleted; queued saves cannot restore old data',async()=>{
  const handle=disk(value(0)),file=new PracticeFile(handle,handle.raw);handle.exists=false;
  const results=await Promise.allSettled([file.save(value(1)),file.save(value(2))]);
  assert.ok(results.every(r=>r.status==='rejected'));assert.equal(handle.exists,false);assert.equal(handle.writes.length,0);
  handle.exists=true;await assert.rejects(file.save(value(3)));assert.equal(handle.raw,value(0));
});
test('external edits and other windows are protected',async()=>{
  const handle=disk(value(0)),file=new PracticeFile(handle,handle.raw);handle.raw=value(90);
  await assert.rejects(file.save(value(1)),/changed outside/);assert.equal(handle.raw,value(90));
});
test('failed write aborts and preserves the last good file',async()=>{
  const handle=disk(value(0)),file=new PracticeFile(handle,handle.raw);handle.fail=true;
  await assert.rejects(file.save(value(1)),/Disk is full/);assert.equal(handle.raw,value(0));assert.equal(handle.aborted,true);
});
test('invalid practice input is rejected',()=>{
  for(const raw of ['null','[]','{}','{"version":1,"history":[],"stats":{},"config":{},"rounds":{}}'])assert.throws(()=>parse(raw));
});
