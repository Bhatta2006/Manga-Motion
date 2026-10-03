/* Native service worker; server substitutes build ID and the complete shell list. */
const SHELL='mm-shell-__BUILD_ID__',INDEX='mm-offline-index-v1',FILES=__SHELL_FILES__;
self.addEventListener('install',event=>event.waitUntil((async()=>{const cache=await caches.open(SHELL);await cache.addAll(FILES);})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{for(const key of await caches.keys())if(key.startsWith('mm-shell-')&&key!==SHELL)await caches.delete(key);await self.clients.claim();})()));
async function saved(request){
  const index=await caches.open(INDEX);
  for(const key of await index.keys()){
    const record=await (await index.match(key)).json();
    if(request.url===new URL(record.playbackUrl,self.location.origin).href)return Response.json({...record.info,offline:true});
    if(request.url.startsWith(new URL(record.info.asset_base,self.location.origin).href)||request.url===new URL(record.info.script_url,self.location.origin).href){
      const cache=await caches.open(record.cacheName);const value=await cache.match(request);if(value)return value;
    }
  }
}
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);
  if(request.method!=='GET'||url.origin!==self.location.origin)return;
  if(url.pathname.startsWith('/assets/')||['/manifest.webmanifest','/icon.svg','/icon-192.png','/icon-512.png'].includes(url.pathname)){
    event.respondWith((async()=>await (await caches.open(SHELL)).match(request)||fetch(request))());return;
  }
  if(request.mode==='navigate'){
    event.respondWith(fetch(request).catch(async()=>await (await caches.open(SHELL)).match('/')||Response.error()));return;
  }
  if(/^\/api\/chapters\/[^/]+\/[^/]+\/playback\/[a-f0-9]{64}\//.test(url.pathname)){
    event.respondWith((async()=>await saved(request)||fetch(request))());return;
  }
  if(/^\/api\/chapters\/[^/]+\/[^/]+\/playback$/.test(url.pathname))event.respondWith(fetch(request).catch(async()=>await saved(request)||Response.error()));
});
