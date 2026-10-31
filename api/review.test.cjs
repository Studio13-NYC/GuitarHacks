const {test}=require('node:test'),assert=require('node:assert/strict');
const {review}=require('./review.cjs');
const principal=Buffer.from(JSON.stringify({identityProvider:'github',userDetails:'nickknyc',userRoles:['authenticated']})).toString('base64');
const payload={mode:'guess',rows:[{id:'major',correct:1,failed:2}],notes:'Less major please'};
const req=(body=payload,auth=principal)=>({headers:new Headers(auth?{'x-ms-client-principal':auth}:{}),text:async()=>JSON.stringify(body)});
const env={OPENAI_API_KEY:'unit-test-placeholder',COACH_ALLOWED_USERS:'github:nickknyc'};
test('Unauthenticated and unauthorized users never reach GPT',async()=>{
 const fetcher=()=>{throw Error('must not call')};
 assert.equal((await review(req(payload,null),null,{env,fetcher})).status,401);
 assert.equal((await review(req(),null,{env:{...env,COACH_ALLOWED_USERS:''},fetcher})).status,403);
});
test('Missing key and invalid input fail safely before an API call',async()=>{
 const fetcher=()=>{throw Error('must not call')};
 assert.equal((await review(req(),null,{env:{...env,OPENAI_API_KEY:''},fetcher})).status,503);
 assert.equal((await review(req({...payload,rows:[{id:'invented'}]}),null,{env,fetcher})).status,400);
 assert.equal((await review(req({...payload,notes:'x'.repeat(60000)}),null,{env,fetcher})).status,413);
});
test('Successful review sends bounded structured request and returns advice only',async()=>{
 const advice={summary:'Major needs practice. Preference considered.',priorities:[{id:'major',priority:1,reason:'Two failures.'}]};
 const fetcher=async(url,options)=>{
   assert.equal(url,'https://api.openai.com/v1/responses');
   const body=JSON.parse(options.body);assert.equal(body.store,false);assert.ok(body.text.format.strict);assert.equal(JSON.parse(body.input).notes,payload.notes);
   return {ok:true,text:async()=>JSON.stringify({status:'completed',output:[{type:'message',content:[{type:'output_text',text:JSON.stringify(advice)}]}]})};
 };
 const result=await review(req(),null,{env,fetcher,now:()=>20000});assert.equal(result.status,200);assert.deepEqual(result.jsonBody,advice);
 const again=await review(req(),null,{env,fetcher,now:()=>20001});assert.equal(again.status,429);
});
test('Malformed or out-of-scope advice is never applied',async()=>{
 const fetcher=async()=>({ok:true,text:async()=>JSON.stringify({status:'completed',output:[{type:'message',content:[{type:'output_text',text:JSON.stringify({summary:'bad',priorities:[{id:'dim',priority:99,reason:'bad'}]})}]}]})});
 const result=await review(req(),null,{env,fetcher,now:()=>40000});assert.equal(result.status,502);assert.ok(result.jsonBody.error);assert.equal(result.jsonBody.priorities,undefined);
});
