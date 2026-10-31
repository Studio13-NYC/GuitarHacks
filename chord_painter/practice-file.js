/* The chosen JSON file is the only persistent copy of web practice data. */
(function(root){
  'use strict';
  function parse(raw){
    const value=JSON.parse(raw);
    const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
    if(value?.version!==1||!Array.isArray(value.history)||!object(value.stats)||!object(value.config)
      ||(value.rounds!==undefined&&!Array.isArray(value.rounds))
      ||(value.practicePreferences!==undefined&&!object(value.practicePreferences)))throw new Error('This is not a Chord Painter practice file.');
    return value;
  }
  class PracticeFile {
    constructor(handle,raw,onStatus=()=>{}){
      this.handle=handle;this.raw=raw;this.onStatus=onStatus;this.pending=0;this.failed=false;this.tail=Promise.resolve();
    }
    async check(){
      const raw=await (await this.handle.getFile()).text();
      if(raw!==this.raw)throw new Error('The practice file changed outside this session. Reopen it to load those changes.');
    }
    save(raw){
      // Capture each snapshot now and serialize writes; a slow earlier save cannot win.
      parse(raw);this.pending++;this.onStatus('Saving…');
      this.tail=this.tail.then(async()=>{
        if(this.failed)throw new Error('Saving is stopped. Reopen your practice file.');
        await this.check(); // A deleted file must never be silently recreated.
        let stream;
        try{
          stream=await this.handle.createWritable();
          await stream.write(raw);await stream.close();this.raw=raw;
        }catch(error){if(stream)await stream.abort().catch(()=>{});throw error;}
      }).catch(error=>{
        this.failed=true;
        const message=error.name==='NotFoundError'?'Your practice file was deleted or moved. It has not been recreated.':error.message;
        this.onStatus('Not saved — '+message,true);
        throw error;
      }).finally(()=>{this.pending--;if(!this.failed&&!this.pending)this.onStatus('Saved to '+this.handle.name);});
      return this.tail;
    }
  }
  async function choose(defaultData,onStatus){
    const $=id=>document.getElementById(id),dialog=$('practice-file-dialog');
    const supported=typeof root.showOpenFilePicker==='function'&&typeof root.showSaveFilePicker==='function';
    const message=$('practice-file-message');
    const options={types:[{description:'Chord Painter practice',accept:{'application/json':['.json']}}],excludeAcceptAllOption:true};
    let legacy=null;
    try{legacy=localStorage.getItem('chord-painter-v1');}catch{}
    $('practice-migrate').hidden=!legacy;
    if(legacy)message.textContent='Earlier browser results were found. Save them to JSON to keep them. Opening or creating a different file replaces that browser copy.';
    if(!supported){message.textContent='Open this app in desktop Chrome or Edge to save directly to a local JSON file.';}
    const buttons=['practice-open','practice-new','practice-migrate'].map($);
    buttons.forEach(button=>button.disabled=!supported);
    dialog.addEventListener('cancel',event=>event.preventDefault());dialog.showModal();
    return new Promise(resolve=>{
      async function select(kind){
        buttons.forEach(button=>button.disabled=true);
        try{
          let handle,raw;
          if(kind==='open'){
            [handle]=await root.showOpenFilePicker({...options,multiple:false});
            if(await handle.requestPermission({mode:'readwrite'})!=='granted')throw new Error('Allow saving to this file to continue.');
            raw=await (await handle.getFile()).text();parse(raw);
          }else{
            const value=kind==='migrate'?parse(legacy):defaultData;
            handle=await root.showSaveFilePicker({...options,suggestedName:'chord-painter.json'});
            raw=await (await handle.getFile()).text();
            // Never replace another practice profile from the New action.
            if(raw.trim())throw new Error('That file already contains data. Use Open practice file, or choose a new filename.');
            const file=new PracticeFile(handle,raw,onStatus);
            await file.save(JSON.stringify(value,null,2));raw=file.raw;
          }
          // Remove the old cache only after a valid file has been selected/saved.
          try{localStorage.removeItem('chord-painter-v1');}catch{}
          const file=new PracticeFile(handle,raw,onStatus);
          onStatus('Saved to '+handle.name);dialog.close();resolve(file);
        }catch(error){if(error.name!=='AbortError')message.textContent=error.message;}
        finally{buttons.forEach(button=>button.disabled=!supported);}
      }
      $('practice-open').onclick=()=>select('open');
      $('practice-new').onclick=()=>select('new');
      $('practice-migrate').onclick=()=>select('migrate');
    });
  }
  const api={parse,PracticeFile,choose};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.PracticeFiles=api;
})(typeof window==='undefined'?globalThis:window);
