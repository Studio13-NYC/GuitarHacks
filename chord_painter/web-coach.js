/* Browser transport uses SWA's backend and session cookie; never a browser API key. */
function createWebCoach(){
  const handlers=[];let pending=null;
  return {
    reviewReady:{connect:fn=>handlers.push(fn)},
    cancelReview(){pending?.abort();pending=null;},
    async reviewPractice(token,raw){
      pending?.abort();const controller=new AbortController();pending=controller;
      const timeout=setTimeout(()=>controller.abort(),45000);
      let result;
      try{
        const reply=await fetch('/api/practice-review',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:raw,signal:controller.signal,cache:'no-store'});
        if(reply.status===401)result={error:'Sign in with GitHub below to use GPT review. Your comments are saved.'};
        else{result=await reply.json();if(!reply.ok&&!result.error)result={error:'GPT review is unavailable. Use the local plan.'};}
      }catch{result={error:'GPT review could not connect or timed out. Use the local plan.'};}
      finally{clearTimeout(timeout);}
      if(pending!==controller)return;pending=null;
      handlers.forEach(fn=>fn(token,JSON.stringify(result)));
    }
  };
}
