const CACHE='nexo-mobile-0.18.0',FILES=/*PRECACHE*/[];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(FILES))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(async names=>{await Promise.all(names.filter(x=>x.startsWith('nexo-mobile-')&&x!==CACHE).map(x=>caches.delete(x)));await self.clients.claim();})));
self.addEventListener('fetch',event=>{if(event.request.method!=='GET'||new URL(event.request.url).origin!==self.location.origin)return;event.respondWith(caches.open(CACHE).then(async cache=>(await cache.match(event.request))||fetch(event.request)));});
