// Chunked IndexedDB storage avoids large single-response Cache API limits.
// Only public model files use this database; encrypted profiles live separately.
const DB='nexo-model-cache-v1',CHUNK=8*1024*1024,MAX=512*1024*1024;
function open(){return new Promise((resolve,reject)=>{const request=indexedDB.open(DB,1);request.onupgradeneeded=()=>{request.result.createObjectStore('files');request.result.createObjectStore('chunks');};request.onerror=()=>reject(request.error);request.onsuccess=()=>resolve(request.result);});}
function transaction(db,store,mode,action){return new Promise((resolve,reject)=>{const tx=db.transaction(store,mode);let value;const req=action(tx.objectStore(store));req.onsuccess=()=>{value=req.result;};tx.oncomplete=()=>resolve(value);tx.onabort=tx.onerror=()=>reject(tx.error||Error('Model cache transaction failed'));});}
export const modelCache={
 async match(name){const db=await open();try{const meta=await transaction(db,'files','readonly',s=>s.get(String(name)));if(!meta){db.close();return undefined;}db.close();let index=0;return new Response(new ReadableStream({async pull(controller){try{if(index>=meta.count){controller.close();return;}const readDb=await open();let bytes;try{bytes=await transaction(readDb,'chunks','readonly',s=>s.get(meta.id+':'+index++));}finally{readDb.close();}if(!bytes)throw Error('Model cache is incomplete; download the model again');controller.enqueue(new Uint8Array(bytes));}catch(e){controller.error(e);}}},{highWaterMark:0}),{headers:meta.headers});}catch(e){db.close();throw e;}},
 async put(name,response,onProgress=()=>{}){const db=await open(),id=crypto.randomUUID(),reader=response.body.getReader();let count=0,total=0,buffer=new Uint8Array(CHUNK),used=0;
  const flush=async()=>{await transaction(db,'chunks','readwrite',s=>s.put(buffer.slice(0,used).buffer,id+':'+count));count++;used=0;};
  try{for(;;){const {done,value}=await reader.read();if(done)break;total+=value.length;onProgress(total);if(total>MAX)throw Error('Model file exceeds the 512 MB mobile download limit');let offset=0;while(offset<value.length){const n=Math.min(CHUNK-used,value.length-offset);buffer.set(value.subarray(offset,offset+n),used);used+=n;offset+=n;if(used===CHUNK)await flush();}}if(used)await flush();
   const old=await transaction(db,'files','readonly',s=>s.get(String(name)));const headers={'Content-Type':response.headers.get('Content-Type')||'application/octet-stream','Content-Length':String(total)};
   await transaction(db,'files','readwrite',s=>s.put({id,count,total,headers},String(name)));
   if(old)for(let i=0;i<old.count;i++)await transaction(db,'chunks','readwrite',s=>s.delete(old.id+':'+i));
  }catch(e){for(let i=0;i<count;i++)await transaction(db,'chunks','readwrite',s=>s.delete(id+':'+i)).catch(()=>{});throw e;}finally{reader.releaseLock();db.close();}
 }
};

// Wllama otherwise constructs its own OPFS cache even when loading our verified
// Blob. Use the same IndexedDB storage on browsers where OPFS is unavailable.
export const indexedModelBackend = {
 isSupported:()=>typeof indexedDB!=='undefined',
 async read(key){const response=await modelCache.match(key);return response?response.blob():null;},
 async write(key,stream){await modelCache.put(key,new Response(stream));},
 async getSize(key){const db=await open();try{return (await transaction(db,'files','readonly',s=>s.get(String(key))))?.total??-1;}finally{db.close();}},
 async list(){const db=await open();try{const keys=await transaction(db,'files','readonly',s=>s.getAllKeys());const result=[];for(const key of keys){const meta=await transaction(db,'files','readonly',s=>s.get(key));if(meta)result.push({key:String(key),size:meta.total});}return result;}finally{db.close();}},
 async delete(key){const db=await open();try{const meta=await transaction(db,'files','readonly',s=>s.get(String(key)));await transaction(db,'files','readwrite',s=>s.delete(String(key)));if(meta)for(let i=0;i<meta.count;i++)await transaction(db,'chunks','readwrite',s=>s.delete(meta.id+':'+i));}finally{db.close();}}
};
