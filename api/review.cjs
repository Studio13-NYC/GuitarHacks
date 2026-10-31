'use strict';
const contract=require('./coach-contract.json');
const ids=new Set(contract.schema.properties.priorities.items.properties.id.enum);
const requests=new Map();
const response=(status,jsonBody)=>({status,jsonBody,headers:{'Cache-Control':'no-store','Content-Type':'application/json'}});
function validate(value){
  if(!value||!['guess','paint'].includes(value.mode)||!Array.isArray(value.rows)||value.rows.length<1||value.rows.length>15)throw Error('Invalid practice summary.');
  const seen=new Set();
  for(const r of value.rows){if(!r||!ids.has(r.id)||seen.has(r.id))throw Error('Invalid chord types.');seen.add(r.id);}
  if(typeof value.notes!=='string'||value.notes.length>2000)throw Error('Notes must be under 2,000 characters.');
  return value;
}
function parse(reply,allowed){
  if(reply.status!=='completed')throw Error('GPT did not finish this review.');
  const text=(reply.output||[]).filter(i=>i.type==='message').flatMap(i=>i.content||[]).filter(i=>i.type==='output_text').map(i=>i.text).join('');
  const r=JSON.parse(text),seen=new Set();
  if(typeof r.summary!=='string'||r.summary.length>2000||!Array.isArray(r.priorities)||r.priorities.length>15)throw Error('Invalid review.');
  for(const p of r.priorities){if(!p||!allowed.has(p.id)||seen.has(p.id)||![-1,0,1].includes(p.priority)||typeof p.reason!=='string'||p.reason.length>500)throw Error('Invalid advice.');seen.add(p.id);}
  return {summary:r.summary,priorities:r.priorities};
}
async function review(req,context,{env=process.env,fetcher=fetch,now=Date.now}={}){
  let principal;
  try{principal=JSON.parse(Buffer.from(req.headers.get('x-ms-client-principal')||'','base64').toString('utf8'));}catch{return response(401,{error:'Sign in with GitHub to use GPT review.'});}
  const allowed=(env.COACH_ALLOWED_USERS||'').split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);
  const identity=`${principal.identityProvider}:${principal.userDetails}`.toLowerCase();
  if(!principal.userRoles?.includes('authenticated')||!allowed.includes(identity))return response(403,{error:'This account is not enabled for GPT review.'});
  if(!env.OPENAI_API_KEY)return response(503,{error:'GPT review is not configured yet. Local analysis is available.'});
  let payload;
  try{const raw=await req.text();if(raw.length>50000)return response(413,{error:'Practice summary is too large.'});payload=validate(JSON.parse(raw));}
  catch{return response(400,{error:'Invalid practice summary.'});}
  const time=now();
  for(const [user,at] of requests)if(time-at>60000)requests.delete(user);
  if(requests.has(identity)&&time-requests.get(identity)<10000)return response(429,{error:'Please wait a few seconds before another review.'});
  requests.set(identity,time);
  try{
    const result=await fetcher('https://api.openai.com/v1/responses',{
      method:'POST',redirect:'error',signal:AbortSignal.timeout(35000),
      headers:{'Authorization':`Bearer ${env.OPENAI_API_KEY}`,'Content-Type':'application/json'},
      body:JSON.stringify({model:env.GUITARHACKS_COACH_MODEL||'gpt-6.1-terra',store:false,max_output_tokens:3000,
        reasoning:{effort:(env.GUITARHACKS_COACH_MODEL||'gpt-6.1-terra').startsWith('gpt-6-astra')?'medium':'high'},
        instructions:contract.instructions,input:JSON.stringify(payload),
        text:{format:{type:'json_schema',name:'practice_review',strict:true,schema:contract.schema}}})
    });
    if(!result.ok)return response(result.status===429?429:502,{error:result.status===429?'OpenAI usage or rate limit reached.':'GPT review could not complete. Your scores are unchanged.'});
    const raw=await result.text();if(raw.length>1000000)throw Error('Oversized response.');
    return response(200,parse(JSON.parse(raw),new Set(payload.rows.map(r=>r.id))));
  }catch{return response(502,{error:'GPT review timed out or returned an unusable response. Use the local plan or try again.'});}
}
module.exports={review,parse,validate};
