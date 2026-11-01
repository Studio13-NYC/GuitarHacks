const CACHE='chord-painter-v18';
const PRACTICE=new URL('./practice',self.location.href);
const LEGACY_START=new URL('./index.html',self.location.href);
// Cache the public routes; native file-based use does not register this worker.
const FILES=['./','./practice','./home.html','./home.css','./home.js','./web-links.js','./github.svg','./style.css','./core.js','./career.js','./review.js','./web-coach.js','./practice-file.js','./app.js','./explorer.html','./explorer.css','./explorer.js','./manifest.webmanifest','./icon.svg','./icon-192.png','./icon-512.png'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(FILES)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('chord-painter-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==self.location.origin)return;
  // Already-installed icons keep their old start URL until the manifest refreshes.
  const key=event.request.mode==='navigate'&&url.pathname===LEGACY_START.pathname?PRACTICE.href:event.request;
  event.respondWith(caches.open(CACHE).then(cache=>cache.match(key)).then(cached=>cached||fetch(event.request)));
});
